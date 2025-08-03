#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_ai_captions.py

Generates a single AI-based caption for each image using BLIP.
Populates/updates the `caption_ai` column in labels.csv.

Logs are saved to <trip_folder>/MemoGraph/logs/generate_ai_captions.log
"""

import os
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def generate_ai_captions(trip_folder):
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "generate_ai_captions.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "generate_ai_captions.py")

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
	log(f"Using device: {device}", log_path)

	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
	model.eval()

	updated = 0
	for i, r in enumerate(rows, 1):
		img_path = os.path.join(trip_folder, r.get("local_path", ""))
		if not os.path.exists(img_path):
			log(f"[{i}] Missing image: {img_path}", log_path)
			continue

		try:
			raw_image = Image.open(img_path).convert("RGB")
			inputs = processor(raw_image, return_tensors="pt").to(device)
			with torch.no_grad():
				output = model.generate(**inputs, max_length=40)
				caption = processor.decode(output[0], skip_special_tokens=True)
			r["caption_ai"] = caption
			log(f"[{i}] {os.path.basename(img_path)} -> {caption}", log_path)
			updated += 1
		except Exception as e:
			log(f"[{i}] Failed to caption {img_path}: {e}", log_path)
			r["caption_ai"] = ""

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"AI captioning complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Generate AI captions for images.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	generate_ai_captions(args.trip_folder)
