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
	read_csv_dict,
	write_csv_dict,
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_image import resize_image

def generate_ai_captions(trip_folder):
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "generate_ai_captions.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "generate_ai_captions.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

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

	def _row_has_ai_caption(row):
		return bool(row.get("caption_ai"))

	def _flush():
		write_csv_dict(csv_path, rows, rows[0].keys())
		log("Incremental save: AI captions flushed to CSV.", log_path)

	for i, r in enumerate(rows, 1):
		# Skip rows that already have an AI caption (resume-friendly).
		if _row_has_ai_caption(r):
			continue

		img_path = os.path.join(trip_folder, r.get("local_path", ""))
		if not os.path.exists(img_path):
			log(f"[{i}] Missing image: {img_path}", log_path)
			continue

		try:
			raw_image = Image.open(img_path).convert("RGB")
			raw_image = resize_image(raw_image)
			inputs = processor(raw_image, return_tensors="pt").to(device)
			with torch.no_grad():
				output = model.generate(**inputs, max_length=40)
				caption = processor.decode(output[0], skip_special_tokens=True)
			r["caption_ai"] = caption
			log(f"[{i}] {os.path.basename(img_path)} -> {caption}", log_path)
			updated += 1
		except Exception as e:
			log(f"[{i}] Failed to caption {img_path}: {e}", log_path)
			# Leave any existing caption_ai value intact to avoid erasing progress.

		# Periodic incremental save.
		if i % 10 == 0:
			_flush()

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"AI captioning complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	import multiprocessing
	p = argparse.ArgumentParser(description="Generate AI captions for images.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()

	generate_ai_captions(args.trip_folder)
