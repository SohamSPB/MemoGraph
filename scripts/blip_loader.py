#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blip_loader.py

Singleton loader for the BLIP captioning model.

caption_filler.py (multi-sample captions for the `caption` and `caption_samples`
columns) and generate_ai_captions.py (single deterministic caption for the
`caption_ai` column) both use Salesforce/blip-image-captioning-base. When
run_all.py runs them back to back, loading the same model from disk twice
wastes ~700 MB of disk reads and keeps an extra ~1 GB of VRAM resident during
the handoff window.

This module loads the model once and caches it at process scope so both
scripts share the same instance.
"""

from __future__ import annotations

from typing import Optional, Tuple

import torch
from transformers import BlipForConditionalGeneration, BlipProcessor

_MODEL_ID = "Salesforce/blip-image-captioning-base"

_processor: Optional[BlipProcessor] = None
_model: Optional[BlipForConditionalGeneration] = None
_device: Optional[str] = None


def get_blip() -> Tuple[BlipProcessor, BlipForConditionalGeneration, str]:
	"""Return (processor, model, device). Loads BLIP on first call, then caches.

	The cache lives at module scope, so a single Python process that imports
	this from multiple callers (the typical run_all.py flow) only pays the
	load cost once.
	"""
	global _processor, _model, _device
	if _model is not None and _processor is not None and _device is not None:
		return _processor, _model, _device

	_device = "cuda" if torch.cuda.is_available() else "cpu"
	_processor = BlipProcessor.from_pretrained(_MODEL_ID, use_fast=True)
	_model = BlipForConditionalGeneration.from_pretrained(_MODEL_ID).to(_device)
	_model.eval()
	return _processor, _model, _device


def unload_blip() -> None:
	"""Free the GPU memory used by BLIP.

	Call this between major pipeline phases when a different heavy model
	(species detector, LLaVA) is about to load and BLIP isn't needed again.
	"""
	global _processor, _model, _device
	_processor = None
	_model = None
	_device = None
	if torch.cuda.is_available():
		torch.cuda.empty_cache()
