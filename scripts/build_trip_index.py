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
  <title>MemoGraph - Your Travel Memories</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
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
      --chip-bg: rgba(148, 163, 184, 0.1);
      --chip-border: rgba(148, 163, 184, 0.2);
      --gradient-1: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%);
      --gradient-2: linear-gradient(135deg, #f472b6 0%, #fb923c 100%);
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
    }}

    /* Animated Background */
    .bg-effects {{
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
      overflow: hidden;
    }}
    .bg-effects::before {{
      content: '';
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background:
        radial-gradient(ellipse 600px 600px at 20% 20%, rgba(6, 182, 212, 0.08), transparent),
        radial-gradient(ellipse 500px 500px at 80% 10%, rgba(139, 92, 246, 0.08), transparent),
        radial-gradient(ellipse 400px 400px at 60% 80%, rgba(244, 114, 182, 0.05), transparent);
      animation: bgFloat 20s ease-in-out infinite;
    }}
    @keyframes bgFloat {{
      0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
      25% {{ transform: translate(2%, 2%) rotate(1deg); }}
      50% {{ transform: translate(-1%, 3%) rotate(-1deg); }}
      75% {{ transform: translate(1%, -2%) rotate(0.5deg); }}
    }}

    /* Floating Particles */
    .particles {{
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
    }}
    .particle {{
      position: absolute;
      width: 4px;
      height: 4px;
      background: var(--accent);
      border-radius: 50%;
      opacity: 0.3;
      animation: float 15s infinite ease-in-out;
    }}
    .particle:nth-child(1) {{ left: 10%; top: 20%; animation-delay: 0s; animation-duration: 18s; }}
    .particle:nth-child(2) {{ left: 20%; top: 60%; animation-delay: -2s; animation-duration: 22s; }}
    .particle:nth-child(3) {{ left: 40%; top: 30%; animation-delay: -4s; animation-duration: 16s; }}
    .particle:nth-child(4) {{ left: 60%; top: 70%; animation-delay: -6s; animation-duration: 20s; }}
    .particle:nth-child(5) {{ left: 80%; top: 40%; animation-delay: -8s; animation-duration: 24s; }}
    .particle:nth-child(6) {{ left: 90%; top: 80%; animation-delay: -10s; animation-duration: 19s; }}
    @keyframes float {{
      0%, 100% {{ transform: translateY(0) scale(1); opacity: 0.3; }}
      50% {{ transform: translateY(-100px) scale(1.5); opacity: 0.6; }}
    }}

    /* Main Content */
    .main-content {{
      position: relative;
      z-index: 1;
    }}

    /* Navigation Bar */
    .navbar {{
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 5vw;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(3, 7, 17, 0.8);
      backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--card-border);
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: inherit;
    }}
    .logo-icon {{
      width: 42px;
      height: 42px;
      background: var(--gradient-1);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 4px 20px var(--accent-glow);
    }}
    .logo-text {{
      font-family: "Playfair Display", serif;
      font-size: 1.5rem;
      font-weight: 700;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .nav-actions {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .nav-btn {{
      padding: 10px 18px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      background: var(--card);
      color: var(--text-secondary);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s ease;
    }}
    .nav-btn:hover {{
      background: var(--card-hover);
      color: var(--accent);
      border-color: var(--accent);
      transform: scale(1.02);
    }}
    .nav-btn.features-btn {{
      background: var(--gradient-1);
      border: none;
      color: white;
      font-weight: 600;
    }}
    .nav-btn.features-btn:hover {{
      transform: scale(1.05);
      box-shadow: 0 4px 20px var(--accent-glow);
    }}
    .info-btn {{
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 1px solid var(--card-border);
      background: var(--card);
      color: var(--text-secondary);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      font-weight: 600;
      transition: all 0.2s ease;
    }}
    .info-btn:hover {{
      background: var(--card-hover);
      color: var(--accent);
      border-color: var(--accent);
      transform: scale(1.05);
    }}

    /* Hero Section */
    .hero {{
      padding: 60px 5vw 40px;
      text-align: center;
    }}
    .hero-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      border-radius: 999px;
      font-size: 0.85rem;
      color: var(--text-secondary);
      margin-bottom: 24px;
    }}
    .hero-badge-dot {{
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.5; transform: scale(1.2); }}
    }}
    .hero h1 {{
      font-family: "Playfair Display", serif;
      font-size: clamp(2.5rem, 6vw, 4rem);
      font-weight: 700;
      line-height: 1.1;
      margin-bottom: 16px;
    }}
    .hero h1 span {{
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .hero-subtitle {{
      font-size: 1.15rem;
      color: var(--text-secondary);
      max-width: 600px;
      margin: 0 auto 40px;
      line-height: 1.6;
    }}

    /* Stats Bar */
    .stats-bar {{
      display: flex;
      justify-content: center;
      gap: 48px;
      flex-wrap: wrap;
      padding: 32px 5vw;
      margin-bottom: 20px;
    }}
    .stat-item {{
      text-align: center;
    }}
    .stat-value {{
      font-size: 2.5rem;
      font-weight: 700;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      line-height: 1;
    }}
    .stat-label {{
      font-size: 0.9rem;
      color: var(--muted);
      margin-top: 8px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}

    /* Search & Controls */
    .controls {{
      padding: 0 5vw 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .search-box {{
      position: relative;
      flex: 1;
      max-width: 400px;
    }}
    .search-box input {{
      width: 100%;
      padding: 14px 20px 14px 48px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
      transition: all 0.2s ease;
    }}
    .search-box input::placeholder {{
      color: var(--muted);
    }}
    .search-box input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }}
    .search-icon {{
      position: absolute;
      left: 16px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: 18px;
    }}
    .view-controls {{
      display: flex;
      gap: 8px;
    }}
    .view-btn {{
      padding: 12px 20px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }}
    .view-btn:hover, .view-btn.active {{
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .sort-select {{
      padding: 12px 16px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      color: var(--text);
      font-size: 0.9rem;
      cursor: pointer;
      outline: none;
    }}
    .sort-select:focus {{
      border-color: var(--accent);
    }}

    /* Grid */
    .grid {{
      padding: 0 5vw 60px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 24px;
    }}

    /* Trip Cards */
    .trip-card {{
      background: var(--card);
      border-radius: 24px;
      padding: 20px;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 20px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
    }}
    .trip-card::before {{
      content: '';
      position: absolute;
      inset: 0;
      background: var(--gradient-1);
      opacity: 0;
      transition: opacity 0.3s ease;
      z-index: 0;
    }}
    .trip-card:hover {{
      transform: translateY(-8px);
      border-color: var(--accent);
      box-shadow: 0 20px 50px rgba(6, 182, 212, 0.15), 0 10px 30px rgba(0, 0, 0, 0.3);
    }}
    .trip-card:hover::before {{
      opacity: 0.03;
    }}
    .trip-card > * {{
      position: relative;
      z-index: 1;
    }}

    /* Thumbnail Gallery */
    .thumb-gallery {{
      position: relative;
      height: 200px;
      border-radius: 16px;
      overflow: hidden;
      background: var(--bg-secondary);
    }}
    .thumb-main {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.4s ease;
    }}
    .trip-card:hover .thumb-main {{
      transform: scale(1.05);
    }}
    .thumb-overlay {{
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, transparent 50%, rgba(0,0,0,0.7) 100%);
    }}
    .thumb-count {{
      position: absolute;
      bottom: 12px;
      right: 12px;
      padding: 6px 12px;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(10px);
      border-radius: 999px;
      font-size: 0.85rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .thumb-mini-stack {{
      position: absolute;
      bottom: 12px;
      left: 12px;
      display: flex;
      gap: -8px;
    }}
    .thumb-mini {{
      width: 36px;
      height: 36px;
      border-radius: 8px;
      object-fit: cover;
      border: 2px solid var(--card);
      margin-left: -8px;
    }}
    .thumb-mini:first-child {{
      margin-left: 0;
    }}

    /* Trip Info */
    .trip-info {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .trip-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
    }}
    .trip-title {{
      font-size: 1.3rem;
      font-weight: 600;
      line-height: 1.3;
      color: var(--text);
    }}
    .trip-location {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      background: var(--chip-bg);
      border-radius: 8px;
      font-size: 0.8rem;
      color: var(--text-secondary);
      white-space: nowrap;
    }}
    .trip-dates {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .trip-dates svg {{
      width: 16px;
      height: 16px;
    }}
    .trip-stats {{
      display: flex;
      gap: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--card-border);
    }}
    .trip-stat {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.85rem;
      color: var(--text-secondary);
    }}
    .trip-stat svg {{
      width: 16px;
      height: 16px;
      color: var(--accent);
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }}
    .chip {{
      padding: 6px 12px;
      border-radius: 8px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      color: var(--text-secondary);
      font-size: 0.8rem;
      font-weight: 500;
      transition: all 0.2s ease;
    }}
    .chip:hover {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}

    /* Footer */
    footer {{
      padding: 40px 5vw;
      border-top: 1px solid var(--card-border);
      text-align: center;
    }}
    .footer-brand {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .footer-logo {{
      width: 32px;
      height: 32px;
      background: var(--gradient-1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }}
    .footer-name {{
      font-family: "Playfair Display", serif;
      font-size: 1.2rem;
      font-weight: 600;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .footer-credit {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .footer-credit a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .footer-credit a:hover {{
      text-decoration: underline;
    }}

    /* Info Modal */
    .modal-overlay {{
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(8px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-overlay.active {{
      display: flex;
    }}
    .modal {{
      background: var(--card);
      border-radius: 24px;
      padding: 40px;
      max-width: 500px;
      width: 100%;
      border: 1px solid var(--card-border);
      position: relative;
      animation: modalIn 0.3s ease;
    }}
    @keyframes modalIn {{
      from {{ opacity: 0; transform: scale(0.9) translateY(20px); }}
      to {{ opacity: 1; transform: scale(1) translateY(0); }}
    }}
    .modal-close {{
      position: absolute;
      top: 16px;
      right: 16px;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: none;
      background: var(--chip-bg);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }}
    .modal-close:hover {{
      background: var(--accent);
      color: var(--bg);
    }}
    .modal-icon {{
      width: 64px;
      height: 64px;
      background: var(--gradient-1);
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      margin-bottom: 24px;
      box-shadow: 0 8px 32px var(--accent-glow);
    }}
    .modal h2 {{
      font-family: "Playfair Display", serif;
      font-size: 1.8rem;
      margin-bottom: 8px;
    }}
    .modal-subtitle {{
      color: var(--muted);
      margin-bottom: 24px;
    }}
    .modal-features {{
      list-style: none;
      margin-bottom: 24px;
    }}
    .modal-features li {{
      padding: 12px 0;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--text-secondary);
    }}
    .modal-features li:last-child {{
      border-bottom: none;
    }}
    .modal-features li svg {{
      color: var(--accent);
      flex-shrink: 0;
    }}
    .modal-author {{
      padding: 20px;
      background: var(--bg-secondary);
      border-radius: 16px;
      text-align: center;
    }}
    .modal-author-label {{
      font-size: 0.8rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 8px;
    }}
    .modal-author-name {{
      font-size: 1.2rem;
      font-weight: 600;
      background: var(--gradient-2);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}

    /* Features Modal */
    .features-overlay {{
      position: fixed;
      inset: 0;
      background: rgba(3, 7, 17, 0.95);
      backdrop-filter: blur(20px);
      z-index: 2000;
      display: none;
      overflow-y: auto;
      padding: 20px;
    }}
    .features-overlay.active {{
      display: block;
    }}
    .features-container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px 0 60px;
    }}
    .features-header {{
      text-align: center;
      padding: 40px 20px 60px;
    }}
    .features-close {{
      position: fixed;
      top: 20px;
      right: 20px;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      border: none;
      background: var(--card);
      color: var(--text);
      cursor: pointer;
      font-size: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
      z-index: 10;
    }}
    .features-close:hover {{
      background: var(--accent);
      transform: rotate(90deg);
    }}
    .features-logo {{
      width: 80px;
      height: 80px;
      background: var(--gradient-1);
      border-radius: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 40px;
      margin: 0 auto 24px;
      box-shadow: 0 8px 40px var(--accent-glow);
    }}
    .features-header h1 {{
      font-family: "Playfair Display", serif;
      font-size: clamp(2rem, 5vw, 3.5rem);
      margin-bottom: 16px;
    }}
    .features-header h1 span {{
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .features-tagline {{
      font-size: 1.2rem;
      color: var(--text-secondary);
      max-width: 600px;
      margin: 0 auto 32px;
    }}
    .features-badges {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .feature-badge {{
      padding: 10px 20px;
      border-radius: 999px;
      font-size: 0.9rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .feature-badge.privacy {{
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
    }}
    .feature-badge.offline {{
      background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
      color: white;
    }}
    .feature-badge.ai {{
      background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
      color: white;
    }}
    .feature-badge.gpu {{
      background: linear-gradient(135deg, #f472b6 0%, #ec4899 100%);
      color: white;
    }}
    .features-section {{
      margin-bottom: 48px;
    }}
    .features-section-title {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1.3rem;
      font-weight: 600;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 2px solid var(--card-border);
    }}
    .features-section-icon {{
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }}
    .features-section-icon.privacy {{ background: linear-gradient(135deg, #10b981, #059669); }}
    .features-section-icon.ai {{ background: linear-gradient(135deg, #06b6d4, #0891b2); }}
    .features-section-icon.nature {{ background: linear-gradient(135deg, #22c55e, #16a34a); }}
    .features-section-icon.scene {{ background: linear-gradient(135deg, #f59e0b, #d97706); }}
    .features-section-icon.people {{ background: linear-gradient(135deg, #ec4899, #db2777); }}
    .features-section-icon.quality {{ background: linear-gradient(135deg, #8b5cf6, #7c3aed); }}
    .features-section-icon.output {{ background: linear-gradient(135deg, #3b82f6, #2563eb); }}
    .features-section-icon.tech {{ background: linear-gradient(135deg, #64748b, #475569); }}
    .features-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 10px;
    }}
    .feature-chip {{
      padding: 12px 16px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      font-size: 0.85rem;
      color: var(--text-secondary);
      text-align: center;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .feature-chip:hover {{
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
      transform: translateY(-2px);
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
    .status-dot.done {{
      background: #10b981;
      box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
    }}
    .status-dot.partial {{
      background: #f59e0b;
      box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
    }}
    .status-dot.todo {{
      background: #ef4444;
      box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
    }}
    .features-legend {{
      display: flex;
      justify-content: center;
      gap: 32px;
      flex-wrap: wrap;
      margin-bottom: 24px;
      padding: 16px;
      background: var(--card);
      border-radius: 12px;
      border: 1px solid var(--card-border);
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--text-secondary);
    }}
    .features-footer {{
      text-align: center;
      padding: 40px 20px;
      border-top: 1px solid var(--card-border);
      margin-top: 40px;
    }}
    .features-footer-text {{
      font-size: 1.1rem;
      color: var(--text-secondary);
      margin-bottom: 24px;
    }}
    .features-footer-brand {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
    }}
    .features-footer-logo {{
      width: 36px;
      height: 36px;
      background: var(--gradient-1);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
    }}
    .features-footer-name {{
      font-family: "Playfair Display", serif;
      font-size: 1.3rem;
      font-weight: 700;
      background: var(--gradient-1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}

    /* Global Search */
    .global-search {{
      padding: 0 5vw 32px;
    }}
    .search-container {{
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .search-header {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;
    }}
    .search-input-wrap {{
      flex: 1;
      position: relative;
    }}
    .search-input-wrap input {{
      width: 100%;
      padding: 16px 20px 16px 50px;
      background: var(--bg-secondary);
      border: 2px solid var(--card-border);
      border-radius: 14px;
      color: var(--text);
      font-size: 1.1rem;
      outline: none;
      transition: all 0.2s ease;
    }}
    .search-input-wrap input::placeholder {{
      color: var(--muted);
    }}
    .search-input-wrap input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-glow);
    }}
    .search-input-wrap .search-icon {{
      position: absolute;
      left: 18px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: 20px;
    }}
    /* Autocomplete Dropdown */
    .autocomplete-dropdown {{
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      margin-top: 4px;
      max-height: 300px;
      overflow-y: auto;
      z-index: 100;
      display: none;
      box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    }}
    .autocomplete-dropdown.active {{
      display: block;
    }}
    .autocomplete-item {{
      padding: 12px 16px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--card-border);
      transition: background 0.1s ease;
    }}
    .autocomplete-item:last-child {{
      border-bottom: none;
    }}
    .autocomplete-item:hover, .autocomplete-item.selected {{
      background: var(--card-hover);
    }}
    .autocomplete-item .icon {{
      font-size: 16px;
      opacity: 0.7;
    }}
    .autocomplete-item .text {{
      flex: 1;
    }}
    .autocomplete-item .text .match {{
      color: var(--accent);
      font-weight: 600;
    }}
    .autocomplete-item .count {{
      font-size: 0.8rem;
      color: var(--muted);
      background: var(--chip-bg);
      padding: 2px 8px;
      border-radius: 999px;
    }}
    .autocomplete-section {{
      padding: 8px 16px;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      background: var(--bg-secondary);
    }}
    /* Spell Suggestion */
    .spell-suggestion {{
      display: none;
      padding: 12px 16px;
      margin-top: 8px;
      background: var(--chip-bg);
      border-radius: 10px;
      font-size: 0.9rem;
      color: var(--text-secondary);
    }}
    .spell-suggestion.active {{
      display: block;
    }}
    .spell-suggestion a {{
      color: var(--accent);
      text-decoration: underline;
      cursor: pointer;
      font-weight: 600;
    }}
    .spell-suggestion a:hover {{
      color: var(--accent-secondary);
    }}
    /* Search Branding */
    .search-brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .search-brand-icon {{
      width: 40px;
      height: 40px;
      background: var(--gradient-2);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }}
    .search-brand-name {{
      font-family: "Playfair Display", serif;
      font-size: 1.4rem;
      font-weight: 600;
      background: var(--gradient-2);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .search-brand-tagline {{
      font-size: 0.85rem;
      color: var(--muted);
    }}
    /* Results Grouping */
    .results-groups {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }}
    .results-group-btn {{
      padding: 8px 16px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      border-radius: 999px;
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 0.85rem;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }}
    .results-group-btn:hover, .results-group-btn.active {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}
    .results-group-btn .count {{
      background: rgba(255,255,255,0.2);
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.75rem;
    }}
    /* Search Lightbox */
    .search-lightbox {{
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.95);
      z-index: 4000;
      display: none;
      flex-direction: column;
    }}
    .search-lightbox.active {{
      display: flex;
    }}
    .search-lightbox-header {{
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(0,0,0,0.5);
    }}
    .search-lightbox-info {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .search-lightbox-trip {{
      font-size: 0.9rem;
      color: var(--accent);
      font-weight: 600;
    }}
    .search-lightbox-caption {{
      font-size: 1rem;
      color: var(--text);
      max-width: 500px;
    }}
    .search-lightbox-counter {{
      font-size: 0.8rem;
      color: var(--muted);
    }}
    .search-lightbox-actions {{
      display: flex;
      gap: 12px;
    }}
    .search-lightbox-btn {{
      padding: 10px 20px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      background: var(--card);
      color: var(--text);
      cursor: pointer;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }}
    .search-lightbox-btn:hover {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}
    .search-lightbox-btn.close {{
      background: transparent;
      border: none;
      font-size: 28px;
      padding: 8px;
    }}
    .search-lightbox-body {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px 80px;
      position: relative;
      overflow: hidden;
      cursor: default;
    }}
    .search-lightbox-img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      border-radius: 8px;
      transition: transform 0.2s ease;
    }}
    .search-lightbox-zoom {{
      position: absolute;
      bottom: 20px;
      right: 20px;
      display: flex;
      gap: 8px;
      z-index: 10;
    }}
    .zoom-btn {{
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: none;
      background: rgba(255,255,255,0.15);
      color: white;
      cursor: pointer;
      font-size: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      backdrop-filter: blur(10px);
      transition: background 0.15s ease;
    }}
    .zoom-btn:hover {{
      background: var(--accent);
    }}
    .search-lightbox-nav {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 50px;
      height: 50px;
      border-radius: 50%;
      border: none;
      background: rgba(255,255,255,0.1);
      color: white;
      cursor: pointer;
      font-size: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
      backdrop-filter: blur(10px);
    }}
    .search-lightbox-nav:hover {{
      background: var(--accent);
    }}
    .search-lightbox-nav.prev {{ left: 20px; }}
    .search-lightbox-nav.next {{ right: 20px; }}
    .search-lightbox-filmstrip {{
      padding: 16px;
      background: rgba(0,0,0,0.5);
      display: flex;
      gap: 8px;
      overflow-x: auto;
      justify-content: center;
    }}
    .search-filmstrip-thumb {{
      width: 60px;
      height: 60px;
      border-radius: 8px;
      object-fit: cover;
      cursor: pointer;
      opacity: 0.5;
      transition: all 0.2s ease;
      border: 2px solid transparent;
    }}
    .search-filmstrip-thumb:hover {{
      opacity: 0.8;
    }}
    .search-filmstrip-thumb.active {{
      opacity: 1;
      border-color: var(--accent);
    }}
    .filter-toggle {{
      padding: 16px 24px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      border-radius: 12px;
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 0.95rem;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }}
    .filter-toggle:hover {{
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .filter-toggle.active {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}
    .quick-filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .quick-filter {{
      padding: 10px 18px;
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      border-radius: 999px;
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }}
    .quick-filter:hover {{
      background: var(--card-hover);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .quick-filter.active {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}
    .advanced-filters {{
      display: none;
      background: var(--bg-secondary);
      border-radius: 16px;
      padding: 24px;
      margin-top: 20px;
    }}
    .advanced-filters.active {{
      display: block;
    }}
    .filter-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 20px;
    }}
    .filter-group {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .filter-group label {{
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .filter-group select {{
      padding: 12px 16px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      color: var(--text);
      font-size: 0.95rem;
      cursor: pointer;
      outline: none;
    }}
    .filter-group select:focus {{
      border-color: var(--accent);
    }}
    .filter-checkboxes {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-height: 120px;
      overflow-y: auto;
    }}
    .filter-checkbox {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.85rem;
      color: var(--text-secondary);
      transition: all 0.2s ease;
    }}
    .filter-checkbox:hover {{
      border-color: var(--accent);
    }}
    .filter-checkbox.active {{
      background: var(--accent);
      color: var(--bg);
      border-color: var(--accent);
    }}
    .color-picker {{
      display: flex;
      gap: 8px;
    }}
    .color-swatch {{
      width: 32px;
      height: 32px;
      border-radius: 8px;
      cursor: pointer;
      border: 2px solid transparent;
      transition: all 0.2s ease;
    }}
    .color-swatch:hover, .color-swatch.active {{
      border-color: var(--text);
      transform: scale(1.1);
    }}
    .search-results {{
      display: none;
    }}
    .search-results.active {{
      display: block;
    }}
    .results-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px;
    }}
    .results-count {{
      font-size: 1.1rem;
      color: var(--text-secondary);
    }}
    .results-count strong {{
      color: var(--accent);
    }}
    .results-actions {{
      display: flex;
      gap: 12px;
    }}
    .results-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 16px;
      max-height: 600px;
      overflow-y: auto;
      padding: 4px;
    }}
    .result-card {{
      background: var(--card);
      border: 2px solid var(--card-border);
      border-radius: 16px;
      overflow: hidden;
      cursor: pointer;
      transition: border-color 0.15s ease;
      text-decoration: none;
      color: inherit;
    }}
    .result-card:hover {{
      border-color: var(--accent);
    }}
    .result-thumb {{
      width: 100%;
      aspect-ratio: 1;
      object-fit: cover;
      background: var(--bg-secondary);
      display: block;
    }}
    .result-info {{
      padding: 12px;
    }}
    .result-trip {{
      font-size: 0.75rem;
      color: var(--accent);
      font-weight: 600;
      margin-bottom: 4px;
    }}
    .result-name {{
      font-size: 0.85rem;
      color: var(--text-secondary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .result-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 8px;
    }}
    .result-tag {{
      font-size: 0.7rem;
      padding: 3px 8px;
      background: var(--chip-bg);
      border-radius: 6px;
      color: var(--muted);
    }}
    .no-results {{
      text-align: center;
      padding: 60px 20px;
      color: var(--muted);
    }}
    .no-results-icon {{
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.5;
    }}

    /* Slideshow Modal */
    .slideshow-overlay {{
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.95);
      z-index: 3000;
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}
    .slideshow-overlay.active {{
      display: flex;
    }}
    .slideshow-header {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      padding: 20px 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, transparent 100%);
      z-index: 10;
    }}
    .slideshow-info {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .slideshow-trip {{
      font-size: 0.9rem;
      color: var(--accent);
      font-weight: 600;
    }}
    .slideshow-caption {{
      font-size: 1rem;
      color: var(--text);
      max-width: 600px;
    }}
    .slideshow-counter {{
      font-size: 0.85rem;
      color: var(--muted);
      margin-top: 4px;
    }}
    .slideshow-close {{
      width: 48px;
      height: 48px;
      border-radius: 50%;
      border: none;
      background: var(--card);
      color: var(--text);
      cursor: pointer;
      font-size: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }}
    .slideshow-close:hover {{
      background: var(--accent);
      transform: scale(1.1);
    }}
    .slideshow-image-container {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 80px 60px;
      width: 100%;
    }}
    .slideshow-image {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      transition: opacity 0.3s ease;
    }}
    .slideshow-nav {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 60px;
      height: 60px;
      border-radius: 50%;
      border: none;
      background: rgba(255,255,255,0.1);
      color: white;
      cursor: pointer;
      font-size: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
      backdrop-filter: blur(10px);
    }}
    .slideshow-nav:hover {{
      background: var(--accent);
      transform: translateY(-50%) scale(1.1);
    }}
    .slideshow-nav.prev {{ left: 20px; }}
    .slideshow-nav.next {{ right: 20px; }}
    .slideshow-controls {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 20px 30px;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 20px;
      background: linear-gradient(0deg, rgba(0,0,0,0.8) 0%, transparent 100%);
    }}
    .slideshow-btn {{
      padding: 12px 24px;
      border-radius: 999px;
      border: none;
      background: var(--card);
      color: var(--text);
      cursor: pointer;
      font-size: 0.9rem;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }}
    .slideshow-btn:hover {{
      background: var(--accent);
      color: var(--bg);
    }}
    .slideshow-btn.active {{
      background: var(--accent);
      color: var(--bg);
    }}
    .slideshow-progress {{
      position: absolute;
      bottom: 0;
      left: 0;
      height: 3px;
      background: var(--accent);
      transition: width 0.1s linear;
    }}

    /* Empty State */
    .empty-state {{
      text-align: center;
      padding: 80px 20px;
    }}
    .empty-icon {{
      font-size: 64px;
      margin-bottom: 24px;
      opacity: 0.5;
    }}
    .empty-state h3 {{
      font-size: 1.5rem;
      margin-bottom: 8px;
    }}
    .empty-state p {{
      color: var(--muted);
    }}

    /* Responsive */
    @media (max-width: 768px) {{
      .hero {{
        padding: 40px 5vw 20px;
      }}
      .stats-bar {{
        gap: 32px;
      }}
      .stat-value {{
        font-size: 2rem;
      }}
      .controls {{
        flex-direction: column;
        align-items: stretch;
      }}
      .search-box {{
        max-width: none;
      }}
      .view-controls {{
        justify-content: center;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      .modal {{
        padding: 24px;
      }}
    }}
  </style>
</head>
<body>
  <!-- Background Effects -->
  <div class="bg-effects"></div>
  <div class="particles">
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
    <div class="particle"></div>
  </div>

  <div class="main-content">
    <!-- Navigation -->
    <nav class="navbar">
      <a href="#" class="logo">
        <div class="logo-icon">&#x1F4F7;</div>
        <span class="logo-text">MemoGraph</span>
      </a>
      <div class="nav-actions">
        <button class="nav-btn" onclick="startSlideshow()" title="Start Slideshow">&#x1F3AC; Slideshow</button>
        <button class="nav-btn features-btn" onclick="toggleFeatures()" title="View All Features">&#x2728; 170+ Features</button>
        <button class="info-btn" onclick="toggleModal()" title="About MemoGraph">i</button>
      </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-badge">
        <span class="hero-badge-dot"></span>
        <span>{trip_count} Trip{trip_suffix} Documented</span>
      </div>
      <h1>Your Travel <span>Memories</span></h1>
      <p class="hero-subtitle">Explore your journeys through AI-powered photo galleries. Each trip is automatically organized with locations, themes, and smart captions.</p>
    </section>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat-item">
        <div class="stat-value">{total_photos}</div>
        <div class="stat-label">Photos</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{total_days}</div>
        <div class="stat-label">Days</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{trip_count}</div>
        <div class="stat-label">Trips</div>
      </div>
    </div>

    <!-- Global Search - MemoLens -->
    <section class="global-search">
      <div class="search-container">
        <div class="search-brand">
          <div class="search-brand-icon">&#x1F50D;</div>
          <div>
            <div class="search-brand-name">MemoLens</div>
            <div class="search-brand-tagline">Search across all your memories</div>
          </div>
        </div>
        <div class="search-header">
          <div class="search-input-wrap">
            <span class="search-icon">&#x1F50D;</span>
            <input type="text" id="globalSearch" placeholder="Search all {total_photos} photos: butterfly, Nepal, 2025, mountain..."
                   onkeyup="handleGlobalSearch(event)"
                   oninput="handleAutocomplete(event)"
                   onfocus="showAutocomplete()"
                   autocomplete="off">
            <div class="autocomplete-dropdown" id="autocompleteDropdown"></div>
          </div>
          <button class="filter-toggle" onclick="toggleAdvancedFilters()">
            <span>&#x2699;</span> Filters
          </button>
        </div>
        <div class="spell-suggestion" id="spellSuggestion"></div>
        <div class="quick-filters">
          <button class="quick-filter" onclick="quickFilter('bird')">&#x1F426; Birds</button>
          <button class="quick-filter" onclick="quickFilter('mountain')">&#x26F0; Mountains</button>
          <button class="quick-filter" onclick="quickFilter('food')">&#x1F35C; Food</button>
          <button class="quick-filter" onclick="quickFilter('temple')">&#x1F6D5; Temples</button>
          <button class="quick-filter" onclick="quickFilter('flower')">&#x1F33A; Flowers</button>
          <button class="quick-filter" onclick="quickFilter('night')">&#x1F303; Night Sky</button>
          <button class="quick-filter" data-filter="faces" onclick="quickFilter('faces:1+')">&#x1F464; People</button>
          <button class="quick-filter" onclick="quickFilter('quality:70+')">&#x2B50; Best Quality</button>
        </div>
        <div class="advanced-filters" id="advancedFilters">
          <div class="filter-grid">
            <div class="filter-group">
              <label>&#x1F4C5; Year</label>
              <select id="filterYear" onchange="applyFilters()">
                <option value="">All Years</option>
              </select>
            </div>
            <div class="filter-group">
              <label>&#x1F4CD; Trip</label>
              <select id="filterTrip" onchange="applyFilters()">
                <option value="">All Trips</option>
              </select>
            </div>
            <div class="filter-group">
              <label>&#x1F4F7; Image Type</label>
              <select id="filterType" onchange="applyFilters()">
                <option value="">All Types</option>
                <option value="natural_photo">Natural Photo</option>
                <option value="screenshot">Screenshot</option>
                <option value="document_scan">Document</option>
              </select>
            </div>
            <div class="filter-group">
              <label>&#x2B50; Min Quality</label>
              <select id="filterQuality" onchange="applyFilters()">
                <option value="0">Any Quality</option>
                <option value="50">50%+</option>
                <option value="60">60%+</option>
                <option value="70">70%+</option>
                <option value="80">80%+</option>
              </select>
            </div>
            <div class="filter-group">
              <label>&#x1F464; Faces</label>
              <select id="filterFaces" onchange="applyFilters()">
                <option value="">Any</option>
                <option value="0">No Faces</option>
                <option value="1">1+ Face</option>
                <option value="2">2+ Faces (Group)</option>
              </select>
            </div>
            <div class="filter-group">
              <label>&#x23F0; Time of Day</label>
              <select id="filterTime" onchange="applyFilters()">
                <option value="">Any Time</option>
                <option value="morning">Morning</option>
                <option value="afternoon">Afternoon</option>
                <option value="evening">Evening</option>
                <option value="night">Night</option>
              </select>
            </div>
          </div>
        </div>
      </div>
      <div class="search-results" id="searchResults">
        <div class="results-header">
          <span class="results-count"><strong id="resultCount">0</strong> photos found</span>
          <div class="results-actions">
            <button class="quick-filter" onclick="clearSearch()">&#x2715; Clear Search</button>
          </div>
        </div>
        <div class="results-groups" id="resultsGroups"></div>
        <div class="results-grid" id="resultsGrid"></div>
        <div class="no-results" id="noResults" style="display:none;">
          <div class="no-results-icon">&#x1F50E;</div>
          <p>No photos match your search. Try different keywords or filters.</p>
        </div>
      </div>
    </section>

    <!-- Search Lightbox (MemoLens Viewer) -->
    <div class="search-lightbox" id="searchLightbox">
      <div class="search-lightbox-header">
        <div class="search-lightbox-info">
          <div class="search-lightbox-trip" id="searchLbTrip"></div>
          <div class="search-lightbox-caption" id="searchLbCaption"></div>
          <div class="search-lightbox-counter" id="searchLbCounter"></div>
        </div>
        <div class="search-lightbox-actions">
          <button class="search-lightbox-btn" id="searchLbGoToTrip" onclick="goToTripFromLightbox()">
            &#x1F4C2; Open Trip
          </button>
          <button class="search-lightbox-btn close" onclick="closeSearchLightbox()">&#x2715;</button>
        </div>
      </div>
      <div class="search-lightbox-body" onclick="if(event.target===this) closeSearchLightbox()">
        <button class="search-lightbox-nav prev" onclick="searchLightboxPrev()">&#x276E;</button>
        <img class="search-lightbox-img" id="searchLbImage" src="" alt="">
        <button class="search-lightbox-nav next" onclick="searchLightboxNext()">&#x276F;</button>
        <div class="search-lightbox-zoom">
          <button class="zoom-btn" onclick="zoomSearchImage(-1)" title="Zoom Out">&#x2212;</button>
          <button class="zoom-btn" onclick="zoomSearchImage(0)" title="Reset Zoom">&#x2299;</button>
          <button class="zoom-btn" onclick="zoomSearchImage(1)" title="Zoom In">&#x002B;</button>
        </div>
      </div>
      <div class="search-lightbox-filmstrip" id="searchLbFilmstrip"></div>
    </div>

    <!-- Trip Controls -->
    <div class="controls" id="tripControls">
      <div class="search-box">
        <span class="search-icon">&#x1F50D;</span>
        <input type="text" id="searchInput" placeholder="Filter trips by name..." onkeyup="filterTrips()">
      </div>
      <div class="view-controls">
        <select class="sort-select" id="sortSelect" onchange="sortTrips()">
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
          <option value="photos">Most Photos</option>
          <option value="name">Alphabetical</option>
        </select>
      </div>
    </div>

    <!-- Trip Grid -->
    <section class="grid" id="tripGrid">
      {cards}
    </section>

    <!-- Footer -->
    <footer>
      <div class="footer-brand">
        <div class="footer-logo">&#x1F4F7;</div>
        <span class="footer-name">MemoGraph</span>
      </div>
      <p class="footer-credit">Created with &#x2764; by <a href="#">Soham Bagayatkar</a></p>
    </footer>
  </div>

  <!-- Info Modal -->
  <div class="modal-overlay" id="infoModal" onclick="closeModalOutside(event)">
    <div class="modal">
      <button class="modal-close" onclick="toggleModal()">&#x2715;</button>
      <div class="modal-icon">&#x1F4F7;</div>
      <h2>MemoGraph</h2>
      <p class="modal-subtitle">AI-Powered Travel Memory Organizer</p>
      <ul class="modal-features">
        <li>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
          Auto-detect locations from GPS data
        </li>
        <li>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg>
          AI-generated captions for every photo
        </li>
        <li>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
          Face detection & recognition
        </li>
        <li>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18M3 12h18"></path></svg>
          Species & wildlife identification
        </li>
        <li>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><path d="M3 9h18M9 21V9"></path></svg>
          Interactive web galleries
        </li>
      </ul>
      <div class="modal-author">
        <div class="modal-author-label">Created By</div>
        <div class="modal-author-name">Soham Bagayatkar</div>
      </div>
    </div>
  </div>

  <!-- Features Showcase Modal -->
  <div class="features-overlay" id="featuresModal">
    <button class="features-close" onclick="toggleFeatures()">&#x2715;</button>
    <div class="features-container">
      <div class="features-header">
        <div class="features-logo">&#x1F4F7;</div>
        <h1>MemoGraph <span>Features</span></h1>
        <p class="features-tagline">Your Photos. Your Privacy. Your Memories.</p>
        <div class="features-badges">
          <span class="feature-badge privacy">&#x1F512; 100% Private</span>
          <span class="feature-badge offline">&#x1F4F4; Fully Offline</span>
          <span class="feature-badge ai">&#x1F916; 6 AI Models</span>
          <span class="feature-badge gpu">&#x26A1; GPU Accelerated</span>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon privacy">&#x1F512;</div>Privacy & Security</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>100% Offline</div><div class="feature-chip"><span class="status-dot done"></span>No Cloud Upload</div><div class="feature-chip"><span class="status-dot done"></span>Local Processing</div><div class="feature-chip"><span class="status-dot done"></span>Privacy First</div><div class="feature-chip"><span class="status-dot done"></span>No Internet</div><div class="feature-chip"><span class="status-dot done"></span>Data Stays Local</div><div class="feature-chip"><span class="status-dot done"></span>No Tracking</div><div class="feature-chip"><span class="status-dot done"></span>Self-Hosted</div><div class="feature-chip"><span class="status-dot done"></span>Open Source</div><div class="feature-chip"><span class="status-dot done"></span>No Analytics</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon ai">&#x1F916;</div>AI Models (6 Integrated)</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>CLIP Detection</div><div class="feature-chip"><span class="status-dot done"></span>BLIP Captioning</div><div class="feature-chip"><span class="status-dot done"></span>LLaVA Vision AI</div><div class="feature-chip"><span class="status-dot done"></span>Face Detection</div><div class="feature-chip"><span class="status-dot partial"></span>Face Recognition</div><div class="feature-chip"><span class="status-dot done"></span>Bird Classifier</div><div class="feature-chip"><span class="status-dot done"></span>Species Detector</div><div class="feature-chip"><span class="status-dot done"></span>Quality Analyzer</div><div class="feature-chip"><span class="status-dot done"></span>Color Extractor</div><div class="feature-chip"><span class="status-dot done"></span>Type Classifier</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon nature">&#x1F33F;</div>Nature & Wildlife (150+ Species)</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>60+ Bird Species</div><div class="feature-chip"><span class="status-dot partial"></span>Plant Detection</div><div class="feature-chip"><span class="status-dot partial"></span>Flower Species</div><div class="feature-chip"><span class="status-dot partial"></span>Tree Detection</div><div class="feature-chip"><span class="status-dot partial"></span>Insect Detection</div><div class="feature-chip"><span class="status-dot partial"></span>Butterfly Species</div><div class="feature-chip"><span class="status-dot done"></span>Animal Detection</div><div class="feature-chip"><span class="status-dot done"></span>Wildlife ID</div><div class="feature-chip"><span class="status-dot done"></span>Forest Scenes</div><div class="feature-chip"><span class="status-dot done"></span>Garden Detection</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon scene">&#x1F3D4;</div>Scenes & Objects (130+ Concepts)</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>Mountains</div><div class="feature-chip"><span class="status-dot done"></span>Beaches</div><div class="feature-chip"><span class="status-dot done"></span>Temples</div><div class="feature-chip"><span class="status-dot done"></span>Monuments</div><div class="feature-chip"><span class="status-dot done"></span>Cities</div><div class="feature-chip"><span class="status-dot done"></span>Markets</div><div class="feature-chip"><span class="status-dot done"></span>Food</div><div class="feature-chip"><span class="status-dot done"></span>Vehicles</div><div class="feature-chip"><span class="status-dot done"></span>Night Sky</div><div class="feature-chip"><span class="status-dot done"></span>Astrophotography</div><div class="feature-chip"><span class="status-dot done"></span>Sunsets</div><div class="feature-chip"><span class="status-dot done"></span>Golden Hour</div><div class="feature-chip"><span class="status-dot done"></span>Indoor Scenes</div><div class="feature-chip"><span class="status-dot done"></span>Road Trips</div><div class="feature-chip"><span class="status-dot done"></span>Hiking Trails</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon people">&#x1F464;</div>People & Portraits</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>Face Detection</div><div class="feature-chip"><span class="status-dot done"></span>Face Counting</div><div class="feature-chip"><span class="status-dot partial"></span>People Recognition</div><div class="feature-chip"><span class="status-dot done"></span>Group Photos</div><div class="feature-chip"><span class="status-dot done"></span>Selfie Detection</div><div class="feature-chip"><span class="status-dot partial"></span>Portrait Mode</div><div class="feature-chip"><span class="status-dot done"></span>Family Photos</div><div class="feature-chip"><span class="status-dot done"></span>Crowd Detection</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon quality">&#x2728;</div>Image Quality Analysis</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>Quality Scoring</div><div class="feature-chip"><span class="status-dot done"></span>Sharpness Check</div><div class="feature-chip"><span class="status-dot done"></span>Exposure Analysis</div><div class="feature-chip"><span class="status-dot done"></span>Contrast Check</div><div class="feature-chip"><span class="status-dot done"></span>Noise Detection</div><div class="feature-chip"><span class="status-dot done"></span>Color Balance</div><div class="feature-chip"><span class="status-dot done"></span>Best Photo Filter</div><div class="feature-chip"><span class="status-dot done"></span>Dominant Colors</div><div class="feature-chip"><span class="status-dot done"></span>Color Palettes</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon output">&#x1F4CA;</div>Output & Visualization</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>Interactive Maps</div><div class="feature-chip"><span class="status-dot done"></span>Photo Gallery</div><div class="feature-chip"><span class="status-dot done"></span>Lightbox Viewer</div><div class="feature-chip"><span class="status-dot done"></span>Filmstrip Nav</div><div class="feature-chip"><span class="status-dot done"></span>Filter System</div><div class="feature-chip"><span class="status-dot done"></span>Search Function</div><div class="feature-chip"><span class="status-dot done"></span>Blog Generation</div><div class="feature-chip"><span class="status-dot done"></span>JSON Export</div><div class="feature-chip"><span class="status-dot done"></span>CSV Database</div><div class="feature-chip"><span class="status-dot done"></span>Trip Overview</div><div class="feature-chip"><span class="status-dot done"></span>Thumbnails</div><div class="feature-chip"><span class="status-dot done"></span>Quality Meters</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon tech">&#x2699;</div>Technical Features</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot done"></span>GPU Accelerated</div><div class="feature-chip"><span class="status-dot done"></span>Batch Processing</div><div class="feature-chip"><span class="status-dot done"></span>Parallel Execution</div><div class="feature-chip"><span class="status-dot done"></span>Incremental Saves</div><div class="feature-chip"><span class="status-dot done"></span>Resume Support</div><div class="feature-chip"><span class="status-dot done"></span>Resource Monitor</div><div class="feature-chip"><span class="status-dot done"></span>Error Recovery</div><div class="feature-chip"><span class="status-dot done"></span>Backup System</div><div class="feature-chip"><span class="status-dot done"></span>EXIF Extraction</div><div class="feature-chip"><span class="status-dot done"></span>GPS Mapping</div><div class="feature-chip"><span class="status-dot done"></span>Day Grouping</div><div class="feature-chip"><span class="status-dot done"></span>Auto Tagging</div>
        </div>
      </div>
      <div class="features-section">
        <div class="features-section-title"><div class="features-section-icon tech" style="background: linear-gradient(135deg, #ef4444, #dc2626);">&#x1F680;</div>Coming Soon</div>
        <div class="features-grid">
          <div class="feature-chip"><span class="status-dot todo"></span>Semantic Search</div><div class="feature-chip"><span class="status-dot todo"></span>Cross-Trip Search</div><div class="feature-chip"><span class="status-dot todo"></span>Plant Classifier</div><div class="feature-chip"><span class="status-dot todo"></span>Insect Classifier</div><div class="feature-chip"><span class="status-dot todo"></span>OCR Text Extract</div><div class="feature-chip"><span class="status-dot todo"></span>Video Support</div>
        </div>
      </div>
      <div class="features-footer">
        <div class="features-legend">
          <div class="legend-item"><span class="status-dot done"></span>Complete</div>
          <div class="legend-item"><span class="status-dot partial"></span>In Progress</div>
          <div class="legend-item"><span class="status-dot todo"></span>Planned</div>
        </div>
        <p class="features-footer-text">170+ Features. Zero Cloud. Complete Privacy.</p>
        <div class="features-footer-brand">
          <div class="features-footer-logo">&#x1F4F7;</div>
          <span class="features-footer-name">MemoGraph</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Slideshow Modal -->
  <div class="slideshow-overlay" id="slideshowModal">
    <div class="slideshow-header">
      <div class="slideshow-info">
        <div class="slideshow-trip" id="slideshowTrip"></div>
        <div class="slideshow-caption" id="slideshowCaption"></div>
        <div class="slideshow-counter" id="slideshowCounter"></div>
      </div>
      <button class="slideshow-close" onclick="stopSlideshow()">&#x2715;</button>
    </div>
    <button class="slideshow-nav prev" onclick="slideshowPrev()">&#x276E;</button>
    <div class="slideshow-image-container" onclick="if(event.target===this) stopSlideshow()">
      <img class="slideshow-image" id="slideshowImage" src="" alt="">
    </div>
    <button class="slideshow-nav next" onclick="slideshowNext()">&#x276F;</button>
    <div class="slideshow-controls">
      <button class="slideshow-btn" id="slideshowPlayBtn" onclick="toggleSlideshowPlay()">
        <span id="playIcon">&#x25B6;</span> <span id="playText">Play</span>
      </button>
      <button class="slideshow-btn" onclick="shuffleSlideshow()">&#x1F500; Shuffle</button>
      <select class="slideshow-btn" id="slideshowSpeed" onchange="updateSlideshowSpeed()" style="appearance:none;padding-right:16px;">
        <option value="3000">3s</option>
        <option value="5000" selected>5s</option>
        <option value="8000">8s</option>
        <option value="10000">10s</option>
      </select>
    </div>
    <div class="slideshow-progress" id="slideshowProgress"></div>
  </div>

  <script>
    // Search index data - embedded directly to work with file:// protocol
    let searchIndex = {search_index_json};
    let searchResults = [];
    let slideshowImages = [];
    let slideshowIndex = 0;
    let slideshowInterval = null;

    // Autocomplete state
    let autocompleteIndex = -1;
    let autocompleteItems = [];
    let allSearchableTerms = [];

    // Load search index on page load (now just populates filters since data is embedded)
    function loadSearchIndex() {{
      if (searchIndex && searchIndex.images) {{
        populateFilters();
        // Prepare slideshow images
        slideshowImages = searchIndex.images.filter(img => img.thumbnail);
        // Build searchable terms for autocomplete
        buildSearchableTerms();
        console.log('Search index loaded:', searchIndex.stats);
      }}
    }}

    // Build list of all searchable terms for autocomplete
    function buildSearchableTerms() {{
      if (!searchIndex) return;
      const termCounts = {{}};

      // Add tags
      searchIndex.facets.top_tags.forEach(tag => {{
        termCounts[tag] = (termCounts[tag] || 0);
      }});

      // Add species
      searchIndex.facets.top_species.forEach(sp => {{
        termCounts[sp] = (termCounts[sp] || 0);
      }});

      // Add trips
      searchIndex.facets.trips.forEach(trip => {{
        const name = trip.replace(/_/g, ' ').toLowerCase();
        termCounts[name] = (termCounts[name] || 0);
      }});

      // Add locations
      searchIndex.facets.locations.slice(0, 20).forEach(loc => {{
        const parts = loc.split(',');
        parts.forEach(part => {{
          const p = part.trim().toLowerCase();
          if (p.length > 2) termCounts[p] = (termCounts[p] || 0);
        }});
      }});

      // Count occurrences
      searchIndex.images.forEach(img => {{
        img.tags.forEach(t => {{ termCounts[t] = (termCounts[t] || 0) + 1; }});
        img.species.forEach(s => {{ termCounts[s] = (termCounts[s] || 0) + 1; }});
      }});

      // Convert to sorted array
      allSearchableTerms = Object.entries(termCounts)
        .map(([term, count]) => ({{ term, count }}))
        .sort((a, b) => b.count - a.count);
    }}

    // Handle autocomplete input
    function handleAutocomplete(event) {{
      const query = event.target.value.trim().toLowerCase();
      const dropdown = document.getElementById('autocompleteDropdown');

      if (query.length < 2) {{
        dropdown.classList.remove('active');
        return;
      }}

      // Filter matching terms
      const matches = allSearchableTerms
        .filter(item => item.term.includes(query))
        .slice(0, 10);

      if (matches.length === 0) {{
        dropdown.classList.remove('active');
        return;
      }}

      // Build dropdown HTML
      autocompleteItems = matches;
      autocompleteIndex = -1;

      let html = '<div class="autocomplete-section">Suggestions</div>';
      matches.forEach((item, idx) => {{
        const highlighted = item.term.replace(
          new RegExp(`(${{query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')}})`, 'gi'),
          '<span class="match">$1</span>'
        );
        html += `<div class="autocomplete-item" data-index="${{idx}}" onclick="selectAutocomplete(${{idx}})">
          <span class="icon">&#x1F50D;</span>
          <span class="text">${{highlighted}}</span>
          <span class="count">${{item.count}}</span>
        </div>`;
      }});

      dropdown.innerHTML = html;
      dropdown.classList.add('active');
    }}

    // Show autocomplete (on focus)
    function showAutocomplete() {{
      const query = document.getElementById('globalSearch').value.trim();
      if (query.length >= 2) {{
        handleAutocomplete({{ target: {{ value: query }} }});
      }}
    }}

    // Select autocomplete item
    function selectAutocomplete(index) {{
      if (index >= 0 && index < autocompleteItems.length) {{
        const term = autocompleteItems[index].term;
        document.getElementById('globalSearch').value = term;
        document.getElementById('autocompleteDropdown').classList.remove('active');
        performSearch(term);
      }}
    }}

    // Navigate autocomplete with keyboard
    function navigateAutocomplete(direction) {{
      if (autocompleteItems.length === 0) return;

      autocompleteIndex += direction;
      if (autocompleteIndex < 0) autocompleteIndex = autocompleteItems.length - 1;
      if (autocompleteIndex >= autocompleteItems.length) autocompleteIndex = 0;

      // Update visual selection
      document.querySelectorAll('.autocomplete-item').forEach((item, idx) => {{
        item.classList.toggle('selected', idx === autocompleteIndex);
      }});
    }}

    // Levenshtein distance for spell correction
    function levenshtein(a, b) {{
      const matrix = [];
      for (let i = 0; i <= b.length; i++) {{ matrix[i] = [i]; }}
      for (let j = 0; j <= a.length; j++) {{ matrix[0][j] = j; }}
      for (let i = 1; i <= b.length; i++) {{
        for (let j = 1; j <= a.length; j++) {{
          if (b.charAt(i - 1) === a.charAt(j - 1)) {{
            matrix[i][j] = matrix[i - 1][j - 1];
          }} else {{
            matrix[i][j] = Math.min(
              matrix[i - 1][j - 1] + 1,
              matrix[i][j - 1] + 1,
              matrix[i - 1][j] + 1
            );
          }}
        }}
      }}
      return matrix[b.length][a.length];
    }}

    // Find spell correction suggestions
    function findSpellCorrection(query) {{
      if (query.length < 3) return null;

      let bestMatch = null;
      let bestDistance = Infinity;
      const maxDistance = Math.max(2, Math.floor(query.length / 3));

      for (const item of allSearchableTerms) {{
        if (item.term === query) return null; // Exact match, no suggestion
        const dist = levenshtein(query, item.term);
        if (dist < bestDistance && dist <= maxDistance && dist > 0) {{
          bestDistance = dist;
          bestMatch = item.term;
        }}
      }}

      return bestMatch;
    }}

    // Show spell suggestion
    function showSpellSuggestion(query) {{
      const suggestion = findSpellCorrection(query);
      const el = document.getElementById('spellSuggestion');

      if (suggestion && searchResults.length === 0) {{
        el.innerHTML = `Did you mean: <a onclick="useSpellSuggestion('${{suggestion}}')">${{suggestion}}</a>?`;
        el.classList.add('active');
      }} else {{
        el.classList.remove('active');
      }}
    }}

    // Use spell suggestion
    function useSpellSuggestion(term) {{
      document.getElementById('globalSearch').value = term;
      document.getElementById('spellSuggestion').classList.remove('active');
      performSearch(term);
    }}

    // ===== SEARCH LIGHTBOX (MemoLens Viewer) =====
    let searchLightboxIndex = 0;
    let currentTripFilter = null;

    function openSearchLightbox(index) {{
      searchLightboxIndex = index;
      document.getElementById('searchLightbox').classList.add('active');
      document.body.style.overflow = 'hidden';
      showSearchLightboxImage();
      buildSearchFilmstrip();
    }}

    function closeSearchLightbox() {{
      document.getElementById('searchLightbox').classList.remove('active');
      document.body.style.overflow = '';
    }}

    function showSearchLightboxImage() {{
      const results = getFilteredResults();
      if (results.length === 0) return;

      // Reset zoom on navigation
      currentZoom = 1;
      const imgEl = document.getElementById('searchLbImage');
      if (imgEl) imgEl.style.transform = 'scale(1)';

      const img = results[searchLightboxIndex];

      // Try full image first, fallback to thumbnail
      const fullPath = img.thumbnail.replace('/MemoGraph/thumbnails/', '/');
      imgEl.src = img.thumbnail;
      const fullImg = new Image();
      fullImg.onload = () => {{ imgEl.src = fullPath; }};
      fullImg.src = fullPath;

      // Update info
      document.getElementById('searchLbTrip').textContent = img.trip.replace(/_/g, ' ');
      document.getElementById('searchLbCaption').textContent =
        img.captions[0] || img.tags.slice(0, 3).join(', ') || img.filename;
      document.getElementById('searchLbCounter').textContent =
        `${{searchLightboxIndex + 1}} / ${{results.length}} in search results`;

      // Update filmstrip selection
      document.querySelectorAll('.search-filmstrip-thumb').forEach((thumb, idx) => {{
        thumb.classList.toggle('active', idx === searchLightboxIndex);
      }});
    }}

    function searchLightboxNext() {{
      const results = getFilteredResults();
      searchLightboxIndex = (searchLightboxIndex + 1) % results.length;
      showSearchLightboxImage();
    }}

    function searchLightboxPrev() {{
      const results = getFilteredResults();
      searchLightboxIndex = (searchLightboxIndex - 1 + results.length) % results.length;
      showSearchLightboxImage();
    }}

    function buildSearchFilmstrip() {{
      const results = getFilteredResults();
      const filmstrip = document.getElementById('searchLbFilmstrip');
      filmstrip.innerHTML = results.slice(0, 20).map((img, idx) =>
        `<img class="search-filmstrip-thumb ${{idx === searchLightboxIndex ? 'active' : ''}}"
              src="${{img.thumbnail}}" alt="" onclick="jumpToSearchImage(${{idx}})"
              onerror="this.style.display='none'">`
      ).join('');
      if (results.length > 20) {{
        filmstrip.innerHTML += `<div style="display:flex;align-items:center;padding:0 12px;color:var(--muted);font-size:0.8rem;">+${{results.length - 20}} more</div>`;
      }}
    }}

    function jumpToSearchImage(idx) {{
      searchLightboxIndex = idx;
      showSearchLightboxImage();
    }}

    let currentZoom = 1;
    function zoomSearchImage(direction) {{
      const imgEl = document.getElementById('searchLbImage');
      if (direction === 0) {{ currentZoom = 1; }}
      else if (direction > 0) {{ currentZoom = Math.min(currentZoom + 0.25, 3); }}
      else {{ currentZoom = Math.max(currentZoom - 0.25, 0.5); }}
      imgEl.style.transform = `scale(${{currentZoom}})`;
    }}

    function goToTripFromLightbox() {{
      const results = getFilteredResults();
      const img = results[searchLightboxIndex];
      window.location.href = `${{img.trip}}/MemoGraph/webapp/index.html#${{img.filename}}`;
    }}

    function getFilteredResults() {{
      if (currentTripFilter) {{
        return searchResults.filter(r => r.trip === currentTripFilter);
      }}
      return searchResults;
    }}

    // ===== RESULTS GROUPING =====
    function buildResultsGroups() {{
      const tripCounts = {{}};
      searchResults.forEach(img => {{
        tripCounts[img.trip] = (tripCounts[img.trip] || 0) + 1;
      }});

      const groupsEl = document.getElementById('resultsGroups');
      if (Object.keys(tripCounts).length <= 1) {{
        groupsEl.innerHTML = '';
        return;
      }}

      let html = `<button class="results-group-btn ${{!currentTripFilter ? 'active' : ''}}" onclick="filterByTrip(null)">
        All <span class="count">${{searchResults.length}}</span>
      </button>`;

      Object.entries(tripCounts)
        .sort((a, b) => b[1] - a[1])
        .forEach(([trip, count]) => {{
          const isActive = currentTripFilter === trip ? 'active' : '';
          const tripName = trip.replace(/_/g, ' ');
          html += `<button class="results-group-btn ${{isActive}}" onclick="filterByTrip('${{trip}}')">
            ${{tripName}} <span class="count">${{count}}</span>
          </button>`;
        }});

      groupsEl.innerHTML = html;
    }}

    function filterByTrip(trip) {{
      currentTripFilter = trip;
      buildResultsGroups();
      renderResultsGrid();
    }}

    // Populate filter dropdowns from search index
    function populateFilters() {{
      if (!searchIndex) return;

      const yearSelect = document.getElementById('filterYear');
      searchIndex.facets.years.forEach(year => {{
        const opt = document.createElement('option');
        opt.value = year;
        opt.textContent = year;
        yearSelect.appendChild(opt);
      }});

      const tripSelect = document.getElementById('filterTrip');
      searchIndex.facets.trips.forEach(trip => {{
        const opt = document.createElement('option');
        opt.value = trip;
        opt.textContent = trip.replace(/_/g, ' ');
        tripSelect.appendChild(opt);
      }});
    }}

    // Handle global search
    function handleGlobalSearch(event) {{
      const dropdown = document.getElementById('autocompleteDropdown');

      // Handle keyboard navigation
      if (event.key === 'ArrowDown') {{
        event.preventDefault();
        if (dropdown.classList.contains('active')) {{
          navigateAutocomplete(1);
        }}
        return;
      }}
      if (event.key === 'ArrowUp') {{
        event.preventDefault();
        if (dropdown.classList.contains('active')) {{
          navigateAutocomplete(-1);
        }}
        return;
      }}
      if (event.key === 'Escape') {{
        dropdown.classList.remove('active');
        return;
      }}

      // Handle Enter key
      if (event.key === 'Enter') {{
        dropdown.classList.remove('active');
        if (autocompleteIndex >= 0 && autocompleteItems.length > 0) {{
          selectAutocomplete(autocompleteIndex);
          return;
        }}
        const query = document.getElementById('globalSearch').value.trim();
        if (query.length >= 2) {{
          performSearch(query);
          showSpellSuggestion(query.toLowerCase());
        }} else if (query.length === 0) {{
          clearSearch();
        }}
      }}
    }}

    // Perform search
    function performSearch(query) {{
      if (!searchIndex) {{
        alert('Search index not loaded. Process trips first.');
        return;
      }}

      const lowerQuery = query.toLowerCase();
      const tokens = lowerQuery.split(/\s+/);

      // Parse special filters
      let minQuality = 0;
      let minFaces = -1;
      const textTokens = [];

      tokens.forEach(token => {{
        if (token.startsWith('quality:')) {{
          minQuality = parseInt(token.replace('quality:', '').replace('+', '')) || 0;
        }} else if (token.startsWith('faces:')) {{
          minFaces = parseInt(token.replace('faces:', '').replace('+', '')) || 0;
        }} else {{
          textTokens.push(token);
        }}
      }});

      const textQuery = textTokens.join(' ');

      // Filter images
      searchResults = searchIndex.images.filter(img => {{
        // Quality filter
        if (minQuality > 0 && img.quality < minQuality) return false;

        // Faces filter
        if (minFaces >= 0 && img.faces_count < minFaces) return false;

        // Text search
        if (textQuery && !img._search.includes(textQuery)) return false;

        return true;
      }});

      // Apply additional dropdown filters
      applyDropdownFilters();

      displayResults();
    }}

    // Apply dropdown filters
    function applyDropdownFilters() {{
      const year = document.getElementById('filterYear').value;
      const trip = document.getElementById('filterTrip').value;
      const type = document.getElementById('filterType').value;
      const quality = parseInt(document.getElementById('filterQuality').value) || 0;
      const faces = document.getElementById('filterFaces').value;
      const time = document.getElementById('filterTime').value;

      if (year || trip || type || quality || faces || time) {{
        searchResults = searchResults.filter(img => {{
          if (year && img.year != year) return false;
          if (trip && img.trip !== trip) return false;
          if (type && img.image_type !== type) return false;
          if (quality && img.quality < quality) return false;
          if (faces === '0' && img.faces_count !== 0) return false;
          if (faces === '1' && img.faces_count < 1) return false;
          if (faces === '2' && img.faces_count < 2) return false;
          if (time && img.time_of_day !== time && !img.time_of_day.includes(time)) return false;
          return true;
        }});
      }}
    }}

    // Apply filters from dropdowns
    function applyFilters() {{
      const query = document.getElementById('globalSearch').value.trim();
      if (query.length >= 2) {{
        performSearch(query);
      }} else if (searchIndex) {{
        // If no text query, search all with filters
        searchResults = [...searchIndex.images];
        applyDropdownFilters();
        if (searchResults.length < searchIndex.images.length) {{
          displayResults();
        }}
      }}
    }}

    // Quick filter buttons
    function quickFilter(filter) {{
      document.getElementById('globalSearch').value = filter;
      performSearch(filter);

      // Update button states
      document.querySelectorAll('.quick-filter').forEach(btn => {{
        btn.classList.remove('active');
        if (btn.textContent.toLowerCase().includes(filter.split(':')[0]) ||
            btn.getAttribute('onclick')?.includes(filter)) {{
          btn.classList.add('active');
        }}
      }});
    }}

    // Display search results
    function displayResults() {{
      const resultsSection = document.getElementById('searchResults');
      const noResults = document.getElementById('noResults');
      const countEl = document.getElementById('resultCount');
      const tripGrid = document.getElementById('tripGrid');
      const tripControls = document.getElementById('tripControls');

      // Hide autocomplete
      document.getElementById('autocompleteDropdown').classList.remove('active');
      currentTripFilter = null; // Reset trip filter

      resultsSection.classList.add('active');
      tripGrid.style.display = 'none';
      tripControls.style.display = 'none';

      countEl.textContent = searchResults.length;

      // Show spell suggestion for no results
      const query = document.getElementById('globalSearch').value.trim().toLowerCase();
      showSpellSuggestion(query);

      if (searchResults.length === 0) {{
        document.getElementById('resultsGrid').style.display = 'none';
        document.getElementById('resultsGroups').innerHTML = '';
        noResults.style.display = 'block';
        return;
      }}

      noResults.style.display = 'none';
      buildResultsGroups();
      renderResultsGrid();
    }}

    // Render results grid (called by displayResults and filterByTrip)
    function renderResultsGrid() {{
      const resultsGrid = document.getElementById('resultsGrid');
      const results = getFilteredResults();

      resultsGrid.style.display = 'grid';

      // Limit to first 100 for performance
      const displayItems = results.slice(0, 100);

      resultsGrid.innerHTML = displayItems.map((img, idx) => `
        <div class="result-card" onclick="openSearchLightbox(${{idx}})" title="${{img.filename}}">
          <img class="result-thumb" src="${{img.thumbnail}}" alt="${{img.filename}}" loading="lazy"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23334%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23666%22 font-size=%2214%22>No Thumb</text></svg>'">
          <div class="result-info">
            <div class="result-trip">${{img.trip.replace(/_/g, ' ')}}</div>
            <div class="result-name">${{img.filename}}</div>
            <div class="result-tags">
              ${{img.tags.slice(0, 3).map(t => `<span class="result-tag">${{t}}</span>`).join('')}}
            </div>
          </div>
        </div>
      `).join('');

      if (results.length > 100) {{
        resultsGrid.innerHTML += `<div style="grid-column: 1/-1; text-align: center; padding: 20px; color: var(--muted);">Showing first 100 of ${{results.length}} results</div>`;
      }}
    }}

    // Clear search
    function clearSearch() {{
      document.getElementById('globalSearch').value = '';
      document.getElementById('filterYear').value = '';
      document.getElementById('filterTrip').value = '';
      document.getElementById('filterType').value = '';
      document.getElementById('filterQuality').value = '0';
      document.getElementById('filterFaces').value = '';
      document.getElementById('filterTime').value = '';

      document.getElementById('searchResults').classList.remove('active');
      document.getElementById('tripGrid').style.display = '';
      document.getElementById('tripControls').style.display = '';

      document.querySelectorAll('.quick-filter').forEach(btn => btn.classList.remove('active'));

      searchResults = [];
    }}

    // Toggle advanced filters
    function toggleAdvancedFilters() {{
      const filters = document.getElementById('advancedFilters');
      const toggle = document.querySelector('.filter-toggle');
      filters.classList.toggle('active');
      toggle.classList.toggle('active');
    }}

    // Toggle info modal
    function toggleModal() {{
      const modal = document.getElementById('infoModal');
      modal.classList.toggle('active');
    }}

    // Toggle features modal
    function toggleFeatures() {{
      const modal = document.getElementById('featuresModal');
      modal.classList.toggle('active');
      document.body.style.overflow = modal.classList.contains('active') ? 'hidden' : '';
    }}

    // Close modal when clicking outside
    function closeModalOutside(event) {{
      if (event.target.classList.contains('modal-overlay')) {{
        toggleModal();
      }}
    }}

    // Filter trips by search
    function filterTrips() {{
      const query = document.getElementById('searchInput').value.toLowerCase();
      const cards = document.querySelectorAll('.trip-card');
      cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? '' : 'none';
      }});
    }}

    // Sort trips
    function sortTrips() {{
      const grid = document.getElementById('tripGrid');
      const cards = Array.from(grid.querySelectorAll('.trip-card'));
      const sortBy = document.getElementById('sortSelect').value;

      cards.sort((a, b) => {{
        switch(sortBy) {{
          case 'newest':
            return b.dataset.date.localeCompare(a.dataset.date);
          case 'oldest':
            return a.dataset.date.localeCompare(b.dataset.date);
          case 'photos':
            return parseInt(b.dataset.photos) - parseInt(a.dataset.photos);
          case 'name':
            return a.dataset.name.localeCompare(b.dataset.name);
          default:
            return 0;
        }}
      }});

      cards.forEach(card => grid.appendChild(card));
    }}

    // ===== SLIDESHOW FUNCTIONS =====
    function startSlideshow() {{
      if (!slideshowImages.length) {{
        alert('No images available for slideshow. Process some trips first.');
        return;
      }}
      slideshowIndex = 0;
      document.getElementById('slideshowModal').classList.add('active');
      document.body.style.overflow = 'hidden';
      showSlideshowImage();
    }}

    function stopSlideshow() {{
      document.getElementById('slideshowModal').classList.remove('active');
      document.body.style.overflow = '';
      pauseSlideshow();
    }}

    function showSlideshowImage() {{
      if (!slideshowImages.length) return;
      const img = slideshowImages[slideshowIndex];
      const imgEl = document.getElementById('slideshowImage');

      // Use full image path (not thumbnail) if available
      const fullPath = img.thumbnail.replace('/MemoGraph/thumbnails/', '/');
      imgEl.src = img.thumbnail; // Start with thumbnail for quick load

      // Try to load full image
      const fullImg = new Image();
      fullImg.onload = () => {{ imgEl.src = fullPath; }};
      fullImg.src = fullPath;

      document.getElementById('slideshowTrip').textContent = img.trip.replace(/_/g, ' ');
      document.getElementById('slideshowCaption').textContent = img.caption || img.tags.slice(0, 3).join(', ') || img.filename;
      document.getElementById('slideshowCounter').textContent = `${{slideshowIndex + 1}} / ${{slideshowImages.length}}`;
    }}

    function slideshowNext() {{
      slideshowIndex = (slideshowIndex + 1) % slideshowImages.length;
      showSlideshowImage();
      resetSlideshowProgress();
    }}

    function slideshowPrev() {{
      slideshowIndex = (slideshowIndex - 1 + slideshowImages.length) % slideshowImages.length;
      showSlideshowImage();
      resetSlideshowProgress();
    }}

    function toggleSlideshowPlay() {{
      if (slideshowInterval) {{
        pauseSlideshow();
      }} else {{
        playSlideshow();
      }}
    }}

    function playSlideshow() {{
      const speed = parseInt(document.getElementById('slideshowSpeed').value);
      slideshowInterval = setInterval(() => {{
        slideshowNext();
      }}, speed);
      document.getElementById('playIcon').innerHTML = '&#x23F8;';
      document.getElementById('playText').textContent = 'Pause';
      document.getElementById('slideshowPlayBtn').classList.add('active');
      startProgressBar();
    }}

    function pauseSlideshow() {{
      if (slideshowInterval) {{
        clearInterval(slideshowInterval);
        slideshowInterval = null;
      }}
      document.getElementById('playIcon').innerHTML = '&#x25B6;';
      document.getElementById('playText').textContent = 'Play';
      document.getElementById('slideshowPlayBtn').classList.remove('active');
      document.getElementById('slideshowProgress').style.width = '0%';
    }}

    function updateSlideshowSpeed() {{
      if (slideshowInterval) {{
        pauseSlideshow();
        playSlideshow();
      }}
    }}

    function shuffleSlideshow() {{
      // Fisher-Yates shuffle
      for (let i = slideshowImages.length - 1; i > 0; i--) {{
        const j = Math.floor(Math.random() * (i + 1));
        [slideshowImages[i], slideshowImages[j]] = [slideshowImages[j], slideshowImages[i]];
      }}
      slideshowIndex = 0;
      showSlideshowImage();
    }}

    let progressInterval = null;
    function startProgressBar() {{
      if (progressInterval) clearInterval(progressInterval);
      const speed = parseInt(document.getElementById('slideshowSpeed').value);
      const progressEl = document.getElementById('slideshowProgress');
      let progress = 0;
      const step = 100 / (speed / 50);
      progressEl.style.width = '0%';
      progressInterval = setInterval(() => {{
        progress += step;
        progressEl.style.width = Math.min(progress, 100) + '%';
        if (progress >= 100) {{
          progress = 0;
        }}
      }}, 50);
    }}

    function resetSlideshowProgress() {{
      if (progressInterval) {{
        const progressEl = document.getElementById('slideshowProgress');
        progressEl.style.width = '0%';
      }}
    }}

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {{
      // Search Lightbox controls
      const searchLightboxActive = document.getElementById('searchLightbox').classList.contains('active');
      if (searchLightboxActive) {{
        if (e.key === 'Escape') {{ closeSearchLightbox(); return; }}
        if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); searchLightboxNext(); return; }}
        if (e.key === 'ArrowLeft') {{ e.preventDefault(); searchLightboxPrev(); return; }}
        if (e.key === 'Enter' || e.key === 'o') {{ goToTripFromLightbox(); return; }}
        return;
      }}

      // Slideshow controls
      const slideshowActive = document.getElementById('slideshowModal').classList.contains('active');
      if (slideshowActive) {{
        if (e.key === 'Escape') {{ stopSlideshow(); return; }}
        if (e.key === 'ArrowRight' || e.key === ' ') {{ slideshowNext(); return; }}
        if (e.key === 'ArrowLeft') {{ slideshowPrev(); return; }}
        if (e.key === 'p') {{ toggleSlideshowPlay(); return; }}
        return;
      }}

      if (e.key === 'Escape') {{
        document.getElementById('infoModal').classList.remove('active');
        document.getElementById('featuresModal').classList.remove('active');
        document.body.style.overflow = '';
        clearSearch();
      }}
      if (e.key === '/' && e.target.tagName !== 'INPUT') {{
        e.preventDefault();
        document.getElementById('globalSearch').focus();
      }}
      if (e.key === 'f' && e.target.tagName !== 'INPUT' && !e.ctrlKey && !e.metaKey) {{
        toggleFeatures();
      }}
      if (e.key === 's' && e.target.tagName !== 'INPUT' && !e.ctrlKey && !e.metaKey) {{
        startSlideshow();
      }}
    }});

    // Load search index on page load
    document.addEventListener('DOMContentLoaded', loadSearchIndex);

    // Close autocomplete when clicking outside
    document.addEventListener('click', (e) => {{
      const searchWrap = document.querySelector('.search-input-wrap');
      if (searchWrap && !searchWrap.contains(e.target)) {{
        document.getElementById('autocompleteDropdown').classList.remove('active');
      }}
    }});
  </script>
</body>
</html>
"""

CARD_TEMPLATE = """<a class="trip-card" href="{link}" data-date="{sort_date}" data-photos="{photo_count}" data-name="{title}">
  <div class="thumb-gallery">
    <img class="thumb-main" src="{main_thumb}" alt="{title}">
    <div class="thumb-overlay"></div>
    <div class="thumb-mini-stack">
      {mini_thumbs}
    </div>
    <div class="thumb-count">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
      {photo_count}
    </div>
  </div>
  <div class="trip-info">
    <div class="trip-header">
      <h2 class="trip-title">{title}</h2>
      {location_badge}
    </div>
    <div class="trip-dates">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
      {date_range}
    </div>
    <div class="trip-stats">
      <span class="trip-stat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        {day_count} day{day_suffix}
      </span>
      <span class="trip-stat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg>
        {photo_count} photo{photo_suffix}
      </span>
    </div>
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

    # Get raw dates for sorting
    start_date_raw = days[0].get("date", "1900-01-01")
    end_date_raw = days[-1].get("date", "1900-01-01")

    start_date = _format_date(start_date_raw)
    end_date = _format_date(end_date_raw)
    date_range = start_date if start_date == end_date else f"{start_date} → {end_date}"

    themes = Counter()
    species = Counter()
    for day in days:
        themes.update(day.get("themes", []))
        species.update(day.get("wildlife_animals", []))
        species.update(day.get("wildlife_plants", []))

    top_themes = [theme for theme, _ in themes.most_common(3)]
    top_species = [sp for sp, _ in species.most_common(2)]

    thumbs = _gather_thumbnails(trip_dir, memo_dir, limit=4)
    if not thumbs:
        thumbs = _fallback_images(trip_dir, days, limit=4)

    location = days[0].get("start_location_short") or ""

    # Format title nicely - replace underscores with spaces
    raw_title = data.get("trip_name") or os.path.basename(trip_dir)
    formatted_title = raw_title.replace("_", " ")
    # Remove year prefix if it starts with year (e.g., "2025 Annapurna Nepal" -> "Annapurna Nepal")
    if formatted_title[:4].isdigit() and len(formatted_title) > 5:
        formatted_title = formatted_title[5:].strip()

    return {
        "title": formatted_title,
        "raw_title": raw_title,
        "date_range": date_range,
        "sort_date": start_date_raw,
        "day_count": day_count,
        "photo_count": photo_count,
        "thumbs": thumbs,
        "themes": top_themes,
        "species": top_species,
        "link": _ensure_posix(os.path.join(os.path.basename(trip_dir), CFG.MEMOGRAPH_FOLDER_NAME, "webapp", "index.html")),
        "location": location,
    }


def _render_mini_thumbs(thumbs: List[str]) -> str:
    """Render mini thumbnail stack (skip first one, show next 2-3)."""
    if len(thumbs) <= 1:
        return ""
    mini = thumbs[1:4]  # Get up to 3 mini thumbs
    return "".join(f'<img class="thumb-mini" src="{src}" alt="">' for src in mini)


def _render_location_badge(location: str) -> str:
    """Render location badge HTML."""
    if not location:
        return ""
    return f'''<span class="trip-location">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
        {location}
      </span>'''


def build_trip_index(trips_root: str | None = None) -> str:
    root = trips_root or CFG.DATA_ROOT
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Trips root not found: {root}")

    # Load search index if it exists
    search_index_path = os.path.join(root, "search_index.json")
    search_index_json = "null"
    if os.path.exists(search_index_path):
        try:
            with open(search_index_path, "r", encoding="utf-8") as f:
                search_data = json.load(f)
                # Add trips facet if not present
                if "facets" in search_data and "trips" not in search_data["facets"]:
                    search_data["facets"]["trips"] = list(search_data.get("trip_counts", {}).keys())
                search_index_json = json.dumps(search_data)
        except Exception as e:
            print(f"Warning: Could not load search index: {e}")

    cards_html: List[str] = []
    all_metadata: List[Dict[str, Any]] = []

    # Collect all trip metadata
    for entry in sorted(os.listdir(root)):
        trip_path = os.path.join(root, entry)
        if not os.path.isdir(trip_path):
            continue
        meta = _collect_trip_metadata(trip_path)
        if not meta:
            continue
        all_metadata.append(meta)

    # Calculate totals for stats
    total_photos = sum(m["photo_count"] for m in all_metadata)
    total_days = sum(m["day_count"] for m in all_metadata)
    trip_count = len(all_metadata)

    # Sort by date (newest first) for default display
    all_metadata.sort(key=lambda m: m["sort_date"], reverse=True)

    # Build cards
    for meta in all_metadata:
        chips = meta["themes"] + meta["species"]
        chips_html = "".join(f'<span class="chip">{chip}</span>' for chip in chips)

        # Main thumbnail (first one)
        main_thumb = meta["thumbs"][0] if meta["thumbs"] else ""

        # Mini thumbnails (rest)
        mini_thumbs_html = _render_mini_thumbs(meta["thumbs"])

        # Location badge
        location_badge = _render_location_badge(meta["location"])

        card = CARD_TEMPLATE.format(
            link=meta["link"],
            title=meta["title"],
            main_thumb=main_thumb,
            mini_thumbs=mini_thumbs_html,
            date_range=meta["date_range"],
            sort_date=meta["sort_date"],
            day_count=meta["day_count"],
            day_suffix="s" if meta["day_count"] != 1 else "",
            photo_count=meta["photo_count"],
            photo_suffix="s" if meta["photo_count"] != 1 else "",
            location_badge=location_badge,
            chips=chips_html or '<span class="chip">MemoGraph</span>',
        )
        cards_html.append(card)

    # Build empty state if no trips
    if not cards_html:
        empty_html = '''<div class="empty-state">
      <div class="empty-icon">&#x1F4F7;</div>
      <h3>No trips yet</h3>
      <p>Process your first trip folder with MemoGraph to see it here.</p>
    </div>'''
        cards_section = empty_html
    else:
        cards_section = "\n    ".join(cards_html)

    html = HTML_TEMPLATE.format(
        cards=cards_section,
        trip_count=trip_count,
        trip_suffix="s" if trip_count != 1 else "",
        total_photos=total_photos,
        total_days=total_days,
        search_index_json=search_index_json,
    )
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
