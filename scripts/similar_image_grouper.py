#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
similar_image_grouper.py

Groups visually similar images taken within a short time window.
Merges and propagates labels/species across similar images in a group.

This helps when:
1. Multiple shots of the same subject have inconsistent detection
2. One image in a sequence has better detection that can be shared
3. AI captions are better on some images than others
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
from collections import Counter

import torch
import clip
from PIL import Image

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import init_log, log
from scripts.utils.utils_image import resize_image
from memograph_config import ensure_memograph_folder

# Configuration
TIME_WINDOW_SECONDS = 300  # 5 minutes - images within this window are candidates
SIMILARITY_THRESHOLD = 0.85  # CLIP embedding cosine similarity threshold
MIN_GROUP_SIZE = 2  # Minimum images to form a group


def parse_datetime(dt_str: str) -> datetime | None:
    """Parse datetime string from EXIF format."""
    if not dt_str:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def compute_image_embedding(image_path: str, model, preprocess, device) -> torch.Tensor | None:
    """Compute CLIP embedding for an image."""
    try:
        image = Image.open(image_path).convert("RGB")
        image = resize_image(image)
        image = preprocess(image).unsqueeze(0).to(device)
        with torch.no_grad():
            features = model.encode_image(image)
            features /= features.norm(dim=-1, keepdim=True)
        return features.cpu()
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None


def find_time_neighbors(rows: List[Dict], time_window: int = TIME_WINDOW_SECONDS) -> Dict[int, List[int]]:
    """Find indices of images within time window of each image.

    Content-duplicate rows (duplicate_of set) are excluded from grouping —
    they share bytes with their canonical so any "similarity" relation is
    trivially true, and dedup_broadcast.py already copies analysis between
    them. Including them would just clutter the groups.
    """
    neighbors = {}
    datetimes = []
    is_duplicate: List[bool] = []

    for row in rows:
        dt = parse_datetime(row.get("datetime_original", ""))
        datetimes.append(dt)
        is_duplicate.append(bool((row.get("duplicate_of") or "").strip()))

    for i, dt_i in enumerate(datetimes):
        if dt_i is None or is_duplicate[i]:
            neighbors[i] = []
            continue

        nearby = []
        for j, dt_j in enumerate(datetimes):
            if i == j or dt_j is None or is_duplicate[j]:
                continue
            if abs((dt_i - dt_j).total_seconds()) <= time_window:
                nearby.append(j)
        neighbors[i] = nearby

    return neighbors


def compute_similarity(emb1: torch.Tensor, emb2: torch.Tensor) -> float:
    """Compute cosine similarity between two embeddings."""
    return float(torch.mm(emb1, emb2.T).squeeze())


def find_similar_groups(
    rows: List[Dict],
    trip_folder: str,
    model,
    preprocess,
    device,
    log_path: str = None
) -> List[Set[int]]:
    """Find groups of visually similar images within time windows."""

    # First, find time-based neighbors
    time_neighbors = find_time_neighbors(rows)

    # Compute embeddings only for images that have neighbors
    embeddings = {}
    images_to_process = set()
    for i, neighbors in time_neighbors.items():
        if neighbors:
            images_to_process.add(i)
            images_to_process.update(neighbors)

    log(f"Computing embeddings for {len(images_to_process)} images with time neighbors...", log_path)

    for i in images_to_process:
        img_path = os.path.join(trip_folder, rows[i].get("local_path", ""))
        if os.path.exists(img_path):
            embeddings[i] = compute_image_embedding(img_path, model, preprocess, device)

    # Find similar pairs using both time proximity and visual similarity
    similar_pairs = []
    for i, neighbors in time_neighbors.items():
        if i not in embeddings or embeddings[i] is None:
            continue

        for j in neighbors:
            if j not in embeddings or embeddings[j] is None:
                continue

            sim = compute_similarity(embeddings[i], embeddings[j])
            if sim >= SIMILARITY_THRESHOLD:
                similar_pairs.append((i, j, sim))

    log(f"Found {len(similar_pairs)} similar image pairs", log_path)

    # Build groups using union-find
    parent = list(range(len(rows)))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i, j, sim in similar_pairs:
        union(i, j)

    # Collect groups
    groups_dict = {}
    for i in range(len(rows)):
        root = find(i)
        if root not in groups_dict:
            groups_dict[root] = set()
        groups_dict[root].add(i)

    # Filter to groups with minimum size
    groups = [g for g in groups_dict.values() if len(g) >= MIN_GROUP_SIZE]
    log(f"Found {len(groups)} image groups with {MIN_GROUP_SIZE}+ images", log_path)

    return groups


def merge_tags(tag_strings: List[str]) -> str:
    """Merge multiple tag strings, keeping most common tags first."""
    all_tags = []
    for tag_str in tag_strings:
        if tag_str:
            tags = [t.strip() for t in tag_str.replace(";", ",").split(",") if t.strip()]
            all_tags.extend(tags)

    if not all_tags:
        return ""

    # Count occurrences and sort by frequency
    counter = Counter(all_tags)
    # Keep tags that appear in at least 1/3 of images, or top 5
    threshold = max(1, len(tag_strings) // 3)
    common_tags = [tag for tag, count in counter.most_common() if count >= threshold][:5]

    return "; ".join(common_tags)


def select_best_caption(captions: List[str]) -> str:
    """Select the best caption from a group (longest and most descriptive)."""
    valid_captions = [c for c in captions if c and len(c) > 10]
    if not valid_captions:
        return captions[0] if captions else ""

    # Prefer captions that mention specific subjects
    subject_keywords = ["bird", "butterfly", "animal", "flower", "person", "building"]
    for caption in valid_captions:
        if any(kw in caption.lower() for kw in subject_keywords):
            return caption

    # Otherwise return the longest
    return max(valid_captions, key=len)


def propagate_labels_in_group(rows: List[Dict], group: Set[int], log_path: str = None) -> int:
    """Propagate and merge labels within a group of similar images."""
    if len(group) < MIN_GROUP_SIZE:
        return 0

    group_list = sorted(group)
    group_rows = [rows[i] for i in group_list]

    # Collect all labels from group
    detected_objects = [r.get("detected_objects", "") for r in group_rows]
    species_tags = [r.get("species_tags", "") for r in group_rows]
    captions = [r.get("caption", "") for r in group_rows]
    captions_ai = [r.get("caption_ai", "") for r in group_rows]

    # Merge labels
    merged_objects = merge_tags(detected_objects)
    merged_species = merge_tags(species_tags)
    best_caption = select_best_caption(captions)
    best_caption_ai = select_best_caption(captions_ai)

    # Apply merged labels to all images in group
    updated = 0
    for i in group_list:
        row = rows[i]

        # Only update if new merged labels are better/different
        old_objects = row.get("detected_objects", "")
        old_species = row.get("species_tags", "")

        if merged_objects and (not old_objects or len(merged_objects) > len(old_objects)):
            row["detected_objects"] = merged_objects
            updated += 1

        if merged_species and (not old_species or len(merged_species) > len(old_species)):
            row["species_tags"] = merged_species

    if updated > 0:
        log(f"Group of {len(group)} images: merged tags = '{merged_species}'", log_path)

    return updated


def process_similar_images(trip_folder: str):
    """Main function to find and process similar image groups."""
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    log_path = os.path.join(logs_dir, "similar_image_grouper.log")
    csv_path = os.path.join(memo_dir, "labels.csv")

    init_log(log_path, "similar_image_grouper.py")
    log(f"Processing: {trip_folder}", log_path)

    rows = read_csv_dict(csv_path)
    if not rows:
        log("No rows found in CSV.", log_path)
        return

    # Load CLIP model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    log(f"Using device: {device}", log_path)

    # Find similar groups
    groups = find_similar_groups(rows, trip_folder, model, preprocess, device, log_path)

    # Propagate labels within groups
    total_updated = 0
    for group in groups:
        updated = propagate_labels_in_group(rows, group, log_path)
        total_updated += updated

    # Save updated CSV
    if total_updated > 0:
        write_csv_dict(csv_path, rows, rows[0].keys())
        log(f"Updated {total_updated} images across {len(groups)} groups", log_path)
    else:
        log("No updates needed", log_path)

    # Print summary
    print(f"\nSimilar Image Groups Found: {len(groups)}")
    for i, group in enumerate(groups, 1):
        group_list = sorted(group)
        filenames = [rows[j].get("image_name", "") for j in group_list]
        print(f"\nGroup {i} ({len(group)} images):")
        for fn in filenames:
            print(f"  - {fn}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m scripts.similar_image_grouper <trip_folder>")
        print("Example: python -m scripts.similar_image_grouper data/trips/2025_Annapurna_Nepal")
        sys.exit(1)

    trip_folder = sys.argv[1]
    process_similar_images(trip_folder)
