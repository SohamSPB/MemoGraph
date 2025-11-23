#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_trip_index.py

Scan data/trips for MemoGraph outputs and build a master index page that
links to each trip's static web app while showing representative thumbnails
and metadata.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import memograph_config as CFG

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MemoGraph Trips</title>
  <style>
    :root {{
      --bg: #050812;
      --card: #0c1220;
      --card-hover: #141c2e;
      --text: #edf0ff;
      --muted: #8b92a9;
      --accent: #5eead4;
      --chip-bg: rgba(255,255,255,0.08);
    }}
    * {{
      box-sizing: border-box;
      font-family: "Inter", "Segoe UI", sans-serif;
    }}
    body {{
      margin: 0;
      background: radial-gradient(circle at 10% 20%, rgba(94,234,212,0.08), transparent 30%),
                  radial-gradient(circle at 80% 0%, rgba(59,130,246,0.10), transparent 35%),
                  var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}
    header {{
      padding: 32px 6vw 8px;
    }}
    header h1 {{
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.6rem);
    }}
    header p {{
      margin: 6px 0 0;
      color: var(--muted);
    }}
    .grid {{
      padding: 16px 6vw 48px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 20px;
    }}
    .trip-card {{
      background: var(--card);
      border-radius: 20px;
      padding: 16px;
      text-decoration: none;
      color: inherit;
      border: 1px solid rgba(255,255,255,0.05);
      box-shadow: 0 20px 40px rgba(0,0,0,0.35);
      display: flex;
      flex-direction: column;
      gap: 16px;
      transition: transform 180ms ease, background 200ms ease;
    }}
    .trip-card:hover {{
      transform: translateY(-6px);
      background: var(--card-hover);
    }}
    .thumb-stack {{
      position: relative;
      height: 180px;
      border-radius: 16px;
      overflow: hidden;
      background: rgba(255,255,255,0.04);
    }}
    .thumb-stack img {{
      position: absolute;
      width: 70%;
      height: 70%;
      object-fit: cover;
      border-radius: 16px;
      box-shadow: 0 10px 20px rgba(0,0,0,0.35);
      transition: transform 200ms ease;
    }}
    .thumb-stack img:nth-child(1) {{ top: 12px; left: 12px; }}
    .thumb-stack img:nth-child(2) {{ top: 28px; right: 12px; }}
    .thumb-stack img:nth-child(3) {{ bottom: 12px; left: 28px; }}
    .trip-card:hover .thumb-stack img {{
      transform: scale(1.02);
    }}
    .trip-title {{
      margin: 0;
      font-size: 1.2rem;
    }}
    .trip-dates {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .trip-meta {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .chips {{
      margin-top: 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .chip {{
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--chip-bg);
      color: var(--text);
      font-size: 0.8rem;
    }}
    @media (max-width: 640px) {{
      .grid {{
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>MemoGraph Trips</h1>
    <p>Browse every processed trip and dive into its interactive gallery.</p>
  </header>
  <section class="grid">
    {cards}
  </section>
</body>
</html>
"""

CARD_TEMPLATE = """<a class="trip-card" href="{link}">
  <div class="thumb-stack">
    {thumbs}
  </div>
  <div>
    <h2 class="trip-title">{title}</h2>
    <p class="trip-dates">{date_range}</p>
    <p class="trip-meta">{day_count} day{day_suffix} • {photo_count} photo{photo_suffix}{location}</p>
    <div class="chips">
      {chips}
    </div>
  </div>
</a>"""


def _format_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return date_str


def _ensure_posix(path: str) -> str:
    return path.replace("\\", "/")


def _gather_thumbnails(trip_dir: str, memo_dir: str, limit: int = 3) -> List[str]:
    thumb_dir = os.path.join(memo_dir, getattr(CFG, "THUMBNAIL_SUBDIR", "thumbnails"))
    rel_base = os.path.basename(trip_dir)
    thumbs: List[str] = []
    if os.path.isdir(thumb_dir):
        files = sorted(
            [f for f in os.listdir(thumb_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        )
        for name in files[:limit]:
            rel = os.path.join(rel_base, CFG.MEMOGRAPH_FOLDER_NAME, getattr(CFG, "THUMBNAIL_SUBDIR", "thumbnails"), name)
            thumbs.append(_ensure_posix(rel))
    return thumbs


def _fallback_images(trip_dir: str, days: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    rel_base = os.path.basename(trip_dir)
    images: List[str] = []
    for day in days:
        for img in day.get("images", []):
            local = img.get("local_path") or img.get("image_name")
            if local:
                images.append(_ensure_posix(os.path.join(rel_base, local)))
                if len(images) >= limit:
                    return images
    return images


def _render_thumb_stack(srcs: List[str]) -> str:
    if not srcs:
        return '<div style="width:100%;height:100%;background:rgba(255,255,255,0.05);"></div>'
    imgs = []
    for src in srcs:
        imgs.append(f'<img src="{src}" alt="">')
    return "".join(imgs)


def _collect_trip_metadata(trip_dir: str) -> Dict[str, Any] | None:
    memo_dir = os.path.join(trip_dir, CFG.MEMOGRAPH_FOLDER_NAME)
    context_path = os.path.join(memo_dir, "blog_context.json")
    if not os.path.exists(context_path):
        return None

    with open(context_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    days: List[Dict[str, Any]] = data.get("days", [])
    if not days:
        return None

    day_count = len(days)
    photo_count = sum(len(day.get("images", [])) for day in days)
    start_date = _format_date(days[0].get("date", "Unknown"))
    end_date = _format_date(days[-1].get("date", "Unknown"))
    date_range = start_date if start_date == end_date else f"{start_date} → {end_date}"

    themes = Counter()
    species = Counter()
    for day in days:
        themes.update(day.get("themes", []))
        species.update(day.get("wildlife_animals", []))
        species.update(day.get("wildlife_plants", []))

    top_themes = [theme for theme, _ in themes.most_common(3)]
    top_species = [sp for sp, _ in species.most_common(2)]

    thumbs = _gather_thumbnails(trip_dir, memo_dir)
    if not thumbs:
        thumbs = _fallback_images(trip_dir, days)

    location = days[0].get("start_location_short") or ""
    location_text = f" • {location}" if location else ""

    return {
        "title": data.get("trip_name") or os.path.basename(trip_dir),
        "date_range": date_range,
        "day_count": day_count,
        "photo_count": photo_count,
        "thumbs": thumbs,
        "themes": top_themes,
        "species": top_species,
        "link": _ensure_posix(os.path.join(os.path.basename(trip_dir), CFG.MEMOGRAPH_FOLDER_NAME, "webapp", "index.html")),
        "location": location_text,
    }


def build_trip_index(trips_root: str | None = None) -> str:
    root = trips_root or CFG.DATA_ROOT
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Trips root not found: {root}")

    cards_html: List[str] = []
    for entry in sorted(os.listdir(root)):
        trip_path = os.path.join(root, entry)
        if not os.path.isdir(trip_path):
            continue
        meta = _collect_trip_metadata(trip_path)
        if not meta:
            continue

        chips = meta["themes"] + meta["species"]
        chips_html = "".join(f'<span class="chip">{chip}</span>' for chip in chips)
        thumbs_html = _render_thumb_stack(meta["thumbs"])
        card = CARD_TEMPLATE.format(
            link=meta["link"],
            thumbs=thumbs_html,
            title=meta["title"],
            date_range=meta["date_range"],
            day_count=meta["day_count"],
            day_suffix="s" if meta["day_count"] != 1 else "",
            photo_count=meta["photo_count"],
            photo_suffix="s" if meta["photo_count"] != 1 else "",
            location=meta["location"],
            chips=chips_html or '<span class="chip">MemoGraph</span>',
        )
        cards_html.append(card)

    html = HTML_TEMPLATE.format(cards="\n    ".join(cards_html) if cards_html else "<p>No trips processed yet.</p>")
    out_path = os.path.join(root, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a master index page for all MemoGraph trips.")
    parser.add_argument("trips_root", nargs="?", default=CFG.DATA_ROOT, help="Root folder containing trip directories (default: data/trips)")
    args = parser.parse_args()
    output = build_trip_index(args.trips_root)
    print(f"Trip index written to: {output}")
