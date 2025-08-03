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

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def detect_faces(image_path):
	"""Return True if at least one face is detected in the image."""
	try:
		image = face_recognition.load_image_file(image_path)
		return len(face_recognition.face_locations(image)) > 0
	except Exception:
		return False


def process_faces(trip_folder):
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "face_detector.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "face_detector.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	backup_csv(csv_path, max_backups=CFG.MAX_BACKUPS, log_path=log_path)
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found. Exiting.", log_path)
		return

	updated = 0
	for i, r in enumerate(rows, 1):
		img_path = os.path.join(trip_folder, r.get("local_path", ""))
		face_flag = 0
		if os.path.exists(img_path):
			if detect_faces(img_path):
				face_flag = 1
				updated += 1
			log(f"[{i}] {os.path.basename(img_path)} -> {'Face' if face_flag else 'No face'}", log_path)
		else:
			log(f"[{i}] Missing image: {img_path}", log_path)
		r["faces_detected"] = face_flag

	write_csv_dict(csv_path, rows, rows[0].keys())
	log(f"Face detection complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Detect faces and update labels.csv.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	process_faces(args.trip_folder)
