#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_scanner.py

Scans a trip folder for image files, extracts EXIF metadata, and writes a fresh
labels CSV inside <trip_folder>/MemoGraph/.

- Backs up existing labels.csv (rotating N backups).
- Logs all steps to <trip_folder>/MemoGraph/logs/image_scanner.log
- Column schema is taken from memograph_config.py if present; else a built-in fallback is used.
"""

import os
import csv
import hashlib
import piexif
import exifread

# --- Local utils ---
from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	write_csv_dict,
	backup_csv,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

# ----------------------------------------------------------------------
# EXIF helpers
# ----------------------------------------------------------------------
def get_md5(file_path: str) -> str:
	"""Calculate the MD5 checksum of a file."""
	hash_md5 = hashlib.md5()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def clean_exif_string(byte_str: bytes) -> str:
	"""Decode EXIF byte string safely and remove null characters."""
	return byte_str.decode(errors="ignore").strip("\x00").strip()

def get_exif_piexif(image_path: str) -> dict:
	"""Load EXIF data using piexif."""
	try:
		return piexif.load(image_path)
	except Exception as e:
		return {}

def get_datetime(exif_dict: dict) -> str:
	"""Extract original datetime from EXIF."""
	try:
		return clean_exif_string(exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal])
	except Exception:
		return ""

def get_device_model(exif_dict: dict) -> str:
	"""Extract camera/device model from EXIF."""
	try:
		make = clean_exif_string(exif_dict["0th"].get(piexif.ImageIFD.Make, b""))
		model = clean_exif_string(exif_dict["0th"].get(piexif.ImageIFD.Model, b""))
		return (make + " " + model).strip()
	except Exception:
		return ""

def _convert_gps(coord, ref) -> float:
	"""Convert GPS coordinates from EXIF to decimal degrees."""
	d, m, s = coord
	deg = d[0] / d[1] + (m[0] / m[1]) / 60 + (s[0] / s[1]) / 3600
	if ref in [b"S", b"W"]:
		deg = -deg
	return deg

def get_gps(exif_dict: dict):
	"""Extract GPS latitude and longitude from EXIF."""
	try:
		gps_info = exif_dict["GPS"]
		lat = _convert_gps(gps_info[piexif.GPSIFD.GPSLatitude], gps_info[piexif.GPSIFD.GPSLatitudeRef])
		lon = _convert_gps(gps_info[piexif.GPSIFD.GPSLongitude], gps_info[piexif.GPSIFD.GPSLongitudeRef])
		return lat, lon
	except Exception:
		return None, None

def extract_exif_fallback(image_path: str):
	"""Fallback method to extract EXIF using exifread."""
	try:
		with open(image_path, "rb") as f:
			tags = exifread.process_file(f, details=False)
			dt = str(tags.get("EXIF DateTimeOriginal", "")).strip()
			make = str(tags.get("Image Make", "")).strip()
			model = str(tags.get("Image Model", "")).strip()

			gps_lat = tags.get("GPS GPSLatitude")
			gps_lat_ref = tags.get("GPS GPSLatitudeRef")
			gps_lon = tags.get("GPS GPSLongitude")
			gps_lon_ref = tags.get("GPS GPSLongitudeRef")

			def convert(coord, ref):
				parts = [float(x.num) / float(x.den) for x in coord.values]
				deg = parts[0] + parts[1] / 60 + parts[2] / 3600
				if ref.values[0] in ["S", "W"]:
					deg = -deg
				return deg

			lat = lon = None
			if gps_lat and gps_lon:
				lat = convert(gps_lat, gps_lat_ref)
				lon = convert(gps_lon, gps_lon_ref)

			return dt, (make + " " + model).strip(), lat, lon
	except Exception:
		return "", "", None, None

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def scan_images(trip_folder: str) -> None:
	"""
	Scan all images in the given folder, extract EXIF metadata,
	and write image metadata rows to <trip_folder>/MemoGraph/labels.csv.

	Notes
	-----
	- If an existing labels.csv exists, it is backed up first (max N backups).
	- Uses utils_log for file + console logging.
	"""
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)

	labels_csv = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "image_scanner.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, title="image_scanner.py")
	log(f"Trip folder: {trip_folder}", log_path)
	log(f"MemoGraph dir: {memo_dir}", log_path)
	log("Starting image scan...", log_path)

	# Backup if exists
	if os.path.exists(labels_csv):
		backup_csv(labels_csv, max_backups=CFG.MAX_BACKUPS, log_path=log_path)

	rows_out = []
	total_files = 0
	processed = 0

	for root, _, files in os.walk(trip_folder):
		for file in files:
			if file.lower().endswith(CFG.IMAGE_EXTENSIONS):
				total_files += 1

	for root, _, files in os.walk(trip_folder):
		for file in files:
			if not file.lower().endswith(CFG.IMAGE_EXTENSIONS):
				continue

			full_path = os.path.join(root, file)
			rel_path = os.path.relpath(full_path, trip_folder)

			processed += 1
			log(f"Scanning [{processed}/{total_files}]: {rel_path}", log_path)

			md5sum = get_md5(full_path)
			exif_dict = get_exif_piexif(full_path)

			if not exif_dict or "Exif" not in exif_dict or piexif.ExifIFD.DateTimeOriginal not in exif_dict["Exif"]:
				datetime_original, device_model, gps_lat, gps_lon = extract_exif_fallback(full_path)
			else:
				datetime_original = get_datetime(exif_dict)
				device_model = get_device_model(exif_dict)
				gps_lat, gps_lon = get_gps(exif_dict)

			# Build row by field order
			default_map = {h: "" for h in CFG.CSV_HEADERS}
			default_map.update({
				"image_name": file,
				"local_path": rel_path,
				"md5sum": md5sum,
				"datetime_original": datetime_original,
				"device_model": device_model,
				"gps_lat": gps_lat if gps_lat is not None else "",
				"gps_lon": gps_lon if gps_lon is not None else "",
			})
			rows_out.append(default_map)

	# write
	write_csv_dict(labels_csv, rows_out, CFG.CSV_HEADERS)
	log(f"Completed. Wrote {len(rows_out)} rows to {labels_csv}", log_path)
	log("Done.", log_path)
	return labels_csv

# CLI
if __name__ == "__main__":
	# Quick & simple CLI:
	import argparse
	parser = argparse.ArgumentParser(description="Scan images + extract EXIF into MemoGraph/labels.csv")
	parser.add_argument("--trip-folder", required=True, help="Path to the trip folder (e.g. data/trips/test_trip)")
	args = parser.parse_args()

	scan_images(args.trip_folder)
