#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trip_day_assigner.py

Assigns consecutive day numbers to rows in labels.csv based on
the earliest valid `datetime_original`.

Writes results back to <trip_folder>/MemoGraph/labels.csv and
logs to <trip_folder>/MemoGraph/logs/trip_day_assigner.log
"""

import os
from datetime import datetime

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def assign_days(trip_folder: str) -> None:
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "trip_day_assigner.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "trip_day_assigner.py")

	labels_csv = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(labels_csv):
		log(f"ERROR: labels.csv not found at {labels_csv}", log_path)
		return

	rows = read_csv_dict(labels_csv)
	if not rows:
		log("ERROR: labels.csv has no rows.", log_path)
		return

	# ensure required columns exist
	if "datetime_original" not in rows[0] or "day_number" not in rows[0]:
		log("ERROR: Missing columns 'datetime_original' or 'day_number' in labels.csv", log_path)
		return

	backup_csv(labels_csv, max_backups=CFG.MAX_BACKUPS, log_path=log_path)

	# collect datetimes
	parsed = []
	for r in rows:
		raw = (r.get("datetime_original") or "").strip()
		if not raw:
			parsed.append((None, r))
			continue
		try:
			dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
			parsed.append((dt, r))
		except Exception:
			log(f"Warning: invalid datetime_original '{raw}' for {r.get('local_path')}", log_path)
			parsed.append((None, r))

	valid = [dt for dt, _ in parsed if dt is not None]
	if not valid:
		log("ERROR: No valid datetime_original values found.", log_path)
		return

	trip_start = min(valid)
	log(f"Trip start date: {trip_start.strftime('%Y-%m-%d')}", log_path)

	# assign
	updated = 0
	for dt, r in parsed:
		if dt is None:
			r["day_number"] = ""
		else:
			day_num = (dt.date() - trip_start.date()).days + 1
			r["day_number"] = str(day_num)
			updated += 1

	write_csv_dict(labels_csv, rows, rows[0].keys())
	log(f"Updated {updated} rows with day_number. Saved: {labels_csv}", log_path)

if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Assign day numbers to labels.csv inside MemoGraph")
	p.add_argument("--trip-folder", required=True, help="Trip folder path (e.g. data/trips/test_trip)")
	args = p.parse_args()
	assign_days(args.trip_folder)
