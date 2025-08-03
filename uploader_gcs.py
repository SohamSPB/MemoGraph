#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloud_uploader.py

Uploads images listed in labels.csv to Google Cloud Storage (GCS).
Creates local backups and tracks uploads in `uploaded_paths_gcs.csv`.

Logs: <trip_folder>/MemoGraph/logs/cloud_uploader.log
"""

import os
import shutil
from google.cloud import storage

from scripts.utils.utils_io import read_csv_dict, write_csv_dict, append_csv_dict, ensure_dir, ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG


def upload_to_gcs(local_path, rel_path, bucket):
	"""Upload a file to GCS."""
	try:
		blob = bucket.blob(rel_path)
		blob.upload_from_filename(local_path)
		return f"gs://{bucket.name}/{rel_path}"
	except Exception as e:
		log(f"Upload failed: {local_path} - {e}", None)
		return ""


def backup_local(local_path, trip_folder):
	"""Backup file to backup directory."""
	rel_path = os.path.relpath(local_path, trip_folder)
	backup_path = os.path.join(CFG.BACKUP_DIR, rel_path)
	ensure_dir(backup_path)
	try:
		shutil.copy2(local_path, backup_path)
		return backup_path
	except Exception as e:
		log(f"Backup failed: {local_path} - {e}", None)
		return ""


def upload_and_backup(csv_path, trip_folder, log_path):
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows to process.", log_path)
		return

	gcs_client = storage.Client()
	bucket = gcs_client.bucket(CFG.GCS_BUCKET_NAME)

	updated_rows = []
	tracker_rows = []

	for row in rows:
		local_path = os.path.join(trip_folder, row.get("local_path", ""))
		if not os.path.exists(local_path):
			log(f"Skipped missing file: {local_path}", log_path)
			continue

		if not row.get("cloud_path"):
			rel_path = os.path.relpath(local_path, trip_folder)
			row["cloud_path"] = upload_to_gcs(local_path, rel_path, bucket)

		if not row.get("backup_path"):
			row["backup_path"] = backup_local(local_path, trip_folder)

		tracker_rows.append({
			"filepath": local_path,
			"cloud_path": row.get("cloud_path", ""),
			"backup_path": row.get("backup_path", "")
		})
		updated_rows.append(row)

	if updated_rows:
		write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())
		log(f"Updated labels CSV: {csv_path}", log_path)

	if tracker_rows:
		tracker_csv = os.path.join(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME, CFG.GCS_TRACKER_CSV)
		append_csv_dict(tracker_csv, tracker_rows, ["filepath", "cloud_path", "backup_path"])
		log(f"Tracker updated: {tracker_csv}", log_path)


if __name__ == "__main__":
	trip_folder = "data/trips/test_trip"
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(memo_dir, "logs", "cloud_uploader.log")

	init_log(log_path, "cloud_uploader.py")
	upload_and_backup(csv_path, trip_folder, log_path)
