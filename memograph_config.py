#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memograph_config.py

Global configuration for MemoGraph scripts.
Edit this file to customize paths, CSV headers, logging behavior, and backup settings.
"""

import os

# -----------------------------
# General Paths
# -----------------------------
# Root data folder (relative to script)
DATA_ROOT = os.path.join("data", "trips")

# -----------------------------
# CSV Configuration
# -----------------------------
CSV_HEADERS = [
	"image_name", "local_path", "md5sum", "datetime_original", "device_model",
	"gps_lat", "gps_lon", "location_inferred", "day_number",
	"detected_objects", "species_tags", "faces_detected", "people_tags",
	"caption", "caption_ai", "notes"
]

# -----------------------------
# Logging & Backups
# -----------------------------
MAX_BACKUPS = 3              # Number of CSV backup copies to maintain
LOG_DIR_NAME = "logs"        # Folder under MemoGraph for logs
LOG_FILE_NAME = "image_scanner.log"  # Default log file name
LOG_TO_FILE = True

# -----------------------------
# Image Settings
# -----------------------------
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tiff", ".png", ".jfif")
# Maximum image size (in pixels) for the longest side before feeding into models.
# Lower values reduce memory/compute at the cost of some detail.
MAX_IMAGE_SIZE = 256

# -----------------------------
# MemoGraph Folder
# -----------------------------
MEMOGRAPH_FOLDER_NAME = "MemoGraph"

# -----------------------------
# MemoGraph Folder
# -----------------------------
def ensure_memograph_folder(trip_folder):
	"""Ensure MemoGraph and logs folders exist inside the given trip folder."""
	memograph_dir = os.path.join(trip_folder, MEMOGRAPH_FOLDER_NAME)
	logs_dir = os.path.join(memograph_dir, LOG_DIR_NAME)
	os.makedirs(logs_dir, exist_ok=True)
	return memograph_dir, logs_dir

# -----------------------------
# Resource Management
# -----------------------------
# Safety thresholds to prevent system overload
MIN_AVAILABLE_RAM_MB = 2048  # e.g., 2GB
MIN_AVAILABLE_GPU_MEM_MB = 1024 # e.g., 1GB

# Number of parallel processes to use for top-level analysis steps in run_all.py.
# Keep this small to avoid overloading CPU/GPU.
PARALLEL_WORKERS = 2

# Batch size for face detection to control memory usage.
FACE_DETECTION_BATCH_SIZE = 2

# Maximum number of worker processes used *inside* face_detector when running
# in parallel mode. Set to 1 to avoid nested process pools and reduce the risk
# of system freezes. Increase cautiously if you have plenty of headroom.
FACE_DETECTION_PARALLEL_WORKERS = 1

# Maximum number of concurrent images to caption in BLIP-based caption_filler.
# This controls the ThreadPoolExecutor size and limits GPU/CPU pressure.
CAPTION_PARALLEL_WORKERS = 2
