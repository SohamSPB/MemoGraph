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
		"a bird", "a flower", "a plant", "a tree", "a forest",
		"a mountain", "a valley", "a lake", "a river", "a waterfall",
		"a landscape", "a person", "a group of people",
		"an insect", "an animal", "a cat", "a dog", "a yak", "a horse",

		# Astro / night sky
		"a night sky", "stars", "the Milky Way", "the galaxy", "a nebula",
		"a star cluster", "an astrophotography photo", "the moon", "the sun",
		"an eclipse", "the Andromeda galaxy", "the Orion nebula",

		# Temples / monuments / heritage / city
		"a temple", "a monastery", "a stupa", "a church", "a mosque",
		"a palace", "a fort", "a castle", "a monument", "a historical gate",
		"a cityscape", "a street market", "a bazaar", "a narrow street",
		"a building", "a museum", "an art gallery", "an old town square",

		# Food / cafes / restaurants
		"a plate of food", "a thali", "a street food stall", "a bowl of curry",
		"a cup of tea", "a cup of coffee", "a glass of chai",
		"a restaurant interior", "a cafe", "a dessert plate", "a pizza", "a burger",

		# Stays / camps / roads
		"a hotel room", "a guesthouse", "a homestay", "a campsite", "a tent",
		"a campfire", "a mountain road", "a hiking trail", "a suspension bridge",
		"a bus on a mountain road", "a highway through the mountains",

		# Other scenes
		"a sunrise", "a sunset", "a cityscape at night",
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
