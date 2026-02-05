#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
face_detector.py

Detects faces in images using `face_recognition` and updates
the `faces_detected` column (1 = face found, 0 = none).

Logs progress to <trip_folder>/MemoGraph/logs/face_detector.log
"""

import os
import face_recognition
from PIL import Image
import numpy as np
import concurrent.futures
import multiprocessing

from scripts.utils.utils_io import (
	read_csv_dict,
	write_csv_dict,
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_image import resize_image

def _row_has_face(row):
	"""Return True if this row already has a valid face scan (faces_count >= 0)."""
	val = str(row.get("faces_count", "")).strip()
	# If empty or -1, it's not scanned.
	if not val or val == "-1":
		return False
	return True

def _process_batch(batch_rows, trip_folder, batch_num, log_path, use_cnn_model=False):
	"""Helper function to detect faces for a batch of rows."""
	updated_rows = []
	log(f"Processing batch {batch_num} with {len(batch_rows)} images...", log_path)
	for i, row in enumerate(batch_rows, 1):
		# Skip work if this row already has a faces_detected value so that
		# re-running the script can cheaply resume incomplete work.
		if _row_has_face(row):
			updated_rows.append(row)
			continue

		img_full_path = os.path.join(trip_folder, row.get("local_path", ""))
		if os.path.exists(img_full_path):
			try:
				with Image.open(img_full_path) as img:
					img = resize_image(img.convert("RGB"))
					image = np.array(img)
				
				model = "cnn" if use_cnn_model else "hog"
				# Upsample HOG to detect smaller faces (e.g. groups/distance).
				upsample = 2 if model == "hog" else 1
				face_locations = face_recognition.face_locations(image, number_of_times_to_upsample=upsample, model=model)
				face_count = len(face_locations)
				face_flag = 1 if face_count > 0 else 0
				# log(f"[Batch {batch_num}-{i}] {os.path.basename(img_full_path)} -> {'Face' if face_flag else 'No face'}", log_path)
			except Exception as e:
				log(f"[Batch {batch_num}-{i}] Failed to process image {img_full_path}: {e}", log_path)
				face_flag = 0
				face_count = 0
		else:
			log(f"[Batch {batch_num}-{i}] Missing image: {img_full_path}", log_path)
			face_flag = 0
			face_count = 0
		
		row["faces_detected"] = face_flag
		row["faces_count"] = face_count
		updated_rows.append(row)
	return updated_rows


def process_faces(trip_folder):
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "face_detector.log")
	init_log(log_path, "face_detector.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found. Exiting.", log_path)
		return

	# If all rows already have a faces_detected value, treat this as a no-op so
	# that re-running the script is a cheap resume operation.
	if all(_row_has_face(r) for r in rows):
		log("All rows already have faces_detected set; nothing to do.", log_path)
		return

	total_faces_found = 0

	def _flush():
		"""Incrementally flush current face flags to CSV."""
		if not rows:
			return
		write_csv_dict(csv_path, rows, rows[0].keys())
		log("Incremental save: faces_detected flushed to CSV.", log_path)

	is_parallel = os.environ.get("MEMOGRAPH_PARALLEL_EXECUTION", "false").lower() == "true"

	try:
		if is_parallel:
			# In parallel pipeline runs, we avoid creating a large nested process pool by
			# default. Instead we iterate batches sequentially with the CNN model (GPU)
			# unless FACE_DETECTION_PARALLEL_WORKERS is explicitly increased.
			batches = [rows[i:i + CFG.FACE_DETECTION_BATCH_SIZE] for i in range(0, len(rows), CFG.FACE_DETECTION_BATCH_SIZE)]
			updated_rows = []

			if getattr(CFG, "FACE_DETECTION_PARALLEL_WORKERS", 1) and CFG.FACE_DETECTION_PARALLEL_WORKERS > 1:
				log(
					f"Running face detection in PARALLEL (CNN model) with "
					f"{CFG.FACE_DETECTION_PARALLEL_WORKERS} workers and batch size {CFG.FACE_DETECTION_BATCH_SIZE}...",
					log_path,
				)
				executor = concurrent.futures.ProcessPoolExecutor(max_workers=CFG.FACE_DETECTION_PARALLEL_WORKERS)
				try:
					future_to_batch = {
						executor.submit(_process_batch, batch, trip_folder, i, log_path, use_cnn_model=True): i
						for i, batch in enumerate(batches, 1)
					}

					for future in concurrent.futures.as_completed(future_to_batch):
						batch_num = future_to_batch[future]
						try:
							processed_batch = future.result()
							updated_rows.extend(processed_batch)
							faces_in_batch = sum(1 for row in processed_batch if row.get("faces_detected") == 1)
							log(f"Batch {batch_num} completed. Found {faces_in_batch} faces.", log_path)
						except Exception as e:
							log(f"Batch {batch_num} generated an exception: {e}", log_path)
				except KeyboardInterrupt:
					executor.shutdown(wait=False, cancel_futures=True)
					raise
				finally:
					executor.shutdown(wait=False)
			else:
				log(
					f"Running face detection in SEQUENTIAL (CNN model) mode with batch size {CFG.FACE_DETECTION_BATCH_SIZE}...",
					log_path,
				)
				for i, batch in enumerate(batches, 1):
					processed_batch = _process_batch(batch, trip_folder, i, log_path, use_cnn_model=True)
					updated_rows.extend(processed_batch)
					faces_in_batch = sum(1 for row in processed_batch if row.get("faces_detected") == 1)
					log(f"Batch {i} completed. Found {faces_in_batch} faces.", log_path)
					# Periodic incremental save in sequential CNN mode.
					if i % 5 == 0:
						rows = sorted(updated_rows, key=lambda r: r.get('image_name', ''))
						_flush()

			updated_rows.sort(key=lambda r: r.get('image_name', ''))
			rows = updated_rows
			total_faces_found = sum(1 for row in rows if row.get("faces_detected") == 1)

		else:
			log("Running face detection in SEQUENTIAL (HOG model) mode...", log_path)
			processed_rows = _process_batch(rows, trip_folder, 1, log_path, use_cnn_model=False)
			rows = processed_rows
			total_faces_found = sum(1 for row in rows if row.get("faces_detected") == 1)
	except KeyboardInterrupt:
		log("[INTERRUPTED] Face detection interrupted. Saving progress...", log_path)
		if rows:
			write_csv_dict(csv_path, rows, rows[0].keys())
		raise

	if rows:
		write_csv_dict(csv_path, rows, rows[0].keys())
		log(f"Face detection complete. Found faces in {total_faces_found} images. Saved: {csv_path}", log_path)
	else:
		log("No rows were processed. CSV not updated.", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Detect faces and update labels.csv.")
	p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()

	process_faces(args.trip_folder)
