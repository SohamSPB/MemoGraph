#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_gpu_processor.py

Unified batch processor that runs all GPU-based AI models on images.
Keeps all models loaded in memory and processes images efficiently.

Features:
- Loads CLIP, BLIP, LLaVA models once at startup
- Processes images through all models in a single pass
- Real-time resource monitoring (CPU, RAM, GPU)
- Detailed timing and throughput statistics
- Saves results incrementally to prevent data loss

Usage:
    python -m scripts.batch_gpu_processor data/trips/MyTrip
    python -m scripts.batch_gpu_processor --all-trips  # Process all trips

RTX 3060 12GB Budget:
- CLIP: ~1GB
- BLIP: ~2GB
- LLaVA: ~2GB
- Processing buffers: ~2-3GB
- Total: ~7-8GB used, ~4-5GB free for safety margin
"""

import os
import sys
import time
import argparse
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

from scripts.gpu_model_manager import GPUModelManager, ResourceSnapshot
from scripts.utils.utils_io import read_csv_dict, write_csv_dict, backup_csv
from scripts.utils.utils_log import init_log, log, get_logger
import memograph_config as CFG


# CLIP concepts - comprehensive list for scene/object detection
CLIP_CONCEPTS = [
    # Nature / landscapes
    "mountain", "valley", "lake", "river", "waterfall", "ocean", "beach",
    "forest", "jungle", "desert", "snow", "glacier", "cliff", "cave",
    "landscape", "scenic view", "panorama", "hill", "meadow", "field",

    # Wildlife - Birds
    "bird", "eagle", "sparrow", "crow", "pigeon", "parrot", "peacock",
    "owl", "kingfisher", "heron", "duck", "swan", "vulture", "hawk",

    # Wildlife - Animals
    "animal", "dog", "cat", "horse", "cow", "goat", "sheep", "yak",
    "elephant", "tiger", "deer", "monkey", "buffalo", "donkey", "camel",

    # Wildlife - Insects & small creatures
    "insect", "butterfly", "bee", "dragonfly", "spider", "ant", "beetle",
    "grasshopper", "moth", "caterpillar", "snail", "frog", "lizard", "snake",

    # Plants & Flowers
    "flower", "plant", "tree", "grass", "bush", "garden", "rose", "lotus",
    "sunflower", "tulip", "orchid", "palm tree", "pine tree", "bamboo",

    # People
    "person", "group of people", "crowd", "selfie", "portrait", "family",
    "child", "old person", "traveler", "hiker", "local people",

    # Astro / night sky
    "night sky", "stars", "Milky Way", "galaxy", "nebula",
    "star cluster", "astrophotography", "moon", "sun",
    "eclipse", "Andromeda galaxy", "Orion nebula", "aurora",

    # Temples / monuments / heritage
    "temple", "monastery", "stupa", "church", "mosque", "shrine",
    "palace", "fort", "castle", "monument", "historical gate", "ruins",
    "statue", "sculpture", "ancient architecture", "heritage building",

    # Urban / city
    "cityscape", "street market", "bazaar", "narrow street", "alley",
    "building", "skyscraper", "museum", "art gallery", "old town square",
    "shop", "store", "mall", "parking lot", "bus stop", "train station",

    # Food / cafes / restaurants
    "plate of food", "thali", "street food stall", "bowl of curry", "rice",
    "cup of tea", "cup of coffee", "glass of chai", "juice", "water bottle",
    "restaurant interior", "cafe", "dessert plate", "pizza", "burger", "sandwich",
    "fruit", "vegetables", "bread", "noodles", "soup", "salad", "ice cream",

    # Stays / camps / roads
    "hotel room", "guesthouse", "homestay", "campsite", "tent", "cabin",
    "campfire", "mountain road", "hiking trail", "suspension bridge", "pathway",
    "bus on a mountain road", "highway through the mountains", "tunnel",

    # Transportation
    "car", "motorcycle", "bicycle", "bus", "truck", "train", "airplane",
    "boat", "ship", "ferry", "rickshaw", "taxi", "jeep",

    # Time of day
    "sunrise", "sunset", "dawn", "dusk", "cityscape at night", "golden hour",

    # Indoor scenes
    "bedroom", "living room", "kitchen", "bathroom", "office", "classroom",
    "library", "gym", "hospital", "airport", "lobby", "corridor",

    # Electronics / tech
    "circuit board", "electronics", "computer chip", "wiring", "soldering",
    "motherboard", "screen", "monitor", "keyboard", "mouse", "laptop",
    "smartphone", "tablet", "television", "camera", "headphones",

    # Everyday objects
    "sign", "billboard", "poster", "rock", "stone", "wall", "lamp",
    "light", "street light", "window", "door", "furniture", "chair",
    "table", "fence", "gate", "pole", "wire", "road sign", "mirror",
    "clock", "bag", "umbrella", "hat", "shoes", "clothes",

    # Activities
    "hiking", "camping", "swimming", "fishing", "cycling", "climbing",
    "cooking", "eating", "dancing", "playing", "reading", "working",
]

# Biological species for filtering
BIOLOGICAL_SPECIES = {
    # Birds
    "bird", "eagle", "sparrow", "crow", "pigeon", "parrot", "peacock",
    "owl", "kingfisher", "heron", "duck", "swan", "vulture", "hawk",
    # Plants & Flowers
    "plant", "flower", "grass", "bush", "tree",
    "rose", "lotus", "sunflower", "orchid", "tulip", "lily",
    "marigold", "hibiscus", "jasmine", "dahlia", "lavender", "daisy",
    # Insects
    "insect", "butterfly", "bee", "dragonfly", "spider", "ant", "beetle",
    "grasshopper", "moth", "caterpillar", "snail",
    # Animals
    "animal", "cat", "dog", "horse", "cow", "goat", "sheep", "yak",
    "elephant", "tiger", "deer", "monkey", "buffalo", "frog", "lizard", "snake",
    "fish", "rabbit", "squirrel", "camel",
}


def find_all_trips(data_root: str = None) -> List[str]:
    """Find all trip folders in the data root."""
    if data_root is None:
        data_root = CFG.DATA_ROOT

    trips = []
    for name in os.listdir(data_root):
        path = os.path.join(data_root, name)
        if os.path.isdir(path) and name not in ('index.html', '.', '..'):
            # Check if it has images
            has_images = any(
                f.lower().endswith(('.jpg', '.jpeg', '.png'))
                for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))
            )
            if has_images:
                trips.append(path)

    return sorted(trips)


def get_images_to_process(csv_path: str, trip_folder: str, force_reprocess: bool = False) -> List[Dict]:
    """Get list of images that need processing."""
    rows = read_csv_dict(csv_path)
    if not rows:
        return []

    to_process = []
    for row in rows:
        # Check which fields need processing
        needs_clip = not row.get("detected_objects", "").strip()
        needs_blip = not row.get("caption", "").strip()
        needs_llava = not row.get("vision_caption", "").strip()

        if force_reprocess or needs_clip or needs_blip or needs_llava:
            local_path = row.get("local_path", "")
            full_path = os.path.join(trip_folder, local_path)
            if os.path.exists(full_path):
                to_process.append({
                    'row': row,
                    'path': full_path,
                    'needs_clip': needs_clip or force_reprocess,
                    'needs_blip': needs_blip or force_reprocess,
                    'needs_llava': needs_llava or force_reprocess,
                })

    return to_process


def process_trip(
    trip_folder: str,
    manager: GPUModelManager,
    models: List[str] = None,
    force_reprocess: bool = False,
    save_interval: int = 5,
    log_func=print
) -> Dict[str, Any]:
    """
    Process a single trip with all loaded models.

    Returns:
        Dict with processing statistics
    """
    trip_name = os.path.basename(trip_folder)
    memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
    csv_path = os.path.join(memo_dir, "labels.csv")
    log_path = os.path.join(logs_dir, "batch_gpu_processor.log")

    init_log(log_path, "batch_gpu_processor.py")

    if not os.path.exists(csv_path):
        log(f"No labels.csv found for {trip_name}", log_path)
        return {'trip': trip_name, 'error': 'No labels.csv'}

    # Backup before processing
    backup_csv(csv_path, max_backups=3, log_path=log_path)

    # Get images to process
    to_process = get_images_to_process(csv_path, trip_folder, force_reprocess)
    if not to_process:
        log(f"No images need processing in {trip_name}", log_path)
        return {'trip': trip_name, 'images': 0, 'skipped': 'all up to date'}

    log(f"Processing {len(to_process)} images in {trip_name}", log_path)
    log_func(f"\n{'='*60}")
    log_func(f"Trip: {trip_name} ({len(to_process)} images)")
    log_func(f"{'='*60}")

    # Read all rows for updating
    all_rows = read_csv_dict(csv_path)
    row_map = {r.get('local_path', ''): r for r in all_rows}

    stats = {
        'trip': trip_name,
        'total_images': len(to_process),
        'processed': 0,
        'clip_updated': 0,
        'blip_updated': 0,
        'llava_updated': 0,
        'failed': 0,
        'start_time': time.time(),
    }

    manager.resource_monitor.start()

    for i, item in enumerate(to_process, 1):
        img_path = item['path']
        row = item['row']
        local_path = row.get('local_path', '')

        try:
            from PIL import Image
            image = Image.open(img_path).convert("RGB")
            image = manager.resize_image(image)

            img_start = time.time()

            # Process with CLIP if needed
            if item['needs_clip'] and 'clip' in manager._loaded:
                labels = manager.process_clip(image, CLIP_CONCEPTS)
                if labels:
                    row['detected_objects'] = "; ".join(labels)
                    # Extract species
                    species = [l for l in labels if l.lower() in BIOLOGICAL_SPECIES]
                    if species:
                        row['species_tags'] = "; ".join(species)
                    stats['clip_updated'] += 1

            # Process with BLIP if needed
            if item['needs_blip'] and 'blip' in manager._loaded:
                caption = manager.process_blip(image)
                if caption:
                    row['caption'] = caption
                    stats['blip_updated'] += 1

            # Process with LLaVA if needed
            if item['needs_llava'] and 'llava' in manager._loaded:
                description = manager.process_llava(image)
                if description:
                    row['vision_caption'] = description
                    stats['llava_updated'] += 1

            # Update row in map
            row_map[local_path] = row
            stats['processed'] += 1

            elapsed = time.time() - img_start
            log(f"[{i}/{len(to_process)}] {os.path.basename(img_path)}: {elapsed:.2f}s", log_path)

            # Log progress
            if i % 5 == 0 or i == len(to_process):
                snapshot = manager.resource_monitor.get_current()
                log_func(f"  [{i}/{len(to_process)}] {snapshot}")

            # Save incrementally
            if i % save_interval == 0:
                updated_rows = list(row_map.values())
                write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())
                log(f"Incremental save at image {i}", log_path)

        except Exception as e:
            stats['failed'] += 1
            log(f"[{i}/{len(to_process)}] FAILED {os.path.basename(img_path)}: {e}", log_path)
            log_func(f"  [{i}/{len(to_process)}] FAILED: {e}")

    # Final save
    updated_rows = list(row_map.values())
    write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())

    # Stop monitoring
    snapshots = manager.resource_monitor.stop()
    stats['end_time'] = time.time()
    stats['elapsed_seconds'] = stats['end_time'] - stats['start_time']
    stats['images_per_second'] = stats['processed'] / stats['elapsed_seconds'] if stats['elapsed_seconds'] > 0 else 0

    # Get peak resources
    if snapshots:
        peak = max(snapshots, key=lambda s: s.gpu_mb)
        stats['peak_gpu_mb'] = peak.gpu_mb
        stats['peak_ram_mb'] = peak.ram_mb

    log(f"Completed {trip_name}: {stats['processed']} images in {stats['elapsed_seconds']:.1f}s", log_path)
    log_func(f"  Completed: {stats['processed']} images, {stats['elapsed_seconds']:.1f}s, {stats['images_per_second']:.2f} img/s")

    return stats


def process_all_trips(
    trips: List[str],
    models: List[str] = None,
    force_reprocess: bool = False,
    log_func=print
) -> Dict[str, Any]:
    """
    Process all trips with shared model manager.

    Returns:
        Dict with overall statistics
    """
    if models is None:
        models = ['clip', 'blip', 'llava']

    overall_start = time.time()
    log_func("\n" + "="*70)
    log_func("MemoGraph Batch GPU Processor")
    log_func("="*70)
    log_func(f"Trips to process: {len(trips)}")
    log_func(f"Models: {models}")
    log_func(f"Force reprocess: {force_reprocess}")
    log_func("="*70)

    # Create and load model manager
    manager = GPUModelManager(max_image_size=getattr(CFG, 'MAX_IMAGE_SIZE', 1024))
    manager.load_models(models, log_func=log_func)

    # Count total images
    total_images = 0
    for trip in trips:
        memo_dir = os.path.join(trip, CFG.MEMOGRAPH_FOLDER_NAME)
        csv_path = os.path.join(memo_dir, "labels.csv")
        if os.path.exists(csv_path):
            to_process = get_images_to_process(csv_path, trip, force_reprocess)
            total_images += len(to_process)

    log_func(f"\nTotal images to process: {total_images}")

    # Process each trip
    all_stats = []
    for trip in trips:
        stats = process_trip(
            trip,
            manager,
            models=models,
            force_reprocess=force_reprocess,
            log_func=log_func
        )
        all_stats.append(stats)

    # Unload models
    manager.unload_models()

    # Calculate overall stats
    overall_stats = {
        'total_trips': len(trips),
        'total_images': sum(s.get('processed', 0) for s in all_stats),
        'total_failed': sum(s.get('failed', 0) for s in all_stats),
        'clip_updated': sum(s.get('clip_updated', 0) for s in all_stats),
        'blip_updated': sum(s.get('blip_updated', 0) for s in all_stats),
        'llava_updated': sum(s.get('llava_updated', 0) for s in all_stats),
        'elapsed_seconds': time.time() - overall_start,
        'trip_stats': all_stats,
    }

    if overall_stats['elapsed_seconds'] > 0:
        overall_stats['images_per_second'] = overall_stats['total_images'] / overall_stats['elapsed_seconds']

    # Print summary
    log_func("\n" + "="*70)
    log_func("PROCESSING COMPLETE")
    log_func("="*70)
    log_func(f"Trips processed: {overall_stats['total_trips']}")
    log_func(f"Images processed: {overall_stats['total_images']}")
    log_func(f"Failed: {overall_stats['total_failed']}")
    log_func(f"CLIP labels updated: {overall_stats['clip_updated']}")
    log_func(f"BLIP captions updated: {overall_stats['blip_updated']}")
    log_func(f"LLaVA descriptions updated: {overall_stats['llava_updated']}")
    log_func(f"Total time: {overall_stats['elapsed_seconds']:.1f}s ({overall_stats['elapsed_seconds']/60:.1f} min)")
    if overall_stats.get('images_per_second'):
        log_func(f"Throughput: {overall_stats['images_per_second']:.2f} images/second")
    log_func("="*70)

    return overall_stats


def main():
    parser = argparse.ArgumentParser(
        description="Batch GPU processor for MemoGraph - runs all AI models on images"
    )
    parser.add_argument(
        "trip_folder",
        nargs="?",
        help="Trip folder to process (or use --all-trips)"
    )
    parser.add_argument(
        "--all-trips",
        action="store_true",
        help="Process all trips in data/trips/"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["clip", "blip", "llava"],
        default=["clip", "blip", "llava"],
        help="Models to use (default: all)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess all images even if already processed"
    )

    args = parser.parse_args()

    if args.all_trips:
        trips = find_all_trips()
        if not trips:
            print("No trips found in data/trips/")
            sys.exit(1)
    elif args.trip_folder:
        if not os.path.isdir(args.trip_folder):
            print(f"Trip folder not found: {args.trip_folder}")
            sys.exit(1)
        trips = [args.trip_folder]
    else:
        parser.print_help()
        sys.exit(1)

    process_all_trips(
        trips,
        models=args.models,
        force_reprocess=args.force
    )


if __name__ == "__main__":
    main()
