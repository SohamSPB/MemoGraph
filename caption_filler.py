#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption_filler.py

Uses BLIP to generate captions for each image in labels.csv.
Updates `caption` and `caption_samples` columns.

Logs progress to <trip_folder>/MemoGraph/logs/caption_filler.log
"""

import os
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def generate_multiple_captions(image, processor, model, num_variations=3):
	"""Generate multiple captions using top-k sampling."""
	captions = []
	inputs = processor(image, return_tensors="pt").to(model.device)
	for _ in range(num_variations):
		output = model.generate(**inputs, do_sample=True, top_k=50, max_length=40)
		captions.append(processor.decode(output[0], skip_special_tokens=True))
	return list(set(captions))


def fill_captions(trip_folder):
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "caption_filler.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "caption_filler.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	backup_csv(csv_path, max_backups=CFG.MAX_BACKUPS, log_path=log_path)
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found. Exiting.", log_path)
		return

	log("Loading BLIP model...", log_path)
	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
	model.eval()

	updated = 0
	for i, r in enumerate(rows, 1):
		local_path = r.get("local_path", "")
		img_path = os.path.join(trip_folder, local_path)
		if not os.path.exists(img_path):
			log(f"[{i}] Missing image: {img_path}", log_path)
			continue

		try:
			image = Image.open(img_path).convert("RGB")
			captions = generate_multiple_captions(image, processor, model, num_variations=4)
			if captions:
				r["caption"] = captions[0]
				r["caption_samples"] = "|".join(captions)
				log(f"[{i}] Captioned: {os.path.basename(img_path)} -> {captions[0]}", log_path)
				updated += 1
		except Exception as e:
			log(f"[{i}] Failed to caption {img_path}: {e}", log_path)

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"Updated {updated} rows with captions. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Fill captions using BLIP.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	fill_captions(args.trip_folder)
