#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py

Runs the entire MemoGraph image processing pipeline for a given trip folder:
1. Image scanning and EXIF extraction
2. Trip day assignment
3. Location resolution (reverse geocoding)
4. Face detection
5. Image labeling (general + species)
6. Caption generation (BLIP-based, multi samples)
7. AI captioning (single column)
8. Blog generation (Markdown + JSON)
9. Map generation (HTML)
10. (optional) Upload to GCS + local backup

Make sure all modules referenced here use the updated config/utils signatures.
"""

import os
import sys
import memograph_config as CFG

from scripts.utils.utils_log import get_logger
from scripts.utils.utils_io import ensure_dir

# pipeline steps
import scripts.image_scanner as image_scanner
import scripts.trip_day_assigner as trip_day_assigner
import scripts.location_resolver as location_resolver
import scripts.face_detector as face_detector
import scripts.image_labeler as image_labeler
import scripts.caption_filler as caption_filler
import scripts.species_detector as species_detector
import scripts.generate_ai_captions as generate_ai_captions
import scripts.blog_generator as blog_generator
import scripts.map_visualizer as map_visualizer
# import scripts.uploader_gcs  # optional


def run_pipeline(trip_folder: str):
	if not os.path.isdir(trip_folder):
		print(f"✗ Trip folder does not exist: {trip_folder}")
		return

	# Prepare MemoGraph + logs folder
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	ensure_dir(memo_dir)
	ensure_dir(logs_dir)

	log_path = os.path.join(logs_dir, "run_all.log")
	logger = get_logger("run_all", log_path)
	logger.info("--- MemoGraph pipeline start ---")

	# All artifacts live inside MemoGraph
	blog_path = os.path.join(memo_dir, "blog.md")
	summary_path = os.path.join(memo_dir, "trip_summary.json")
	map_path = os.path.join(memo_dir, "trip_map.html")

	try:
		logger.info("--- STEP 1: Scanning Images ---")
		# NEW signature: scan_images(trip_folder) -> returns csv_path it wrote
		csv_path = image_scanner.scan_images(trip_folder)

		logger.info("--- STEP 2: Assigning Day Numbers ---")
		trip_day_assigner.assign_days(trip_folder)

		logger.info("--- STEP 3: Resolving Locations ---")
		# function was renamed to fill_location_column in your updated code
		location_resolver.fill_location(trip_folder)

		logger.info("--- STEP 4: Detecting Faces ---")
		face_detector.process_faces(trip_folder)

		logger.info("--- STEP 5: Labeling Images (CLIP concepts) ---")
		image_labeler.label_images(trip_folder)

		logger.info("--- STEP 6: Generating multi-sample captions (BLIP) ---")
		caption_filler.fill_captions(trip_folder)

		logger.info("--- STEP 7: Detecting species (CLIP prompts) ---")
		species_detector.process_species(csv_path, trip_folder, log_path)

		logger.info("--- STEP 8: Generating AI captions (single) ---")
		generate_ai_captions.generate_ai_captions(trip_folder)

		logger.info("--- STEP 9: Generating Blog ---")
		blog_generator.generate_blog(trip_folder)

		logger.info("--- STEP 10: Creating Map ---")
		points = map_visualizer.load_geo_points(csv_path, trip_folder)
		map_visualizer.create_map(points, map_path)

		# logger.info("--- STEP 11: Upload to GCS & local backup ---")
		# uploader_gcs.upload_and_backup(csv_path)

		logger.info("[OK] All steps completed for: %s", trip_folder)
		logger.info("Artifacts:")
		logger.info("  CSV:     %s", csv_path)
		logger.info("  Blog MD: %s", blog_path)
		logger.info("  Summary: %s", summary_path)
		logger.info("  Map:     %s", map_path)

	except Exception as e:
		logger.exception("[ERROR] Pipeline failed: %s", e)
		raise


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python run_all.py <trip_folder_path>")
		sys.exit(1)
	run_pipeline(sys.argv[1])
