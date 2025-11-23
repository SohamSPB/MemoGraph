#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map_visualizer.py

Generates an interactive HTML map of GPS-tagged photos using Folium.
Each marker shows the photo and caption.

Outputs:
- <trip_folder>/MemoGraph/trip_map.html
- Logs in <trip_folder>/MemoGraph/logs/map_visualizer.log
"""

import os
import shutil
import folium
from folium.plugins import MarkerCluster

from scripts.utils.utils_io import (
	read_csv_dict,
	ensure_dir
)
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_text import clean_caption

def load_geo_points(csv_path, trip_folder):
	points = []
	rows = read_csv_dict(csv_path)
	for r in rows:
		try:
			lat = float(r.get("gps_lat") or 0)
			lon = float(r.get("gps_lon") or 0)
			if lat == 0 or lon == 0:
				continue
			caption = clean_caption(r.get("caption_ai") or r.get("caption") or "Untitled")
			img_path = os.path.join(trip_folder, r.get("local_path", ""))
			img_tag = f"<br/><img src='{img_path}' width='150'/>" if os.path.exists(img_path) else ""
			day = str(r.get("day_number") or "").strip()
			loc = (r.get("location_inferred") or "").strip()
			meta_parts = []
			if day:
				meta_parts.append(f"Day {day}")
			if loc:
				meta_parts.append(loc)
			meta = " – ".join(meta_parts)
			meta_html = f"<br/><small>{meta}</small>" if meta else ""
			popup = f"<b>{caption}</b>{meta_html}{img_tag}"
			points.append((lat, lon, popup))
		except:
			continue
	return points


def create_map(points, output_path):
	if not points:
		return False
	center = points[0][:2]
	map_obj = folium.Map(location=center, zoom_start=12)
	cluster = MarkerCluster().add_to(map_obj)
	for lat, lon, popup in points:
		folium.Marker(location=[lat, lon], popup=popup).add_to(cluster)
	map_obj.save(output_path)
	return True


def visualize_map(trip_folder):
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "map_visualizer.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "map_visualizer.py")

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	points = load_geo_points(csv_path, trip_folder)
	if not points:
		log("No GPS-tagged points found.", log_path)
		return

	output_html = os.path.join(memo_dir, "trip_map.html")
	if create_map(points, output_html):
		log(f"Map generated: {output_html}", log_path)
	else:
		log("Failed to generate map (no points).", log_path)


def create_overview_page(trip_folder):
	"""
	Create an overview HTML page that embeds the main trip_map.html and also
	lists photos that do not have GPS coordinates (and therefore do not
	appear on the map) on the side.

	Output: <trip_folder>/MemoGraph/trip_overview.html
	"""
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "map_visualizer.log") if CFG.LOG_TO_FILE else None

	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV; cannot build overview.", log_path)
		return

	unlocated = []
	all_tags = set()

	def infer_tags(row):
		"""Infer coarse tags for filtering based on detected_objects/species/image_type."""
		text = " ".join(
			str(row.get(field, "")).lower()
			for field in ("detected_objects", "species_tags", "caption", "caption_ai")
		)
		image_type = (row.get("image_type") or "").lower()
		tags = set()

		# Selfie/group hints from faces_count (if present) or faces_detected.
		try:
			fc_val = str(row.get("faces_count", "")).strip()
			fc = int(fc_val) if fc_val else 0
		except ValueError:
			fc = 0
		if fc >= 2:
			tags.add("group")
		elif fc == 1 or row.get("faces_detected") == "1":
			tags.add("selfie")

		if "person" in text or "people" in text or row.get("faces_detected") == "1":
			tags.add("people")
		if "bird" in text:
			tags.add("birds")
		if "flower" in text or "plant" in text or "tree" in text or "forest" in text:
			tags.add("nature")
			tags.add("plants_flowers")
		if "insect" in text or "butterfly" in text or "spider" in text:
			tags.add("insects")
		if "animal" in text or "dog" in text or "cat" in text or "yak" in text or "cow" in text:
			tags.add("animals")
		if "mountain" in text or "landscape" in text or "lake" in text or "river" in text:
			tags.add("landscapes")
		if "galaxy" in text or "nebula" in text or "astrophotography" in text or "night sky" in text:
			tags.add("astro")

		if image_type:
			tags.add(image_type)

		return tags

	for r in rows:
		lat_raw = (str(r.get("gps_lat") or "").strip())
		lon_raw = (str(r.get("gps_lon") or "").strip())
		if not lat_raw or not lon_raw:
			unlocated.append(r)
			tags = infer_tags(r)
			r["_mg_tags"] = sorted(tags)
			all_tags.update(tags)

	overview_path = os.path.join(memo_dir, "trip_overview.html")

	# Copy shared Material-style CSS theme into MemoGraph so the overview
	# page can reference it locally.
	root_dir = os.path.dirname(os.path.dirname(__file__))
	template_css = os.path.join(root_dir, "templates", "memograph_ui.css")
	target_css = os.path.join(memo_dir, "memograph_ui.css")
	if os.path.exists(template_css):
		try:
			shutil.copyfile(template_css, target_css)
		except Exception as e:
			log(f"WARNING: Failed to copy memograph_ui.css: {e}", log_path)

	# Build a simple HTML shell that embeds the existing map and shows
	# unlocated images in a sidebar.
	html_parts = []
	html_parts.append("<!DOCTYPE html>")
	html_parts.append("<html lang='en'>")
	html_parts.append("<head>")
	html_parts.append("<meta charset='utf-8'/>")
	html_parts.append("<title>MemoGraph Trip Overview</title>")
	html_parts.append("<link rel='stylesheet' href='memograph_ui.css'/>")
	html_parts.append("</head>")
	html_parts.append("<body>")
	html_parts.append("<div class='mg-app-bar'>")
	html_parts.append("<div class='mg-app-bar-title'>MemoGraph Trip Overview</div>")
	html_parts.append("<div class='mg-app-bar-subtle'>GPS map + photos without location</div>")
	html_parts.append("</div>")
	html_parts.append("<div class='layout'>")

	# Left: map iframe (trip_map.html in same MemoGraph folder)
	html_parts.append("<div class='map-pane'>")
	html_parts.append("<iframe src='trip_map.html' title='Trip Map'></iframe>")
	html_parts.append("</div>")

	# Right: list of images without GPS
	html_parts.append("<div class='side-pane'>")
	html_parts.append("<h2>Photos without location</h2>")

	# Filter bar
	if all_tags:
		html_parts.append("<div class='filters'>")
		html_parts.append("<strong>Filters:</strong><br/>")
		for tag in sorted(all_tags):
			html_parts.append(
				f"<label class='mg-chip'><input type='checkbox' class='filter-checkbox' value='{tag}'/> {tag}</label>"
			)
		html_parts.append("<br/><button type='button' id='clear-filters' class='mg-button'>Clear filters</button>")
		html_parts.append("<hr/>")

	if not unlocated:
		html_parts.append("<p>All photos have GPS coordinates and appear on the map.</p>")
	else:
		for r in unlocated:
			name = r.get("image_name", "") or r.get("local_path", "")
			local_path = r.get("local_path", "")
			# From MemoGraph folder, images live one level up.
			img_rel = os.path.join("..", local_path) if local_path else ""
			caption = r.get("caption_ai") or r.get("caption") or ""
			tag_list = r.get("_mg_tags", [])
			tag_attr = " ".join(tag_list)
			html_parts.append(f"<div class='thumb mg-card' data-tags='{tag_attr}'>")
			if img_rel:
				html_parts.append(f"<img src='{img_rel}' alt='{name}' loading='lazy'/>")
			html_parts.append(f"<div class='thumb-title'>{name}</div>")
			if caption:
				html_parts.append(f"<div class='thumb-caption'>{caption}</div>")
			if tag_list:
				html_parts.append(
					f"<div class='thumb-caption'><em>tags: {', '.join(tag_list)}</em></div>"
				)
			html_parts.append("</div>")
	html_parts.append("</div>")  # side-pane

	html_parts.append("</div>")  # layout

	# Simple JS to handle filter checkboxes (OR semantics, no filter = show all)
	html_parts.append(
		"<script>"
		"const checkboxes = document.querySelectorAll('.filter-checkbox');"
		"const clearBtn = document.getElementById('clear-filters');"
		"const thumbs = document.querySelectorAll('.thumb');"
		"function syncChipState() {"
		"  checkboxes.forEach(cb => {"
		"    const label = cb.closest('.mg-chip');"
		"    if (!label) return;"
		"    if (cb.checked) label.classList.add('mg-chip--active');"
		"    else label.classList.remove('mg-chip--active');"
		"  });"
		"}"
		"function applyFilters() {"
		"  const active = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);"
		"  if (active.length === 0) {"
		"    thumbs.forEach(t => t.style.display = 'block');"
		"    return;"
		"  }"
		"  thumbs.forEach(t => {"
		"    const tags = (t.getAttribute('data-tags') || '').split(' ').filter(Boolean);"
		"    const show = tags.some(tag => active.includes(tag));"
		"    t.style.display = show ? 'block' : 'none';"
		"  });"
		"}"
		"checkboxes.forEach(cb => cb.addEventListener('change', () => { syncChipState(); applyFilters(); }));"
		"if (clearBtn) {"
		"  clearBtn.addEventListener('click', () => {"
		"    checkboxes.forEach(cb => cb.checked = false);"
		"    syncChipState();"
		"    applyFilters();"
		"  });"
		"}"
		"window.addEventListener('DOMContentLoaded', syncChipState);"
		"</script>"
	)

	html_parts.append("</body></html>")

	with open(overview_path, "w", encoding="utf-8") as f:
		f.write("\n".join(html_parts))

	log(f"Overview page generated: {overview_path}", log_path)


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Generate an interactive map for the trip.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	visualize_map(args.trip_folder)
