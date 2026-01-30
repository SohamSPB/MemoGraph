#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_labeler.py

Uses OpenAI CLIP to label images based on predefined concepts.
Populates/updates `detected_objects` and `species_tags` columns.

Logs to <trip_folder>/MemoGraph/logs/image_labeler.log
"""

import os
import torch
import clip
from PIL import Image
from datetime import datetime

from scripts.utils.utils_io import (
	read_csv_dict,
	write_csv_dict,
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_image import resize_image

def _row_has_labels(row):
	"""Return True if this row already has CLIP labels."""
	return bool((row.get("detected_objects") or "").strip())

def _refine_sun_labels(labels, datetime_str):
	"""Filter sunrise/sunset based on hour of day."""
	if not datetime_str or not any(x in labels for x in ("sunrise", "sunset")):
		return labels
	
	try:
		# Parse flexible formats
		dt = None
		for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
			try:
				dt = datetime.strptime(datetime_str, fmt)
				break
			except ValueError:
				continue
		
		if not dt:
			return labels

		h = dt.hour
		# Sunrise window: ~4 AM to 11 AM
		if 4 <= h < 12:
			if "sunset" in labels:
				labels.remove("sunset")
		
		# Sunset window: ~4 PM to 9 PM (16 to 21)
		# But practically, anything after noon is rarely "sunrise".
		elif h >= 12:
			if "sunrise" in labels:
				labels.remove("sunrise")
				
	except Exception:
		pass
	
	return labels

def label_images(trip_folder):
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "image_labeler.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "image_labeler.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV.", log_path)
		return

	device = "cuda" if torch.cuda.is_available() else "cpu"
	model, preprocess = clip.load("ViT-B/32", device=device)

	concepts = [
		# Nature / landscapes / people
		"bird", "flower", "plant", "tree", "forest",
		"mountain", "valley", "lake", "river", "waterfall",
		"landscape", "person", "group of people",
		"insect", "animal", "cat", "dog", "yak", "horse",

		# Astro / night sky
		"night sky", "stars", "Milky Way", "galaxy", "nebula",
		"star cluster", "astrophotography", "moon", "sun",
		"eclipse", "Andromeda galaxy", "Orion nebula",

		# Temples / monuments / heritage / city
		"temple", "monastery", "stupa", "church", "mosque",
		"palace", "fort", "castle", "monument", "historical gate",
		"cityscape", "street market", "bazaar", "narrow street",
		"building", "museum", "art gallery", "old town square",

		# Food / cafes / restaurants
		"plate of food", "thali", "street food stall", "bowl of curry",
		"cup of tea", "cup of coffee", "glass of chai",
		"restaurant interior", "cafe", "dessert plate", "pizza", "burger",

		# Stays / camps / roads
		"hotel room", "guesthouse", "homestay", "campsite", "tent",
		"campfire", "mountain road", "hiking trail", "suspension bridge",
		"bus on a mountain road", "highway through the mountains",

		# Other scenes
		"sunrise", "sunset", "cityscape at night",

		# Electronics / indoor objects
		"circuit board", "electronics", "computer chip", "wiring", "soldering",
		"motherboard", "screen", "monitor", "keyboard", "mouse", "laptop",
		"smartphone", "tablet", "television", "appliance", "tool",

		# Everyday objects / structures
		"sign", "billboard", "poster", "rock", "stone", "wall", "lamp",
		"light", "street light", "window", "door", "furniture", "chair",
		"table", "fence", "gate", "pole", "wire", "road sign",
	]
	text_tokens = clip.tokenize(concepts).to(device)

	updated = 0

	def _flush():
		"""Incrementally flush current labels to CSV."""
		write_csv_dict(csv_path, rows, rows[0].keys())
		log("Incremental save: labels flushed to CSV.", log_path)

	for i, r in enumerate(rows, 1):
		# Skip rows that already have labels so re-running the script naturally
		# resumes only on missing entries.
		if _row_has_labels(r):
			continue

		img_path = os.path.join(trip_folder, r.get("local_path", ""))
		if not os.path.exists(img_path):
			log(f"[{i}] Missing image: {img_path}", log_path)
			continue

		try:
			image = Image.open(img_path).convert("RGB")
			image = resize_image(image)
			image = preprocess(image).unsqueeze(0).to(device)
			with torch.no_grad():
				img_features = model.encode_image(image)
				txt_features = model.encode_text(text_tokens)
				img_features /= img_features.norm(dim=-1, keepdim=True)
				txt_features /= txt_features.norm(dim=-1, keepdim=True)
				similarity = (100.0 * img_features @ txt_features.T).softmax(dim=-1)

			topk = similarity[0].topk(5)
			top_labels = [concepts[i] for i in topk.indices.cpu().numpy()]
			
			# Refine sunrise/sunset based on time
			top_labels = _refine_sun_labels(top_labels, r.get("datetime_original", ""))

			# Coarse species categories (kept in both detected_objects and species_tags).
			species_keywords = [
				"bird",
				"flower",
				"insect",
				"animal",
				"cat",
				"dog",
				"plant",
				"galaxy",
				"nebula",
				"milky way",
				"stars",
				"astrophotography",
				"star cluster",
			]
			species = [l for l in top_labels if any(k in l.lower() for k in species_keywords)]

			# Keep all top labels in detected_objects so the CSV always reflects
			# what CLIP saw (including birds, insects, etc.).
			r["detected_objects"] = "; ".join(top_labels)
			# Store coarse categories in species_tags; more detailed species
			# detection can refine/override this later.
			if species:
				r["species_tags"] = "; ".join(species)
			updated += 1
			log(f"[{i}] {os.path.basename(img_path)} -> {top_labels}", log_path)
		except Exception as e:
			log(f"[{i}] Failed on {img_path}: {e}", log_path)

		# Periodic incremental save so that long runs can resume with minimal loss.
		if updated and updated % 10 == 0:
			_flush()

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"Labeling complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	import multiprocessing
	p = argparse.ArgumentParser(description="Label images using CLIP.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()

	label_images(args.trip_folder)
