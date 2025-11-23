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
      flex-wrap: wrap;
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
    .preset-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 0 24px 10px;
      align-items: center;
      color: var(--muted);
      font-size: 0.9rem;
    }
    .preset-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .preset-buttons button {
      border: none;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(94,234,212,0.15);
      color: var(--text);
      cursor: pointer;
      transition: transform 150ms ease, background 150ms ease;
    }
    .preset-buttons button:hover { transform: translateY(-1px); background: rgba(94,234,212,0.3); }
    .custom-presets {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .custom-presets select {
      background: rgba(255,255,255,0.05);
      color: var(--text);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 8px;
      padding: 6px 10px;
      min-width: 160px;
    }
    .custom-presets button {
      border: none;
      background: rgba(37,99,235,0.3);
      color: var(--text);
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 150ms ease;
    }
    .custom-presets button:hover { background: rgba(37,99,235,0.5); }
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
      transition: background 150ms ease, color 150ms ease, transform 150ms ease;
      font-size: 13px;
      position: relative;
      overflow: hidden;
    }
    .chip.active {
      background: linear-gradient(120deg, var(--accent), var(--accent-2));
      color: #0b1222;
      border-color: transparent;
    }
    .chip:hover { border-color: rgba(255,255,255,0.3); }
    .chip:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
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
      transition: transform 180ms ease, box-shadow 220ms ease, border 180ms ease;
      transform: translateY(0);
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: rgba(56,189,248,0.4);
      box-shadow: 0 18px 45px rgba(0,0,0,0.5);
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
    .lightbox-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 10px 0;
    }
    .lightbox-actions button {
      border: none;
      background: rgba(56,189,248,0.2);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 999px;
      cursor: pointer;
    }
    .lightbox-actions button:hover { background: rgba(56,189,248,0.35); }
    .lightbox-map {
      width: 100%;
      height: 150px;
      border-radius: 16px;
      overflow: hidden;
      margin-top: 8px;
      display: none;
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
      width: 108px;
      height: 72px;
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
    .cluster-icon {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: rgba(56,189,248,0.8);
      color: #031225;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid rgba(255,255,255,0.8);
      font-weight: 600;
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
    <div class="preset-toolbar">
      <div style="min-width:120px;">Quick filters:</div>
      <div class="preset-buttons" id="presetButtons"></div>
      <div class="custom-presets">
        <select id="customPresetSelect"></select>
        <button id="applyPresetBtn">Apply</button>
        <button id="savePresetBtn">Save current</button>
        <button id="deletePresetBtn">Delete</button>
      </div>
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
    const presetButtonsEl = document.getElementById('presetButtons');
    const customPresetSelect = document.getElementById('customPresetSelect');
    const applyPresetBtn = document.getElementById('applyPresetBtn');
    const savePresetBtn = document.getElementById('savePresetBtn');
    const deletePresetBtn = document.getElementById('deletePresetBtn');

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
              <div class="lightbox-actions">
                <button id="copyDetailsBtn">Copy details</button>
                <button id="openOriginalBtn">Open photo</button>
              </div>
              <div class="lightbox-map" id="lightboxMap"></div>
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
    const lightboxMapEl = document.getElementById('lightboxMap');
    const copyDetailsBtn = document.getElementById('copyDetailsBtn');
    const openOriginalBtn = document.getElementById('openOriginalBtn');

    const PRESET_DEFS = [
      { id: "birds", label: "Birds", tokens: ["birds"] },
      { id: "landscapes", label: "Landscapes", tokens: ["landscape"] },
      { id: "astro", label: "Astro", tokens: ["astro", "galaxy"] },
      { id: "people", label: "People", tokens: ["selfie", "group"] }
    ];
    const STORAGE_KEY = "memograph_filters_v1";
    const storedPresets = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    let customPresets = storedPresets[TRIP_NAME] || [];

    let activeChips = new Set();
    let map;
    let markers = [];
    let filteredImages = images.slice();
    let currentFilteredIndex = 0;
    let filtersCollapsed = false;
    let lightboxVisible = false;
    let lightboxMapInstance = null;
    let lightboxMapMarker = null;
    let latestDetailText = "";
    let currentFullSrc = "";

    tripNameEl.textContent = TRIP_NAME;
    backBtn.onclick = () => { window.location.href = MASTER_BASE; };
    filterToggle.onclick = () => {
      filtersCollapsed = !filtersCollapsed;
      filtersWrapper.classList.toggle('collapsed', filtersCollapsed);
      filterToggle.textContent = filtersCollapsed ? 'Show Filters' : 'Hide Filters';
    };
    const closeLightbox = () => {
      lightbox.classList.remove('show');
      lightboxVisible = false;
    };
    lightboxClose.onclick = closeLightbox;
    lightbox.onclick = (ev) => {
      if (ev.target === lightbox) closeLightbox();
    };
    navPrev.onclick = (ev) => { ev.stopPropagation(); stepLightbox(-1); };
    navNext.onclick = (ev) => { ev.stopPropagation(); stepLightbox(1); };
    document.addEventListener('keydown', (ev) => {
      if (!lightboxVisible) return;
      if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        stepLightbox(-1);
      } else if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        stepLightbox(1);
      } else if (ev.key === 'Escape') {
        ev.preventDefault();
        closeLightbox();
      }
    });

    copyDetailsBtn.onclick = async () => {
      if (!latestDetailText) return;
      try {
        await navigator.clipboard.writeText(latestDetailText);
      } catch (err) {
        console.warn("Clipboard write failed", err);
      }
    };

    openOriginalBtn.onclick = () => {
      if (!currentFullSrc) return;
      window.open(currentFullSrc, "_blank");
    };

    function updateMiniMap(lat, lon) {
      if (!lightboxMapEl) return;
      if (lat == null || lon == null) {
        lightboxMapEl.style.display = "none";
        if (lightboxMapInstance) {
          lightboxMapInstance.remove();
          lightboxMapInstance = null;
          lightboxMapMarker = null;
        }
        return;
      }
      lightboxMapEl.style.display = "block";
      if (!lightboxMapInstance) {
        lightboxMapInstance = L.map(lightboxMapEl, { zoomControl: false, attributionControl: false });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19
        }).addTo(lightboxMapInstance);
      }
      lightboxMapInstance.setView([lat, lon], 10);
      if (lightboxMapMarker) {
        lightboxMapMarker.setLatLng([lat, lon]);
      } else {
        lightboxMapMarker = L.circleMarker([lat, lon], { radius: 6, color: "#5eead4", fillOpacity: 0.9 }).addTo(lightboxMapInstance);
      }
    }

    function renderChips() {
      filtersEl.innerHTML = '';
      chips.forEach(ch => {
        const btn = document.createElement('button');
        btn.className = 'chip';
        btn.textContent = ch;
        if (activeChips.has(ch)) btn.classList.add('active');
        btn.onclick = () => {
          if (activeChips.has(ch)) activeChips.delete(ch);
          else activeChips.add(ch);
          renderChips();
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

    function clusterImagesForMap(list) {
      const clusterMap = new Map();
      list.forEach(img => {
        if (img.gps_lat == null || img.gps_lon == null) return;
        const key = `${img.gps_lat.toFixed(2)}|${img.gps_lon.toFixed(2)}`;
        if (!clusterMap.has(key)) {
          clusterMap.set(key, { lat: img.gps_lat, lon: img.gps_lon, items: [] });
        }
        clusterMap.get(key).items.push(img);
      });
      return Array.from(clusterMap.values());
    }

    function renderMap(list) {
      if (!map) initMap();
      // Clear markers
      markers.forEach(m => m.remove());
      markers = [];

      const clusters = clusterImagesForMap(list);
      const coords = [];
      clusters.forEach(cluster => {
        coords.push([cluster.lat, cluster.lon]);
        if (cluster.items.length > 1) {
          const marker = L.marker([cluster.lat, cluster.lon], {
            icon: L.divIcon({ className: 'cluster-icon', html: cluster.items.length.toString(), iconSize: [36, 36] })
          }).addTo(map);
          marker.on('click', () => {
            const previews = cluster.items.slice(0, 4).map(item => {
              const imgSrc = item.thumbnail
                ? MEMO_BASE + item.thumbnail
                : TRIP_BASE + (item.local_path || item.image_name || '');
              return `<div style="margin-bottom:6px;">
                        <div style="font-weight:600;">${item.caption_ai || item.caption || item.image_name}</div>
                        <img src="${imgSrc}" style="width:150px;height:90px;object-fit:cover;border-radius:8px;" />
                      </div>`;
            }).join('');
            marker.bindPopup(previews || `${cluster.items.length} photos`).openPopup();
          });
          markers.push(marker);
        } else {
          const img = cluster.items[0];
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
      currentFullSrc = fullSrc;
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
      latestDetailText = [
        img.caption_ai || img.caption || img.image_name,
        img.location_full || img.location_short ? `Location: ${img.location_full || img.location_short}` : "",
        img.time ? `Captured: ${img.time}` : "",
        img.device_model ? `Device: ${img.device_model}` : "",
        img.species_tags && img.species_tags.length ? `Species: ${img.species_tags.join(', ')}` : "",
        img.detected_objects && img.detected_objects.length ? `Objects: ${img.detected_objects.join(', ')}` : ""
      ].filter(Boolean).join('\n');
      updateMiniMap(img.gps_lat, img.gps_lon);
      lightbox.classList.add('show');
      lightboxVisible = true;
      renderFilmstrip();
    }

    function stepLightbox(delta) {
      if (!filteredImages.length) return;
      openLightbox(currentFilteredIndex + delta);
    }

    function setActiveChipsFromArray(arr) {
      activeChips = new Set((arr || []).map(s => s.toLowerCase()));
      renderChips();
      render();
    }

    function renderPresetButtons() {
      presetButtonsEl.innerHTML = "";
      PRESET_DEFS.forEach(preset => {
        const btn = document.createElement('button');
        btn.textContent = preset.label;
        btn.onclick = () => setActiveChipsFromArray(preset.tokens);
        presetButtonsEl.appendChild(btn);
      });
    }

    function persistCustomPresets() {
      storedPresets[TRIP_NAME] = customPresets;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(storedPresets));
    }

    function renderCustomPresetOptions() {
      customPresetSelect.innerHTML = "";
      if (!customPresets.length) {
        const opt = document.createElement('option');
        opt.value = "";
        opt.textContent = "No saved filters";
        customPresetSelect.appendChild(opt);
        applyPresetBtn.disabled = true;
        deletePresetBtn.disabled = true;
        return;
      }
      applyPresetBtn.disabled = false;
      deletePresetBtn.disabled = false;
      customPresets.forEach(preset => {
        const opt = document.createElement('option');
        opt.value = preset.name;
        opt.textContent = preset.name;
        customPresetSelect.appendChild(opt);
      });
    }

    renderPresetButtons();
    renderCustomPresetOptions();
    applyPresetBtn.onclick = () => {
      const name = customPresetSelect.value;
      const preset = customPresets.find(p => p.name === name);
      if (preset) setActiveChipsFromArray(preset.tokens);
    };
    savePresetBtn.onclick = () => {
      const tokens = Array.from(activeChips);
      if (!tokens.length) {
        alert("Select at least one chip before saving.");
        return;
      }
      const proposed = `Preset ${customPresets.length + 1}`;
      const name = prompt("Name for this filter preset:", proposed);
      if (!name) return;
      customPresets = customPresets.filter(p => p.name !== name);
      customPresets.push({ name, tokens });
      persistCustomPresets();
      renderCustomPresetOptions();
      customPresetSelect.value = name;
    };
    deletePresetBtn.onclick = () => {
      const name = customPresetSelect.value;
      if (!name) return;
      if (!confirm(`Delete preset "${name}"?`)) return;
      customPresets = customPresets.filter(p => p.name !== name);
      persistCustomPresets();
      renderCustomPresetOptions();
    };

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
