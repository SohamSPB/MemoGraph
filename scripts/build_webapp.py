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
      gap: 16px;
      align-items: center;
      background: linear-gradient(120deg, rgba(56,189,248,0.15), rgba(34,211,238,0.10), rgba(56,189,248,0.05));
      backdrop-filter: blur(6px);
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      box-shadow: var(--shadow);
    }
    .brand {
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .trip-name {
      font-size: 0.85rem;
      color: var(--muted);
    }
    .back-btn {
      border: none;
      background: rgba(255,255,255,0.1);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 999px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: var(--transition);
    }
    .back-btn:hover { background: rgba(255,255,255,0.2); }
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
    .filters-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 24px 6px;
    }
    .filters-bar button {
      border: none;
      background: rgba(255,255,255,0.08);
      color: var(--text);
      padding: 6px 14px;
      border-radius: 999px;
      cursor: pointer;
      transition: var(--transition);
    }
    .filters-bar button:hover { background: rgba(255,255,255,0.2); }
    .filters-wrapper {
      padding: 0 24px 12px;
    }
    .filters-wrapper.collapsed {
      max-height: 0;
      overflow: hidden;
      padding-bottom: 0;
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-height: 96px;
      overflow-y: auto;
      padding-right: 4px;
    }
    .filters::-webkit-scrollbar { height: 6px; }
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
    .lightbox {
      position: fixed;
      inset: 0;
      background: rgba(5,8,18,0.92);
      display: flex;
      justify-content: center;
      align-items: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 200ms ease;
      z-index: 99;
    }
    .lightbox.show {
      opacity: 1;
      pointer-events: auto;
    }
    .lightbox-shell {
      width: min(1280px, 96vw);
      height: min(900px, 96vh);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .lightbox-content {
      width: 100%;
      flex: 1;
      background: var(--card);
      border-radius: 24px;
      padding: 24px;
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      position: relative;
      min-height: 60vh;
    }
    .lightbox-img-wrap {
      position: relative;
      border-radius: 18px;
      overflow: hidden;
      background: #050812;
    }
    .lightbox-img-wrap img {
      width: 100%;
      height: 60vh;
      object-fit: contain;
      background: #050812;
    }
    .lightbox-close {
      position: absolute;
      top: 16px;
      right: 16px;
      background: rgba(255,255,255,0.12);
      border: none;
      color: var(--text);
      padding: 8px 12px;
      border-radius: 999px;
      cursor: pointer;
    }
    .lightbox-nav {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: calc(100% - 32px);
      display: flex;
      justify-content: space-between;
      pointer-events: none;
    }
    .lightbox-nav button {
      pointer-events: auto;
      border: none;
      background: rgba(0,0,0,0.4);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 999px;
      cursor: pointer;
    }
    .lightbox-meta h3 {
      margin: 0 0 6px;
    }
    .lightbox-meta ul {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--muted);
      font-size: 0.95rem;
    }
    .filmstrip {
      width: 100%;
      background: rgba(5,8,18,0.9);
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.08);
      padding: 10px 16px;
      display: flex;
      gap: 12px;
      overflow-x: auto;
      align-items: center;
    }
    .filmstrip img {
      width: 100px;
      height: 70px;
      object-fit: cover;
      border-radius: 8px;
      cursor: pointer;
      opacity: 0.7;
      transition: opacity 150ms ease, transform 150ms ease;
    }
    .filmstrip img.active,
    .filmstrip img:hover {
      opacity: 1;
      transform: translateY(-2px);
    }
    @media (max-width: 1024px) {
      .main { grid-template-columns: 1fr; }
      .map-pane { height: 360px; position: relative; top: 0; }
      .lightbox-shell {
        width: min(640px, 96vw);
        height: min(850px, 96vh);
      }
      .lightbox-content {
        grid-template-columns: 1fr;
        max-height: 90vh;
      }
      .lightbox-img-wrap img { height: 45vh; }
      .filmstrip {
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <button class="back-btn" id="backBtn">← Trips</button>
      <div class="brand">
        <span>MemoGraph Browser</span>
        <span class="trip-name" id="tripName">Trip</span>
      </div>
      <label class="search">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="5"/><path d="M11 11l4 4"/></svg>
        <input id="search" type="text" placeholder="Search captions, tags, species, scenes..." />
      </label>
    </header>
    <div class="filters-bar">
      <button id="filterToggle">Hide Filters</button>
    </div>
    <div class="filters-wrapper" id="filtersWrapper">
      <div class="filters" id="filters"></div>
    </div>
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
    const TRIP_NAME = data.trip_name || "MemoGraph Trip";
    // - MemoGraph assets (thumbnails/css) live one level up from webapp/
    // - Original trip images live two levels up (trip root).
    const MEMO_BASE = "../";
    const TRIP_BASE = "../../";
    const MASTER_BASE = "../../../index.html";

    // Collect all images
    const images = [];
    (data.days || []).forEach(day => {
      (day.images || []).forEach(img => {
        images.push({
          ...img,
          day_number: day.day_number,
          date: day.date,
          _index: images.length
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
    const filtersWrapper = document.getElementById('filtersWrapper');
    const filterToggle = document.getElementById('filterToggle');
    const galleryEl = document.getElementById('gallery');
    const searchInput = document.getElementById('search');
    const tripNameEl = document.getElementById('tripName');
    const backBtn = document.getElementById('backBtn');

    const lightbox = document.getElementById('lightbox') || (function() {
      const div = document.createElement('div');
      div.className = 'lightbox';
      div.id = 'lightbox';
      div.innerHTML = `
        <div class="lightbox-shell">
          <div class="lightbox-content">
            <button class="lightbox-close" id="lightboxClose">Close ✕</button>
            <div class="lightbox-img-wrap">
              <img id="lightboxImage" src="" alt="">
              <div class="lightbox-nav">
                <button id="navPrev">◀</button>
                <button id="navNext">▶</button>
              </div>
            </div>
            <div class="lightbox-meta">
              <h3 id="lightboxTitle">Photo details</h3>
              <ul id="lightboxMeta"></ul>
            </div>
          </div>
          <div class="filmstrip" id="filmstrip"></div>
        </div>`;
      document.body.appendChild(div);
      return div;
    })();
    const lightboxImage = document.getElementById('lightboxImage');
    const lightboxTitle = document.getElementById('lightboxTitle');
    const lightboxMeta = document.getElementById('lightboxMeta');
    const filmstripEl = document.getElementById('filmstrip');
    const navPrev = document.getElementById('navPrev');
    const navNext = document.getElementById('navNext');
    const lightboxClose = document.getElementById('lightboxClose');

    let activeChips = new Set();
    let map;
    let markers = [];
    let filteredImages = images.slice();
    let currentFilteredIndex = 0;
    let filtersCollapsed = false;

    tripNameEl.textContent = TRIP_NAME;
    backBtn.onclick = () => { window.location.href = MASTER_BASE; };
    filterToggle.onclick = () => {
      filtersCollapsed = !filtersCollapsed;
      filtersWrapper.classList.toggle('collapsed', filtersCollapsed);
      filterToggle.textContent = filtersCollapsed ? 'Show Filters' : 'Hide Filters';
    };
    lightboxClose.onclick = () => lightbox.classList.remove('show');
    lightbox.onclick = (ev) => {
      if (ev.target === lightbox) lightbox.classList.remove('show');
    };
    navPrev.onclick = (ev) => { ev.stopPropagation(); stepLightbox(-1); };
    navNext.onclick = (ev) => { ev.stopPropagation(); stepLightbox(1); };

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
      filteredImages = result;

      galleryEl.innerHTML = '';
      if (!result.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = 'No photos match your filters.';
        galleryEl.appendChild(empty);
      } else {
        result.forEach((img, idx) => {
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
          card.onclick = () => openLightbox(idx);
          galleryEl.appendChild(card);
        });
      }

      renderMap(result);
      renderFilmstrip();
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

    function renderFilmstrip() {
      filmstripEl.innerHTML = '';
      filteredImages.forEach((img, idx) => {
        const thumb = document.createElement('img');
        thumb.src = img.thumbnail
          ? MEMO_BASE + img.thumbnail
          : TRIP_BASE + (img.local_path || img.image_name || '');
        thumb.classList.toggle('active', idx === currentFilteredIndex);
        thumb.onclick = (ev) => {
          ev.stopPropagation();
          openLightbox(idx);
        };
        filmstripEl.appendChild(thumb);
      });
    }

    function openLightbox(idx) {
      if (!filteredImages.length) return;
      currentFilteredIndex = (idx + filteredImages.length) % filteredImages.length;
      const img = filteredImages[currentFilteredIndex];
      const fullSrc = TRIP_BASE + (img.local_path || img.image_name || '');
      lightboxImage.src = fullSrc;
      lightboxTitle.textContent = img.caption_ai || img.caption || img.image_name;

      const metaEntries = [];
      if (img.location_full || img.location_short) {
        metaEntries.push(`<strong>Location:</strong> ${img.location_full || img.location_short}`);
      }
      if (img.time) {
        metaEntries.push(`<strong>Captured:</strong> ${img.time}`);
      }
      if (img.image_type) {
        metaEntries.push(`<strong>Type:</strong> ${img.image_type}`);
      }
      if (typeof img.faces_count !== "undefined") {
        metaEntries.push(`<strong>Faces:</strong> ${img.faces_count}`);
      }
      if (img.species_tags && img.species_tags.length) {
        metaEntries.push(`<strong>Species:</strong> ${img.species_tags.join(', ')}`);
      }
      if (img.detected_objects && img.detected_objects.length) {
        metaEntries.push(`<strong>Detected objects:</strong> ${img.detected_objects.join(', ')}`);
      }
      if (img.places_scenes && img.places_scenes.length) {
        metaEntries.push(`<strong>Scenes:</strong> ${img.places_scenes.join(', ')}`);
      }
      if (img.yolo_objects && img.yolo_objects.length) {
        metaEntries.push(`<strong>YOLO:</strong> ${img.yolo_objects.join(', ')}`);
      }
      if (img.gps_lat != null && img.gps_lon != null) {
        const link = `https://maps.google.com/?q=${img.gps_lat},${img.gps_lon}`;
        metaEntries.push(`<strong>Map:</strong> <a href="${link}" target="_blank">Open location</a>`);
      }
      lightboxMeta.innerHTML = metaEntries.map(entry => `<li>${entry}</li>`).join('') || '<li>No additional metadata</li>';
      lightbox.classList.add('show');
      renderFilmstrip();
    }

    function stepLightbox(delta) {
      if (!filteredImages.length) return;
      openLightbox(currentFilteredIndex + delta);
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
