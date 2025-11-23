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
from collections import defaultdict, Counter

from scripts.utils.utils_io import (
	read_csv_dict,
	ensure_dir,
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_text import (
	clean_caption,
	combine_captions_for_day,
	clean_species_list,
)

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
	# Clean and normalize species names for human-facing text.
	raw = clean_species_list(species)

	def _norm(name: str) -> str:
		name = (name or "").strip()
		if not name:
			return ""
		low = name.lower()
		for art in ("a ", "an ", "the "):
			if low.startswith(art):
				name = name[len(art):].lstrip()
				break
		if name and name[0].islower():
			name = name[0].upper() + name[1:]
		return name

	species = [s for s in (_norm(n) for n in raw) if s]
	if not species:
		return ""
	species = sorted(species)
	if len(species) == 1:
		return f"We spotted {species[0]}."
	elif len(species) == 2:
		return f"We saw {species[0]} and {species[1]}."
	else:
		return f"We encountered species like {', '.join(species[:-1])}, and {species[-1]}."


def _classify_row_themes(row):
	"""
	Assign coarse thematic tags to a row based on labels/captions.
	Used to build slightly richer day summaries without heavy models.
	"""
	text = " ".join(
		[
			str(row.get("detected_objects") or ""),
			str(row.get("species_tags") or ""),
			str(row.get("caption") or ""),
			str(row.get("caption_ai") or ""),
			str(row.get("image_type") or ""),
		]
	).lower()
	tags = set()

	if str(row.get("faces_detected", "")).strip() == "1":
		tags.add("people")
	if any(k in text for k in ("mountain", "valley", "ridge", "pass", "peak", "himalaya")):
		tags.add("mountains")
	if any(k in text for k in ("river", "lake", "waterfall", "pool", "sea", "ocean")):
		tags.add("water")
	if any(k in text for k in ("monument", "temple", "monastery", "building", "cityscape", "village", "street")):
		tags.add("towns")
	if any(k in text for k in ("galaxy", "nebula", "milky way", "night sky", "star cluster", "astrophotography")):
		tags.add("astro")
	if any(k in text for k in ("bird", "yak", "horse", "dog", "cat", "animal")):
		tags.add("wildlife")
	if any(k in text for k in ("plate of food", "food dish", "thali", "curry", "meal", "breakfast", "dinner", "lunch", "snack", "street food", "chai", "tea", "coffee", "restaurant", "cafe", "dessert")):
		tags.add("food")
	if any(k in text for k in ("temple", "monastery", "stupa", "mosque", "church", "palace", "fort", "castle", "shrine", "historical gate", "gate", "arch")):
		tags.add("temples_palaces")
	if any(k in text for k in ("market", "bazaar", "street market", "shop", "stall", "souvenir", "shopping street", "street vendor")):
		tags.add("markets")
	if any(k in text for k in ("hotel room", "guesthouse", "homestay", "hostel", "resort", "campsite", "tent", "campfire")):
		tags.add("stays")
	if any(k in text for k in ("mountain road", "highway", "road", "trail", "path", "steps", "staircase", "bridge", "suspension bridge")):
		tags.add("roads_trails")
	return tags


def summarize_day_themes(rows):
	"""Return a Counter of coarse themes and a count of people photos."""
	theme_counts = Counter()
	people_photos = 0
	for r in rows:
		tags = _classify_row_themes(r)
		for t in tags:
			theme_counts[t] += 1
		if "people" in tags:
			people_photos += 1
	return theme_counts, people_photos


def generate_day_paragraph(date, rows, day_number):
	"""Build a paragraph summary for a day."""
	rows.sort(key=lambda x: x["_datetime"])
	first, last = rows[0], rows[-1]

	captions = [clean_caption(r.get("caption", "")) for r in rows if r.get("caption")]
	ai_captions = [clean_caption(r.get("caption_ai", "")) for r in rows if r.get("caption_ai")]

	species = set()
	for r in rows:
		tags = r.get("species_tags", "").strip()
		if tags:
			species.update(s.strip() for s in tags.split(",") if s.strip())

	time_start = first["_datetime"].strftime("%I:%M %p")
	time_end = last["_datetime"].strftime("%I:%M %p")
	start_loc = first.get("location_inferred", "an unknown place")
	end_loc = last.get("location_inferred", start_loc)

	theme_counts, people_photos = summarize_day_themes(rows)

	paragraph = f"**Day {day_number} - {date}**\n"
	paragraph += f"Our journey began around {time_start} from {start_loc}, and we concluded the day by {time_end} near {end_loc}. "

	# Add short thematic sentences based on what we mostly photographed.
	top_themes = [t for t, _ in theme_counts.most_common(4)]
	theme_parts = []

	def add_theme(tag, sentence, threshold=1):
		if theme_counts.get(tag, 0) >= threshold and sentence not in theme_parts:
			theme_parts.append(sentence)

	# Prioritise a few key themes; keep at most 3 theme sentences.
	add_theme("mountains", "Much of the day was spent among high roads and mountain valleys.", threshold=2)
	add_theme("water", "We followed rivers, lakes, and pools for a good part of the day.", threshold=2)
	add_theme("towns", "We wandered through towns, streets, and small settlements along the route.", threshold=2)
	add_theme("temples_palaces", "We spent time exploring temples, monasteries, and old monuments along the way.", threshold=1)
	add_theme("markets", "At ground level, markets and narrow lanes pulled us in with their shops and street stalls.", threshold=1)
	add_theme("food", "Food breaks became part of the journey, from street snacks to heavier plates of local food.", threshold=1)
	add_theme("stays", "By evening we settled into simple stays that looked back over the roads and trails we had just covered.", threshold=1)
	add_theme("astro", "Later, we turned our attention to the night sky, capturing galaxies and nebulae.", threshold=1)
	if people_photos > 0:
		add_theme("people", "We also paused for photos with people we met along the way.", threshold=1)

	# Trim to avoid overly long intros.
	if len(theme_parts) > 3:
		theme_parts = theme_parts[:3]

	if theme_parts:
		paragraph += " ".join(theme_parts) + " "

	if ai_captions:
		sample = combine_captions_for_day(ai_captions, max_items=2)
		if sample:
			paragraph += f"Scenes we captured include: {sample} "
	elif captions:
		sample = combine_captions_for_day(captions, max_items=3)
		if sample:
			paragraph += f"Moments captured include: {sample} "

	paragraph += describe_species(species) + "\n\n"
	return paragraph


# -----------------------------
# Main blog generation
# -----------------------------
def generate_blog(trip_folder):
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
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
