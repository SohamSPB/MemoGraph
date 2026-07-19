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
# `duplicate_of` is set by image_scanner when two rows share an md5sum: the row
# whose local_path sorts first is the canonical (duplicate_of=""), and the
# others carry duplicate_of=<canonical image_name>. Analysis scripts skip rows
# with a non-empty duplicate_of, and scripts/dedup_broadcast.py copies the
# canonical's analysis columns to its duplicates at the end of the pipeline.
CSV_HEADERS = [
	"image_name", "local_path", "md5sum", "duplicate_of",
	"datetime_original", "device_model",
	"gps_lat", "gps_lon", "location_inferred", "day_number",
	"detected_objects", "species_tags", "species_boxes", "faces_detected", "faces_count", "face_locations", "people_tags",
	"caption", "caption_samples", "caption_ai", "vision_caption", "notes", "image_type", "color_palette",
	"quality_score", "exposure_score", "color_balance_score",
	"contrast_score", "sharpness_score", "noise_score", "quality_notes"
]

# Columns that analysis steps populate and dedup_broadcast copies between
# md5-siblings. Everything that's a pure function of the image bytes belongs
# here. EXIF-derived columns (datetime, device, gps) are not in this list —
# they're already populated by image_scanner for every row directly.
ANALYSIS_COLUMNS = [
	"detected_objects", "species_tags", "species_boxes",
	"faces_detected", "faces_count", "face_locations", "people_tags",
	"caption", "caption_samples", "caption_ai", "vision_caption",
	"notes", "image_type", "color_palette",
	"quality_score", "exposure_score", "color_balance_score",
	"contrast_score", "sharpness_score", "noise_score", "quality_notes",
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
# Recommended: 256 for 4GB GPU, 512 for 8GB+, 1024 for 12GB+ (better accuracy)
MAX_IMAGE_SIZE = 512

# Physical thumbnail generation for the web app / overview UI.
# Thumbnails live under <trip>/MemoGraph/thumbnails and default to 320px.
THUMBNAIL_MAX_SIZE = 320
THUMBNAIL_SUBDIR = "thumbnails"

# Quality analysis
ENABLE_IMAGE_QUALITY = True
QUALITY_MAX_SIZE = 512
QUALITY_LIGHTING_TARGET = 0.5  # desired brightness mid-point (0-1 scale)

# Blog context extras (YOLO / OCR / Places365) are heavy; disable by default.
BLOG_CONTEXT_INCLUDE_EXTRAS = False

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
PARALLEL_WORKERS = 4

# Batch size for face detection to control memory usage.
FACE_DETECTION_BATCH_SIZE = 4

# Image size for face detection (independent of MAX_IMAGE_SIZE for AI models).
# Faces need more pixels than object/scene detection. 1024+ recommended.
# face_recognition runs on CPU so this won't affect GPU memory.
FACE_DETECTION_IMAGE_SIZE = 1024

# Use CNN model for face detection (more accurate, especially for sunglasses/angles).
# CNN is slower but catches faces that HOG misses entirely.
# Set to False to use HOG (faster but less accurate).
FACE_DETECTION_USE_CNN = True

# Maximum number of worker processes used *inside* face_detector when running
# in parallel mode. Set to 1 to avoid nested process pools and reduce the risk
# of system freezes. Increase cautiously if you have plenty of headroom.
FACE_DETECTION_PARALLEL_WORKERS = 2

# Maximum number of concurrent images to caption in BLIP-based caption_filler.
# This controls the ThreadPoolExecutor size and limits GPU/CPU pressure.
CAPTION_PARALLEL_WORKERS = 4

# -----------------------------
# Batch GPU Processor Settings
# -----------------------------
# Enable unified batch processing that loads all AI models once.
# This is more efficient than loading/unloading models for each step.
ENABLE_BATCH_GPU_PROCESSOR = True

# Which models to load in batch GPU processor
# Options: 'clip' (object detection), 'blip' (captioning), 'llava' (vision LLM)
BATCH_GPU_MODELS = ['clip', 'blip', 'llava']

# How often to save progress during batch processing (every N images)
BATCH_SAVE_INTERVAL = 5

# Enable Vision LLM (LLaVA) for detailed image descriptions
ENABLE_VISION_LLM = True


def get_gpu_memory_mb():
	"""Get available GPU memory in MB. Returns 0 if no GPU or detection fails."""
	try:
		import torch
		if not torch.cuda.is_available():
			return 0
		try:
			import pynvml
			pynvml.nvmlInit()
			handle = pynvml.nvmlDeviceGetHandleByIndex(0)
			mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
			return mem_info.free / (1024 * 1024)
		except Exception:
			# Fallback: estimate from torch (less accurate)
			return torch.cuda.get_device_properties(0).total_memory / (1024 * 1024) * 0.8
	except Exception:
		return 0


def get_dynamic_workers():
	"""
	Dynamically determine optimal worker counts based on available GPU memory.
	Returns (caption_workers, face_workers, batch_size).

	GPU Memory Tiers:
	- < 4GB:  Conservative (GTX 1650 class) - 2 caption, 1 face, batch 2
	- 4-8GB:  Moderate (RTX 2060/3050 class) - 4 caption, 2 face, batch 4
	- 8-12GB: High (RTX 3060/3070 class) - 6 caption, 3 face, batch 6
	- > 12GB: Maximum (RTX 3080+ class) - 8 caption, 4 face, batch 8
	"""
	gpu_mb = get_gpu_memory_mb()

	if gpu_mb < 4000:
		return (2, 1, 2)  # Conservative
	elif gpu_mb < 8000:
		return (4, 2, 4)  # Moderate
	elif gpu_mb < 12000:
		return (6, 3, 6)  # High
	else:
		return (8, 4, 8)  # Maximum

# Time window (in minutes) within which GPS coordinates can be propagated
# from a nearby image that has valid lat/lon. This helps fill in missing
# gps_lat/gps_lon for photos taken shortly before/after a geotagged image.
GPS_PROPAGATION_MAX_MINUTES = 15

# -----------------------------
# Specialist species models
# -----------------------------
# Bird classifier based on a Hugging Face image classification model.
# The recommended starting point is:
#   dennisjooo/Birds-Classifier-EfficientNetB2
# Download and save it under models/birds/Birds-Classifier-EfficientNetB2
# using AutoImageProcessor + AutoModelForImageClassification, then enable it.
ENABLE_BIRD_MODEL = True
BIRD_MODEL_DIR = os.path.join("models", "birds", "Birds-Classifier-EfficientNetB2")
# Number of bird species to keep per image when using the specialist model.
BIRD_TOPK = 3

# OWLv2 - zero-shot object detection for species bounding boxes.
# Detects birds, butterflies, insects etc. (155M params, ~591MB VRAM).
# Auto-downloads from HF, or use local copy at models/owlv2/
ENABLE_SPECIES_DETECTION = True
OWLV2_DIR = os.path.join("models", "owlv2")
# Detection confidence threshold (lower = more detections, higher = fewer/more confident)
SPECIES_DETECTION_THRESHOLD = 0.15

# BioCLIP 2 - biology-focused species classifier (952K+ taxa).
# Classifies cropped detections to species level.
# Download: python -m scripts.download_species_models --model bioclip2
ENABLE_BIOCLIP = True
BIOCLIP2_DIR = os.path.join("models", "bioclip2")
BIOCLIP2_ID = "imageomics/bioclip-2"
# Number of top species predictions to keep per detection
BIOCLIP_TOPK = 3
# Minimum confidence to accept a species classification
BIOCLIP_MIN_CONFIDENCE = 0.15

# -----------------------------
# Face recognition (optional)
# -----------------------------
# When enabled, an additional step will try to recognise known people in
# images that contain faces, using a gallery of face encodings built from
# reference photos under models/faces/known/ (see build_face_gallery.py).
ENABLE_FACE_RECOGNITION = False
FACE_GALLERY_PATH = os.path.join("models", "faces", "face_gallery.pkl")
# Lower threshold = stricter matches (fewer, more confident).
FACE_RECOGNITION_THRESHOLD = 0.6

# -----------------------------
# Pipeline Timing Estimates
# -----------------------------
# Approximate seconds per image for each pipeline step (used for pre-flight estimates).
# The vision_llm value is filled in dynamically based on the detected GPU below —
# LLaVA varies from ~3s/image on RTX 3060-class GPUs to ~40s/image on GTX 1650 /
# CPU fallback, which would otherwise make ETAs wrong by 10-20x.
STEP_TIMING_PER_IMAGE = {
    "scan": 0.05, "days": 0.01, "location": 0.02,
    "faces": 0.30, "labels": 0.40, "captions": 0.15,
    "ai_captions": 0.20, "species": 0.15, "image_type": 0.10,
    "vision_llm": 5.0,  # placeholder, overwritten by _calibrate_vision_llm_timing()
    "quality": 0.05, "colors": 0.05,
    "similar_grouping": 0.20, "bird_refiner": 0.10,
}
# Fixed-time steps (seconds, independent of image count).
STEP_FIXED_TIME = {"blog_map_webapp": 5, "search_index": 1}


def _calibrate_vision_llm_timing():
    """Estimate LLaVA per-image inference time based on the available GPU.

    Calibration points from working.txt and the README benchmarks:
      - CPU fallback / <4GB VRAM (GTX 1650-class): ~40s per image
      - 4-8GB VRAM mid-range: ~10s per image
      - 8GB+ VRAM (RTX 3060 12GB ran the full 138-image trip at 0.29 img/s
        across CLIP+BLIP+LLaVA combined, so LLaVA alone is ~3s/image).

    Without this calibration the static 2.0s default made GTX 1650 ETAs
    understate by 20x. Called once at import time so the dict above carries
    the right value before pipeline_preflight reads it.
    """
    gpu_mb = get_gpu_memory_mb()
    if gpu_mb < 4000:
        STEP_TIMING_PER_IMAGE["vision_llm"] = 40.0
    elif gpu_mb < 8000:
        STEP_TIMING_PER_IMAGE["vision_llm"] = 10.0
    else:
        STEP_TIMING_PER_IMAGE["vision_llm"] = 3.0


_calibrate_vision_llm_timing()
