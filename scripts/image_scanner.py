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
	read_csv_dict,
	write_csv_dict,
	ensure_dir,
)
from memograph_config import ensure_memograph_folder
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
def _extract_exif_row(full_path: str, rel_path: str, md5sum: str) -> dict:
	"""Build a fresh CSV row dict for a single image with EXIF columns populated.

	Analysis columns (faces_*, caption, species_tags, etc.) start empty/-1 and
	will be filled in by downstream pipeline steps. Used for both brand-new
	photos and photos whose content changed (different md5 at the same path).
	"""
	exif_dict = get_exif_piexif(full_path)
	if not exif_dict or "Exif" not in exif_dict or piexif.ExifIFD.DateTimeOriginal not in exif_dict["Exif"]:
		datetime_original, device_model, gps_lat, gps_lon = extract_exif_fallback(full_path)
	else:
		datetime_original = get_datetime(exif_dict)
		device_model = get_device_model(exif_dict)
		gps_lat, gps_lon = get_gps(exif_dict)

	row = {h: "" for h in CFG.CSV_HEADERS}
	row.update(
		{
			"image_name": os.path.basename(full_path),
			"local_path": rel_path,
			"md5sum": md5sum,
			"datetime_original": datetime_original,
			"device_model": device_model,
			"gps_lat": gps_lat if gps_lat is not None else "",
			"gps_lon": gps_lon if gps_lon is not None else "",
			"faces_detected": -1,
			"faces_count": -1,
		}
	)
	return row


def scan_images(trip_folder: str) -> None:
	"""
	Scan all images in the given folder, extract EXIF metadata,
	and write image metadata rows to <trip_folder>/MemoGraph/labels.csv.

	Resume-safe merge behavior (the previous implementation just overwrote
	the CSV, destroying every analysis column on every re-run):

	- Photos already present in labels.csv with the same local_path AND md5
	  are kept verbatim — including all analysis columns (faces, captions,
	  species, quality scores, color palette, vision_caption, etc.).
	- Photos at the same path but with a different md5 (content replaced)
	  are re-scanned for EXIF; analysis columns reset.
	- Photos newly present on disk get a fresh EXIF-only row.
	- Photos that vanished from disk are dropped from the CSV.

	The MemoGraph subfolder is excluded from the walk so our own generated
	thumbnails (MemoGraph/thumbnails/*.jpg) aren't picked up as new photos.
	"""
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)

	labels_csv = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "image_scanner.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, title="image_scanner.py")
	log(f"Trip folder: {trip_folder}", log_path)
	log(f"MemoGraph dir: {memo_dir}", log_path)
	log("Starting image scan...", log_path)

	# Existing rows, indexed by local_path. read_csv_dict returns [] if the
	# file doesn't exist yet, which is the natural state on a fresh trip.
	existing_rows = read_csv_dict(labels_csv)
	existing_by_path = {
		r.get("local_path", ""): r for r in existing_rows if r.get("local_path")
	}

	# Collect candidate images, skipping our own MemoGraph outputs.
	image_files = []
	memograph_folder = CFG.MEMOGRAPH_FOLDER_NAME
	for root, dirs, files in os.walk(trip_folder):
		dirs[:] = [d for d in dirs if d != memograph_folder]
		for file in files:
			if file.lower().endswith(CFG.IMAGE_EXTENSIONS):
				full_path = os.path.join(root, file)
				rel_path = os.path.relpath(full_path, trip_folder)
				image_files.append((rel_path, full_path))

	# Sort by relative path so the CSV row order is deterministic across runs.
	image_files.sort(key=lambda x: x[0])
	total_files = len(image_files)

	rows_out = []
	preserved = 0
	rescanned = 0
	new_count = 0

	for processed, (rel_path, full_path) in enumerate(image_files, 1):
		md5sum = get_md5(full_path)
		prev = existing_by_path.get(rel_path)

		if prev and prev.get("md5sum") == md5sum:
			# Same path, same content — keep the entire prior row, including
			# every analysis column. This is the "resume preserves work" path,
			# which the previous implementation broke by always rebuilding
			# from scratch.
			rows_out.append(prev)
			preserved += 1
			log(f"[{processed}/{total_files}] preserved: {rel_path}", log_path)
			continue

		# New file, or the file at this path was replaced (different md5).
		# Either way, re-extract EXIF and reset analysis columns to defaults.
		row = _extract_exif_row(full_path, rel_path, md5sum)
		rows_out.append(row)
		if prev:
			rescanned += 1
			log(
				f"[{processed}/{total_files}] content changed, re-scanning: {rel_path}",
				log_path,
			)
		else:
			new_count += 1
			log(f"[{processed}/{total_files}] new: {rel_path}", log_path)

	dropped = len(existing_by_path) - preserved - rescanned

	# Content-dedup: group rows by md5sum, pick a canonical per group, and mark
	# the others with duplicate_of=<canonical_image_name>. Analysis scripts
	# downstream check this column and skip duplicates; dedup_broadcast.py
	# copies the canonical's analysis to its siblings at the end of the pipeline.
	#
	# Canonical = the group member whose local_path sorts first. This is
	# deterministic so the same files always elect the same canonical across
	# runs, which makes resume/preserve work cleanly with B1's merge logic.
	md5_groups: dict = {}
	for row in rows_out:
		md5 = row.get("md5sum", "")
		if md5:
			md5_groups.setdefault(md5, []).append(row)

	duplicate_count = 0
	for md5, group in md5_groups.items():
		# Reset all members first so a previously-marked duplicate becomes a
		# canonical when its canonical is removed or the group changes.
		for r in group:
			r["duplicate_of"] = ""
		if len(group) < 2:
			continue
		group.sort(key=lambda r: r.get("local_path", ""))
		canonical = group[0]
		canonical_name = canonical.get("image_name", "")
		for r in group[1:]:
			r["duplicate_of"] = canonical_name
			duplicate_count += 1

	# Field order: preserve whatever the existing CSV had (which may include
	# dynamic columns like face_locations / species_boxes that aren't in
	# CSV_HEADERS), then append any new headers introduced by CSV_HEADERS.
	if existing_rows:
		fieldnames = list(dict.fromkeys(list(existing_rows[0].keys()) + list(CFG.CSV_HEADERS)))
	else:
		fieldnames = list(CFG.CSV_HEADERS)

	write_csv_dict(labels_csv, rows_out, fieldnames)
	log(
		(
			f"Scan complete: {len(rows_out)} rows "
			f"(preserved={preserved}, rescanned={rescanned}, new={new_count}, "
			f"dropped={dropped}, duplicates={duplicate_count}). Saved: {labels_csv}"
		),
		log_path,
	)
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
