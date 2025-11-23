#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_webapp.py

Generate a lightweight, client-side web app (single HTML) inside a trip's
MemoGraph folder to browse photos, filter/search, and view them on a map.

- Reads <trip>/MemoGraph/blog_context.json (run build_blog_context first).
- Writes <trip>/MemoGraph/webapp/index.html with inline CSS/JS and embedded data.
- Uses:
    - Gallery with search + filters (themes, faces/selfie/group, text).
    - Map (Leaflet) to show GPS-tagged photos (when lat/lon available).

Usage:
    python -m scripts.build_webapp data/trips/2025_Annapurna_Nepal
"""

import json
import os
from textwrap import dedent

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_image import create_thumbnail

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MemoGraph Browser</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css" />
  <style>
    :root {
      --bg: #0f172a;
      --card: #111827;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --accent-2: #22d3ee;
      --shadow: 0 10px 30px rgba(0,0,0,0.3);
      --radius: 14px;
      --transition: 180ms ease;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Inter", "Segoe UI", sans-serif;
      background: radial-gradient(circle at 20% 20%, rgba(56,189,248,0.08), transparent 25%),
                  radial-gradient(circle at 80% 0%, rgba(34,211,238,0.12), transparent 30%),
                  var(--bg);
      color: var(--text);
    }
    .app {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
    }
    header {
      padding: 16px 24px;
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      background: linear-gradient(120deg, rgba(56,189,248,0.15), rgba(34,211,238,0.10), rgba(56,189,248,0.05));
      backdrop-filter: blur(6px);
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      box-shadow: var(--shadow);
    }
    .brand { font-weight: 700; letter-spacing: 0.5px; }
    .search {
      flex: 1;
      display: flex;
      gap: 10px;
      align-items: center;
      max-width: 600px;
      background: rgba(255,255,255,0.06);
      border-radius: 999px;
      padding: 8px 14px;
      border: 1px solid rgba(255,255,255,0.08);
      transition: var(--transition);
    }
    .search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(56,189,248,0.25); }
    .search input {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 15px;
      outline: none;
    }
    .filters {
      padding: 12px 24px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      cursor: pointer;
      transition: var(--transition);
      font-size: 13px;
    }
    .chip.active {
      background: linear-gradient(120deg, var(--accent), var(--accent-2));
      color: #0b1222;
      border-color: transparent;
    }
    .chip:hover { border-color: rgba(255,255,255,0.3); }
    .main {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 12px;
      padding: 0 24px 24px;
    }
    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 12px;
      align-content: start;
    }
    .card {
      background: var(--card);
      border-radius: var(--radius);
      padding: 10px;
      border: 1px solid rgba(255,255,255,0.05);
      box-shadow: var(--shadow);
      transition: var(--transition);
      transform: translateY(0);
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: rgba(56,189,248,0.4);
      box-shadow: 0 12px 40px rgba(0,0,0,0.45);
    }
    .thumb {
      width: 100%;
      border-radius: 12px;
      overflow: hidden;
      background: #0a0f1d;
      aspect-ratio: 4/3;
      display: grid;
      place-items: center;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform var(--transition);
    }
    .card:hover .thumb img { transform: scale(1.02); }
    .title { font-weight: 700; margin: 8px 0 4px; }
    .meta { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .tags { display: flex; flex-wrap: wrap; gap: 6px; }
    .tag {
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--text);
    }
    .map-pane {
      background: var(--card);
      border-radius: var(--radius);
      border: 1px solid rgba(255,255,255,0.05);
      box-shadow: var(--shadow);
      position: sticky;
      top: 90px;
      height: calc(100vh - 140px);
      overflow: hidden;
    }
    #map { width: 100%; height: 100%; }
    .empty-state {
      grid-column: 1 / -1;
      text-align: center;
      color: var(--muted);
      padding: 40px 0;
    }
    @media (max-width: 1024px) {
      .main { grid-template-columns: 1fr; }
      .map-pane { height: 360px; position: relative; top: 0; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">MemoGraph Browser</div>
      <label class="search">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="5"/><path d="M11 11l4 4"/></svg>
        <input id="search" type="text" placeholder="Search captions, tags, species, scenes..." />
      </label>
    </header>
    <div class="filters" id="filters"></div>
    <div class="main">
      <div class="gallery" id="gallery"></div>
      <div class="map-pane"><div id="map"></div></div>
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <script>
    // Embedded data (blog_context)
    const data = __DATA_PLACEHOLDER__;
    // Paths:
    // - MemoGraph assets (thumbnails/css) live one level up from webapp/
    // - Original trip images live two levels up (trip root).
    const MEMO_BASE = "../";
    const TRIP_BASE = "../../";

    // Collect all images
    const images = [];
    (data.days || []).forEach(day => {
      (day.images || []).forEach(img => {
        images.push({
          ...img,
          day_number: day.day_number,
          date: day.date,
        });
      });
    });

    // Derive a set of theme chips (from day themes + detected/yolo/places)
    const chipSet = new Set(["mountains","water","towns","temples","markets","food","stays","astro","wildlife","selfie","group"]);
    images.forEach(img => {
      (img.detected_objects || []).forEach(t => chipSet.add(t.toLowerCase()));
      (img.yolo_objects || []).forEach(t => chipSet.add(t.toLowerCase()));
      (img.places_scenes || []).forEach(t => {
        const name = t.split("(")[0].trim().toLowerCase();
        chipSet.add(name);
      });
    });
    const chips = Array.from(chipSet).filter(Boolean).sort();

    const filtersEl = document.getElementById('filters');
    const galleryEl = document.getElementById('gallery');
    const searchInput = document.getElementById('search');

    let activeChips = new Set();
    let map;
    let markers = [];

    function renderChips() {
      filtersEl.innerHTML = '';
      chips.forEach(ch => {
        const btn = document.createElement('button');
        btn.className = 'chip';
        btn.textContent = ch;
        btn.onclick = () => {
          if (activeChips.has(ch)) activeChips.delete(ch); else activeChips.add(ch);
          btn.classList.toggle('active');
          render();
        };
        filtersEl.appendChild(btn);
      });
    }

    function matchesFilters(img, term) {
      // text match against multiple fields
      const haystack = [
        img.caption || '',
        img.caption_ai || '',
        (img.species_tags || []).join(' '),
        (img.detected_objects || []).join(' '),
        (img.yolo_objects || []).join(' '),
        (img.places_scenes || []).join(' '),
        img.location_full || '',
        img.location_short || ''
      ].join(' ').toLowerCase();
      if (term && !haystack.includes(term)) return false;

      // chip filters
      if (activeChips.size === 0) return true;
      const tags = new Set();
      (img.detected_objects || []).forEach(t => tags.add(t.toLowerCase()));
      (img.yolo_objects || []).forEach(t => tags.add(t.toLowerCase()));
      (img.places_scenes || []).forEach(t => tags.add(t.split('(')[0].trim().toLowerCase()));
      (img.species_tags || []).forEach(t => tags.add(t.toLowerCase()));
      // faces-derived tags
      const fc = Number(img.faces_count || 0);
      if (fc === 1) tags.add('selfie');
      if (fc >= 2) tags.add('group');
      // day themes could also be added if needed

      // require that each active chip is present in tags
      for (const ch of activeChips) {
        if (!tags.has(ch)) return false;
      }
      return true;
    }

    function render() {
      const term = searchInput.value.trim().toLowerCase();
      const result = images.filter(img => matchesFilters(img, term));

      galleryEl.innerHTML = '';
      if (!result.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = 'No photos match your filters.';
        galleryEl.appendChild(empty);
      } else {
        result.forEach(img => {
          const card = document.createElement('div');
          card.className = 'card';
          const thumb = document.createElement('div');
          thumb.className = 'thumb';
          const imgTag = document.createElement('img');
          imgTag.loading = 'lazy';
          // Prefer thumbnails; fallback to original image path.
          const thumbSrc = img.thumbnail
            ? MEMO_BASE + img.thumbnail
            : TRIP_BASE + (img.local_path || img.image_name || '');
          imgTag.src = thumbSrc;
          imgTag.alt = img.caption_ai || img.caption || img.image_name;
          thumb.appendChild(imgTag);
          card.appendChild(thumb);

          const title = document.createElement('div');
          title.className = 'title';
          title.textContent = img.caption_ai || img.caption || img.image_name;
          card.appendChild(title);

          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = `Day ${img.day_number} · ${img.date} · ${img.location_short || '—'}`;
          card.appendChild(meta);

          const tagsWrap = document.createElement('div');
          tagsWrap.className = 'tags';
          const pushTag = (t) => {
            const span = document.createElement('span');
            span.className = 'tag';
            span.textContent = t;
            tagsWrap.appendChild(span);
          };
          (img.species_tags || []).slice(0,3).forEach(pushTag);
          (img.detected_objects || []).slice(0,2).forEach(pushTag);
          (img.places_scenes || []).slice(0,1).forEach(t => pushTag(t.split('(')[0].trim()));
          const fc = Number(img.faces_count || 0);
          if (fc === 1) pushTag('selfie');
          if (fc >= 2) pushTag('group');

          card.appendChild(tagsWrap);
          galleryEl.appendChild(card);
        });
      }

      renderMap(result);
    }

    function initMap() {
      map = L.map('map', { zoomControl: true });
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
      }).addTo(map);
      map.setView([20,0], 2);
    }

    function renderMap(list) {
      if (!map) initMap();
      // Clear markers
      markers.forEach(m => m.remove());
      markers = [];

      const coords = [];
      list.forEach(img => {
        if (img.gps_lat != null && img.gps_lon != null) {
          const marker = L.marker([img.gps_lat, img.gps_lon]).addTo(map);
          const popupImg = img.thumbnail
            ? MEMO_BASE + img.thumbnail
            : TRIP_BASE + (img.local_path || img.image_name || '');
          marker.bindPopup(
            `<div style="font-weight:600;">${img.caption_ai || img.caption || img.image_name}</div>
             <div style="color:#999;font-size:12px;margin:4px 0;">Day ${img.day_number} · ${img.location_short || ''}</div>
             <img src="${popupImg}" alt="" style="width:180px;max-height:140px;object-fit:cover;border-radius:8px;">`
          );
          markers.push(marker);
          coords.push([img.gps_lat, img.gps_lon]);
        }
      });
      if (coords.length) {
        const bounds = L.latLngBounds(coords);
        map.fitBounds(bounds.pad(0.25));
      }
    }

    renderChips();
    searchInput.addEventListener('input', render);
    render();
  </script>
</body>
</html>
"""


def _sanitize_thumbnail_name(rel_path: str) -> str:
	name_without_ext = os.path.splitext(rel_path)[0]
	safe_name = name_without_ext.replace("\\", "_").replace("/", "_")
	return f"{safe_name}.jpg"


def _attach_thumbnails(trip_folder: str, memo_dir: str, data: dict) -> int:
	"""Generate thumbnails (if needed) and attach their relative paths to image dicts."""
	thumb_subdir = getattr(CFG, "THUMBNAIL_SUBDIR", "thumbnails")
	thumb_dir = os.path.join(memo_dir, thumb_subdir)
	os.makedirs(thumb_dir, exist_ok=True)

	created = 0
	for day in data.get("days", []):
		for image in day.get("images", []):
			rel_path = image.get("local_path") or image.get("image_name")
			if not rel_path:
				continue

			src_path = os.path.join(trip_folder, rel_path)
			if not os.path.exists(src_path):
				continue

			thumb_name = _sanitize_thumbnail_name(rel_path)
			dest_path = os.path.join(thumb_dir, thumb_name)
			needs_build = True

			if os.path.exists(dest_path):
				try:
					needs_build = os.path.getmtime(dest_path) < os.path.getmtime(src_path)
				except OSError:
					needs_build = True

			if needs_build:
				if create_thumbnail(src_path, dest_path, max_size=getattr(CFG, "THUMBNAIL_MAX_SIZE", 320)):
					created += 1
				else:
					# Skip attaching if generation failed.
					continue

			if os.path.exists(dest_path):
				image["thumbnail"] = os.path.join(thumb_subdir, thumb_name).replace("\\", "/")

	return created


def build_webapp(trip_folder: str) -> str:
	memo_dir, _ = ensure_memograph_folder(trip_folder)
	context_path = os.path.join(memo_dir, "blog_context.json")
	if not os.path.exists(context_path):
		raise FileNotFoundError(f"blog_context.json not found at {context_path}. Run build_blog_context first.")

	with open(context_path, "r", encoding="utf-8") as f:
		data = json.load(f)

	_attach_thumbnails(trip_folder, memo_dir, data)

	html = TEMPLATE.replace("__DATA_PLACEHOLDER__", json.dumps(data))

	out_dir = os.path.join(memo_dir, "webapp")
	os.makedirs(out_dir, exist_ok=True)
	out_path = os.path.join(out_dir, "index.html")
	with open(out_path, "w", encoding="utf-8") as f:
		f.write(html)

	return out_path


if __name__ == "__main__":
	import argparse

	p = argparse.ArgumentParser(description="Generate a static webapp HTML to browse a MemoGraph trip.")
	p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
	args = p.parse_args()

	out = build_webapp(args.trip_folder)
	print(f"Web app written to: {out}")
