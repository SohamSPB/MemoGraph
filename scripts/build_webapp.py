#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_webapp.py

Generate a lightweight, client-side web app (single HTML) inside a trip's
MemoGraph folder to browse photos, filter/search, and view them on a map.

- Reads <trip>/MemoGraph/blog_context.json (run build_blog_context first).
- Writes <trip>/MemoGraph/webapp/index.html with inline CSS/JS and embedded data.
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
      --header-height: 64px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Inter", "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
    }
    .app {
      display: grid;
      grid-template-rows: var(--header-height) 1fr;
      height: 100%;
    }
    header {
      padding: 0 24px;
      display: flex;
      gap: 16px;
      align-items: center;
      background: linear-gradient(120deg, rgba(56,189,248,0.15), rgba(34,211,238,0.10), rgba(56,189,248,0.05));
      backdrop-filter: blur(6px);
      border-bottom: 1px solid rgba(255,255,255,0.06);
      box-shadow: var(--shadow);
      z-index: 20;
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
    .search input {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 15px;
      outline: none;
    }
    .app-body {
      display: grid;
      grid-template-columns: 260px 1fr 320px;
      overflow: hidden;
    }
    .sidebar {
      background: rgba(17, 24, 39, 0.5);
      border-right: 1px solid rgba(255,255,255,0.06);
      padding: 16px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .sidebar::-webkit-scrollbar { width: 6px; }
    .sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
    
    .sidebar-section h3 {
      margin: 0 0 10px;
      font-size: 0.85rem;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0.5px;
    }
    .filters-group {
      margin-bottom: 16px;
    }
    .filters-group-title {
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      margin: 12px 0 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .filters {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .chip {
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      cursor: pointer;
      transition: background 150ms ease, color 150ms ease;
      font-size: 13px;
      text-align: left;
    }
    .chip:hover { background: rgba(255,255,255,0.08); }
    .chip.active {
      background: linear-gradient(90deg, rgba(56,189,248,0.2), rgba(34,211,238,0.1));
      color: var(--accent-2);
      border-color: rgba(56,189,248,0.3);
    }
    .preset-buttons {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    .preset-buttons button {
        border: none;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(94,234,212,0.15);
        color: var(--text);
        cursor: pointer;
        font-size: 12px;
    }
    .preset-buttons button.active { background: rgba(94,234,212,0.4); }

    .main {
      padding: 16px;
      overflow-y: auto;
      position: relative;
    }
    .main::-webkit-scrollbar { width: 8px; }
    .main::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
    
    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      align-content: start;
    }
    .card {
      background: var(--card);
      border-radius: var(--radius);
      padding: 10px;
      border: 1px solid rgba(255,255,255,0.05);
      box-shadow: var(--shadow);
      transition: transform 180ms ease, box-shadow 220ms ease, border 180ms ease;
      backface-visibility: hidden;
      will-change: transform; 
      contain: layout paint;
    }
    .card:hover {
      transform: translateY(-3px);
      border-color: rgba(56,189,248,0.4);
      box-shadow: 0 12px 30px rgba(0,0,0,0.4);
      z-index: 2;
    }
    .thumb {
      width: 100%;
      border-radius: 8px;
      overflow: hidden;
      background: #0a0f1d;
      aspect-ratio: 4/3;
      display: grid;
      place-items: center;
      position: relative;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .color-bar {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 4px;
        display: flex;
    }
    .swatch {
        flex: 1;
        height: 100%;
    }
    .title { font-weight: 600; font-size: 14px; margin: 8px 0 4px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .meta { font-size: 11px; color: var(--muted); margin-bottom: 6px; }
    .tags { display: flex; flex-wrap: wrap; gap: 4px; }
    .tag {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(255,255,255,0.06);
      color: var(--text);
    }

    .map-pane {
      border-left: 1px solid rgba(255,255,255,0.06);
      position: relative;
      z-index: 10;
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
      background: rgba(5,8,18,0.98);
      display: flex;
      justify-content: center;
      align-items: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 200ms ease;
      z-index: 3000;
    }
    .lightbox.show { opacity: 1; pointer-events: auto; }
    .lightbox-shell {
      width: min(1280px, 96vw);
      height: min(900px, 96vh);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .lightbox-content {
      flex: 1;
      background: var(--card);
      border-radius: 20px;
      padding: 20px;
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
      overflow: hidden;
    }
    .lightbox-img-wrap {
      border-radius: 12px;
      overflow: hidden;
      background: #000;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .lightbox-img-wrap img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    .lightbox-close {
        position: absolute; top: 10px; right: 10px;
        background: rgba(255,255,255,0.1); border:none; color:#fff;
        padding: 6px 10px; border-radius: 20px; cursor: pointer;
        z-index: 10;
    }
    .lightbox-meta {
        overflow-y: auto;
        padding-right: 10px;
    }
    .lightbox-meta h2 { margin-top: 0; font-size: 1.2rem; }
    .lightbox-meta ul {
        padding-left: 20px;
        line-height: 1.6;
        color: #ccc;
        list-style: disc;
        font-size: 0.95rem;
    }
    .lightbox-map {
        height: 180px;
        width: 100%;
        margin-top: 15px;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .lightbox-colors {
        display: flex;
        height: 12px;
        width: 100%;
        margin: 10px 0;
        border-radius: 6px;
        overflow: hidden;
    }
    .lightbox-actions {
        margin-top: 15px;
        display: flex;
        gap: 10px;
    }
    .lightbox-actions button {
        background: rgba(56,189,248,0.2);
        border: 1px solid rgba(56,189,248,0.3);
        color: var(--text);
        padding: 8px 16px;
        border-radius: 999px;
        cursor: pointer;
        font-size: 13px;
        transition: background 0.2s;
    }
    .lightbox-actions button:hover { background: rgba(56,189,248,0.3); }
    
    .filmstrip {
        height: 100px;
        display: flex;
        gap: 10px;
        overflow-x: auto;
        padding: 10px;
        background: rgba(0,0,0,0.3);
        border-radius: 12px;
    }
    .filmstrip img {
        height: 100%;
        border-radius: 6px;
        opacity: 0.5;
        cursor: pointer;
        transition: opacity 0.2s;
    }
    .filmstrip img.active { opacity: 1; border: 2px solid var(--accent); }

    @media (max-width: 1024px) {
      .app-body { grid-template-columns: 1fr; }
      .sidebar, .map-pane { display: none; }
      .lightbox-content { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <button class="back-btn" id="backBtn">← Trips</button>
      <div class="brand">
        <span>MemoGraph</span>
        <span class="trip-name" id="tripName">Trip</span>
      </div>
      <label class="search">
        <input id="search" type="text" placeholder="Search captions, tags..." />
      </label>
    </header>
    
    <div class="app-body">
      <div class="sidebar">
        <button id="clearFiltersBtn" style="width:100%;padding:10px;margin-bottom:16px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#fca5a5;cursor:pointer;border-radius:8px;font-weight:600;transition:all 0.2s;">Clear All Filters</button>
        <div class="sidebar-section">
            <h3>Quick Presets</h3>
            <div class="preset-buttons" id="presetButtons"></div>
        </div>
        <div class="sidebar-section">
            <h3>Categories</h3>
            <div id="filters"></div>
        </div>
      </div>

      <div class="main">
        <div class="gallery" id="gallery"></div>
      </div>

      <div class="map-pane">
        <div id="map"></div>
      </div>
    </div>
  </div>

  <div id="lightbox" class="lightbox">
     <div class="lightbox-shell">
        <div class="lightbox-content">
           <button class="lightbox-close" id="lightboxClose">✕ Close</button>
           <div class="lightbox-img-wrap">
              <button id="navPrev" style="position:absolute;left:15px;z-index:10;background:rgba(0,0,0,0.6);color:#fff;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;">◀</button>
              <img id="lightboxImage" src="">
              <button id="navNext" style="position:absolute;right:15px;z-index:10;background:rgba(0,0,0,0.6);color:#fff;border:none;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:18px;">▶</button>
           </div>
           <div class="lightbox-meta">
              <h2 id="lightboxTitle"></h2>
              <div id="lightboxColors" class="lightbox-colors"></div>
              <ul id="lightboxMeta"></ul>
              <div class="lightbox-actions">
                <button id="openOriginalBtn">Open Original</button>
                <button id="copyMetaBtn">Copy Info</button>
              </div>
              <div id="lightboxMap" class="lightbox-map"></div>
           </div>
        </div>
        <div class="filmstrip" id="filmstrip"></div>
     </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <script>
    const data = __DATA_PLACEHOLDER__;
    const TRIP_NAME = data.trip_name || "MemoGraph Trip";
    const MEMO_BASE = "../";
    const TRIP_BASE = "../../";
    const MASTER_BASE = "../../../index.html";

    const images = [];
    (data.days || []).forEach(day => {
      (day.images || []).forEach(img => {
        images.push({ ...img, day_number: day.day_number, date: day.date });
      });
    });

    const chipSet = new Set();
    images.forEach(img => {
      (img.detected_objects || []).forEach(t => chipSet.add(t.toLowerCase()));
      (img.yolo_objects || []).forEach(t => chipSet.add(t.toLowerCase()));
      (img.places_scenes || []).forEach(t => chipSet.add(t.split("(")[0].trim().toLowerCase()));
      (img.species_tags || []).forEach(t => chipSet.add(t.toLowerCase()));
    });
    const chips = Array.from(chipSet).filter(Boolean).sort();

    let activeChips = new Set();
    let map, lightboxMap;
    let markers = [], lightboxMarker;
    let filteredImages = images.slice();
    let currentLightboxIndex = 0;

    const galleryEl = document.getElementById('gallery');
    const filtersEl = document.getElementById('filters');
    const searchInput = document.getElementById('search');
    const mapEl = document.getElementById('map');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImage');
    const lightboxTitle = document.getElementById('lightboxTitle');
    const lightboxMeta = document.getElementById('lightboxMeta');
    const lightboxColors = document.getElementById('lightboxColors');
    const filmstripEl = document.getElementById('filmstrip');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    const openOriginalBtn = document.getElementById('openOriginalBtn');
    const copyMetaBtn = document.getElementById('copyMetaBtn');

    document.getElementById('tripName').textContent = TRIP_NAME;
    document.getElementById('backBtn').onclick = () => window.location.href = MASTER_BASE;
    document.getElementById('lightboxClose').onclick = () => lightbox.classList.remove('show');
    document.getElementById('navPrev').onclick = (e) => { e.stopPropagation(); showLightbox(currentLightboxIndex - 1); };
    document.getElementById('navNext').onclick = (e) => { e.stopPropagation(); showLightbox(currentLightboxIndex + 1); };
    
    clearFiltersBtn.onclick = () => {
        activeChips.clear();
        searchInput.value = "";
        renderFilters();
        renderGallery();
    };
    
    openOriginalBtn.onclick = () => {
        const img = filteredImages[currentLightboxIndex];
        if (img) window.open(TRIP_BASE + (img.local_path || img.image_name), '_blank');
    };

    copyMetaBtn.onclick = () => {
        const text = Array.from(lightboxMeta.querySelectorAll('li')).map(li => li.innerText).join('\\n');
        navigator.clipboard.writeText(text).then(() => alert('Info copied to clipboard!'));
    };

    const CATEGORIES = {
      "Nature": ["bird", "insect", "flower", "plant", "tree", "forest", "mountain", "valley", "lake", "river", "waterfall", "landscape", "wildlife", "animal", "yak", "cat", "dog", "sunrise", "sunset", "night sky", "stars", "moon", "eclipse", "galaxy", "nebula", "milky way", "star cluster", "astrophotography", "rock", "stone"],
      "Structures": ["building", "home stay", "guesthouse", "homestay", "hotel", "hotel room", "market", "bazaar", "street market", "temple", "monastery", "stupa", "church", "mosque", "palace", "fort", "castle", "monument", "historical gate", "bridge", "suspension bridge", "city", "cityscape", "town", "village", "street", "narrow street", "highway", "road", "mountain road", "bus on a mountain road", "sign", "billboard", "poster", "wall", "lamp", "light", "street light", "window", "door", "furniture", "chair", "table", "fence", "gate", "pole", "wire", "road sign"],
      "People": ["person", "group of people", "selfie", "group"],
      "Food/Drink": ["food", "thali", "curry", "tea", "chai", "coffee", "cafe", "restaurant", "plate of food", "street food stall", "bowl of curry", "cup of tea", "cup of coffee", "glass of chai", "dessert plate", "pizza", "burger"],
      "Tech": ["circuit board", "electronics", "computer chip", "wiring", "soldering", "motherboard", "screen", "monitor", "keyboard", "mouse", "laptop", "smartphone", "tablet", "television", "appliance", "tool"],
    };

    function renderFilters() {
      filtersEl.innerHTML = '';
      const categorized = { "Nature": [], "Structures": [], "People": [], "Food/Drink": [], "Tech": [], "Others": [] };
      
      chips.forEach(ch => {
        let found = false;
        for (const cat in CATEGORIES) {
          if (CATEGORIES[cat].includes(ch)) {
            categorized[cat].push(ch);
            found = true;
            break;
          }
        }
        if (!found) categorized["Others"].push(ch);
      });

      for (const cat in categorized) {
        if (!categorized[cat].length) continue;
        const group = document.createElement('div');
        group.className = 'filters-group';
        group.innerHTML = `<div class="filters-group-title">${cat}</div>`;
        const container = document.createElement('div');
        container.className = 'filters';
        categorized[cat].forEach(ch => {
          const btn = document.createElement('div');
          btn.className = 'chip';
          if (activeChips.has(ch)) btn.classList.add('active');
          btn.textContent = ch;
          btn.onclick = () => {
            if (activeChips.has(ch)) activeChips.delete(ch); else activeChips.add(ch);
            renderFilters();
            renderGallery();
          };
          container.appendChild(btn);
        });
        group.appendChild(container);
        filtersEl.appendChild(group);
      }
    }

    function initMap() {
      map = L.map('map', { zoomControl: false }).setView([20, 0], 2);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
    }
    
    function updateMap() {
      if (!map) initMap();
      markers.forEach(m => m.remove());
      markers = [];
      const bounds = [];
      filteredImages.forEach(img => {
        if (img.gps_lat && img.gps_lon) {
           const m = L.circleMarker([img.gps_lat, img.gps_lon], { radius: 5, color: '#38bdf8', weight: 2, fillOpacity: 0.8 }).addTo(map);
           markers.push(m);
           bounds.push([img.gps_lat, img.gps_lon]);
        }
      });
      if (bounds.length) map.fitBounds(bounds, { padding: [20, 20] });
    }

    function renderGallery() {
      const term = searchInput.value.toLowerCase();
      filteredImages = images.filter(img => {
        const text = [img.caption, img.caption_ai, ...(img.detected_objects||[]), ...(img.species_tags||[])].join(' ').toLowerCase();
        if (term && !text.includes(term)) return false;
        if (activeChips.size) {
           const imgTags = new Set([...(img.detected_objects||[]), ...(img.species_tags||[])].map(s=>s.toLowerCase()));
           for (let c of activeChips) if (!imgTags.has(c)) return false;
        }
        return true;
      });

      galleryEl.innerHTML = '';
      if (!filteredImages.length) {
        galleryEl.innerHTML = '<div class="empty-state">No photos match your filters</div>';
      } else {
        filteredImages.forEach((img, idx) => {
           const card = document.createElement('div');
           card.className = 'card';
           
           const thumbSrc = img.thumbnail ? MEMO_BASE + img.thumbnail : TRIP_BASE + (img.local_path||img.image_name);
           let colorsHtml = '';
           if (img.color_palette && img.color_palette.length) {
               colorsHtml = `<div class="color-bar">${img.color_palette.map(c => `<div class="swatch" style="background:${c}"></div>`).join('')}</div>`;
           }

           card.innerHTML = `
             <div class="thumb">
               <img src="${thumbSrc}" loading="lazy">
               ${colorsHtml}
             </div>
             <div class="title" title="${img.caption_ai || img.caption}">${img.caption_ai || img.caption || "Untitled"}</div>
             <div class="meta">
               ${img.location_short || "Unknown"} • Day ${img.day_number}
               ${img.quality_score ? ` • Q ${(img.quality_score*100).toFixed(0)}%` : ""}
             </div>
             <div class="tags"></div>
           `;
           
           const tagsDiv = card.querySelector('.tags');
           (img.species_tags||[]).slice(0,1).forEach(t => {
               const s = document.createElement('span'); s.className='tag'; s.textContent=t; tagsDiv.appendChild(s);
           });
           
           const fcVal = img.faces_count;
           if (String(fcVal) === "-1") {
               const s = document.createElement('span'); s.className='tag'; s.style.color='#fca5a5'; s.textContent='Scan Pending'; tagsDiv.appendChild(s);
           } else {
               const fc = Number(fcVal || 0);
               if (fc === 0) {
                   const s = document.createElement('span'); s.className='tag'; s.style.color='#9ca3af'; s.textContent='No Faces'; tagsDiv.appendChild(s);
               } else {
                   const s = document.createElement('span'); s.className='tag'; s.style.color='#86efac'; s.textContent=`${fc} Face${fc>1?'s':''}`; tagsDiv.appendChild(s);
               }
           }

           card.onclick = () => showLightbox(idx);
           galleryEl.appendChild(card);
        });
      }
      updateMap();
    }

    function showLightbox(idx) {
        if (idx < 0 || idx >= filteredImages.length) return;
        currentLightboxIndex = idx;
        const img = filteredImages[idx];
        const src = TRIP_BASE + (img.local_path || img.image_name);
        lightboxImg.src = src;
        lightboxTitle.textContent = img.caption_ai || img.caption || "Photo Details";
        
        // Colors
        lightboxColors.innerHTML = "";
        if (img.color_palette && img.color_palette.length) {
            lightboxColors.innerHTML = img.color_palette.map(c => `<div style="flex:1;background:${c};height:100%"></div>`).join('');
        }

        // Detailed Metadata
        lightboxMeta.innerHTML = `
           <li><strong>Location:</strong> ${img.location_full || img.location_short || "Unknown"}</li>
           <li><strong>Captured:</strong> ${img.time}</li>
           <li><strong>Type:</strong> ${img.image_type || "Unknown"}</li>
           <li><strong>Device:</strong> ${img.device_model || "Unknown"}</li>
           <li><strong>Faces:</strong> ${img.faces_count === -1 ? "Pending" : img.faces_count}</li>
           <li><strong>Tags:</strong> ${(img.detected_objects||[]).join(', ') || 'None'}</li>
           <li><strong>Species:</strong> ${(img.species_tags||[]).join(', ') || 'None'}</li>
           <li><strong>Quality:</strong> ${img.quality_score ? (img.quality_score*100).toFixed(0)+'%' : 'N/A'} ${img.quality_notes ? '('+img.quality_notes+')' : ''}</li>
           <li><strong>Balance:</strong> Exp ${(img.exposure_score*100).toFixed(0)}% · Con ${(img.contrast_score*100).toFixed(0)}% · Shp ${(img.sharpness_score*100).toFixed(0)}% · Noi ${(img.noise_score*100).toFixed(0)}%</li>
        `;
        
        if (img.vision_caption) {
            const vli = document.createElement('li');
            vli.innerHTML = `<strong>AI Description:</strong> <span style="color:var(--accent-2)">${img.vision_caption}</span>`;
            lightboxMeta.appendChild(vli);
        }

        // Mini Map
        const mapContainer = document.getElementById('lightboxMap');
        if (img.gps_lat && img.gps_lon) {
            mapContainer.style.display = 'block';
            if (!lightboxMap) {
                lightboxMap = L.map(mapContainer, { zoomControl: false, attributionControl: false });
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(lightboxMap);
            }
            lightboxMap.setView([img.gps_lat, img.gps_lon], 13);
            if (lightboxMarker) lightboxMarker.remove();
            lightboxMarker = L.circleMarker([img.gps_lat, img.gps_lon], { radius: 7, color: "#5eead4", weight: 3, fillOpacity: 0.9 }).addTo(lightboxMap);
            
            const linkLi = document.createElement('li');
            linkLi.innerHTML = `<strong>Map:</strong> <a href="https://maps.google.com/?q=${img.gps_lat},${img.gps_lon}" target="_blank" style="color:var(--accent)">Open in Google Maps</a>`;
            lightboxMeta.appendChild(linkLi);
        } else {
            mapContainer.style.display = 'none';
        }

        lightbox.classList.add('show');
        setTimeout(() => { if(lightboxMap) lightboxMap.invalidateSize(); }, 300);
        renderFilmstrip();
    }

    function renderFilmstrip() {
        filmstripEl.innerHTML = '';
        filteredImages.forEach((img, i) => {
            const thumb = document.createElement('img');
            thumb.src = img.thumbnail ? MEMO_BASE + img.thumbnail : TRIP_BASE + (img.local_path||img.image_name);
            if (i === currentLightboxIndex) thumb.classList.add('active');
            thumb.onclick = (e) => { e.stopPropagation(); showLightbox(i); };
            filmstripEl.appendChild(thumb);
        });
        const active = filmstripEl.querySelector('.active');
        if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (!lightbox.classList.contains('show')) return;
        if (e.key === 'ArrowLeft') showLightbox(currentLightboxIndex - 1);
        else if (e.key === 'ArrowRight') showLightbox(currentLightboxIndex + 1);
        else if (e.key === 'Escape') lightbox.classList.remove('show');
    });

    searchInput.oninput = renderGallery;
    renderFilters();
    renderGallery();

  </script>
</body>
</html>
"""

def _sanitize_thumbnail_name(rel_path: str) -> str:
	name_without_ext = os.path.splitext(rel_path)[0]
	# Use os.sep and handle common separators
	safe_name = name_without_ext.replace("/", "_").replace("\\\\", "_")
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
					continue

			if os.path.exists(dest_path):
				# Ensure correct slash for web URL
				image["thumbnail"] = os.path.join(thumb_subdir, thumb_name).replace("\\\\", "/")

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