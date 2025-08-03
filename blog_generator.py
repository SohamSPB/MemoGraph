#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blog_generator.py

Generates:
- A Markdown blog summarizing the trip day by day.
- A JSON summary (photos per day, locations, species spotted).

Outputs:
- <trip_folder>/MemoGraph/blog.md
- <trip_folder>/MemoGraph/trip_summary.json
- Logs to <trip_folder>/MemoGraph/logs/blog_generator.log
"""

import os
import json
import csv
from datetime import datetime
from collections import defaultdict

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	ensure_dir,
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

# -----------------------------
# Helper functions
# -----------------------------
def group_by_day(rows):
	"""Groups image rows by datetime (YYYY-MM-DD)."""
	daywise = defaultdict(list)
	for row in rows:
		dt_str = row.get("datetime_original", "").strip()
		try:
			dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
			row["_datetime"] = dt
			daywise[dt.strftime("%Y-%m-%d")].append(row)
		except Exception:
			continue
	return dict(sorted(daywise.items()))


def describe_species(species):
	"""Return a sentence summarizing species observed that day."""
	if not species:
		return ""
	species = sorted(species)
	if len(species) == 1:
		return f"We spotted a {species[0]}."
	elif len(species) == 2:
		return f"We saw a {species[0]} and a {species[1]}."
	else:
		return f"We encountered species like {', '.join(species[:-1])}, and {species[-1]}."


def generate_day_paragraph(date, rows, day_number):
	"""Build a paragraph summary for a day."""
	rows.sort(key=lambda x: x["_datetime"])
	first, last = rows[0], rows[-1]

	captions = [r.get("caption", "").strip() for r in rows if r.get("caption")]
	ai_captions = [r.get("caption_ai", "").strip() for r in rows if r.get("caption_ai")]

	species = set()
	for r in rows:
		tags = r.get("species_tags", "").strip()
		if tags:
			species.update(s.strip() for s in tags.split(",") if s.strip())

	time_start = first["_datetime"].strftime("%I:%M %p")
	time_end = last["_datetime"].strftime("%I:%M %p")
	start_loc = first.get("location_inferred", "an unknown place")
	end_loc = last.get("location_inferred", start_loc)

	paragraph = f"**Day {day_number} – {date}**\n"
	paragraph += f"Our journey began around {time_start} from {start_loc}, and we concluded the day by {time_end} near {end_loc}. "

	if ai_captions:
		sample = " ".join(ai_captions[:2]) + ("..." if len(ai_captions) > 2 else "")
		paragraph += f"Scenes we captured include: {sample} "
	elif captions:
		sample = " ".join(captions[:3]) + ("..." if len(captions) > 3 else "")
		paragraph += f"Moments captured include: {sample} "

	paragraph += describe_species(species) + "\n\n"
	return paragraph


# -----------------------------
# Main blog generation
# -----------------------------
def generate_blog(trip_folder):
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
	log_path = os.path.join(logs_dir, "blog_generator.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "blog_generator.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		log("ERROR: No rows in CSV.", log_path)
		return

	daywise = group_by_day(rows)
	if not daywise:
		log("ERROR: No valid dates for grouping.", log_path)
		return

	blog_lines = ["# Trip Blog", ""]
	trip_summary = []

	for i, (day, day_rows) in enumerate(daywise.items()):
		summary = generate_day_paragraph(day, day_rows, i + 1)
		blog_lines.append(summary)
		trip_summary.append({
			"date": day,
			"day_number": i + 1,
			"num_photos": len(day_rows),
			"locations": list({r.get("location_inferred", "").strip() for r in day_rows if r.get("location_inferred")}),
			"species_spotted": sorted({s.strip() for r in day_rows for s in r.get("species_tags", "").split(",") if s.strip()}),
			"caption_samples": [r.get("caption_ai") or r.get("caption") for r in day_rows if r.get("caption_ai") or r.get("caption")][:3]
		})

	blog_md_path = os.path.join(memo_dir, "blog.md")
	summary_json_path = os.path.join(memo_dir, "trip_summary.json")

	try:
		with open(blog_md_path, "w", encoding="utf-8") as f:
			f.write("\n".join(blog_lines))
		log(f"Blog written to: {blog_md_path}", log_path)
	except Exception as e:
		log(f"ERROR: Failed to write blog: {e}", log_path)

	try:
		with open(summary_json_path, "w", encoding="utf-8") as f:
			json.dump(trip_summary, f, indent=2)
		log(f"Summary JSON written to: {summary_json_path}", log_path)
	except Exception as e:
		log(f"ERROR: Failed to write JSON: {e}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Generate a trip blog + summary JSON.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	generate_blog(args.trip_folder)
