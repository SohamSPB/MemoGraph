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
  <title>MemoGraph - Trip Gallery</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css" />
  <style>
    :root {
      --bg: #030711;
      --bg-secondary: #0a1122;
      --card: #0f172a;
      --card-hover: #1e293b;
      --card-border: rgba(148, 163, 184, 0.1);
      --text: #f1f5f9;
      --text-secondary: #94a3b8;
      --muted: #64748b;
      --accent: #06b6d4;
      --accent-glow: rgba(6, 182, 212, 0.4);
      --accent-secondary: #8b5cf6;
      --accent-tertiary: #f472b6;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --chip-bg: rgba(148, 163, 184, 0.1);
      --chip-border: rgba(148, 163, 184, 0.2);
      --gradient-1: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%);
      --gradient-2: linear-gradient(135deg, #f472b6 0%, #fb923c 100%);
      --shadow: 0 10px 40px rgba(0,0,0,0.3);
      --header-height: 72px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
    }

    /* Background Effects - Static gradient to prevent flickering */
    .bg-effects {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
      background:
        radial-gradient(ellipse 600px 600px at 20% 20%, rgba(6, 182, 212, 0.05), transparent),
        radial-gradient(ellipse 500px 500px at 80% 10%, rgba(139, 92, 246, 0.05), transparent),
        radial-gradient(ellipse 400px 400px at 60% 80%, rgba(244, 114, 182, 0.03), transparent);
    }

    .app {
      display: grid;
      grid-template-rows: var(--header-height) 1fr;
      height: 100%;
      position: relative;
      z-index: 1;
    }

    /* Header */
    header {
      padding: 0 24px;
      display: flex;
      gap: 20px;
      align-items: center;
      background: rgba(3, 7, 17, 0.85);
      backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--card-border);
      z-index: 100;
    }
    .back-btn {
      border: 1px solid var(--card-border);
      background: var(--card);
      color: var(--text-secondary);
      padding: 10px 18px;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.2s ease;
    }
    .back-btn:hover {
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .logo-icon {
      width: 40px;
      height: 40px;
      background: var(--gradient-1);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 4px 16px var(--accent-glow);
    }
    .brand-text {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .brand-name {
      font-family: "Playfair Display", serif;
      font-size: 1.1rem;
      font-weight: 700;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .trip-name {
      font-size: 0.8rem;
      color: var(--muted);
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .header-stats {
      display: flex;
      gap: 24px;
      margin-left: auto;
      margin-right: 20px;
    }
    .header-stat {
      text-align: center;
    }
    .header-stat-value {
      font-size: 1.2rem;
      font-weight: 700;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .header-stat-label {
      font-size: 0.7rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .search-box {
      flex: 1;
      max-width: 400px;
      position: relative;
    }
    .search-box input {
      width: 100%;
      padding: 12px 18px 12px 44px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      color: var(--text);
      font-size: 0.9rem;
      outline: none;
      transition: all 0.2s ease;
    }
    .search-box input::placeholder { color: var(--muted); }
    .search-box input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }
    .search-icon {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: 16px;
    }

    /* Main Layout */
    .app-body {
      display: grid;
      grid-template-columns: 280px 1fr 340px;
      overflow: hidden;
    }

    /* Sidebar */
    .sidebar {
      background: rgba(15, 23, 42, 0.6);
      border-right: 1px solid var(--card-border);
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .sidebar::-webkit-scrollbar { width: 6px; }
    .sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

    .clear-filters-btn {
      width: 100%;
      padding: 12px;
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.2);
      color: #fca5a5;
      cursor: pointer;
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.85rem;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .clear-filters-btn:hover {
      background: rgba(239, 68, 68, 0.2);
      border-color: rgba(239, 68, 68, 0.4);
    }

    .sidebar-section h3 {
      margin: 0 0 12px;
      font-size: 0.75rem;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 1px;
      font-weight: 600;
    }
    .filters-group {
      margin-bottom: 16px;
    }
    .filters-group-title {
      font-size: 0.7rem;
      font-weight: 700;
      color: var(--accent);
      margin: 16px 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .filters-group-title::before {
      content: '';
      width: 4px;
      height: 4px;
      background: var(--accent);
      border-radius: 50%;
    }
    .filters {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .chip {
      padding: 8px 14px;
      border-radius: 8px;
      border: 1px solid var(--chip-border);
      background: var(--chip-bg);
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.15s ease;
      font-size: 0.85rem;
      text-align: left;
      font-weight: 500;
    }
    .chip:hover {
      background: rgba(148, 163, 184, 0.15);
      border-color: var(--accent);
    }
    .chip.active {
      background: linear-gradient(90deg, rgba(6, 182, 212, 0.2), rgba(139, 92, 246, 0.1));
      color: var(--accent);
      border-color: var(--accent);
    }

    /* Main Gallery */
    .main {
      padding: 20px;
      overflow-y: auto;
      position: relative;
      transform: translateZ(0);
      -webkit-overflow-scrolling: touch;
    }
    .main::-webkit-scrollbar { width: 8px; }
    .main::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 20px;
      align-content: start;
      transform: translateZ(0);
    }
    .card {
      background: var(--card);
      border-radius: 16px;
      padding: 12px;
      border: 1px solid var(--card-border);
      cursor: pointer;
      transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                  border-color 0.25s ease,
                  box-shadow 0.25s ease;
      transform: translateZ(0);
      backface-visibility: hidden;
    }
    .card:hover {
      transform: translateY(-6px) translateZ(0);
      border-color: var(--accent);
      box-shadow: 0 16px 40px rgba(6, 182, 212, 0.12), 0 8px 20px rgba(0, 0, 0, 0.3);
    }

    .thumb {
      width: 100%;
      border-radius: 10px;
      overflow: hidden;
      background: var(--bg-secondary);
      aspect-ratio: 4/3;
      display: grid;
      place-items: center;
      position: relative;
      transform: translateZ(0);
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transform: translateZ(0);
      backface-visibility: hidden;
    }

    .color-bar {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 6px;
      display: flex;
      z-index: 2;
    }
    .swatch { flex: 1; height: 100%; }

    .quality-badge {
      position: absolute;
      top: 8px;
      right: 8px;
      padding: 4px 8px;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(8px);
      border-radius: 6px;
      font-size: 0.7rem;
      font-weight: 600;
      color: var(--success);
    }
    .quality-badge.low { color: var(--warning); }
    .quality-badge.vlow { color: var(--danger); }

    .card-content { padding: 10px 4px 4px; }
    .title {
      font-weight: 600;
      font-size: 0.9rem;
      margin: 0 0 6px;
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text);
    }
    .meta {
      font-size: 0.75rem;
      color: var(--muted);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .meta svg { width: 12px; height: 12px; }
    .tags { display: flex; flex-wrap: wrap; gap: 6px; }
    .tag {
      font-size: 0.7rem;
      padding: 4px 8px;
      border-radius: 6px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      color: var(--text-secondary);
      font-weight: 500;
    }
    .tag.species { color: var(--success); border-color: rgba(16, 185, 129, 0.3); }
    .tag.faces { color: var(--accent-tertiary); border-color: rgba(244, 114, 182, 0.3); }
    .tag.no-faces { color: var(--muted); border-color: rgba(100, 116, 139, 0.3); }
    .tag.pending { color: var(--warning); border-color: rgba(245, 158, 11, 0.3); }

    /* Map Pane */
    .map-pane {
      border-left: 1px solid var(--card-border);
      position: relative;
      z-index: 10;
      display: flex;
      flex-direction: column;
    }
    .map-header {
      padding: 16px 20px;
      background: var(--card);
      border-bottom: 1px solid var(--card-border);
    }
    .map-header h3 {
      margin: 0;
      font-size: 0.85rem;
      color: var(--text);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .map-header h3 svg { color: var(--accent); }
    #map { flex: 1; }

    .empty-state {
      grid-column: 1 / -1;
      text-align: center;
      color: var(--muted);
      padding: 60px 20px;
    }
    .empty-state-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
    .empty-state h3 { font-size: 1.2rem; margin-bottom: 8px; color: var(--text); }

    /* Lightbox */
    .lightbox {
      position: fixed;
      inset: 0;
      background: rgba(3, 7, 17, 0.95);
      backdrop-filter: blur(8px);
      display: flex;
      justify-content: center;
      align-items: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 250ms ease;
      z-index: 3000;
    }
    .lightbox.show { opacity: 1; pointer-events: auto; }
    .lightbox-shell {
      width: min(1400px, 96vw);
      height: min(900px, 94vh);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .lightbox-content {
      flex: 1;
      background: var(--card);
      border-radius: 24px;
      padding: 24px;
      display: grid;
      grid-template-columns: 1.8fr 1fr;
      gap: 24px;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }
    .lightbox-img-wrap {
      border-radius: 16px;
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
      position: absolute;
      top: 16px;
      right: 16px;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.1);
      color: #fff;
      padding: 10px 18px;
      border-radius: 999px;
      cursor: pointer;
      z-index: 10;
      font-size: 0.85rem;
      font-weight: 500;
      transition: all 0.2s ease;
    }
    .lightbox-close:hover {
      background: rgba(239, 68, 68, 0.8);
      border-color: transparent;
    }
    .nav-btn {
      position: absolute;
      z-index: 10;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(8px);
      color: #fff;
      border: 1px solid rgba(255,255,255,0.1);
      width: 48px;
      height: 48px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 18px;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .nav-btn:hover {
      background: var(--accent);
      border-color: transparent;
      transform: scale(1.1);
    }
    .nav-btn.prev { left: 20px; }
    .nav-btn.next { right: 20px; }

    .lightbox-panel {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .lightbox-meta {
      flex: 1;
      overflow-y: auto;
      padding-right: 8px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .lightbox-meta::-webkit-scrollbar { width: 4px; }
    .lightbox-meta::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
    .lightbox-footer {
      flex-shrink: 0;
      padding-top: 12px;
      border-top: 1px solid var(--card-border);
      margin-top: 12px;
    }

    .lightbox-header {
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
    }
    .lightbox-filename {
      font-size: 0.75rem;
      color: var(--muted);
      font-family: monospace;
      background: var(--chip-bg);
      padding: 4px 8px;
      border-radius: 4px;
      display: inline-block;
      margin-bottom: 8px;
      word-break: break-all;
    }
    .lightbox-caption {
      font-size: 1.2rem;
      font-weight: 600;
      line-height: 1.4;
      color: var(--text);
      margin: 0;
    }
    .lightbox-colors {
      display: flex;
      height: 12px;
      width: 100%;
      margin-top: 12px;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }
    .lightbox-colors:empty {
      display: none;
    }

    .meta-section {
      background: rgba(15, 23, 42, 0.5);
      border-radius: 12px;
      padding: 14px;
      border: 1px solid var(--card-border);
    }
    .meta-section-title {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--accent);
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .meta-grid.single-col {
      grid-template-columns: 1fr;
    }
    .meta-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .meta-item.full-width {
      grid-column: 1 / -1;
    }
    .meta-label {
      font-size: 0.7rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }
    .meta-value {
      font-size: 0.85rem;
      color: var(--text);
      word-break: break-word;
    }
    .meta-value a { color: var(--accent); text-decoration: none; }
    .meta-value a:hover { text-decoration: underline; }
    .meta-value.highlight { color: var(--accent); }
    .meta-value.muted { color: var(--muted); font-style: italic; }

    .meta-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .meta-tag {
      font-size: 0.75rem;
      padding: 4px 10px;
      border-radius: 6px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      color: var(--text-secondary);
    }
    .meta-tag.species { color: var(--success); border-color: rgba(16, 185, 129, 0.3); }
    .meta-tag.faces { color: var(--accent-tertiary); border-color: rgba(244, 114, 182, 0.3); }

    .quality-meters {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .quality-meter {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .quality-meter-label {
      font-size: 0.75rem;
      color: var(--muted);
      min-width: 70px;
    }
    .quality-meter-bar {
      flex: 1;
      height: 6px;
      background: var(--chip-bg);
      border-radius: 3px;
      overflow: hidden;
    }
    .quality-meter-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.3s ease;
    }
    .quality-meter-fill.good { background: var(--success); }
    .quality-meter-fill.medium { background: var(--warning); }
    .quality-meter-fill.low { background: var(--danger); }
    .quality-meter-value {
      font-size: 0.75rem;
      color: var(--text-secondary);
      min-width: 35px;
      text-align: right;
    }

    .lightbox-actions {
      margin-top: 20px;
      display: flex;
      gap: 12px;
    }
    .lightbox-actions button {
      flex: 1;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      color: var(--text);
      padding: 12px 16px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 500;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .lightbox-actions button:hover {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--bg);
    }

    .lightbox-map {
      height: 160px;
      width: 100%;
      margin-top: 20px;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }

    .filmstrip {
      height: 90px;
      display: flex;
      gap: 12px;
      overflow-x: auto;
      padding: 12px 16px;
      background: var(--card);
      border-radius: 16px;
      border: 1px solid var(--card-border);
    }
    .filmstrip::-webkit-scrollbar { height: 4px; }
    .filmstrip::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
    .filmstrip img {
      height: 100%;
      border-radius: 8px;
      opacity: 0.4;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 2px solid transparent;
    }
    .filmstrip img:hover { opacity: 0.7; }
    .filmstrip img.active {
      opacity: 1;
      border-color: var(--accent);
      box-shadow: 0 0 20px var(--accent-glow);
    }

    /* Footer */
    .webapp-footer {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 12px 24px;
      background: rgba(3, 7, 17, 0.9);
      backdrop-filter: blur(20px);
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
      z-index: 50;
      font-size: 0.8rem;
      color: var(--muted);
    }
    .webapp-footer a { color: var(--accent); text-decoration: none; }
    .webapp-footer a:hover { text-decoration: underline; }

    /* Responsive */
    @media (max-width: 1200px) {
      .app-body { grid-template-columns: 260px 1fr; }
      .map-pane { display: none; }
      .header-stats { display: none; }
    }
    @media (max-width: 900px) {
      .app-body { grid-template-columns: 1fr; }
      .sidebar { display: none; }
      .lightbox-content { grid-template-columns: 1fr; }
      .lightbox-meta { max-height: 300px; }
    }
    @media (max-width: 600px) {
      header { padding: 0 16px; gap: 12px; }
      .brand-text { display: none; }
      .search-box { max-width: none; }
      .gallery { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
    }
  </style>
</head>
<body>
  <div class="bg-effects"></div>

  <div class="app">
    <header>
      <button class="back-btn" id="backBtn">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        All Trips
      </button>
      <div class="brand">
        <div class="logo-icon">&#x1F4F7;</div>
        <div class="brand-text">
          <span class="brand-name">MemoGraph</span>
          <span class="trip-name" id="tripName">Trip Gallery</span>
        </div>
      </div>
      <div class="header-stats" id="headerStats">
        <div class="header-stat">
          <div class="header-stat-value" id="statPhotos">0</div>
          <div class="header-stat-label">Photos</div>
        </div>
        <div class="header-stat">
          <div class="header-stat-value" id="statDays">0</div>
          <div class="header-stat-label">Days</div>
        </div>
        <div class="header-stat">
          <div class="header-stat-value" id="statLocations">0</div>
          <div class="header-stat-label">Locations</div>
        </div>
      </div>
      <div class="search-box">
        <span class="search-icon">&#x1F50D;</span>
        <input id="search" type="text" placeholder="Search photos, tags, locations..." />
      </div>
    </header>

    <div class="app-body">
      <div class="sidebar">
        <button class="clear-filters-btn" id="clearFiltersBtn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          Clear All Filters
        </button>
        <div class="sidebar-section">
          <h3>Filter by Category</h3>
          <div id="filters"></div>
        </div>
      </div>

      <div class="main">
        <div class="gallery" id="gallery"></div>
      </div>

      <div class="map-pane">
        <div class="map-header">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            Photo Locations
          </h3>
        </div>
        <div id="map"></div>
      </div>
    </div>
  </div>

  <footer class="webapp-footer">
    <span>&#x1F4F7;</span>
    <span>MemoGraph</span>
    <span>•</span>
    <span>Created by <a href="#">Soham Bagayatkar</a></span>
  </footer>

  <div id="lightbox" class="lightbox">
    <div class="lightbox-shell">
      <div class="lightbox-content">
        <div class="lightbox-img-wrap">
          <button class="lightbox-close" id="lightboxClose">&#x2715; Close</button>
          <button class="nav-btn prev" id="navPrev">&#x25C0;</button>
          <img id="lightboxImage" src="">
          <button class="nav-btn next" id="navNext">&#x25B6;</button>
        </div>
        <div class="lightbox-panel">
          <div class="lightbox-meta" id="lightboxMeta">
            <!-- Content populated by JavaScript -->
          </div>
          <div class="lightbox-footer">
            <div class="lightbox-actions">
              <button id="openOriginalBtn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                Open Original
              </button>
              <button id="copyMetaBtn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy Info
              </button>
            </div>
            <div id="lightboxMap" class="lightbox-map"></div>
          </div>
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
    const uniqueLocations = new Set();
    (data.days || []).forEach(day => {
      (day.images || []).forEach(img => {
        images.push({ ...img, day_number: day.day_number, date: day.date });
        if (img.location_short) uniqueLocations.add(img.location_short);
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

    // Smart title extraction: prefer vision_caption's first sentence over caption_ai
    function getSmartTitle(img) {
      // If vision_caption exists, extract a concise title from it
      if (img.vision_caption && img.vision_caption.length > 20) {
        let vc = img.vision_caption;
        // Get first sentence
        let first = vc.split(/\.\s/)[0];
        // Remove generic openings like "The image captures..."
        first = first.replace(/^The image (captures|shows|features|depicts|presents|displays)\s+(a\s+)?(moment of [^,]+,\s+(featuring|with)\s+)?/i, '');
        first = first.replace(/^In the [^,]+,\s*/i, '');
        first = first.replace(/^(A|An|The)\s+(serene|tranquil|vibrant|beautiful|stunning)\s+(scene|moment|view|image)\s+(of|in|featuring|with)\s+/i, '');
        // Capitalize first letter
        first = first.charAt(0).toUpperCase() + first.slice(1);
        // Trim to reasonable length
        if (first.length > 120) first = first.substring(0, 117) + '...';
        if (first.length > 10) return first;
      }
      return img.caption_ai || img.caption || "Untitled";
    }

    let activeChips = new Set();
    let map, lightboxMap;
    let markers = [], lightboxMarker;
    let filteredImages = images.slice();
    let currentLightboxIndex = 0;

    const galleryEl = document.getElementById('gallery');
    const filtersEl = document.getElementById('filters');
    const searchInput = document.getElementById('search');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImage');
    const lightboxMeta = document.getElementById('lightboxMeta');
    const filmstripEl = document.getElementById('filmstrip');

    // Update header stats
    document.getElementById('tripName').textContent = TRIP_NAME;
    document.getElementById('statPhotos').textContent = images.length;
    document.getElementById('statDays').textContent = data.days?.length || 0;
    document.getElementById('statLocations').textContent = uniqueLocations.size;

    document.getElementById('backBtn').onclick = () => window.location.href = MASTER_BASE;
    document.getElementById('lightboxClose').onclick = () => lightbox.classList.remove('show');
    document.getElementById('navPrev').onclick = (e) => { e.stopPropagation(); showLightbox(currentLightboxIndex - 1); };
    document.getElementById('navNext').onclick = (e) => { e.stopPropagation(); showLightbox(currentLightboxIndex + 1); };

    document.getElementById('clearFiltersBtn').onclick = () => {
      activeChips.clear();
      searchInput.value = "";
      renderFilters();
      renderGallery();
    };

    document.getElementById('openOriginalBtn').onclick = () => {
      const img = filteredImages[currentLightboxIndex];
      if (img) window.open(TRIP_BASE + (img.local_path || img.image_name), '_blank');
    };

    document.getElementById('copyMetaBtn').onclick = () => {
      const text = Array.from(lightboxMeta.querySelectorAll('li')).map(li => li.innerText).join('\\n');
      navigator.clipboard.writeText(text).then(() => alert('Photo info copied to clipboard!'));
    };

    const CATEGORIES = {
      "Nature": ["bird", "insect", "flower", "plant", "tree", "forest", "mountain", "valley", "lake", "river", "waterfall", "landscape", "wildlife", "animal", "yak", "cat", "dog", "sunrise", "sunset", "night sky", "stars", "moon", "rock", "stone"],
      "Structures": ["building", "home stay", "guesthouse", "homestay", "hotel", "market", "temple", "monastery", "stupa", "church", "mosque", "palace", "fort", "castle", "monument", "bridge", "city", "town", "village", "street", "road", "sign"],
      "People": ["person", "group of people", "selfie", "group"],
      "Food/Drink": ["food", "thali", "curry", "tea", "chai", "coffee", "cafe", "restaurant", "plate of food", "dessert"],
      "Tech": ["circuit board", "electronics", "computer", "screen", "monitor", "laptop", "smartphone"],
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
          const m = L.circleMarker([img.gps_lat, img.gps_lon], {
            radius: 6,
            color: '#06b6d4',
            weight: 2,
            fillColor: '#06b6d4',
            fillOpacity: 0.7
          }).addTo(map);
          markers.push(m);
          bounds.push([img.gps_lat, img.gps_lon]);
        }
      });
      if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
    }

    function renderGallery() {
      const term = searchInput.value.toLowerCase();
      filteredImages = images.filter(img => {
        const text = [img.caption, img.caption_ai, img.location_short, ...(img.detected_objects||[]), ...(img.species_tags||[])].join(' ').toLowerCase();
        if (term && !text.includes(term)) return false;
        if (activeChips.size) {
          const imgTags = new Set([...(img.detected_objects||[]), ...(img.species_tags||[])].map(s=>s.toLowerCase()));
          for (let c of activeChips) if (!imgTags.has(c)) return false;
        }
        return true;
      });

      galleryEl.innerHTML = '';
      if (!filteredImages.length) {
        galleryEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">&#x1F50D;</div>
            <h3>No photos found</h3>
            <p>Try adjusting your search or filters</p>
          </div>`;
      } else {
        filteredImages.forEach((img, idx) => {
          const card = document.createElement('div');
          card.className = 'card';

          const thumbSrc = img.thumbnail ? MEMO_BASE + img.thumbnail : TRIP_BASE + (img.local_path||img.image_name);
          let colorsHtml = '';
          if (img.color_palette && img.color_palette.length) {
            colorsHtml = `<div class="color-bar">${img.color_palette.map(c => `<div class="swatch" style="background:${c}"></div>`).join('')}</div>`;
          }

          let qualityBadge = '';
          if (img.quality_score) {
            const qs = img.quality_score * 100;
            let qClass = '';
            if (qs < 40) qClass = 'vlow';
            else if (qs < 60) qClass = 'low';
            qualityBadge = `<div class="quality-badge ${qClass}">${qs.toFixed(0)}%</div>`;
          }

          card.innerHTML = `
            <div class="thumb">
              <img src="${thumbSrc}" loading="lazy" alt="${getSmartTitle(img)}">
              ${colorsHtml}
              ${qualityBadge}
            </div>
            <div class="card-content">
              <div class="title" title="${getSmartTitle(img)}">${getSmartTitle(img)}</div>
              <div class="meta">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                ${img.location_short || "Unknown"} &bull; Day ${img.day_number}
              </div>
              <div class="tags"></div>
            </div>
          `;

          const tagsDiv = card.querySelector('.tags');
          (img.species_tags||[]).slice(0,1).forEach(t => {
            const s = document.createElement('span');
            s.className = 'tag species';
            s.textContent = t;
            tagsDiv.appendChild(s);
          });

          const fcVal = img.faces_count;
          if (String(fcVal) === "-1") {
            const s = document.createElement('span');
            s.className = 'tag pending';
            s.textContent = 'Scan Pending';
            tagsDiv.appendChild(s);
          } else {
            const fc = Number(fcVal || 0);
            if (fc === 0) {
              const s = document.createElement('span');
              s.className = 'tag no-faces';
              s.textContent = 'No Faces';
              tagsDiv.appendChild(s);
            } else {
              const s = document.createElement('span');
              s.className = 'tag faces';
              s.textContent = `${fc} Face${fc>1?'s':''}`;
              tagsDiv.appendChild(s);
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

      // Helper for quality meter
      function qualityMeter(label, value) {
        if (value === null || value === undefined) return '';
        const pct = Math.round(value * 100);
        let cls = 'good';
        if (pct < 40) cls = 'low';
        else if (pct < 60) cls = 'medium';
        return `
          <div class="quality-meter">
            <span class="quality-meter-label">${label}</span>
            <div class="quality-meter-bar"><div class="quality-meter-fill ${cls}" style="width:${pct}%"></div></div>
            <span class="quality-meter-value">${pct}%</span>
          </div>`;
      }

      // Face detection text
      let facesHtml = '<span class="meta-value muted">No faces present</span>';
      if (String(img.faces_count) === "-1") {
        facesHtml = '<span class="meta-value muted">Scan pending</span>';
      } else if (Number(img.faces_count) > 0) {
        const fc = Number(img.faces_count);
        let names = img.face_names && img.face_names.length ? img.face_names.join(', ') : '';
        facesHtml = `<span class="meta-tag faces">${fc} face${fc > 1 ? 's' : ''}</span>`;
        if (names) facesHtml += ` <span class="meta-value">${names}</span>`;
      }

      // Colors HTML
      let colorsHtml = '';
      if (img.color_palette && img.color_palette.length) {
        colorsHtml = `<div class="lightbox-colors">${img.color_palette.map(c => `<div style="flex:1;background:${c};height:100%"></div>`).join('')}</div>`;
      }

      // Tags HTML
      let tagsHtml = '<span class="meta-value muted">None detected</span>';
      if (img.detected_objects && img.detected_objects.length) {
        tagsHtml = `<div class="meta-tags">${img.detected_objects.map(t => `<span class="meta-tag">${t}</span>`).join('')}</div>`;
      }

      // Species HTML
      let speciesHtml = '<span class="meta-value muted">None detected</span>';
      if (img.species_tags && img.species_tags.length) {
        speciesHtml = `<div class="meta-tags">${img.species_tags.map(t => `<span class="meta-tag species">${t}</span>`).join('')}</div>`;
      }

      // GPS coordinates
      let coordsHtml = '<span class="meta-value muted">Not available</span>';
      let mapLink = '';
      if (img.gps_lat && img.gps_lon) {
        coordsHtml = `<span class="meta-value">${img.gps_lat.toFixed(5)}, ${img.gps_lon.toFixed(5)}</span>`;
        mapLink = `<a href="https://maps.google.com/?q=${img.gps_lat},${img.gps_lon}" target="_blank">Open in Google Maps &#x2197;</a>`;
      }

      // Quality section
      let qualityHtml = '';
      if (img.quality_score !== null && img.quality_score !== undefined) {
        qualityHtml = `
          <div class="meta-section">
            <div class="meta-section-title">&#x2B50; Quality Analysis</div>
            <div class="quality-meters">
              ${qualityMeter('Overall', img.quality_score)}
              ${qualityMeter('Exposure', img.exposure_score)}
              ${qualityMeter('Contrast', img.contrast_score)}
              ${qualityMeter('Sharpness', img.sharpness_score)}
              ${qualityMeter('Noise', img.noise_score)}
              ${qualityMeter('Color', img.color_balance_score)}
            </div>
            ${img.quality_notes ? `<div style="margin-top:8px;font-size:0.75rem;color:var(--muted);">${img.quality_notes}</div>` : ''}
          </div>`;
      }

      // Vision caption section
      let visionHtml = '';
      if (img.vision_caption) {
        visionHtml = `
          <div class="meta-section">
            <div class="meta-section-title">&#x1F916; AI Vision Analysis</div>
            <div class="meta-value highlight">${img.vision_caption}</div>
          </div>`;
      }

      // Build the full metadata panel
      lightboxMeta.innerHTML = `
        <div class="lightbox-header">
          <div class="lightbox-filename">${img.image_name || 'Unknown'}</div>
          <h2 class="lightbox-caption">${getSmartTitle(img)}</h2>
          ${colorsHtml}
        </div>

        <div class="meta-section">
          <div class="meta-section-title">&#x1F4CD; Location</div>
          <div class="meta-grid">
            <div class="meta-item full-width">
              <span class="meta-label">Address</span>
              <span class="meta-value">${img.location_full || img.location_short || "Unknown"}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Coordinates</span>
              ${coordsHtml}
            </div>
            <div class="meta-item">
              <span class="meta-label">Trip Day</span>
              <span class="meta-value">Day ${img.day_number || '?'}</span>
            </div>
          </div>
          ${mapLink ? `<div style="margin-top:8px;font-size:0.8rem;">${mapLink}</div>` : ''}
        </div>

        <div class="meta-section">
          <div class="meta-section-title">&#x1F4F7; Camera Info</div>
          <div class="meta-grid">
            <div class="meta-item">
              <span class="meta-label">Device</span>
              <span class="meta-value">${img.device_model || "Unknown"}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Captured</span>
              <span class="meta-value">${img.time || "Unknown"}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Type</span>
              <span class="meta-value">${img.image_type || "Unknown"}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Path</span>
              <span class="meta-value" style="font-size:0.7rem;font-family:monospace;">${img.local_path || img.image_name}</span>
            </div>
          </div>
        </div>

        <div class="meta-section">
          <div class="meta-section-title">&#x1F3F7; Tags & Detection</div>
          <div class="meta-grid single-col">
            <div class="meta-item">
              <span class="meta-label">Objects</span>
              ${tagsHtml}
            </div>
            <div class="meta-item">
              <span class="meta-label">Species</span>
              ${speciesHtml}
            </div>
            <div class="meta-item">
              <span class="meta-label">Faces</span>
              ${facesHtml}
            </div>
          </div>
        </div>

        ${qualityHtml}
        ${visionHtml}
      `;

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
        lightboxMarker = L.circleMarker([img.gps_lat, img.gps_lon], {
          radius: 8,
          color: "#06b6d4",
          weight: 3,
          fillColor: "#06b6d4",
          fillOpacity: 0.8
        }).addTo(lightboxMap);
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
      if (active) active.scrollIntoView({ behavior: 'smooth', inline: 'center' });
    }

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (!lightbox.classList.contains('show')) {
        if (e.key === '/' && e.target.tagName !== 'INPUT') {
          e.preventDefault();
          searchInput.focus();
        }
        return;
      }
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