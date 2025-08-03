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
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def label_images(trip_folder):
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "image_labeler.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "image_labeler.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	backup_csv(csv_path, CFG.MAX_BACKUPS, log_path)
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV.", log_path)
		return

	device = "cuda" if torch.cuda.is_available() else "cpu"
	model, preprocess = clip.load("ViT-B/32", device=device)

	concepts = [
		# Nature / People
		"a bird", "a flower", "a plant", "a tree", "a mountain", "a lake",
		"a landscape", "a person", "a group of people", "a waterfall", "a forest",
		"an insect", "an animal", "a cat", "a dog",
		# Astro
		"a night sky", "stars", "the Milky Way", "the galaxy", "a nebula",
		"a star cluster", "an astrophotography photo", "the moon", "the sun",
		"an eclipse", "the Andromeda galaxy", "the Orion nebula",
		# Other scenes
		"a sunrise", "a sunset", "a cityscape", "a building", "a monument", "a food dish"
	]
	text_tokens = clip.tokenize(concepts).to(device)

	updated = 0
	for i, r in enumerate(rows, 1):
		img_path = os.path.join(trip_folder, r.get("local_path", ""))
		if not os.path.exists(img_path):
			log(f"[{i}] Missing image: {img_path}", log_path)
			continue

		try:
			image = preprocess(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
			with torch.no_grad():
				img_features = model.encode_image(image)
				txt_features = model.encode_text(text_tokens)
				img_features /= img_features.norm(dim=-1, keepdim=True)
				txt_features /= txt_features.norm(dim=-1, keepdim=True)
				similarity = (100.0 * img_features @ txt_features.T).softmax(dim=-1)

			topk = similarity[0].topk(5)
			top_labels = [concepts[i] for i in topk.indices.cpu().numpy()]

			species_keywords = ["bird", "flower", "insect", "animal", "cat", "dog", "plant", "galaxy", "nebula", "Milky Way", "stars", "astrophotography", "star cluster"]
			species = [l for l in top_labels if any(k.lower() in l.lower() for k in species_keywords)]
			objects = [l for l in top_labels if l not in species]

			r["detected_objects"] = "; ".join(objects)
			r["species_tags"] = "; ".join(species)
			updated += 1
			log(f"[{i}] {os.path.basename(img_path)} -> {objects + species}", log_path)
		except Exception as e:
			log(f"[{i}] Failed on {img_path}: {e}", log_path)

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"Labeling complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Label images using CLIP.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	label_images(args.trip_folder)
