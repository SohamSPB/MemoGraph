#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dev_fixture.py

Generates a synthetic trip under data/trips/SyntheticTrip/ with placeholder
JPEGs and a pre-built MemoGraph/blog_context.json, so that build_webapp.py
and build_trip_index.py can be exercised without running the AI pipeline.

The fixture deliberately covers every lightbox/UI edge case:
  - photos with single face, with multiple faces, with no face but person tag
  - species bounding boxes (bird, butterfly)
  - varied image_type values (natural_photo, document_scan, screenshot)
  - missing GPS (forces sidebar/overview)
  - varied quality scores (high, mid, low)
  - vision_caption vs caption_ai vs caption divergence
  - color palettes
  - multiple days for timeline view

Usage:
    .venv\\Scripts\\python.exe -m scripts.dev_fixture
    # then:
    .venv\\Scripts\\python.exe -m scripts.build_webapp data/trips/SyntheticTrip
    .venv\\Scripts\\python.exe -m scripts.build_trip_index
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import memograph_config as CFG

TRIP_NAME = "SyntheticTrip"
TRIP_DIR = Path(CFG.DATA_ROOT) / TRIP_NAME
MEMO_DIR = TRIP_DIR / CFG.MEMOGRAPH_FOLDER_NAME

IMG_W, IMG_H = 1024, 768


def _gradient_image(top: tuple, bottom: tuple, label: str, accents: List[tuple] | None = None) -> Image.Image:
	"""Generate a vertical-gradient placeholder with a label and optional accent rectangles."""
	img = Image.new("RGB", (IMG_W, IMG_H), top)
	pixels = img.load()
	for y in range(IMG_H):
		t = y / max(1, IMG_H - 1)
		r = int(top[0] * (1 - t) + bottom[0] * t)
		g = int(top[1] * (1 - t) + bottom[1] * t)
		b = int(top[2] * (1 - t) + bottom[2] * t)
		for x in range(IMG_W):
			pixels[x, y] = (r, g, b)

	draw = ImageDraw.Draw(img)
	# Accent rectangles let us paint a "subject" so face/species boxes have something to highlight visually.
	for (color, box) in accents or []:
		draw.rectangle(box, outline=color, width=6)

	# Label in the bottom-left corner so we can identify each fixture photo at a glance.
	try:
		font = ImageFont.truetype("arial.ttf", 48)
	except Exception:
		font = ImageFont.load_default()
	draw.rectangle((20, IMG_H - 90, 20 + len(label) * 24 + 20, IMG_H - 30), fill=(0, 0, 0))
	draw.text((30, IMG_H - 80), label, fill=(255, 255, 255), font=font)

	return img


def _write_image(path: Path, image: Image.Image) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	image.save(path, format="JPEG", quality=88)


# ---------------------------------------------------------------------------
# Per-photo fixture spec. The list order is the order rows would appear in
# labels.csv; days are derived from the `time` field, like the real pipeline.
# ---------------------------------------------------------------------------
PHOTO_FIXTURES: List[Dict[str, Any]] = [
	{
		"image_name": "fx_01_mountain_solo.jpg",
		"time": "2026-04-12 06:42:11",
		"device_model": "Sony ILCE-7M4",
		"location_full": "Ghorepani, Myagdi, Gandaki Province, 33700, Nepal",
		"location_short": "Ghorepani",
		"gps_lat": 28.4006, "gps_lon": 83.6883,
		"caption": "a snowy mountain peak under a clear blue sky",
		"caption_ai": "Sunrise lights up snow on a distant Himalayan peak with prayer flags in the foreground.",
		"vision_caption": (
			"A wide-angle shot taken just after dawn looks east across a valley toward the snow-laden "
			"face of Dhaulagiri. Strings of prayer flags strung across a wooden pole occupy the lower "
			"left, their colours muted by frost. The sky is a graduated cobalt with no clouds. "
			"Composition uses leading lines along the flag rope to draw the eye to the peak."
		),
		"detected_objects": ["mountain", "snow", "panorama", "sunrise", "scenic view"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.88, "exposure_score": 0.92, "contrast_score": 0.85,
		"sharpness_score": 0.90, "noise_score": 0.86, "color_balance_score": 0.84,
		"quality_notes": "balanced highlight",
		"color_palette": ["#1c2e58", "#5a7da4", "#e8f1f7"],
		"_top": (40, 80, 160), "_bottom": (220, 230, 240), "_label": "01 mountain",
	},
	{
		"image_name": "fx_02_group_selfie.jpg",
		"time": "2026-04-12 09:15:30",
		"device_model": "iPhone 15 Pro",
		"location_full": "Tikhedhunga, Myagdi, Nepal",
		"location_short": "Tikhedhunga",
		"gps_lat": 28.3814, "gps_lon": 83.6712,
		"caption": "a group of three people smiling at the camera",
		"caption_ai": "Three hikers pose together on a stone-paved trail surrounded by rhododendron trees.",
		"vision_caption": (
			"Three smiling travelers crouch in the foreground of a stone trail. The central subject "
			"holds a wooden walking stick. Behind them the trail winds upward through dense rhododendron "
			"forest in early bloom. Lighting is soft and overcast, evenly exposing skin tones. "
			"This is clearly a posed selfie taken with a handheld phone."
		),
		"detected_objects": ["person", "group of people", "hiking trail", "forest", "selfie"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		"faces_detected": "1", "faces_count": 3,
		# Three face boxes (top,right,bottom,left as percentages).
		"face_locations": "32.0,40.0,55.0,22.0; 30.0,62.0,53.0,44.0; 34.0,82.0,57.0,64.0",
		"quality_score": 0.74, "exposure_score": 0.78, "contrast_score": 0.65,
		"sharpness_score": 0.70, "noise_score": 0.82, "color_balance_score": 0.76,
		"quality_notes": "balanced",
		"color_palette": ["#3d5a3d", "#a8c08a", "#f3e7c9"],
		"_top": (60, 100, 60), "_bottom": (200, 210, 160),
		"_label": "02 group",
		"_accents": [((30, 90, 160), (220, 240, 470, 410)), ((30, 90, 160), (450, 230, 700, 400)), ((30, 90, 160), (660, 260, 910, 430))],
	},
	{
		"image_name": "fx_03_bird_species.jpg",
		"time": "2026-04-12 13:08:54",
		"device_model": "Sony ILCE-7M4",
		"location_full": "Banthanti, Myagdi, Nepal",
		"location_short": "Banthanti",
		"gps_lat": 28.3956, "gps_lon": 83.6601,
		"caption": "a small green bird perched on a branch",
		"caption_ai": "An Asian Green Bee-eater perches on a thin branch with insects fluttering nearby.",
		"vision_caption": (
			"A close telephoto frame of a small green bird gripping a slender branch in the middle "
			"third of the image. Its body is bright lime green with a turquoise throat and an "
			"elongated tail-streamer. The background is a creamy out-of-focus wash typical of f/4 "
			"at long focal length. The bird is sharply focused with a catchlight in the eye."
		),
		"detected_objects": ["bird", "tree", "forest"],
		"species_tags": ["Asian Green Bee-eater", "Green Bee-eater"],
		"species_boxes": "a bird:Asian Green Bee-eater@38.5,28.0,68.0,72.0",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.81, "exposure_score": 0.74, "contrast_score": 0.82,
		"sharpness_score": 0.95, "noise_score": 0.70, "color_balance_score": 0.86,
		"quality_notes": "balanced highlight",
		"color_palette": ["#2d4a2d", "#86b25e", "#d8dbb1"],
		"_top": (40, 90, 60), "_bottom": (140, 180, 100),
		"_label": "03 bird",
		"_accents": [((40, 200, 60), (394, 215, 696, 553))],
	},
	{
		"image_name": "fx_04_butterfly_lowq.jpg",
		"time": "2026-04-12 14:42:09",
		"device_model": "iPhone 15 Pro",
		"location_full": "Banthanti, Myagdi, Nepal",
		"location_short": "Banthanti",
		"gps_lat": 28.3961, "gps_lon": 83.6605,
		"caption": "a yellow butterfly on damp soil",
		"caption_ai": "A common grass yellow butterfly mud-puddling on a wet trail.",
		"vision_caption": (
			"Handheld macro frame at f/2.8 of a yellow butterfly resting on dark, wet soil. Motion "
			"blur is visible on the wing edges suggesting it was about to take off. The composition "
			"is centred and slightly soft; the background is uniformly brown with no separation. "
			"Highlights on the wings are mildly clipped."
		),
		"detected_objects": ["butterfly", "insect", "mud-puddling butterflies"],
		"species_tags": ["Common Grass Yellow"],
		"species_boxes": "a butterfly:Common Grass Yellow@42.0,40.0,60.0,58.0",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.46, "exposure_score": 0.55, "contrast_score": 0.40,
		"sharpness_score": 0.35, "noise_score": 0.55, "color_balance_score": 0.45,
		"quality_notes": "soft focus, noise",
		"color_palette": ["#604c2a", "#a07a3a", "#d8c267"],
		"_top": (80, 60, 30), "_bottom": (160, 130, 70),
		"_label": "04 butterfly",
		"_accents": [((240, 220, 60), (430, 307, 614, 445))],
	},
	{
		"image_name": "fx_05_hiker_person_tag.jpg",
		"time": "2026-04-12 16:30:00",
		"device_model": "Canon EOS R6",
		"location_full": "Above Ulleri, Myagdi, Nepal",
		"location_short": "Above Ulleri",
		"gps_lat": 28.3729, "gps_lon": 83.6531,
		"caption": "a hiker walking up a mountain trail",
		"caption_ai": "A lone hiker climbs a stepped stone staircase with valley views behind.",
		"vision_caption": (
			"A medium shot of a solo hiker viewed from behind, ascending a wide stepped trail of "
			"weathered stones. The figure is small against a dramatic backdrop of terraced hillsides "
			"falling away into haze. Late-afternoon side light creates long shadows from the steps. "
			"The hiker's face is not visible, so face detection returns nothing."
		),
		"detected_objects": ["hiker", "person", "mountain", "hiking trail", "landscape"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		# No face detected (face is turned away) but CLIP tags include "hiker" / "person"
		# so the lightbox should fall back to a "Person detected (from tags)" indicator.
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.79, "exposure_score": 0.82, "contrast_score": 0.78,
		"sharpness_score": 0.80, "noise_score": 0.78, "color_balance_score": 0.77,
		"quality_notes": "balanced",
		"color_palette": ["#503a28", "#a48656", "#e8d9b6"],
		"_top": (100, 80, 50), "_bottom": (210, 190, 140),
		"_label": "05 hiker",
	},
	{
		"image_name": "fx_06_astro.jpg",
		"time": "2026-04-12 22:48:17",
		"device_model": "Sony ILCE-7M4",
		"location_full": "Ghorepani, Myagdi, Nepal",
		"location_short": "Ghorepani",
		"gps_lat": 28.4006, "gps_lon": 83.6883,
		"caption": "stars and the milky way over a dark valley",
		"caption_ai": "The Milky Way arches over silhouetted Himalayan ridgelines.",
		"vision_caption": (
			"A 20-second exposure at ISO 3200 captures the galactic core rising above a serrated "
			"silhouette of distant peaks. Sagittarius is clearly visible. Lower foreground is "
			"completely black; the sky contains thousands of stars with no light pollution. Slight "
			"chromatic noise is present in the deep shadows but star colours remain natural."
		),
		"detected_objects": ["night sky", "Milky Way", "stars", "astrophotography", "galaxy"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.69, "exposure_score": 0.62, "contrast_score": 0.88,
		"sharpness_score": 0.75, "noise_score": 0.40, "color_balance_score": 0.78,
		"quality_notes": "noise",
		"color_palette": ["#080814", "#1c2540", "#6470a8"],
		"_top": (5, 5, 18), "_bottom": (30, 40, 80),
		"_label": "06 astro",
	},
	{
		"image_name": "fx_07_no_gps_food.jpg",
		"time": "2026-04-13 12:55:02",
		"device_model": "iPhone 15 Pro",
		"location_full": "",
		"location_short": "an unknown place",
		# GPS deliberately omitted to test the overview-sidebar path for non-geotagged photos.
		"gps_lat": None, "gps_lon": None,
		"caption": "a bowl of curry next to rice on a metal plate",
		"caption_ai": "A steaming dal bhat thali with rice, vegetable curry, and lentils.",
		"vision_caption": (
			"Top-down view of a stainless-steel thali plate divided into compartments containing "
			"rice, a vegetable curry, yellow dal, and a small dish of pickle. Steam is visible in "
			"the upper third. Lighting is warm tungsten with mild colour cast. The image is sharp "
			"and well exposed; no people are visible."
		),
		"detected_objects": ["plate of food", "thali", "bowl of curry", "rice"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.72, "exposure_score": 0.80, "contrast_score": 0.65,
		"sharpness_score": 0.78, "noise_score": 0.74, "color_balance_score": 0.62,
		"quality_notes": "color cast",
		"color_palette": ["#7a3a18", "#d8a04a", "#f2e1ad"],
		"_top": (100, 50, 20), "_bottom": (220, 170, 80),
		"_label": "07 food",
	},
	{
		"image_name": "fx_08_document_scan.jpg",
		"time": "2026-04-13 15:00:00",
		"device_model": "iPhone 15 Pro",
		"location_full": "Pokhara, Kaski, Nepal",
		"location_short": "Pokhara",
		"gps_lat": 28.2096, "gps_lon": 83.9856,
		"caption": "a printed receipt with text",
		"caption_ai": "Receipt printed in black ink listing several items and a total.",
		"vision_caption": (
			"A scanned image of a thermal-printed receipt, oriented portrait, with eight line items "
			"of unreadable Nepali text and a numeric total at the bottom. There is no scene content; "
			"this is a document scan that should not feed into species or wildlife detection."
		),
		"detected_objects": ["sign", "billboard"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "document_scan",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.55, "exposure_score": 0.92, "contrast_score": 0.40,
		"sharpness_score": 0.85, "noise_score": 0.65, "color_balance_score": 0.30,
		"quality_notes": "color cast",
		"color_palette": ["#f4f4ee", "#cfcfcf", "#1a1a1a"],
		"_top": (245, 245, 240), "_bottom": (210, 210, 200),
		"_label": "08 receipt",
	},
	{
		"image_name": "fx_09_scan_pending.jpg",
		"time": "2026-04-13 17:18:42",
		"device_model": "iPhone 15 Pro",
		"location_full": "Pokhara, Kaski, Nepal",
		"location_short": "Pokhara",
		"gps_lat": 28.2150, "gps_lon": 83.9762,
		"caption": "lakeside boats at dusk",
		"caption_ai": "Wooden rowboats sit moored along the edge of a calm lake at dusk.",
		"vision_caption": "",  # left empty to test the "no VLM caption" path
		"detected_objects": ["lake", "boat", "sunset"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		# faces_count = -1 means the face scan never ran on this row.
		"faces_detected": "", "faces_count": -1, "face_locations": "",
		"quality_score": 0.66, "exposure_score": 0.50, "contrast_score": 0.72,
		"sharpness_score": 0.68, "noise_score": 0.72, "color_balance_score": 0.70,
		"quality_notes": "exposure extremes",
		"color_palette": ["#3b3050", "#a87858", "#e9b070"],
		"_top": (60, 50, 80), "_bottom": (240, 170, 90),
		"_label": "09 lake",
	},
	{
		"image_name": "fx_10_temple_macro.jpg",
		"time": "2026-04-14 08:20:00",
		"device_model": "Sony ILCE-7M4",
		"location_full": "Bindabasini Temple, Pokhara, Nepal",
		"location_short": "Bindabasini Temple",
		"gps_lat": 28.2380, "gps_lon": 83.9819,
		"caption": "ornate carving on a temple pillar",
		"caption_ai": "Sun-bleached wooden carvings of deities adorn a temple's eaves.",
		"vision_caption": (
			"Tight detail of weathered teak carving on the eaves of a Hindu temple. The figure "
			"appears to be a stylised lion with prominent fangs and a curled mane. Paint has "
			"flaked from much of the surface. Side light at low angle accentuates carved depth. "
			"The framing fills the entire frame with the subject, no environment is visible."
		),
		"detected_objects": ["temple", "monument", "heritage building", "ancient architecture"],
		"species_tags": [],
		"species_boxes": "",
		"image_type": "natural_photo",
		"faces_detected": "0", "faces_count": 0, "face_locations": "",
		"quality_score": 0.84, "exposure_score": 0.78, "contrast_score": 0.88,
		"sharpness_score": 0.92, "noise_score": 0.85, "color_balance_score": 0.79,
		"quality_notes": "balanced highlight",
		"color_palette": ["#5a2a14", "#a07050", "#e8d4b0"],
		"_top": (90, 50, 30), "_bottom": (190, 140, 90),
		"_label": "10 temple",
	},
]


def _classify_themes(image: Dict[str, Any]) -> List[str]:
	text = " ".join(
		[
			" ".join(image.get("detected_objects", [])),
			" ".join(image.get("species_tags", [])),
			image.get("caption", "") or "",
			image.get("caption_ai", "") or "",
			image.get("image_type", "") or "",
		]
	).lower()
	tags: List[str] = []
	if image.get("faces_count", 0) > 0:
		tags.append("people")
	if any(k in text for k in ("mountain", "valley", "ridge", "peak", "himalaya")):
		tags.append("mountains")
	if any(k in text for k in ("river", "lake", "waterfall", "sea", "ocean")):
		tags.append("water")
	if any(k in text for k in ("temple", "monastery", "building", "village", "street", "monument")):
		tags.append("towns")
	if any(k in text for k in ("milky way", "galaxy", "nebula", "night sky", "astrophotography", "stars")):
		tags.append("astro")
	if any(k in text for k in ("bird", "butterfly", "insect", "animal", "wildlife")):
		tags.append("wildlife")
	if any(k in text for k in ("food", "thali", "curry", "tea", "coffee", "restaurant", "cafe")):
		tags.append("food")
	if any(k in text for k in ("temple", "monastery", "shrine", "monument", "palace", "fort")):
		tags.append("temples_palaces")
	if any(k in text for k in ("trail", "road", "path", "step", "bridge", "highway")):
		tags.append("roads_trails")
	return tags


def _split_species(species: List[str]) -> Dict[str, List[str]]:
	animal_keywords = ("yak", "horse", "dog", "cat", "bird", "elephant", "cow", "butterfly", "insect", "monkey", "bee-eater")
	plant_keywords = ("tulsi", "ficus", "fern", "tree", "flower", "plant", "lotus", "rose")
	animals, plants = [], []
	for raw in species:
		low = raw.lower()
		if any(k in low for k in animal_keywords):
			animals.append(raw)
		elif any(k in low for k in plant_keywords):
			plants.append(raw)
	return {"animals": sorted(set(animals)), "plants": sorted(set(plants))}


def _build_blog_context(photos: List[Dict[str, Any]]) -> Dict[str, Any]:
	# Group by date.
	per_day: Dict[str, List[Dict[str, Any]]] = {}
	for p in photos:
		date_key = p["time"][:10]
		per_day.setdefault(date_key, []).append(p)

	days_out: List[Dict[str, Any]] = []
	for idx, date_key in enumerate(sorted(per_day.keys()), start=1):
		rows = sorted(per_day[date_key], key=lambda r: r["time"])
		first, last = rows[0], rows[-1]

		# Per-image context.
		images_ctx: List[Dict[str, Any]] = []
		from collections import Counter
		theme_counts: Counter = Counter()
		all_species: List[str] = []
		for r in rows:
			for t in _classify_themes(r):
				theme_counts[t] += 1
			all_species.extend(r.get("species_tags", []))
			images_ctx.append(
				{
					"image_name": r["image_name"],
					"local_path": r["image_name"],
					"time": r["time"],
					"device_model": r["device_model"],
					"location_full": r.get("location_full", ""),
					"location_short": r.get("location_short", ""),
					"caption": r.get("caption", ""),
					"caption_ai": r.get("caption_ai", ""),
					"vision_caption": r.get("vision_caption", ""),
					"species_tags": r.get("species_tags", []),
					"species_boxes": r.get("species_boxes", ""),
					"detected_objects": r.get("detected_objects", []),
					"image_type": r.get("image_type", "natural_photo"),
					"faces_detected": r.get("faces_detected", ""),
					"faces_count": r.get("faces_count", 0),
					"face_locations": r.get("face_locations", ""),
					"gps_lat": r.get("gps_lat"),
					"gps_lon": r.get("gps_lon"),
					"yolo_objects": [],
					"ocr_text": [],
					"places_scenes": [],
					"quality_score": r.get("quality_score"),
					"exposure_score": r.get("exposure_score"),
					"contrast_score": r.get("contrast_score"),
					"sharpness_score": r.get("sharpness_score"),
					"noise_score": r.get("noise_score"),
					"color_balance_score": r.get("color_balance_score"),
					"quality_notes": r.get("quality_notes", ""),
					"color_palette": r.get("color_palette", []),
				}
			)

		themes_sorted = sorted(t for t, c in theme_counts.items() if c > 0)
		activities = []
		if theme_counts.get("mountains") and theme_counts.get("roads_trails"):
			activities.append("travelled along mountain roads and passes")
		if theme_counts.get("wildlife"):
			activities.append("noticed animals or birds around the route")
		if theme_counts.get("astro"):
			activities.append("spent time on night-sky or astro photography")
		if theme_counts.get("temples_palaces"):
			activities.append("visited temples, monasteries, or old monuments")
		if theme_counts.get("food"):
			activities.append("took breaks around food, tea, or cafes")

		wildlife = _split_species(all_species)

		all_locs_full = sorted({r.get("location_full", "") for r in rows if r.get("location_full")})
		all_locs_short = sorted({r.get("location_short", "") for r in rows if r.get("location_short")})

		days_out.append(
			{
				"date": date_key,
				"day_number": idx,
				"start_time": first["time"],
				"end_time": last["time"],
				"start_location_full": first.get("location_full", ""),
				"end_location_full": last.get("location_full", ""),
				"start_location_short": first.get("location_short", ""),
				"end_location_short": last.get("location_short", ""),
				"locations_full": all_locs_full,
				"locations_short": all_locs_short,
				"themes": themes_sorted,
				"theme_counts": dict(theme_counts),
				"activities": activities,
				"wildlife_animals": wildlife["animals"],
				"wildlife_plants": wildlife["plants"],
				"images": images_ctx,
			}
		)

	return {"trip_name": TRIP_NAME, "days": days_out}


def generate_fixture() -> None:
	if TRIP_DIR.exists():
		shutil.rmtree(TRIP_DIR)
	TRIP_DIR.mkdir(parents=True, exist_ok=True)
	MEMO_DIR.mkdir(parents=True, exist_ok=True)
	(MEMO_DIR / "logs").mkdir(parents=True, exist_ok=True)

	for p in PHOTO_FIXTURES:
		img = _gradient_image(
			top=p["_top"],
			bottom=p["_bottom"],
			label=p["_label"],
			accents=p.get("_accents"),
		)
		_write_image(TRIP_DIR / p["image_name"], img)

	# Add a byte-identical duplicate of the bird photo (fx_03) under a
	# different filename. Exercises the md5-based dedup pipeline:
	# image_scanner should mark this row duplicate_of=fx_03_bird_species.jpg,
	# every analysis script should skip it, and dedup_broadcast should fill
	# in its analysis columns from the canonical at the end.
	bird_src = TRIP_DIR / "fx_03_bird_species.jpg"
	bird_dup = TRIP_DIR / "fx_03_bird_species_COPY.jpg"
	shutil.copyfile(bird_src, bird_dup)

	context = _build_blog_context(PHOTO_FIXTURES)
	with open(MEMO_DIR / "blog_context.json", "w", encoding="utf-8") as f:
		json.dump(context, f, indent=2)

	print(f"Synthetic trip written to: {TRIP_DIR}")
	print(f"  {len(PHOTO_FIXTURES)} placeholder JPEGs + 1 byte-identical duplicate (fx_03_bird_species_COPY.jpg)")
	print(f"  blog_context.json: {MEMO_DIR / 'blog_context.json'}")
	print()
	print("Next:")
	print(f"  python -m scripts.image_scanner --trip-folder {TRIP_DIR.as_posix()}")
	print(f"  python -m scripts.dedup_broadcast {TRIP_DIR.as_posix()}")
	print(f"  python -m scripts.build_webapp {TRIP_DIR.as_posix()}")


if __name__ == "__main__":
	generate_fixture()
