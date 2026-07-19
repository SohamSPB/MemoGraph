#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_quality.py

Computes lightweight image-quality metrics (exposure balance, color balance,
contrast, sharpness, noise/high-frequency energy) for every photo in a trip
and stores the results in labels.csv.

These metrics are later surfaced in blog_context.json + the static web app so
we can highlight "best balanced" photos per trip.
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np
from PIL import Image, ImageOps, ImageFilter

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import get_logger


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
	return max(lo, min(hi, value))


def _load_image(image_path: str, max_side: int) -> Image.Image | None:
	if not os.path.exists(image_path):
		return None
	try:
		img = Image.open(image_path)
		img = ImageOps.exif_transpose(img).convert("RGB")
		if max(img.size) > max_side:
			img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
		return img
	except Exception:
		return None


def _compute_metrics(image: Image.Image) -> Dict[str, float]:
	arr = np.asarray(image, dtype=np.float32) / 255.0
	if arr.ndim != 3 or arr.shape[2] != 3:
		return {}

	gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
	brightness = float(gray.mean())
	contrast = float(gray.std())

	shadow_frac = float((gray < 0.08).mean())
	highlight_frac = float((gray > 0.92).mean())
	midtone_frac = 1.0 - min(1.0, shadow_frac + highlight_frac)
	exposure_score = _clamp(midtone_frac)

	channel_means = arr.reshape(-1, 3).mean(axis=0)
	global_mean = float(channel_means.mean())
	color_dev = float(np.mean(np.abs(channel_means - global_mean)))
	color_balance = _clamp(1.0 - color_dev * 6.0)

	contrast_score = _clamp(contrast * 4.0)

	gray_img = image.convert("L")
	if max(gray_img.size) > max(image.size):
		gray_img.thumbnail(image.size, Image.Resampling.LANCZOS)

	edges = gray_img.filter(ImageFilter.FIND_EDGES)
	edge_arr = np.asarray(edges, dtype=np.float32) / 255.0
	sharpness_score = _clamp(float(edge_arr.mean()) * 2.5)

	blurred = gray_img.filter(ImageFilter.GaussianBlur(radius=1.2))
	noise_residual = (
		np.asarray(gray_img, dtype=np.float32) - np.asarray(blurred, dtype=np.float32)
	) / 255.0
	noise_level = float(np.std(noise_residual))
	noise_score = _clamp(1.0 - noise_level * 8.0)

	quality_components = [
		exposure_score,
		color_balance,
		contrast_score,
		sharpness_score,
		noise_score,
	]
	quality_score = sum(quality_components) / len(quality_components)

	return {
		"brightness": brightness,
		"exposure_score": exposure_score,
		"color_balance_score": color_balance,
		"contrast_score": contrast_score,
		"sharpness_score": sharpness_score,
		"noise_score": noise_score,
		"quality_score": quality_score,
	}


def _describe_quality(metrics: Dict[str, float]) -> str:
	notes = []
	if metrics["exposure_score"] < 0.55:
		notes.append("exposure extremes")
	if metrics["color_balance_score"] < 0.6:
		notes.append("color cast")
	if metrics["sharpness_score"] < 0.5:
		notes.append("soft focus")
	if metrics["noise_score"] < 0.55:
		notes.append("noise")
	if not notes and metrics["quality_score"] >= 0.75:
		return "balanced highlight"
	if not notes:
		return "balanced"
	return ", ".join(notes)


def evaluate_image_quality(trip_folder: str) -> None:
	if not getattr(CFG, "ENABLE_IMAGE_QUALITY", True):
		return

	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	csv_path = os.path.join(memo_dir, "labels.csv")
	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"labels.csv not found at {csv_path}")

	logger = get_logger(
		"image_quality",
		os.path.join(logs_dir, "image_quality.log"),
	)

	rows = read_csv_dict(csv_path)
	if not rows:
		logger.warning("No rows found in labels.csv; skipping quality analysis.")
		return

	quality_size = getattr(CFG, "QUALITY_MAX_SIZE", 512)
	for row in rows:
		# Content duplicate: quality metrics are pure functions of bytes, so
		# they'll be identical to the canonical's. Skip the work; the values
		# get copied later by dedup_broadcast.py.
		if (row.get("duplicate_of") or "").strip():
			continue
		rel_path = row.get("local_path") or row.get("image_name")
		if not rel_path:
			continue
		full_path = os.path.join(trip_folder, rel_path)
		image = _load_image(full_path, quality_size)
		if image is None:
			logger.warning("Unable to open image for quality metrics: %s", rel_path)
			continue

		metrics = _compute_metrics(image)
		if not metrics:
			logger.warning("Failed to compute metrics for %s", rel_path)
			continue

		row["quality_score"] = f"{metrics['quality_score']:.3f}"
		row["exposure_score"] = f"{metrics['exposure_score']:.3f}"
		row["color_balance_score"] = f"{metrics['color_balance_score']:.3f}"
		row["contrast_score"] = f"{metrics['contrast_score']:.3f}"
		row["sharpness_score"] = f"{metrics['sharpness_score']:.3f}"
		row["noise_score"] = f"{metrics['noise_score']:.3f}"
		row["quality_notes"] = _describe_quality(metrics)

	# Preserve any columns that aren't in the canonical CSV_HEADERS list —
	# face_detector adds face_locations dynamically, species_detector adds
	# species_boxes, and future steps may add more. Using CFG.CSV_HEADERS
	# directly here would silently drop them.
	known = list(CFG.CSV_HEADERS)
	seen = set(known)
	for row in rows:
		for key in row.keys():
			if key not in seen:
				known.append(key)
				seen.add(key)
	write_csv_dict(csv_path, rows, known)
	logger.info("Image quality metrics written to %s", csv_path)


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Compute image quality metrics for a trip.")
	parser.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
	args = parser.parse_args()

	evaluate_image_quality(args.trip_folder)
