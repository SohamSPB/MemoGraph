#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
query_images.py

Provides an advanced query interface for labels.csv.
Filters by captions, species, dates, day ranges, tags, etc.
Exports results to CSV if requested.

Logs: <trip_folder>/MemoGraph/logs/query_images.log
"""

import os
import csv
import argparse
from datetime import datetime

from scripts.utils.utils_io import ensure_memograph_folder, read_csv_dict, write_csv_dict, ensure_dir
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG


def parse_args():
	p = argparse.ArgumentParser(description="Query image metadata CSV.")
	p.add_argument("--trip-folder", required=True, help="Trip folder")
	p.add_argument("--text", help="Search in captions")
	p.add_argument("--species", help="Search species_tags")
	p.add_argument("--faces", action="store_true", help="Filter images with faces")
	p.add_argument("--people", help="Search people_tags")
	p.add_argument("--location", help="Search location_inferred")
	p.add_argument("--device", help="Match device_model")
	p.add_argument("--date", help="Date or range (e.g., 2024-08-16:2024-08-18)")
	p.add_argument("--day", help="Match day_number or range")
	p.add_argument("--notes", help="Search notes")
	p.add_argument("--ext", help="Restrict file types (.jpg,.png)")
	p.add_argument("--limit", type=int, help="Limit result count")
	p.add_argument("--export", help="Export matched rows to new CSV")
	return p.parse_args()


def matches_date(date_str, date_range):
	if not date_str:
		return False
	try:
		dt = datetime.strptime(date_str.split(" ")[0], "%Y:%m:%d")
	except:
		return False
	if ":" in date_range:
		try:
			start_str, end_str = date_range.split(":")
			start = datetime.strptime(start_str, "%Y-%m-%d")
			end = datetime.strptime(end_str, "%Y-%m-%d")
			return start <= dt <= end
		except:
			return False
	else:
		try:
			target = datetime.strptime(date_range, "%Y-%m-%d")
			return dt.date() == target.date()
		except:
			return False


def matches_range(val_str, filter_str):
	try:
		val = int(val_str)
	except:
		return False
	if ":" in filter_str:
		try:
			start, end = map(int, filter_str.split(":"))
			return start <= val <= end
		except:
			return False
	return val_str == filter_str


def query_images(csv_path, log_path, **filters):
	matched = []
	rows = read_csv_dict(csv_path)
	for row in rows:
		if filters.get("text"):
			if not any(filters["text"].lower() in (row.get(col) or "").lower()
					   for col in ["caption", "caption_ai", "caption_samples"]):
				continue
		if filters.get("species") and filters["species"].lower() not in (row.get("species_tags") or "").lower():
			continue
		if filters.get("faces") and not row.get("faces_detected"):
			continue
		if filters.get("people") and filters["people"].lower() not in (row.get("people_tags") or "").lower():
			continue
		if filters.get("location") and filters["location"].lower() not in (row.get("location_inferred") or "").lower():
			continue
		if filters.get("device") and filters["device"].lower() not in (row.get("device_model") or "").lower():
			continue
		if filters.get("date") and not matches_date(row.get("datetime_original"), filters["date"]):
			continue
		if filters.get("day") and not matches_range(row.get("day_number"), filters["day"]):
			continue
		if filters.get("notes") and filters["notes"].lower() not in (row.get("notes") or "").lower():
			continue
		if filters.get("ext"):
			exts = [e.strip().lower() for e in filters["ext"].split(",")]
			if not any(row.get("image_name", "").lower().endswith(ext) for ext in exts):
				continue
		matched.append(row)
		if filters.get("limit") and len(matched) >= filters["limit"]:
			break

	if filters.get("export") and matched:
		export_path = os.path.join(os.path.dirname(csv_path), "outputs", filters["export"])
		ensure_dir(export_path)
		write_csv_dict(export_path, matched, matched[0].keys())
		log(f"Exported {len(matched)} rows to {export_path}", log_path)

	return matched


if __name__ == "__main__":
	args = parse_args()
	memo_dir = ensure_memograph_folder(args.trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	log_path = os.path.join(memo_dir, "logs", "query_images.log")

	init_log(log_path, "query_images.py")
	csv_path = os.path.join(memo_dir, "labels.csv")

	results = query_images(
		csv_path, log_path,
		text=args.text,
		species=args.species,
		faces=args.faces,
		people=args.people,
		location=args.location,
		device=args.device,
		date=args.date,
		day=args.day,
		notes=args.notes,
		ext=args.ext,
		limit=args.limit,
		export=args.export
	)

	print("Matched Images:")
	for r in results:
		print("-", r.get("image_name"))
	print("Total:", len(results))
