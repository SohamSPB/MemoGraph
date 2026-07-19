#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
face_recognizer.py

Recognise known people in trip images using a pre-built face gallery.

Pipeline:
- Uses CFG.FACE_GALLERY_PATH (built by build_face_gallery.py) which contains:
    {"encodings": [np.ndarray, ...], "labels": ["PersonA", "PersonB", ...]}
- For each labels.csv row where faces_detected indicates faces:
    - Loads the image.
    - Detects faces and computes encodings.
    - Compares each encoding against the gallery.
    - Writes recognised names into the people_tags column.

This script is optional and controlled via memograph_config:
    ENABLE_FACE_RECOGNITION = True/False
"""

import os
import pickle
from typing import List, Dict, Any, Tuple

import numpy as np
import face_recognition
from PIL import Image, ImageOps

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import init_log, log


def _load_gallery(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Face gallery not found at {path}")
    with open(path, "rb") as f:
        data = pickle.load(f)
    encodings = data.get("encodings", [])
    labels = data.get("labels", [])
    if not encodings or not labels or len(encodings) != len(labels):
        raise RuntimeError("Face gallery is invalid or empty.")
    return encodings, labels


def _parse_cached_face_locations(
    face_locations_str: str, img_height: int, img_width: int
) -> List[Tuple[int, int, int, int]]:
    """Parse the face_locations CSV column back into (top, right, bottom, left) pixel tuples.

    face_detector.py writes these as "top%,right%,bottom%,left%" percentages
    separated by '; ', normalized against the image's EXIF-corrected
    dimensions. Re-multiplying by the same EXIF-corrected dimensions here
    gives pixel coordinates that face_encodings can consume directly.
    """
    out: List[Tuple[int, int, int, int]] = []
    if not face_locations_str or not face_locations_str.strip():
        return out
    for face_str in face_locations_str.split(";"):
        parts = face_str.strip().split(",")
        if len(parts) != 4:
            continue
        try:
            t_pct, r_pct, b_pct, l_pct = (float(p) for p in parts)
        except ValueError:
            continue
        out.append(
            (
                max(0, int(round(t_pct / 100.0 * img_height))),
                max(0, int(round(r_pct / 100.0 * img_width))),
                max(0, int(round(b_pct / 100.0 * img_height))),
                max(0, int(round(l_pct / 100.0 * img_width))),
            )
        )
    return out


def recognise_faces(trip_folder: str) -> None:
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    log_path = os.path.join(logs_dir, "face_recognizer.log") if CFG.LOG_TO_FILE else None

    init_log(log_path, "face_recognizer.py")

    csv_path = os.path.join(memo_dir, "labels.csv")
    if not os.path.exists(csv_path):
        log(f"ERROR: labels.csv not found at {csv_path}", log_path)
        return

    try:
        gallery_encodings, gallery_labels = _load_gallery(CFG.FACE_GALLERY_PATH)
    except Exception as e:
        log(f"Face recognition skipped: {e}", log_path)
        return

    rows = read_csv_dict(csv_path)
    if not rows:
        log("No rows in CSV; nothing to recognise.", log_path)
        return

    threshold = getattr(CFG, "FACE_RECOGNITION_THRESHOLD", 0.6)

    # Ensure people_tags column exists.
    fieldnames = list(rows[0].keys())
    if "people_tags" not in fieldnames:
        fieldnames.append("people_tags")

    updated = 0
    for idx, row in enumerate(rows, start=1):
        # Content duplicate: people_tags will be copied from the canonical
        # row by dedup_broadcast.py at the end of the pipeline.
        if (row.get("duplicate_of") or "").strip():
            continue
        faces_flag = str(row.get("faces_detected", "")).strip()
        if faces_flag not in {"1"}:
            # Skip images with no faces_detected or unknown flag.
            continue

        local_path = row.get("local_path", "")
        img_path = os.path.join(trip_folder, local_path)
        if not os.path.exists(img_path):
            log(f"[{idx}] Missing image for face recognition: {img_path}", log_path)
            continue

        try:
            # Apply EXIF transpose so coordinates from face_detector (which also
            # transposes before detection) line up with the array we feed to
            # face_recognition here.
            with Image.open(img_path) as pil_img:
                pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
                img_w, img_h = pil_img.size
                image = np.array(pil_img)

            # Reuse the boxes face_detector already wrote to the CSV, instead of
            # paying for a second detection pass per photo.
            cached_locations = _parse_cached_face_locations(
                row.get("face_locations", ""), img_h, img_w
            )
            if cached_locations:
                locations = cached_locations
            else:
                # Fallback: face_detector didn't persist boxes for this row
                # (older CSVs, or face_locations column wasn't populated).
                locations = face_recognition.face_locations(image, model="hog")
            if not locations:
                continue
            encodings = face_recognition.face_encodings(
                image, known_face_locations=locations
            )
        except Exception as e:
            log(f"[{idx}] Failed to process {img_path} for recognition: {e}", log_path)
            continue

        recognised: List[str] = []
        for enc in encodings:
            distances = face_recognition.face_distance(gallery_encodings, enc)
            if len(distances) == 0:
                continue
            best_idx = int(np.argmin(distances))
            best_dist = float(distances[best_idx])
            if best_dist <= threshold:
                recognised.append(gallery_labels[best_idx])

        if recognised:
            # Deduplicate while preserving order.
            seen = set()
            names_out: List[str] = []
            for name in recognised:
                if name not in seen:
                    seen.add(name)
                    names_out.append(name)
            row["people_tags"] = "; ".join(names_out)
            updated += 1
            log(f"[{idx}] Recognised faces in {os.path.basename(img_path)} -> {row['people_tags']}", log_path)

    if updated:
        write_csv_dict(csv_path, rows, fieldnames)
        log(f"Face recognition complete. Updated people_tags for {updated} images. Saved: {csv_path}", log_path)
    else:
        log("Face recognition complete. No images were updated.", log_path)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Recognise known faces in a MemoGraph trip.")
    p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/test_trip)")
    args = p.parse_args()

    recognise_faces(args.trip_folder)

