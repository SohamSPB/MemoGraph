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
from typing import Dict, List, Any, Optional

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_io import read_csv_dict

# Optional dependencies for richer image analysis (YOLO + OCR + Places365).
_EXTRAS_ENABLED = getattr(CFG, "BLOG_CONTEXT_INCLUDE_EXTRAS", False)

if _EXTRAS_ENABLED:
    try:
        from ultralytics import YOLO  # type: ignore
        _YOLO_AVAILABLE = True
    except Exception:
        YOLO = None  # type: ignore
        _YOLO_AVAILABLE = False

    try:
        import easyocr  # type: ignore
        _EASYOCR_AVAILABLE = True
    except Exception:
        easyocr = None  # type: ignore
        _EASYOCR_AVAILABLE = False

    try:
        import torch
        import torchvision.transforms as T
        from torchvision import models as tv_models
        _PLACES_AVAILABLE = True
    except Exception:
        torch = None  # type: ignore
        T = None  # type: ignore
        tv_models = None  # type: ignore
        _PLACES_AVAILABLE = False
else:
    YOLO = None  # type: ignore
    easyocr = None  # type: ignore
    torch = None  # type: ignore
    T = None  # type: ignore
    tv_models = None  # type: ignore
    _YOLO_AVAILABLE = False
    _EASYOCR_AVAILABLE = False
    _PLACES_AVAILABLE = False

_yolo_model = None
_ocr_reader = None
_places_model = None
_places_labels: List[str] = []


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


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _get_yolo_model():
    """Lazily load a small YOLO model if ultralytics is available.

    We prefer to keep the weights under models/yolo/yolov8s.pt so that
    they live alongside other project models rather than in a global cache.
    """
    global _yolo_model
    if not _YOLO_AVAILABLE:
        return None
    if _yolo_model is None:
        # Use a small model to keep downloads and memory modest.
        weights_path = os.path.join("models", "yolo", "yolov8s.pt")
        os.makedirs(os.path.dirname(weights_path), exist_ok=True)
        _yolo_model = YOLO(weights_path)
    return _yolo_model


def _get_ocr_reader():
    """Lazily construct an EasyOCR reader if available."""
    global _ocr_reader
    if not _EASYOCR_AVAILABLE:
        return None
    if _ocr_reader is None:
        # English-only is usually enough for road signs / shop boards.
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def _get_places_model():
    """Lazily load a ResNet-50 Places365 scene classifier, if weights are present."""
    global _places_model, _places_labels
    if not _PLACES_AVAILABLE:
        return None, []

    if _places_model is not None and _places_labels:
        return _places_model, _places_labels

    weights_path = os.path.join("models", "places", "resnet50_places365.pth.tar")
    categories_path = os.path.join("models", "places", "categories_places365.txt")
    if not (os.path.exists(weights_path) and os.path.exists(categories_path)):
        return None, []

    # Load category labels
    labels: List[str] = []
    try:
        with open(categories_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # File format: "/a/airfield 0"
                # We keep the last path segment ("airfield") and make it human-friendly.
                tokens = line.split()
                if not tokens:
                    continue
                path_token = tokens[0]
                leaf = path_token.split("/")[-1]
                label = leaf.replace("_", " ").replace("-", " ").strip()
                if label:
                    labels.append(label)
    except Exception:
        labels = []

    # Load model and weights
    try:
        model = tv_models.resnet50(num_classes=365)
        checkpoint = torch.load(weights_path, map_location="cpu")
        state_dict = checkpoint.get("state_dict", checkpoint)
        # Strip 'module.' prefix if present
        clean_state_dict = {}
        for k, v in state_dict.items():
            if k.startswith("module."):
                k = k[len("module.") :]
            clean_state_dict[k] = v
        model.load_state_dict(clean_state_dict, strict=False)
        model.eval()

        _places_model = model
        _places_labels = labels
        return _places_model, _places_labels
    except Exception:
        return None, []


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


def _analyze_image_extras(image_path: str, include_extras: bool) -> Dict[str, Any]:
    """
    Run optional detectors (YOLO + OCR) on a single image.

    Returns a dict with:
        - yolo_objects: list of coarse object labels (if available)
        - ocr_text: list of short text snippets detected on the image (if any)
    """
    extras: Dict[str, Any] = {"yolo_objects": [], "ocr_text": [], "places_scenes": []}

    if not include_extras:
        return extras

    # YOLO: detect objects and keep a small set of labels.
    model = _get_yolo_model()
    if model is not None and os.path.exists(image_path):
        try:
            results = model(image_path, verbose=False)
            labels: List[str] = []
            if results:
                r0 = results[0]
                names = r0.names
                for box in r0.boxes:
                    cls_idx = int(box.cls.item())
                    label = names.get(cls_idx, str(cls_idx))
                    labels.append(label)
            # Deduplicate, keep a small subset to avoid overwhelming the JSON.
            extras["yolo_objects"] = sorted(set(labels))
        except Exception:
            # Fail silently; extras remain empty.
            pass

    # OCR: read short text snippets (e.g., signs, boards).
    reader = _get_ocr_reader()
    if reader is not None and os.path.exists(image_path):
        try:
            results = reader.readtext(image_path, detail=0)
            cleaned = []
            for txt in results:
                t = str(txt).strip()
                if 3 <= len(t) <= 40:
                    cleaned.append(t)
            extras["ocr_text"] = cleaned
        except Exception:
            pass

    # Places365: scene classification (top-1 or top-2 labels).
    places_model, places_labels = _get_places_model()
    if places_model is not None and places_labels and os.path.exists(image_path):
        from PIL import Image  # local import to avoid top-level dependency if unused

        try:
            with Image.open(image_path).convert("RGB") as im:
                transform = T.Compose(
                    [
                        T.Resize(256),
                        T.CenterCrop(224),
                        T.ToTensor(),
                        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                    ]
                )
                tensor = transform(im).unsqueeze(0)
                with torch.no_grad():
                    logits = places_model(tensor)
                    probs = torch.softmax(logits, dim=1)[0]
                    top_probs, top_idxs = probs.topk(2)
                scenes: List[str] = []
                for idx, prob in zip(top_idxs.tolist(), top_probs.tolist()):
                    if 0 <= idx < len(places_labels):
                        label = places_labels[idx]
                        scenes.append(f"{label} ({prob:.2f})")
                extras["places_scenes"] = scenes
        except Exception:
            pass

    return extras


def _build_day_context(
    day_rows: List[Dict[str, Any]],
    date_str: str,
    day_number: int,
    trip_folder: str,
    include_extras: bool,
) -> Dict[str, Any]:
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

        full_img_path = os.path.join(trip_folder, r.get("local_path", ""))
        extras = _analyze_image_extras(full_img_path, include_extras)

        # Faces count (optional column)
        try:
            faces_count_val = str(r.get("faces_count", "")).strip()
            faces_count = int(faces_count_val) if faces_count_val else 0
        except ValueError:
            faces_count = 0

        # GPS
        try:
            lat = float(r.get("gps_lat")) if str(r.get("gps_lat") or "").strip() else None
        except Exception:
            lat = None
        try:
            lon = float(r.get("gps_lon")) if str(r.get("gps_lon") or "").strip() else None
        except Exception:
            lon = None

        quality_score = _safe_float(r.get("quality_score"))
        exposure_score = _safe_float(r.get("exposure_score"))
        contrast_score = _safe_float(r.get("contrast_score"))
        sharpness_score = _safe_float(r.get("sharpness_score"))
        noise_score = _safe_float(r.get("noise_score"))
        color_balance_score = _safe_float(r.get("color_balance_score"))

        images_ctx.append(
            {
                "image_name": r.get("image_name"),
                "local_path": r.get("local_path"),
                "time": r["_dt"].strftime("%Y-%m-%d %H:%M:%S"),
                "device_model": r.get("device_model"),
                "location_full": r.get("location_inferred", ""),
                "location_short": _shorten_location(r.get("location_inferred", "")),
                "caption": r.get("caption"),
                "caption_ai": r.get("caption_ai"),
                "species_tags": img_species,
                "detected_objects": detected,
                "image_type": r.get("image_type"),
                "faces_detected": r.get("faces_detected"),
                "faces_count": faces_count,
                "gps_lat": lat,
                "gps_lon": lon,
                "yolo_objects": extras.get("yolo_objects", []),
                "ocr_text": extras.get("ocr_text", []),
                "places_scenes": extras.get("places_scenes", []),
                "quality_score": quality_score,
                "exposure_score": exposure_score,
                "contrast_score": contrast_score,
                "sharpness_score": sharpness_score,
                "noise_score": noise_score,
                "color_balance_score": color_balance_score,
                "quality_notes": r.get("quality_notes"),
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


def build_blog_context(trip_folder: str, include_extras: bool | None = None) -> str:
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
    if include_extras is None:
        include_extras = getattr(CFG, "BLOG_CONTEXT_INCLUDE_EXTRAS", False)

    for idx, date_key in enumerate(sorted(per_day.keys()), start=1):
        ctx = _build_day_context(per_day[date_key], date_key, idx, trip_folder, include_extras)
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
    p.add_argument(
        "--include-extras",
        dest="include_extras",
        action="store_true",
        help="Enable expensive YOLO/OCR/Places analysis when building context.",
    )
    p.add_argument(
        "--skip-extras",
        dest="include_extras",
        action="store_false",
        help="Disable YOLO/OCR/Places analysis even if enabled in config.",
    )
    p.set_defaults(include_extras=None)
    args = p.parse_args()

    out = build_blog_context(args.trip_folder, include_extras=args.include_extras)
    print(f"Blog context written to: {out}")
