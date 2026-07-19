#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_vision_llm.py

Download Vision LLM models for MemoGraph image captioning:

1. LLaVA OneVision 0.5B  (~1.7 GB)  - Lightweight multimodal model
   Source: llava-hf/llava-onevision-qwen2-0.5b-ov-hf (Hugging Face)

2. Qwen2.5-VL-7B-AWQ     (~5 GB)   - High-quality quantised multimodal model
   Source: Qwen/Qwen2.5-VL-7B-Instruct-AWQ (Hugging Face)

Models are saved under the project's models/ directory:
  models/llava_onevision_qwen2_0.5b/
  models/qwen2.5_vl_7b_awq/

Usage:
    source .venv/bin/activate
    python -m scripts.download_vision_llm

    # Download only one model:
    python -m scripts.download_vision_llm --model llava-0.5b
    python -m scripts.download_vision_llm --model qwen-7b
"""

import argparse
import os
import sys
import time


MODELS_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

LLAVA_05B_ID  = "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"
LLAVA_05B_DIR = os.path.join(MODELS_BASE, "llava_onevision_qwen2_0.5b")

QWEN_7B_ID  = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"
QWEN_7B_DIR = os.path.join(MODELS_BASE, "qwen2.5_vl_7b_awq")


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


def download_llava_05b(output_dir=None):
    """Download LLaVA OneVision 0.5B for lightweight image captioning."""
    output_dir = output_dir or LLAVA_05B_DIR

    if os.path.exists(os.path.join(output_dir, "config.json")):
        size = _dir_size(output_dir)
        print(f"  LLaVA OneVision 0.5B already exists at {output_dir} ({_size_fmt(size)})")
        print("  Skipping download. Use --force to re-download.")
        return output_dir

    print(f"  Downloading LLaVA OneVision 0.5B from {LLAVA_05B_ID}...")
    print(f"  Destination: {output_dir}")
    print(f"  Expected size: ~1.7 GB")
    print()

    os.makedirs(output_dir, exist_ok=True)
    start = time.time()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=LLAVA_05B_ID,
        local_dir=output_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )

    elapsed = time.time() - start
    size = _dir_size(output_dir)
    print(f"\n  LLaVA OneVision 0.5B downloaded successfully!")
    print(f"  Size: {_size_fmt(size)} | Time: {elapsed:.0f}s")
    print(f"  Location: {os.path.abspath(output_dir)}")
    return output_dir


def download_qwen_7b(output_dir=None):
    """Download Qwen2.5-VL-7B-Instruct-AWQ for high-quality image captioning."""
    output_dir = output_dir or QWEN_7B_DIR

    if os.path.exists(os.path.join(output_dir, "config.json")):
        size = _dir_size(output_dir)
        print(f"  Qwen2.5-VL-7B-AWQ already exists at {output_dir} ({_size_fmt(size)})")
        print("  Skipping download. Use --force to re-download.")
        return output_dir

    print(f"  Downloading Qwen2.5-VL-7B-Instruct-AWQ from {QWEN_7B_ID}...")
    print(f"  Destination: {output_dir}")
    print(f"  Expected size: ~5 GB")
    print()

    os.makedirs(output_dir, exist_ok=True)
    start = time.time()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=QWEN_7B_ID,
        local_dir=output_dir,
        ignore_patterns=["*.md", "*.txt", ".gitattributes"],
    )

    elapsed = time.time() - start
    size = _dir_size(output_dir)
    print(f"\n  Qwen2.5-VL-7B-AWQ downloaded successfully!")
    print(f"  Size: {_size_fmt(size)} | Time: {elapsed:.0f}s")
    print(f"  Location: {os.path.abspath(output_dir)}")
    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Download Vision LLM models for MemoGraph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Models downloaded:
  LLaVA OneVision 0.5B   (~1.7 GB)  - Lightweight multimodal model
  Qwen2.5-VL-7B-AWQ      (~5 GB)    - High-quality quantised multimodal model

Total download: ~6.7 GB
        """,
    )
    parser.add_argument(
        "--model",
        choices=["llava-0.5b", "qwen-7b", "all"],
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
        if args.model in ("llava-0.5b", "all") and os.path.exists(LLAVA_05B_DIR):
            print(f"  Removing existing LLaVA 0.5B at {LLAVA_05B_DIR}...")
            shutil.rmtree(LLAVA_05B_DIR)
        if args.model in ("qwen-7b", "all") and os.path.exists(QWEN_7B_DIR):
            print(f"  Removing existing Qwen 7B at {QWEN_7B_DIR}...")
            shutil.rmtree(QWEN_7B_DIR)

    print()
    print("=" * 60)
    print("  MemoGraph Vision LLM Downloader")
    print("=" * 60)
    print()

    if args.model in ("llava-0.5b", "all"):
        print("[1] LLaVA OneVision 0.5B (Lightweight)")
        print("-" * 40)
        download_llava_05b()
        print()

    if args.model in ("qwen-7b", "all"):
        print("[2] Qwen2.5-VL-7B-Instruct-AWQ (High Quality)")
        print("-" * 40)
        download_qwen_7b()
        print()

    print("=" * 60)
    print("  All downloads complete!")
    print()
    print("  Next steps:")
    print("    1. Run the pipeline:  python run_all.py data/trips/<trip> --reset")
    print("    2. Or run vision LLM only:")
    print("       python -m scripts.batch_vision_llm data/trips/<trip>")
    print("    3. Force a specific model:")
    print('       Set VLM_MODEL_OVERRIDE = "qwen-7b" in memograph_config.py')
    print("=" * 60)


if __name__ == "__main__":
    main()
