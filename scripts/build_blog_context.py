#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_blog_context.py

Builds a richer, structured JSON description of a trip that can be fed into
an external text-generation model (LLM) to create natural, narrative blogs.

It reads MemoGraph's labels.csv and derives, for each day:
- Start/end times and locations (shortened for readability).
- Per-day themes (mountains, water, towns, temples/monuments, markets,
  food, stays, astro, wildlife, roads/trails).
- Simple "activities" strings based on those themes.
- Wildlife broken down into animals vs plants.
- A per-image summary (time, location, captions, species, detected objects, etc.).

Output:
- <trip_folder>/MemoGraph/blog_context.json
"""

import os
import json
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Any

from memograph_config import ensure_memograph_folder
from scripts.utils.utils_io import read_csv_dict


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


def _shorten_location(loc: str) -> str:
    """Shorten a long location_inferred string to something blog-friendly."""
    loc = (loc or "").strip()
    if not loc:
        return "an unknown place"
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if not parts:
        return loc
    for p in parts:
        if any(k in p.lower() for k in ("highway", "road", "pass")):
            return p
    return min(parts, key=len)


def _classify_row_themes(row: Dict[str, Any]) -> List[str]:
    """Assign coarse thematic tags to a row based on labels/captions."""
    text = " ".join(
        [
            str(row.get("detected_objects") or ""),
            str(row.get("species_tags") or ""),
            str(row.get("caption") or ""),
            str(row.get("caption_ai") or ""),
            str(row.get("image_type") or ""),
        ]
    ).lower()

    tags: List[str] = []

    if str(row.get("faces_detected", "")).strip() == "1":
        tags.append("people")
    if any(k in text for k in ("mountain", "valley", "ridge", "pass", "peak", "himalaya")):
        tags.append("mountains")
    if any(k in text for k in ("river", "lake", "waterfall", "pool", "sea", "ocean")):
        tags.append("water")
    if any(k in text for k in ("monument", "temple", "monastery", "building", "cityscape", "village", "street")):
        tags.append("towns")
    if any(k in text for k in ("galaxy", "nebula", "milky way", "night sky", "star cluster", "astrophotography")):
        tags.append("astro")
    if any(k in text for k in ("bird", "yak", "horse", "dog", "cat", "animal", "elephant", "cow")):
        tags.append("wildlife")
    if any(
        k in text
        for k in (
            "plate of food",
            "food dish",
            "thali",
            "curry",
            "meal",
            "breakfast",
            "dinner",
            "lunch",
            "snack",
            "street food",
            "chai",
            "tea",
            "coffee",
            "restaurant",
            "cafe",
            "dessert",
        )
    ):
        tags.append("food")
    if any(
        k in text
        for k in (
            "temple",
            "monastery",
            "stupa",
            "mosque",
            "church",
            "palace",
            "fort",
            "castle",
            "shrine",
            "historical gate",
            "gate",
            "arch",
        )
    ):
        tags.append("temples_palaces")
    if any(
        k in text
        for k in (
            "market",
            "bazaar",
            "street market",
            "shop",
            "stall",
            "souvenir",
            "shopping street",
            "street vendor",
        )
    ):
        tags.append("markets")
    if any(
        k in text
        for k in ("hotel room", "guesthouse", "homestay", "hostel", "resort", "campsite", "tent", "campfire")
    ):
        tags.append("stays")
    if any(
        k in text
        for k in ("mountain road", "highway", "road", "trail", "path", "steps", "staircase", "bridge", "suspension bridge")
    ):
        tags.append("roads_trails")

    return tags


def _split_species(species: List[str]) -> Dict[str, List[str]]:
    """Split species-like strings into animals vs plants based on simple keywords."""
    animals: List[str] = []
    plants: List[str] = []

    animal_keywords = ("yak", "horse", "dog", "cat", "bird", "elephant", "cow")
    plant_keywords = ("tulsi", "ficus", "fern", "tree", "flower", "plant")

    for name in species:
        raw = (name or "").strip()
        if not raw:
            continue
        low = raw.lower()
        if any(k in low for k in animal_keywords):
            animals.append(raw)
        elif any(k in low for k in plant_keywords):
            plants.append(raw)

    return {"animals": sorted(set(animals)), "plants": sorted(set(plants))}


def _build_day_context(day_rows: List[Dict[str, Any]], date_str: str, day_number: int) -> Dict[str, Any]:
    """Build a structured context dict for a single day."""
    # Parse datetimes for ordering within the day.
    for r in day_rows:
        r["_dt"] = _parse_datetime(r.get("datetime_original", ""))
    day_rows = [r for r in day_rows if r["_dt"] is not None]
    if not day_rows:
        return {}

    day_rows.sort(key=lambda r: r["_dt"])
    first = day_rows[0]
    last = day_rows[-1]

    start_time = first["_dt"].strftime("%Y-%m-%d %H:%M:%S")
    end_time = last["_dt"].strftime("%Y-%m-%d %H:%M:%S")

    start_loc_full = first.get("location_inferred", "")
    end_loc_full = last.get("location_inferred", start_loc_full)
    start_location_short = _shorten_location(start_loc_full)
    end_location_short = _shorten_location(end_loc_full)

    # All unique locations (short + full for reference)
    all_locations_full = sorted(
        {str(r.get("location_inferred") or "").strip() for r in day_rows if r.get("location_inferred")}
    )
    all_locations_short = sorted({_shorten_location(loc) for loc in all_locations_full if loc})

    # Theme counts and people count
    theme_counts: Counter = Counter()
    for r in day_rows:
        for t in _classify_row_themes(r):
            theme_counts[t] += 1

    themes = sorted(t for t, count in theme_counts.items() if count > 0)

    # Derive simple "activities" strings from themes.
    activities: List[str] = []
    if theme_counts.get("mountains", 0) and theme_counts.get("roads_trails", 0):
        activities.append("travelled along mountain roads and passes")
    elif theme_counts.get("mountains", 0):
        activities.append("spent time around mountain views and valleys")
    if theme_counts.get("water", 0):
        activities.append("spent time near rivers, lakes, or pools")
    if theme_counts.get("temples_palaces", 0):
        activities.append("visited temples, monasteries, or old monuments")
    if theme_counts.get("markets", 0):
        activities.append("walked through markets or bazaar-like streets")
    if theme_counts.get("food", 0):
        activities.append("took breaks around food, tea, or cafes")
    if theme_counts.get("stays", 0):
        activities.append("stayed in simple hotels, guesthouses, or homestays")
    if theme_counts.get("astro", 0):
        activities.append("spent time on night-sky or astro photography")
    if theme_counts.get("wildlife", 0):
        activities.append("noticed animals or birds around the route")

    # Collect species across all rows for this day.
    all_species_raw: List[str] = []
    for r in day_rows:
        raw = str(r.get("species_tags") or "").strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        all_species_raw.extend(parts)
    wildlife = _split_species(all_species_raw)

    # Per-image records
    images_ctx: List[Dict[str, Any]] = []
    for r in day_rows:
        detected_raw = str(r.get("detected_objects") or "")
        detected = [p.strip() for p in detected_raw.split(";") if p.strip()]

        img_species_raw = str(r.get("species_tags") or "").strip()
        img_species = [p.strip() for p in img_species_raw.split(",") if p.strip()]

        images_ctx.append(
            {
                "image_name": r.get("image_name"),
                "time": r["_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "location_full": r.get("location_inferred", ""),
                "location_short": _shorten_location(r.get("location_inferred", "")),
                "caption": r.get("caption"),
                "caption_ai": r.get("caption_ai"),
                "species_tags": img_species,
                "detected_objects": detected,
                "image_type": r.get("image_type"),
                "faces_detected": r.get("faces_detected"),
            }
        )

    day_ctx: Dict[str, Any] = {
        "date": date_str,
        "day_number": day_number,
        "start_time": start_time,
        "end_time": end_time,
        "start_location_full": start_loc_full,
        "end_location_full": end_loc_full,
        "start_location_short": start_location_short,
        "end_location_short": end_location_short,
        "locations_full": all_locations_full,
        "locations_short": all_locations_short,
        "themes": themes,
        "theme_counts": dict(theme_counts),
        "activities": activities,
        "wildlife_animals": wildlife["animals"],
        "wildlife_plants": wildlife["plants"],
        "images": images_ctx,
    }
    return day_ctx


def build_blog_context(trip_folder: str) -> str:
    """Main entrypoint: build blog_context.json for the given trip."""
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    csv_path = os.path.join(memo_dir, "labels.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"labels.csv not found at {csv_path}")

    rows = read_csv_dict(csv_path)
    if not rows:
        raise RuntimeError("labels.csv is empty.")

    # Group rows by date.
    per_day: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        dt = _parse_datetime(r.get("datetime_original", ""))
        if not dt:
            continue
        r["_dt"] = dt
        date_key = dt.strftime("%Y-%m-%d")
        per_day[date_key].append(r)

    if not per_day:
        raise RuntimeError("No valid datetime_original values; cannot build per-day context.")

    days_out: List[Dict[str, Any]] = []
    for idx, date_key in enumerate(sorted(per_day.keys()), start=1):
        ctx = _build_day_context(per_day[date_key], date_key, idx)
        if ctx:
            days_out.append(ctx)

    trip_name = os.path.basename(os.path.normpath(trip_folder))
    context = {"trip_name": trip_name, "days": days_out}

    out_path = os.path.join(memo_dir, "blog_context.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    return out_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Build structured blog_context.json for a MemoGraph trip.")
    p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
    args = p.parse_args()

    out = build_blog_context(args.trip_folder)
    print(f"Blog context written to: {out}")

