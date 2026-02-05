#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_search_index.py

Build a unified search index across ALL MemoGraph-processed trips.
This enables global search by tags, location, person, date, species, color, etc.

Output: data/trips/search_index.json
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import memograph_config as CFG
from scripts.utils.utils_io import read_csv_dict
from scripts.utils.utils_log import get_logger

logger = get_logger("build_search_index")


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime string in various formats."""
    if not dt_str:
        return None
    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _get_time_of_day(dt: datetime) -> str:
    """Determine time of day from datetime."""
    hour = dt.hour
    if 5 <= hour < 9:
        return "early_morning"
    elif 9 <= hour < 12:
        return "morning"
    elif 12 <= hour < 14:
        return "noon"
    elif 14 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 20:
        return "evening"
    elif 20 <= hour < 22:
        return "night"
    else:
        return "late_night"


def _get_season(dt: datetime) -> str:
    """Determine season from month (Northern Hemisphere bias)."""
    month = dt.month
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "autumn"


def _parse_color_palette(palette_str: str) -> List[str]:
    """Parse color palette string into list of hex colors."""
    if not palette_str:
        return []
    # Format: "#RRGGBB; #RRGGBB; ..."
    colors = [c.strip() for c in palette_str.split(";") if c.strip().startswith("#")]
    return colors[:5]  # Max 5 colors


def _parse_tags(tags_str: str) -> List[str]:
    """Parse semicolon or comma separated tags into list."""
    if not tags_str:
        return []
    # Split by semicolon or comma
    tags = re.split(r"[;,]", tags_str)
    return [t.strip().lower() for t in tags if t.strip()]


def _extract_country(location: str) -> str:
    """Try to extract country from location string."""
    if not location:
        return ""
    # Common country patterns at the end
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        last = parts[-1].lower()
        # Known countries
        countries = ["india", "nepal", "usa", "uk", "australia", "germany", "france",
                     "japan", "china", "thailand", "indonesia", "malaysia", "singapore"]
        for country in countries:
            if country in last:
                return country.title()
        return parts[-1]
    return location


def _safe_float(val: str, default: float = 0.0) -> float:
    """Safely convert string to float."""
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _safe_int(val: str, default: int = 0) -> int:
    """Safely convert string to int."""
    try:
        return int(float(val)) if val else default
    except (ValueError, TypeError):
        return default


def build_image_entry(row: Dict[str, str], trip_name: str, trip_folder: str) -> Dict[str, Any]:
    """Build a search index entry for a single image."""
    # Parse datetime
    dt = _parse_datetime(row.get("datetime_original", ""))

    # Build entry
    entry = {
        "id": f"{trip_name}/{row.get('image_name', '')}",
        "trip": trip_name,
        "trip_folder": trip_folder,
        "filename": row.get("image_name", ""),
        "local_path": row.get("local_path", ""),
        "thumbnail": f"{trip_name}/MemoGraph/thumbnails/{row.get('image_name', '')}",
    }

    # Datetime fields
    if dt:
        entry["datetime"] = dt.isoformat()
        entry["year"] = dt.year
        entry["month"] = dt.month
        entry["month_name"] = dt.strftime("%B")
        entry["day"] = dt.day
        entry["weekday"] = dt.strftime("%A")
        entry["time"] = dt.strftime("%H:%M")
        entry["time_of_day"] = _get_time_of_day(dt)
        entry["season"] = _get_season(dt)
    else:
        entry["datetime"] = ""
        entry["year"] = 0
        entry["month"] = 0
        entry["month_name"] = ""
        entry["day"] = 0
        entry["weekday"] = ""
        entry["time"] = ""
        entry["time_of_day"] = ""
        entry["season"] = ""

    # Location
    location = row.get("location_inferred", "")
    entry["location"] = location
    entry["country"] = _extract_country(location)

    # GPS
    lat = _safe_float(row.get("gps_lat", ""))
    lon = _safe_float(row.get("gps_lon", ""))
    if lat and lon:
        entry["gps"] = [lat, lon]
    else:
        entry["gps"] = None

    # Tags (detected objects)
    entry["tags"] = _parse_tags(row.get("detected_objects", ""))

    # Species
    entry["species"] = _parse_tags(row.get("species_tags", ""))

    # Captions (for text search)
    captions = []
    for field in ["caption", "caption_ai", "vision_caption"]:
        cap = row.get(field, "")
        if cap:
            captions.append(cap)
    entry["captions"] = captions
    entry["caption_text"] = " ".join(captions).lower()

    # People
    entry["people"] = _parse_tags(row.get("people_tags", ""))
    entry["faces_count"] = _safe_int(row.get("faces_count", "0"))

    # Colors
    entry["colors"] = _parse_color_palette(row.get("color_palette", ""))

    # Image type
    entry["image_type"] = row.get("image_type", "natural_photo")

    # Quality
    entry["quality"] = _safe_int(row.get("quality_score", "0"))

    # Device
    entry["device"] = row.get("device_model", "")

    # Day number in trip
    entry["day_number"] = _safe_int(row.get("day_number", "0"))

    # Build searchable text blob
    search_parts = [
        row.get("image_name", ""),
        location,
        " ".join(entry["tags"]),
        " ".join(entry["species"]),
        " ".join(entry["people"]),
        entry["caption_text"],
        entry.get("month_name", ""),
        entry.get("weekday", ""),
        entry.get("time_of_day", ""),
        entry.get("season", ""),
        str(entry.get("year", "")),
    ]
    entry["_search"] = " ".join(search_parts).lower()

    return entry


def collect_trip_data(trip_folder: str) -> List[Dict[str, Any]]:
    """Collect all image entries from a trip's labels.csv."""
    memo_dir = os.path.join(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
    labels_path = os.path.join(memo_dir, "labels.csv")

    if not os.path.exists(labels_path):
        return []

    trip_name = os.path.basename(trip_folder)
    rows = read_csv_dict(labels_path)

    entries = []
    for row in rows:
        if not row.get("image_name"):
            continue
        entry = build_image_entry(row, trip_name, trip_folder)
        entries.append(entry)

    return entries


def build_facets(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build faceted search data from all entries."""
    years: Set[int] = set()
    months: Set[str] = set()
    locations: Counter = Counter()
    countries: Set[str] = set()
    people: Set[str] = set()
    tags: Counter = Counter()
    species: Counter = Counter()
    image_types: Set[str] = set()
    devices: Set[str] = set()
    trips: Set[str] = set()

    for e in entries:
        if e.get("year"):
            years.add(e["year"])
        if e.get("month_name"):
            months.add(e["month_name"])
        if e.get("location"):
            locations[e["location"]] += 1
        if e.get("country"):
            countries.add(e["country"])
        for p in e.get("people", []):
            people.add(p)
        for t in e.get("tags", []):
            tags[t] += 1
        for s in e.get("species", []):
            species[s] += 1
        if e.get("image_type"):
            image_types.add(e["image_type"])
        if e.get("device"):
            devices.add(e["device"])
        if e.get("trip"):
            trips.add(e["trip"])

    return {
        "years": sorted(years, reverse=True),
        "months": ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"],
        "locations": [loc for loc, _ in locations.most_common(50)],
        "countries": sorted(countries),
        "people": sorted(people),
        "top_tags": [tag for tag, _ in tags.most_common(100)],
        "top_species": [sp for sp, _ in species.most_common(50)],
        "image_types": sorted(image_types),
        "devices": sorted(devices),
        "trips": sorted(trips),
        "time_of_day": ["early_morning", "morning", "noon", "afternoon", "evening", "night", "late_night"],
        "seasons": ["spring", "summer", "autumn", "winter"],
    }


def build_search_index(trips_root: Optional[str] = None) -> str:
    """Build unified search index from all trips."""
    root = trips_root or CFG.DATA_ROOT

    if not os.path.isdir(root):
        raise FileNotFoundError(f"Trips root not found: {root}")

    logger.info(f"Scanning trips in: {root}")

    all_entries: List[Dict[str, Any]] = []
    trip_stats: Dict[str, int] = {}

    # Collect from all trips
    for entry in sorted(os.listdir(root)):
        trip_path = os.path.join(root, entry)
        if not os.path.isdir(trip_path):
            continue

        memo_dir = os.path.join(trip_path, CFG.MEMOGRAPH_FOLDER_NAME)
        if not os.path.isdir(memo_dir):
            continue

        entries = collect_trip_data(trip_path)
        if entries:
            all_entries.extend(entries)
            trip_stats[entry] = len(entries)
            logger.info(f"  {entry}: {len(entries)} images")

    # Build facets
    facets = build_facets(all_entries)

    # Build final index
    index = {
        "version": "1.0",
        "generated": datetime.now().isoformat(),
        "stats": {
            "total_images": len(all_entries),
            "total_trips": len(trip_stats),
            "unique_tags": len(facets["top_tags"]),
            "unique_species": len(facets["top_species"]),
            "unique_people": len(facets["people"]),
            "unique_locations": len(facets["locations"]),
        },
        "trip_counts": trip_stats,
        "facets": facets,
        "images": all_entries,
    }

    # Write index
    out_path = os.path.join(root, "search_index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    logger.info(f"Search index written: {out_path}")
    logger.info(f"Total: {len(all_entries)} images across {len(trip_stats)} trips")

    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build unified search index for all MemoGraph trips.")
    parser.add_argument("trips_root", nargs="?", default=CFG.DATA_ROOT,
                        help="Root folder containing trip directories")
    args = parser.parse_args()

    output = build_search_index(args.trips_root)
    print(f"Search index: {output}")
