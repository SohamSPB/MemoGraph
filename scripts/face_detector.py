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

def _resize_image(image, max_size=1024):
	"""Resize image to a max size, preserving aspect ratio."""
	if max(image.size) > max_size:
		image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
	return image

def _process_batch(batch_rows, trip_folder, batch_num, log_path, use_cnn_model=False):
	"""Helper function to detect faces for a batch of rows."""
	updated_rows = []
	log(f"Processing batch {batch_num} with {len(batch_rows)} images...", log_path)
	for i, row in enumerate(batch_rows, 1):
		img_full_path = os.path.join(trip_folder, row.get("local_path", ""))
		face_flag = 0
		if os.path.exists(img_full_path):
			try:
				with Image.open(img_full_path) as img:
					img = _resize_image(img.convert("RGB"))
					image = np.array(img)
				
				model = "cnn" if use_cnn_model else "hog"
				face_locations = face_recognition.face_locations(image, model=model)
				
				if len(face_locations) > 0:
					face_flag = 1
				# log(f"[Batch {batch_num}-{i}] {os.path.basename(img_full_path)} -> {'Face' if face_flag else 'No face'}", log_path)
			except Exception as e:
				log(f"[Batch {batch_num}-{i}] Failed to process image {img_full_path}: {e}", log_path)
		else:
			log(f"[Batch {batch_num}-{i}] Missing image: {img_full_path}", log_path)
		
		row["faces_detected"] = face_flag
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

	total_faces_found = 0
	
	is_parallel = os.environ.get("MEMOGRAPH_PARALLEL_EXECUTION", "false").lower() == "true"

	if is_parallel:
		log(f"Running face detection in PARALLEL (CNN model) with batch size {CFG.FACE_DETECTION_BATCH_SIZE}...", log_path)
		
		# Split rows into batches
		batches = [rows[i:i + CFG.FACE_DETECTION_BATCH_SIZE] for i in range(0, len(rows), CFG.FACE_DETECTION_BATCH_SIZE)]
		updated_rows = []

		with concurrent.futures.ProcessPoolExecutor(max_workers=CFG.PARALLEL_WORKERS) as executor:
			# Submit each batch to the executor
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
		
		# Sort updated_rows to maintain original order, just in case
		updated_rows.sort(key=lambda r: r.get('image_name', ''))
		rows = updated_rows
		total_faces_found = sum(1 for row in rows if row.get("faces_detected") == 1)

	else:
		log("Running face detection in SEQUENTIAL (HOG model) mode...", log_path)
		# Sequential processing can also benefit from batching logic, though memory pressure is lower
		processed_rows = _process_batch(rows, trip_folder, 1, log_path, use_cnn_model=False)
		rows = processed_rows
		total_faces_found = sum(1 for row in rows if row.get("faces_detected") == 1)

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
