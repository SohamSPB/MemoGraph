#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils_image.py

Shared image utilities (e.g., resizing) used across MemoGraph scripts.
"""

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
