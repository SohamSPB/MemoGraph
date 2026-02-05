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
import torch
import concurrent.futures

from scripts.utils.utils_io import (
	read_csv_dict,
	write_csv_dict,
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_image import resize_image
from scripts.utils.utils_text import clean_caption, clean_caption_list

def generate_multiple_captions(image, processor, model, num_variations=3):
	"""Generate multiple captions using top-k sampling."""
	captions = []
	inputs = processor(image, return_tensors="pt").to(model.device)
	for _ in range(num_variations):
		# Increased max_length from 40 to 60 for more detailed captions
		output = model.generate(**inputs, do_sample=True, top_k=50, max_length=60)
		raw = processor.decode(output[0], skip_special_tokens=True)
		captions.append(clean_caption(raw))
	return clean_caption_list(captions)

def _process_image_for_captioning(row, trip_folder, processor, model, i, log_path):
	"""Helper function to process a single image for captioning, used in parallel processing."""
	local_path = row.get("local_path", "")
	img_path = os.path.join(trip_folder, local_path)
	
	if not os.path.exists(img_path):
		log(f"[{i}] Missing image: {img_path}", log_path)
		return row, False # Return original row and False for not updated

	try:
		image = Image.open(img_path).convert("RGB")
		image = resize_image(image)
		captions = generate_multiple_captions(image, processor, model, num_variations=4)
		if captions:
			row["caption"] = captions[0]
			row["caption_samples"] = "|".join(captions)
			log(f"[{i}] Captioned: {os.path.basename(img_path)} -> {captions[0]}", log_path)
			return row, True # Return updated row and True for updated
	except Exception as e:
		log(f"[{i}] Failed to caption {img_path}: {e}", log_path)
	return row, False # Return original row and False for not updated


def fill_captions(trip_folder):
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "caption_filler.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "caption_filler.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found. Exiting.", log_path)
		return

	log("Loading BLIP model...", log_path)
	device = "cuda" if torch.cuda.is_available() else "cpu"
	processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", use_fast=True)
	model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
	model.eval()

	updated = 0

	# Helper to decide if a row already has captions.
	def _row_has_caption(row):
		return bool(row.get("caption"))

	# Helper to flush current rows to CSV (for incremental saving).
	def _flush():
		write_csv_dict(csv_path, rows, rows[0].keys())
		log("Incremental save: captions flushed to CSV.", log_path)
	
	try:
		if os.environ.get("MEMOGRAPH_PARALLEL_EXECUTION", "false").lower() == "true":
			log(
				f"Running BLIP captioning in parallel mode with up to {CFG.CAPTION_PARALLEL_WORKERS} workers...",
				log_path,
			)
			max_workers = max(1, getattr(CFG, "CAPTION_PARALLEL_WORKERS", 2))
			executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
			try:
				futures = {
					executor.submit(_process_image_for_captioning, row, trip_folder, processor, model, i, log_path): i
					for i, row in enumerate(rows, 1)
					if not _row_has_caption(row)
				}
				pending = len(futures)
				completed_since_flush = 0

				for future in concurrent.futures.as_completed(futures):
					idx = futures[future]
					try:
						result_row, is_updated = future.result()
						rows[idx - 1] = result_row
						if is_updated:
							updated += 1
						completed_since_flush += 1
						if completed_since_flush >= 10:
							_flush()
							completed_since_flush = 0
					except Exception as e:
						log(f"[{idx}] Error processing image for captioning: {e}", log_path)
			except KeyboardInterrupt:
				executor.shutdown(wait=False, cancel_futures=True)
				raise
			finally:
				executor.shutdown(wait=False)
		else:
			log("Running BLIP captioning in sequential mode...", log_path)
			for i, r in enumerate(rows, 1):
				if _row_has_caption(r):
					continue

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

				if i % 10 == 0:
					_flush()
	except KeyboardInterrupt:
		log(f"[INTERRUPTED] Captioning interrupted after {updated} images. Saving progress...", log_path)
		write_csv_dict(csv_path, rows, rows[0].keys())
		raise

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"Updated {updated} rows with captions. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	import multiprocessing
	p = argparse.ArgumentParser(description="Fill captions using BLIP.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()

	fill_captions(args.trip_folder)
