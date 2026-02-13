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

def _resize_for_face_detection(pil_img):
	"""Resize image for face detection using the dedicated FACE_DETECTION_IMAGE_SIZE.
	This is typically larger than MAX_IMAGE_SIZE to preserve face detail."""
	from PIL import ImageOps
	pil_img = ImageOps.exif_transpose(pil_img)
	face_size = getattr(CFG, 'FACE_DETECTION_IMAGE_SIZE', 1024)
	w, h = pil_img.size
	longest = max(w, h)
	if longest > face_size:
		scale = face_size / longest
		new_w = int(w * scale)
		new_h = int(h * scale)
		pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
	return pil_img


def _format_face_locations(face_locations, img_width, img_height):
	"""Format face bounding boxes as normalized coordinates for storage.
	Each face becomes 'top,right,bottom,left' as percentages, separated by semicolons."""
	if not face_locations:
		return ""
	parts = []
	for (top, right, bottom, left) in face_locations:
		# Normalize to percentages for resolution-independence
		t = round(top / img_height * 100, 1)
		r = round(right / img_width * 100, 1)
		b = round(bottom / img_height * 100, 1)
		l = round(left / img_width * 100, 1)
		parts.append(f"{t},{r},{b},{l}")
	return "; ".join(parts)


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
					img = _resize_for_face_detection(img.convert("RGB"))
					img_width, img_height = img.size
					image = np.array(img)

				model = "cnn" if use_cnn_model else "hog"
				# Upsample HOG to detect smaller faces (e.g. groups/distance).
				upsample = 2 if model == "hog" else 1
				face_locations = face_recognition.face_locations(image, number_of_times_to_upsample=upsample, model=model)
				face_count = len(face_locations)
				face_flag = 1 if face_count > 0 else 0

				# Store face bounding box locations as normalized percentages
				row["face_locations"] = _format_face_locations(face_locations, img_width, img_height)
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

	def _get_fieldnames():
		"""Get fieldnames including any new columns added during processing."""
		if not rows:
			return []
		# Start with original keys, then add any new keys from processed rows
		seen = set()
		fields = []
		for key in rows[0].keys():
			if key not in seen:
				fields.append(key)
				seen.add(key)
		# Ensure face_locations is included if present in any row
		for row in rows:
			for key in row.keys():
				if key not in seen:
					fields.append(key)
					seen.add(key)
		return fields

	def _flush():
		"""Incrementally flush current face flags to CSV."""
		if not rows:
			return
		write_csv_dict(csv_path, rows, _get_fieldnames())
		log("Incremental save: faces_detected flushed to CSV.", log_path)

	use_cnn = getattr(CFG, "FACE_DETECTION_USE_CNN", True)
	model_name = "CNN" if use_cnn else "HOG"
	face_img_size = getattr(CFG, "FACE_DETECTION_IMAGE_SIZE", 1024)
	log(f"Face detection config: model={model_name}, image_size={face_img_size}px, batch_size={CFG.FACE_DETECTION_BATCH_SIZE}", log_path)

	try:
		batches = [rows[i:i + CFG.FACE_DETECTION_BATCH_SIZE] for i in range(0, len(rows), CFG.FACE_DETECTION_BATCH_SIZE)]
		updated_rows = []

		if CFG.FACE_DETECTION_PARALLEL_WORKERS > 1:
			log(
				f"Running face detection in PARALLEL ({model_name} model) with "
				f"{CFG.FACE_DETECTION_PARALLEL_WORKERS} workers...",
				log_path,
			)
			executor = concurrent.futures.ProcessPoolExecutor(max_workers=CFG.FACE_DETECTION_PARALLEL_WORKERS)
			try:
				future_to_batch = {
					executor.submit(_process_batch, batch, trip_folder, i, log_path, use_cnn_model=use_cnn): i
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
				f"Running face detection in SEQUENTIAL ({model_name} model) mode with batch size {CFG.FACE_DETECTION_BATCH_SIZE}...",
				log_path,
			)
			for i, batch in enumerate(batches, 1):
				processed_batch = _process_batch(batch, trip_folder, i, log_path, use_cnn_model=use_cnn)
				updated_rows.extend(processed_batch)
				faces_in_batch = sum(1 for row in processed_batch if row.get("faces_detected") == 1)
				log(f"Batch {i} completed. Found {faces_in_batch} faces.", log_path)
				# Periodic incremental save in sequential mode.
				if i % 5 == 0:
					rows = sorted(updated_rows, key=lambda r: r.get('image_name', ''))
					_flush()

		updated_rows.sort(key=lambda r: r.get('image_name', ''))
		rows = updated_rows
		total_faces_found = sum(1 for row in rows if row.get("faces_detected") == 1)
	except KeyboardInterrupt:
		log("[INTERRUPTED] Face detection interrupted. Saving progress...", log_path)
		if rows:
			write_csv_dict(csv_path, rows, _get_fieldnames())
		raise

	if rows:
		write_csv_dict(csv_path, rows, _get_fieldnames())
		log(f"Face detection complete. Found faces in {total_faces_found} images. Saved: {csv_path}", log_path)
	else:
		log("No rows were processed. CSV not updated.", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Detect faces and update labels.csv.")
	p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()

	process_faces(args.trip_folder)
