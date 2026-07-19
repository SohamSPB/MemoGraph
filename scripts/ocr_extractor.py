#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_extractor.py

Extracts readable text from images (signs, menus, nameplates, etc.) using
EasyOCR and writes results to the `ocr_text` column in labels.csv.

Only processes images not yet tagged (resume-safe).
Skips meme_or_graphic, chart_or_plot, and screenshot image types since
those are typically non-photographic and not the target use case.

Logs: <trip_folder>/MemoGraph/logs/ocr_extractor.log
"""

import os

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG


def _row_has_ocr(row) -> bool:
	return bool((row.get("ocr_text") or "").strip())


def _get_fieldnames(rows):
	seen = set()
	fields = []
	for row in rows:
		for key in row.keys():
			if key not in seen:
				fields.append(key)
				seen.add(key)
	return fields


def extract_ocr(trip_folder: str) -> None:
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "ocr_extractor.log")

	init_log(log_path, "ocr_extractor.py")

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV.", log_path)
		return

	already_done = sum(1 for r in rows if _row_has_ocr(r))
	if already_done == len(rows):
		log("All rows already have ocr_text. Nothing to do.", log_path)
		return

	try:
		import easyocr
	except ImportError:
		log("EasyOCR not installed. Skipping OCR step. Install with: pip install easyocr", log_path)
		return

	import torch
	gpu = torch.cuda.is_available()
	log(f"Loading EasyOCR (gpu={gpu})...", log_path)
	reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
	log("EasyOCR ready.", log_path)

	# Image types where OCR is not useful
	skip_types = {"meme_or_graphic", "chart_or_plot", "screenshot"}

	updated_rows = []
	found_text_count = 0

	try:
		for row in rows:
			if _row_has_ocr(row):
				updated_rows.append(row)
				continue

			image_type = str(row.get("image_type", "")).strip()
			if image_type in skip_types:
				row["ocr_text"] = ""
				updated_rows.append(row)
				continue

			local_path = row.get("local_path", "")
			image_path = os.path.join(trip_folder, local_path)
			if not os.path.exists(image_path):
				row["ocr_text"] = ""
				updated_rows.append(row)
				continue

			try:
				results = reader.readtext(image_path, detail=0, paragraph=True)
				# Filter out very short noise (single chars, pure numbers under 2 digits)
				texts = [t.strip() for t in results if len(t.strip()) >= 3]
				row["ocr_text"] = "; ".join(texts) if texts else ""
				if texts:
					log(f"{os.path.basename(image_path)} -> {row['ocr_text'][:100]}", log_path)
					found_text_count += 1
				else:
					log(f"{os.path.basename(image_path)} -> no text found", log_path)
			except Exception as e:
				log(f"{os.path.basename(image_path)} -> OCR error: {e}", log_path)
				row["ocr_text"] = ""

			updated_rows.append(row)

			if len(updated_rows) % 10 == 0:
				write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
				log("Incremental save.", log_path)

	except KeyboardInterrupt:
		log(f"[INTERRUPTED] OCR extraction interrupted. Saving progress...", log_path)
		if updated_rows:
			write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
		raise

	write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
	log(f"OCR extraction complete. Found text in {found_text_count} images.", log_path)


if __name__ == "__main__":
	import sys
	trip_folder = sys.argv[1] if len(sys.argv) > 1 else "data/trips/test_trip"
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	extract_ocr(trip_folder)
