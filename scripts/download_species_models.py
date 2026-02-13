#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_species_models.py

Download AI models for wildlife detection and species classification:

1. Grounding DINO Tiny   - Open-vocabulary object detector (~380MB)
   Detects birds, butterflies, insects etc. with bounding boxes.
   Source: IDEA-Research/grounding-dino-tiny (Hugging Face)

2. BioCLIP 2             - Biology-focused species classifier (~1.8GB)
   Classifies 952,000+ taxa: birds, insects, butterflies, plants, etc.
   Source: imageomics/bioclip-2 (Hugging Face)

Models are saved under the project's models/ directory:
  models/grounding_dino_tiny/
  models/bioclip2/

Usage:
    source .venv/bin/activate
    python -m scripts.download_species_models

    # Download only one model:
    python -m scripts.download_species_models --model grounding-dino
    python -m scripts.download_species_models --model bioclip2
"""

import argparse
import os
import sys
import time


MODELS_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

GROUNDING_DINO_ID = "IDEA-Research/grounding-dino-tiny"
GROUNDING_DINO_DIR = os.path.join(MODELS_BASE, "grounding_dino_tiny")

BIOCLIP2_ID = "imageomics/bioclip-2"
BIOCLIP2_DIR = os.path.join(MODELS_BASE, "bioclip2")


def _size_fmt(num_bytes):
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def _dir_size(path):
    """Get total size of a directory."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def download_grounding_dino(output_dir=None):
    """Download Grounding DINO Tiny for open-vocabulary object detection."""
    output_dir = output_dir or GROUNDING_DINO_DIR

    # Check if already downloaded
    if os.path.exists(os.path.join(output_dir, "config.json")):
        size = _dir_size(output_dir)
        print(f"  Grounding DINO Tiny already exists at {output_dir} ({_size_fmt(size)})")
        print("  Skipping download. Use --force to re-download.")
        return output_dir

    print(f"  Downloading Grounding DINO Tiny from {GROUNDING_DINO_ID}...")
    print(f"  Destination: {output_dir}")
    print(f"  Expected size: ~380 MB")
    print()

    os.makedirs(output_dir, exist_ok=True)
    start = time.time()

    from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

    print("  [1/2] Downloading processor...")
    processor = AutoProcessor.from_pretrained(GROUNDING_DINO_ID)
    processor.save_pretrained(output_dir)

    print("  [2/2] Downloading model weights...")
    model = AutoModelForZeroShotObjectDetection.from_pretrained(GROUNDING_DINO_ID)
    model.save_pretrained(output_dir)

    elapsed = time.time() - start
    size = _dir_size(output_dir)
    print(f"\n  Grounding DINO Tiny downloaded successfully!")
    print(f"  Size: {_size_fmt(size)} | Time: {elapsed:.0f}s")
    print(f"  Location: {os.path.abspath(output_dir)}")
    return output_dir


def download_bioclip2(output_dir=None):
    """Download BioCLIP 2 for species classification (952K taxa)."""
    output_dir = output_dir or BIOCLIP2_DIR

    # Check if already downloaded
    if os.path.exists(os.path.join(output_dir, "open_clip_pytorch_model.bin")) or \
       os.path.exists(os.path.join(output_dir, "open_clip_model.safetensors")):
        size = _dir_size(output_dir)
        print(f"  BioCLIP 2 already exists at {output_dir} ({_size_fmt(size)})")
        print("  Skipping download. Use --force to re-download.")
        return output_dir

    print(f"  Downloading BioCLIP 2 from {BIOCLIP2_ID}...")
    print(f"  Destination: {output_dir}")
    print(f"  Expected size: ~1.8 GB")
    print()

    os.makedirs(output_dir, exist_ok=True)
    start = time.time()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=BIOCLIP2_ID,
        local_dir=output_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )

    elapsed = time.time() - start
    size = _dir_size(output_dir)
    print(f"\n  BioCLIP 2 downloaded successfully!")
    print(f"  Size: {_size_fmt(size)} | Time: {elapsed:.0f}s")
    print(f"  Location: {os.path.abspath(output_dir)}")
    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Download species detection & classification models for MemoGraph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Models downloaded:
  Grounding DINO Tiny  (~380 MB)  - Object detection with bounding boxes
  BioCLIP 2            (~1.8 GB)  - Species classification (952K+ taxa)

Total download: ~2.2 GB
        """,
    )
    parser.add_argument(
        "--model",
        choices=["grounding-dino", "bioclip2", "all"],
        default="all",
        help="Which model to download (default: all).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if model already exists.",
    )
    args = parser.parse_args()

    if args.force:
        import shutil
        if args.model in ("grounding-dino", "all") and os.path.exists(GROUNDING_DINO_DIR):
            print(f"  Removing existing Grounding DINO at {GROUNDING_DINO_DIR}...")
            shutil.rmtree(GROUNDING_DINO_DIR)
        if args.model in ("bioclip2", "all") and os.path.exists(BIOCLIP2_DIR):
            print(f"  Removing existing BioCLIP 2 at {BIOCLIP2_DIR}...")
            shutil.rmtree(BIOCLIP2_DIR)

    print()
    print("=" * 60)
    print("  MemoGraph Species Model Downloader")
    print("=" * 60)
    print()

    if args.model in ("grounding-dino", "all"):
        print("[1] Grounding DINO Tiny (Object Detection)")
        print("-" * 40)
        download_grounding_dino()
        print()

    if args.model in ("bioclip2", "all"):
        print("[2] BioCLIP 2 (Species Classification)")
        print("-" * 40)
        download_bioclip2()
        print()

    print("=" * 60)
    print("  All downloads complete!")
    print()
    print("  Next steps:")
    print("    1. Run the pipeline:  python run_all.py data/trips/<trip> --reset")
    print("    2. Or run species detection only:")
    print("       python -m scripts.species_detector data/trips/<trip>")
    print("=" * 60)


if __name__ == "__main__":
    main()
