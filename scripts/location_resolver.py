#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
location_resolver.py

Reverse-geocodes GPS coordinates in labels.csv and fills the
`location_inferred` column. Falls back to the trip folder name when
coordinates are missing or geocoding fails.

Writes to <trip_folder>/MemoGraph/labels.csv and logs to
<trip_folder>/MemoGraph/logs/location_resolver.log
"""

import os
import time
from geopy.geocoders import Nominatim

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def infer_trip_name_from_path(trip_folder: str) -> str:
	"""Use the folder's basename as a human hint for fallback locations."""
	return os.path.basename(trip_folder).replace("_", " ")

def resolve_location_from_gps(lat: float, lon: float, geolocator: Nominatim) -> str | None:
	"""Return address string or None if reverse geocoding fails."""
	try:
		location = geolocator.reverse((lat, lon), language="en", timeout=10)
		if location:
			return location.address
	except Exception as e:
		# We'll log the failure above.
		pass
	return None

def fill_location(trip_folder: str) -> None:
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "location_resolver.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "location_resolver.py")

	labels_csv = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(labels_csv):
		log(f"ERROR: labels.csv not found at {labels_csv}", log_path)
		return

	rows = read_csv_dict(labels_csv)
	if not rows:
		log("ERROR: labels.csv is empty.", log_path)
		return

	# Ensure required fields exist
	first = rows[0]
	required = {"gps_lat", "gps_lon", "location_inferred"}
	if not required.issubset(first.keys()):
		log(f"ERROR: labels.csv missing columns: {required - set(first.keys())}", log_path)
		return

	# Backup
	backup_csv(labels_csv, max_backups=CFG.MAX_BACKUPS, log_path=log_path)

	trip_hint = infer_trip_name_from_path(trip_folder)
	geolocator = Nominatim(user_agent="memograph_location_resolver")

	updated = 0
	for i, r in enumerate(rows, 1):
		current_loc = (r.get("location_inferred") or "").strip()
		lat_raw = (r.get("gps_lat") or "").strip()
		lon_raw = (r.get("gps_lon") or "").strip()

		if current_loc:
			continue

		if lat_raw and lon_raw:
			try:
				lat = float(lat_raw)
				lon = float(lon_raw)
				addr = resolve_location_from_gps(lat, lon, geolocator)
				if addr:
					r["location_inferred"] = addr
					updated += 1
					log(f"[{i}/{len(rows)}] Resolved -> {addr[:80]}...", log_path)
				else:
					r["location_inferred"] = trip_hint
					log(f"[{i}/{len(rows)}] Reverse geocoding failed, fallback -> {trip_hint}", log_path)
			except ValueError:
				r["location_inferred"] = trip_hint
				log(f"[{i}/{len(rows)}] Invalid GPS values, fallback -> {trip_hint}", log_path)
			time.sleep(getattr(CFG, "NOMINATIM_SLEEP_S", 1.0))  # be nice to Nominatim
		else:
			r["location_inferred"] = trip_hint

	write_csv_dict(labels_csv, rows, first.keys())
	log(f"Done. Updated {updated} rows. Saved to {labels_csv}", log_path)

if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Fill location_inferred via reverse geocoding.")
	p.add_argument("--trip-folder", required=True, help="Trip folder path (e.g. data/trips/test_trip)")
	args = p.parse_args()
	fill_location(args.trip_folder)
