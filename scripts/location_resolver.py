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
from datetime import datetime
from geopy.geocoders import Nominatim

from scripts.utils.utils_io import (
	read_csv_dict,
	write_csv_dict,
	ensure_dir,
)
from memograph_config import ensure_memograph_folder
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


def _parse_datetime(value: str):
	"""Parse EXIF-style datetime strings into datetime objects, or None if invalid."""
	value = (value or "").strip()
	if not value:
		return None
	for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
		try:
			return datetime.strptime(value, fmt)
		except ValueError:
			continue
	return None


def _propagate_gps_for_nearby_images(rows, log_path: str | None = None) -> None:
	"""
	Propagate gps_lat/gps_lon from the nearest previous image that has valid
	GPS coordinates when the time difference is within a configurable window.

	This is useful when some photos on a trip lack GPS tags but are taken
	within a few minutes of a geotagged image, so their physical location is
	effectively the same.
	"""
	max_minutes = getattr(CFG, "GPS_PROPAGATION_MAX_MINUTES", 15)
	if max_minutes <= 0:
		return

	parsed_times = [_parse_datetime(r.get("datetime_original", "")) for r in rows]
	indices_with_time = [i for i, dt in enumerate(parsed_times) if dt is not None]
	if not indices_with_time:
		return

	# Sort indices by datetime so we can sweep in chronological order.
	indices_with_time.sort(key=lambda i: parsed_times[i])

	last_idx_with_gps = None
	last_dt = None
	for idx in indices_with_time:
		row = rows[idx]
		dt = parsed_times[idx]
		lat_raw = (row.get("gps_lat") or "").strip()
		lon_raw = (row.get("gps_lon") or "").strip()

		if lat_raw and lon_raw:
			# This row has GPS; remember it as the latest source.
			last_idx_with_gps = idx
			last_dt = dt
			continue

		if last_idx_with_gps is None or last_dt is None:
			continue

		# Only propagate if the time difference is within the configured window.
		delta_min = abs((dt - last_dt).total_seconds()) / 60.0
		if delta_min <= max_minutes:
			src = rows[last_idx_with_gps]
			src_lat = (src.get("gps_lat") or "").strip()
			src_lon = (src.get("gps_lon") or "").strip()
			if src_lat and src_lon:
				row["gps_lat"] = src_lat
				row["gps_lon"] = src_lon
				log(
					f"[GPS propagate] {row.get('image_name')} <- {src.get('image_name')} (delta_t ~= {delta_min:.1f} min)",
					log_path,
				)

def fill_location(trip_folder: str) -> None:
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
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

	# First, try to propagate missing GPS from nearby-in-time images that
	# already have valid coordinates, so that more rows can be reverse-geocoded.
	_propagate_gps_for_nearby_images(rows, log_path)

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
