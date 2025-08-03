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
import folium
from folium.plugins import MarkerCluster

from scripts.utils.utils_io import (
	ensure_memograph_folder,
	read_csv_dict,
	ensure_dir
)
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

def load_geo_points(csv_path, trip_folder):
	points = []
	rows = read_csv_dict(csv_path)
	for r in rows:
		try:
			lat = float(r.get("gps_lat") or 0)
			lon = float(r.get("gps_lon") or 0)
			if lat == 0 or lon == 0:
				continue
			caption = r.get("caption_ai") or r.get("caption") or "Untitled"
			img_path = os.path.join(trip_folder, r.get("local_path", ""))
			img_tag = f"<br/><img src='{img_path}' width='150'/>" if os.path.exists(img_path) else ""
			popup = f"<b>{caption}</b>{img_tag}"
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
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memo_dir, "logs")
	ensure_dir(logs_dir)
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


if __name__ == "__main__":
	import argparse
	p = argparse.ArgumentParser(description="Generate an interactive map for the trip.")
	p.add_argument("--trip-folder", required=True, help="Trip folder (e.g. data/trips/test_trip)")
	args = p.parse_args()
	visualize_map(args.trip_folder)
