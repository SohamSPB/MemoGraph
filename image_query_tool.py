import argparse
import csv
import os
import sys
from datetime import datetime


def parse_args():
	parser = argparse.ArgumentParser(description="Query image metadata CSV.")
	parser.add_argument("--csv", required=True, help="Path to CSV file")
	parser.add_argument("--text", help="Search in caption, caption_ai, and caption_samples")
	parser.add_argument("--species", help="Search species_tags")
	parser.add_argument("--faces", action="store_true", help="Filter images with faces_detected")
	parser.add_argument("--people", help="Search people_tags")
	parser.add_argument("--location", help="Search location_inferred")
	parser.add_argument("--device", help="Match device_model")
	parser.add_argument("--date", help="Date or date range (e.g. 2024-08-16:2024-08-18)")
	parser.add_argument("--day", help="Match day_number or range")
	parser.add_argument("--notes", help="Search in notes")
	parser.add_argument("--ext", help="Restrict file types (e.g. .jpg,.png)")
	parser.add_argument("--limit", type=int, help="Limit result count")
	parser.add_argument("--export", help="Export matched rows to new CSV")
	return parser.parse_args()


def matches_date(date_str, date_range):
	if not date_str:
		return False
	try:
		dt = datetime.strptime(date_str.split(" ")[0], "%Y:%m:%d")
	except:
		return False
	if ":" in date_range:
		start_str, end_str = date_range.split(":")
		try:
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
	else:
		return val_str == filter_str


def query_images(csv_path, **filters):
	matched = []
	with open(csv_path, "r", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			if filters.get("text"):
				text_match = any(filters["text"].lower() in (row.get(col) or "").lower()
								 for col in ["caption", "caption_ai", "caption_samples"])
				if not text_match:
					continue
			if filters.get("species") and filters["species"].lower() not in (row.get("species_tags") or "").lower():
				continue
			if filters.get("faces") and not (row.get("faces_detected") and row["faces_detected"].strip()):
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
				ext_match = any(row.get("image_name", "").lower().endswith(ext.strip()) for ext in filters["ext"].split(","))
				if not ext_match:
					continue
			matched.append(row)
			if filters.get("limit") and len(matched) >= filters["limit"]:
				break

	if filters.get("export"):
		with open(filters["export"], "w", encoding="utf-8", newline="") as f:
			if matched:
				writer = csv.DictWriter(f, fieldnames=matched[0].keys())
				writer.writeheader()
				writer.writerows(matched)

	return matched


if __name__ == "__main__":
	# python image_query_tool.py --csv data/trips/test_trip/labels.csv --text "flowers" --date 2025-04-01:2025-04-04 --limit 10 --export matched_results.csv
	
	args = parse_args()
	results = query_images(
		csv_path=args.csv,
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
