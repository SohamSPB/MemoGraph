#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_colors.py

Extracts dominant color palette for images and updates `color_palette` column.
"""

import os
from PIL import Image

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
from scripts.utils.utils_image import extract_dominant_colors
import memograph_config as CFG

def process_colors(trip_folder: str):
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "image_colors.log")
	init_log(log_path, "image_colors.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"CSV not found: {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		return

	updated = 0
	
	# Check if headers need update
	if rows and "color_palette" not in rows[0]:
		for r in rows:
			r["color_palette"] = ""

	for i, row in enumerate(rows, 1):
		# Content duplicate: color palette is byte-deterministic; duplicates
		# inherit it from the canonical via dedup_broadcast.py.
		if (row.get("duplicate_of") or "").strip():
			continue
		if row.get("color_palette"):
			continue

		local_path = row.get("local_path", "")
		full_path = os.path.join(trip_folder, local_path)
		
		if os.path.exists(full_path):
			try:
				with Image.open(full_path) as img:
					colors = extract_dominant_colors(img, num_colors=3)
					row["color_palette"] = ";".join(colors)
					updated += 1
					# log(f"[{i}] {local_path} -> {colors}", log_path)
			except Exception as e:
				log(f"Failed {local_path}: {e}", log_path)
		
		if updated % 20 == 0 and updated > 0:
			 write_csv_dict(csv_path, rows, rows[0].keys())

	if updated:
		write_csv_dict(csv_path, rows, rows[0].keys())
		log(f"Updated colors for {updated} images.", log_path)
	else:
		log("No updates needed.", log_path)

if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser()
	p.add_argument("trip_folder")
	args = p.parse_args()
	process_colors(args.trip_folder)
