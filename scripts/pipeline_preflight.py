#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_preflight.py

Pre-flight confirmation screen and post-flight summary for the MemoGraph pipeline.
Shows image counts, system info, resume progress, time estimates, and resource warnings
before starting the pipeline, and a completion summary afterwards.
"""

import os
import sys
import glob
import time
import platform
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import psutil

import memograph_config as CFG
from scripts.utils.utils_io import read_csv_dict


# ---------------------------------------------------------------------------
# Skip-condition mapping: column name -> "done" predicate
# ---------------------------------------------------------------------------
STEP_SKIP_CONDITIONS = {
    "Faces":       ("faces_count",      lambda v: v and v.strip() not in ("", "-1")),
    "Labels":      ("detected_objects",  lambda v: bool(v and v.strip())),
    "Captions":    ("caption",           lambda v: bool(v and v.strip())),
    "AI Captions": ("caption_ai",        lambda v: bool(v and v.strip())),
    "Species":     ("species_tags",      lambda v: bool(v and v.strip())),
    "Image Type":  ("image_type",        lambda v: bool(v and v.strip())),
    "Vision LLM":  ("vision_caption",    lambda v: bool(v and v.strip())),
    "Quality":     ("quality_score",     lambda v: bool(v and v.strip())),
    "Colors":      ("color_palette",     lambda v: bool(v and v.strip())),
}

# Map step display names to timing-dict keys
_STEP_TIMING_KEY = {
    "Faces": "faces", "Labels": "labels", "Captions": "captions",
    "AI Captions": "ai_captions", "Species": "species",
    "Image Type": "image_type", "Vision LLM": "vision_llm",
    "Quality": "quality", "Colors": "colors",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_images(trip_folder: str) -> Tuple[int, Dict[str, int]]:
    """Count images in *trip_folder* (not inside MemoGraph).

    Returns (total_count, {extension: count}).
    """
    ext_counts: Dict[str, int] = {}
    for ext in CFG.IMAGE_EXTENSIONS:
        pattern = os.path.join(trip_folder, f"*{ext}")
        matches = glob.glob(pattern, recursive=False)
        # Also check uppercase
        matches += glob.glob(os.path.join(trip_folder, f"*{ext.upper()}"), recursive=False)
        # Deduplicate (case-insensitive filesystems)
        unique = {os.path.normcase(p) for p in matches}
        if unique:
            ext_counts[ext] = len(unique)
    total = sum(ext_counts.values())
    return total, ext_counts


def get_resume_progress(csv_path: str) -> Dict[str, Tuple[int, int]]:
    """Check how many images already have each analysis column filled.

    Returns {step_name: (done_count, total_count)}, where `total` excludes
    md5-duplicates (rows with duplicate_of set) — those are filled in by
    dedup_broadcast.py, not by the individual analysis steps, so counting
    them as "pending" would understate progress.
    """
    rows = read_csv_dict(csv_path)
    if not rows:
        return {}
    # Treat duplicates as already-accounted-for by dedup_broadcast.
    non_dup_rows = [r for r in rows if not (r.get("duplicate_of") or "").strip()]
    total = len(non_dup_rows)
    progress: Dict[str, Tuple[int, int]] = {}
    for step_name, (col, predicate) in STEP_SKIP_CONDITIONS.items():
        done = sum(1 for r in non_dup_rows if predicate(r.get(col, "")))
        progress[step_name] = (done, total)
    return progress


def get_system_info() -> Dict[str, str]:
    """Gather basic system information for the pre-flight display."""
    info: Dict[str, str] = {}

    # CPU
    cores = psutil.cpu_count(logical=True)
    info["cpu"] = f"{cores} cores"

    # RAM
    mem = psutil.virtual_memory()
    info["ram"] = f"{mem.available / (1024**3):.1f} GB free / {mem.total / (1024**3):.1f} GB total"

    # GPU (best-effort)
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_free = mem_info.free / (1024**2)
                gpu_total = mem_info.total / (1024**2)
                info["gpu"] = f"{name} ({gpu_free:.0f} MB free / {gpu_total:.0f} MB total)"
            except Exception:
                info["gpu"] = name
        else:
            info["gpu"] = "No CUDA GPU detected"
    except ImportError:
        info["gpu"] = "PyTorch not installed"

    info["platform"] = f"{platform.system()} {platform.release()}"
    return info


def get_feature_flags() -> Dict[str, bool]:
    """Return the state of relevant feature flags from the config."""
    return {
        "Vision LLM":       getattr(CFG, "ENABLE_VISION_LLM", False),
        "Bird model":       getattr(CFG, "ENABLE_BIRD_MODEL", False),
        "Face recognition": getattr(CFG, "ENABLE_FACE_RECOGNITION", False),
        "Image quality":    getattr(CFG, "ENABLE_IMAGE_QUALITY", True),
    }


def get_last_run_info(logs_dir: str) -> Optional[Tuple[str, Optional[float]]]:
    """Parse the most recent run_all.log to find when the pipeline last ran.

    Returns (timestamp_str, duration_seconds) or None.
    """
    log_path = os.path.join(logs_dir, "run_all.log")
    if not os.path.isfile(log_path):
        return None
    try:
        mtime = os.path.getmtime(log_path)
        ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        # Try to extract duration from log (look for pipeline start/end)
        duration = None
        first_ts = None
        last_ts = None
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Lines typically start with "2024-01-05 12:34:56,789 - ..."
                if len(line) >= 19 and line[4] == '-' and line[10] == ' ':
                    try:
                        t = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
                        if first_ts is None:
                            first_ts = t
                        last_ts = t
                    except ValueError:
                        pass
        if first_ts and last_ts and last_ts > first_ts:
            duration = (last_ts - first_ts).total_seconds()
        return (ts, duration)
    except Exception:
        return None


def estimate_time(image_count: int, progress: Dict[str, Tuple[int, int]],
                  is_reset: bool) -> float:
    """Estimate remaining pipeline time in seconds."""
    total = 0.0

    # Fixed overhead steps (scan, days, location, blog/map/webapp, search)
    total += image_count * CFG.STEP_TIMING_PER_IMAGE.get("scan", 0.05)
    total += image_count * CFG.STEP_TIMING_PER_IMAGE.get("days", 0.01)
    total += image_count * CFG.STEP_TIMING_PER_IMAGE.get("location", 0.02)

    # Per-image analysis steps (skip already-done images unless reset)
    for step_name, timing_key in _STEP_TIMING_KEY.items():
        per_image = CFG.STEP_TIMING_PER_IMAGE.get(timing_key, 0.1)
        if is_reset or step_name not in progress:
            remaining = image_count
        else:
            done, total_imgs = progress[step_name]
            remaining = max(0, total_imgs - done)
        total += remaining * per_image

    # Similar grouping + bird refiner
    total += image_count * CFG.STEP_TIMING_PER_IMAGE.get("similar_grouping", 0.2)
    total += image_count * CFG.STEP_TIMING_PER_IMAGE.get("bird_refiner", 0.1)

    # Fixed-time steps
    for _name, secs in CFG.STEP_FIXED_TIME.items():
        total += secs

    return total


def estimate_output_size(image_count: int) -> float:
    """Rough estimate of MemoGraph output size in MB."""
    # ~50KB per thumbnail + ~2KB CSV row + ~50KB webapp overhead
    thumb_mb = image_count * 50 / 1024
    csv_mb = image_count * 2 / 1024
    overhead_mb = 2  # maps, blog, json, html
    return thumb_mb + csv_mb + overhead_mb


def check_resource_warnings(image_count: int) -> List[str]:
    """Return a list of warning strings if system resources look tight."""
    warnings: List[str] = []

    # RAM check
    mem = psutil.virtual_memory()
    avail_mb = mem.available / (1024**2)
    if avail_mb < CFG.MIN_AVAILABLE_RAM_MB:
        warnings.append(f"Low RAM: {avail_mb:.0f} MB free (min {CFG.MIN_AVAILABLE_RAM_MB} MB)")

    # GPU check
    try:
        import torch
        if torch.cuda.is_available():
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_free = mem_info.free / (1024**2)
                if gpu_free < CFG.MIN_AVAILABLE_GPU_MEM_MB:
                    warnings.append(f"Low GPU memory: {gpu_free:.0f} MB free (min {CFG.MIN_AVAILABLE_GPU_MEM_MB} MB)")
            except Exception:
                pass
    except ImportError:
        warnings.append("PyTorch not installed - GPU steps will fail")

    # Disk space check (rough)
    try:
        disk = psutil.disk_usage(os.getcwd())
        free_gb = disk.free / (1024**3)
        est_mb = estimate_output_size(image_count)
        if free_gb < est_mb / 1024 * 2:  # want 2x the estimate
            warnings.append(f"Low disk space: {free_gb:.1f} GB free")
    except Exception:
        pass

    return warnings


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}m"


# ---------------------------------------------------------------------------
# Display functions
# ---------------------------------------------------------------------------

def _bar(done: int, total: int, width: int = 20) -> str:
    """Render a simple ASCII progress bar."""
    if total == 0:
        return "[" + "-" * width + "]"
    filled = int(width * done / total)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def display_preflight(trip_folder: str, is_reset: bool, parallel: bool) -> None:
    """Print the pre-flight summary screen."""
    trip_name = os.path.basename(os.path.normpath(trip_folder))
    memo_dir = os.path.join(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
    csv_path = os.path.join(memo_dir, "labels.csv")
    logs_dir = os.path.join(memo_dir, CFG.LOG_DIR_NAME)

    image_count, ext_counts = count_images(trip_folder)
    sys_info = get_system_info()
    flags = get_feature_flags()

    has_csv = os.path.isfile(csv_path)
    is_fresh = is_reset or not has_csv

    progress = {} if is_fresh else get_resume_progress(csv_path)

    # Header
    separator = "=" * 60
    print()
    print(separator)
    if is_fresh:
        print(f"  MEMOGRAPH PIPELINE - FRESH RUN")
    else:
        print(f"  MEMOGRAPH PIPELINE - RESUME RUN")
    print(separator)

    # Trip info
    print(f"  Trip:     {trip_name}")
    print(f"  Path:     {trip_folder}")
    print(f"  Images:   {image_count}", end="")
    if ext_counts:
        parts = [f"{count} {ext}" for ext, count in sorted(ext_counts.items())]
        print(f"  ({', '.join(parts)})")
    else:
        print()
    print(f"  Mode:     {'Parallel' if parallel else 'Sequential'}")

    if is_reset:
        print(f"  Reset:    Yes (MemoGraph folder will be rebuilt)")

    # Last run info
    if not is_fresh:
        last_run = get_last_run_info(logs_dir)
        if last_run:
            ts, duration = last_run
            dur_str = f" ({format_time(duration)})" if duration else ""
            print(f"  Last run: {ts}{dur_str}")

    # System info
    print()
    print("  System:")
    print(f"    CPU:      {sys_info['cpu']}")
    print(f"    RAM:      {sys_info['ram']}")
    print(f"    GPU:      {sys_info['gpu']}")
    print(f"    Platform: {sys_info['platform']}")

    # Feature flags
    print()
    print("  Features:")
    for name, enabled in flags.items():
        status = "ON" if enabled else "OFF"
        print(f"    {name:<20s} {status}")

    # Progress (resume only)
    if progress:
        print()
        print("  Progress:")
        for step_name, (done, total) in progress.items():
            bar = _bar(done, total)
            pct = (done / total * 100) if total > 0 else 0
            status = "DONE" if done == total else f"{done}/{total}"
            print(f"    {step_name:<14s} {bar} {pct:5.1f}%  {status}")

    # Time & size estimates
    est_seconds = estimate_time(image_count, progress, is_fresh)
    est_mb = estimate_output_size(image_count)
    print()
    print(f"  Estimated time:   ~{format_time(est_seconds)}")
    print(f"  Estimated output: ~{est_mb:.0f} MB")

    # Resource warnings
    warnings = check_resource_warnings(image_count)
    if warnings:
        print()
        print("  Warnings:")
        for w in warnings:
            print(f"    ! {w}")

    print(separator)
    print()


def confirm_proceed(auto_yes: bool = False) -> bool:
    """Prompt the user to confirm pipeline execution.

    Returns True to proceed, False to abort.
    """
    if auto_yes:
        print("  Auto-confirmed (-y/--yes flag set)")
        print()
        return True

    try:
        answer = input("  Proceed? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    if answer in ("", "y", "yes"):
        return True

    print("  Aborted.")
    print()
    return False


# ---------------------------------------------------------------------------
# Post-flight summary
# ---------------------------------------------------------------------------

def display_postflight(
    trip_folder: str,
    step_results: List[Dict],
    interrupted_at: Optional[str],
    pipeline_start_time: float,
    estimated_time: float,
) -> None:
    """Print the post-flight summary screen.

    Parameters
    ----------
    trip_folder : str
        Path to the trip folder.
    step_results : list of dict
        Each dict has keys: name, status, time, items_processed, items_skipped.
        status is one of: "completed", "interrupted", "skipped", "failed".
    interrupted_at : str or None
        Name of step where Ctrl+C was pressed, or None for normal completion.
    pipeline_start_time : float
        time.time() when the pipeline started.
    estimated_time : float
        The pre-flight time estimate in seconds.
    """
    trip_name = os.path.basename(os.path.normpath(trip_folder))
    actual_time = time.time() - pipeline_start_time

    separator = "=" * 60

    print()
    print(separator)
    if interrupted_at:
        print("  PIPELINE INTERRUPTED")
    else:
        print("  PIPELINE COMPLETE")
    print(separator)

    print(f"  Trip: {trip_name}")
    print()

    # Step table
    if step_results:
        # Header
        print(f"  {'Step':<24s} {'Status':<13s} {'Time':>8s}  {'Processed':>5s}")
        print(f"  {'-'*24} {'-'*13} {'-'*8}  {'-'*5}")

        for r in step_results:
            name = r["name"]
            status = r["status"]
            elapsed = format_time(r["time"]) if r["time"] > 0 else "-"
            processed = r.get("items_processed")
            skipped = r.get("items_skipped", 0)

            # Status indicator
            if status == "completed":
                indicator = "OK"
            elif status == "interrupted":
                indicator = "INTERRUPTED"
            elif status == "skipped":
                indicator = "SKIPPED"
            elif status == "failed":
                indicator = "FAILED"
            else:
                indicator = status

            proc_str = str(processed) if processed is not None else "-"
            if skipped and processed is not None:
                proc_str = f"{processed} (+{skipped} skip)"

            print(f"  {name:<24s} {indicator:<13s} {elapsed:>8s}  {proc_str:>5s}")

    # Timing summary
    print()
    print(f"  Total time:     {format_time(actual_time)}")
    print(f"  Estimated was:  ~{format_time(estimated_time)}")
    if estimated_time > 0:
        ratio = actual_time / estimated_time
        if ratio < 0.8:
            print(f"  (Faster than estimated)")
        elif ratio > 1.2:
            print(f"  (Slower than estimated)")

    # Output artifacts
    memo_dir = os.path.join(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
    if os.path.isdir(memo_dir):
        # Calculate actual output size
        total_size = 0
        for dirpath, _dirnames, filenames in os.walk(memo_dir):
            for f in filenames:
                total_size += os.path.getsize(os.path.join(dirpath, f))
        print(f"  Output size:    {total_size / (1024*1024):.1f} MB")

    # Interrupt hint
    if interrupted_at:
        print()
        print(f"  Pipeline was interrupted during: {interrupted_at}")
        print(f"  To resume, run:")
        print(f"    python run_all.py {trip_folder}")
        print()
        print(f"  Already-processed images will be skipped automatically.")

    print(separator)
    print()
