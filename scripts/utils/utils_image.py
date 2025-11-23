#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils_image.py

Shared image utilities (e.g., resizing) used across MemoGraph scripts.
"""

import os

from PIL import Image

import memograph_config as CFG


def resize_image(image: Image.Image, max_size: int | None = None) -> Image.Image:
	"""Resize image to a max size, preserving aspect ratio.

	If max_size is None, falls back to CFG.MAX_IMAGE_SIZE.
	"""
	if max_size is None:
		max_size = getattr(CFG, "MAX_IMAGE_SIZE", 1024)
	if max(image.size) > max_size:
		image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
	return image


def create_thumbnail(src_path: str, dest_path: str, max_size: int | None = None, quality: int = 85) -> bool:
	"""Create a JPEG thumbnail for the given source image.

	Returns True when the thumbnail is written successfully.
	"""
	if not os.path.exists(src_path):
		return False

	if max_size is None:
		max_size = getattr(CFG, "THUMBNAIL_MAX_SIZE", 320)

	dest_dir = os.path.dirname(dest_path)
	if dest_dir:
		os.makedirs(dest_dir, exist_ok=True)

	try:
		with Image.open(src_path) as img:
			if img.mode not in ("RGB", "L"):
				img = img.convert("RGB")
			else:
				img = img.copy()
			img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
			img.save(dest_path, format="JPEG", quality=quality, optimize=True)
		return True
	except Exception:
		return False
