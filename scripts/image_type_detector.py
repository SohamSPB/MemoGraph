#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_type_detector.py

Assigns a coarse image_type to each image using CLIP zero-shot classification.

Categories (fixed set for now):
    - natural_photo
    - document_scan
    - meme_or_graphic
    - screenshot
    - chart_or_plot

Writes into the `image_type` column in labels.csv (as defined in
memograph_config.CSV_HEADERS). This script is designed to be idempotent:
rows where image_type is already non-empty are skipped, so it can be
re-run to fill only missing entries.

Logs to <trip_folder>/MemoGraph/logs/image_type_detector.log
"""

import os
from typing import Dict, List

import torch
import clip
from PIL import Image

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_image import resize_image
from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import init_log, log


IMAGE_TYPE_LABELS = {
    "natural_photo": "a natural photograph of the real world taken with a camera",
    "document_scan": "a scanned document or page of printed or handwritten text",
    "meme_or_graphic": "a meme or graphic image with bold text or illustration",
    "screenshot": "a screenshot of a screen, website, application or chat window",
    "chart_or_plot": "a chart, graph, data visualization or plot of numbers",
}


def _ensure_image_type_column(rows: List[Dict[str, str]]) -> None:
    """
    Ensure each row dict has an image_type key so downstream logic can
    safely read/write it even if older CSVs did not contain the column.
    """
    for r in rows:
        if "image_type" not in r:
            r["image_type"] = ""


def classify_image_type(
    image_path: str,
    model,
    preprocess,
    device: str,
) -> str:
    """
    Run CLIP zero-shot classification over the fixed IMAGE_TYPE_LABELS prompts
    and return the best-matching image_type key.
    """
    image = Image.open(image_path).convert("RGB")
    image = resize_image(image)
    image = preprocess(image).unsqueeze(0).to(device)

    text_labels = list(IMAGE_TYPE_LABELS.keys())
    text_prompts = [IMAGE_TYPE_LABELS[k] for k in text_labels]

    with torch.no_grad():
        text_tokens = clip.tokenize(text_prompts).to(device)
        image_features = model.encode_image(image)
        text_features = model.encode_text(text_tokens)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        logits = (100.0 * image_features @ text_features.T).softmax(dim=-1)[0]
        top_prob, top_idx = logits.max(dim=0)

    return text_labels[int(top_idx)]


def detect_image_types(trip_folder: str) -> None:
    """
    Main entrypoint: populate the image_type column in labels.csv for the
    given trip_folder, skipping rows that already have a non-empty image_type.
    """
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    log_path = os.path.join(logs_dir, "image_type_detector.log") if CFG.LOG_TO_FILE else None

    init_log(log_path, "image_type_detector.py")

    csv_path = os.path.join(memo_dir, "labels.csv")
    if not os.path.exists(csv_path):
        log(f"ERROR: labels.csv not found at {csv_path}", log_path)
        return

    rows = read_csv_dict(csv_path)
    if not rows:
        log("No rows found in CSV.", log_path)
        return

    _ensure_image_type_column(rows)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    log(f"Using device: {device}", log_path)

    updated = 0
    for idx, row in enumerate(rows, 1):
        # Content duplicate: image_type is copied from the canonical by
        # dedup_broadcast.py at the end of the pipeline.
        if (row.get("duplicate_of") or "").strip():
            continue
        # Skip if image_type is already set (idempotent behavior)
        if row.get("image_type"):
            continue

        local_path = row.get("local_path", "")
        if not local_path:
            log(f"[{idx}] Missing local_path in row; skipping.", log_path)
            continue

        image_path = os.path.join(trip_folder, local_path)
        if not os.path.exists(image_path):
            log(f"[{idx}] Missing image: {image_path}", log_path)
            continue

        try:
            image_type = classify_image_type(image_path, model, preprocess, device)
            row["image_type"] = image_type
            updated += 1
            log(f"[{idx}] {os.path.basename(image_path)} -> image_type={image_type}", log_path)
        except Exception as e:
            log(f"[{idx}] Failed to classify {image_path}: {e}", log_path)

    # Preserve any additional columns that may exist in the CSV.
    write_csv_dict(csv_path, rows, rows[0].keys())
    log(f"Image type detection complete. Updated {updated} rows. Saved: {csv_path}", log_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect coarse image_type using CLIP.")
    parser.add_argument(
        "--trip-folder",
        required=True,
        help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)",
    )
    args = parser.parse_args()

    detect_image_types(args.trip_folder)

