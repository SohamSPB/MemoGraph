#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
species_models.py

Specialist species models (e.g., bird classifier) used by species_detector.
This module is designed so that models can be added incrementally without
breaking the rest of the pipeline.
"""

import os
from typing import List, Tuple

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

import memograph_config as CFG

_bird_model = None
_bird_processor = None
_bird_device = None


def _bird_model_available() -> bool:
	"""Return True if the bird model directory looks usable."""
	model_dir = CFG.BIRD_MODEL_DIR
	# Basic check: directory exists and contains a config + weights file
	# (either PyTorch or safetensors).
	if not os.path.isdir(model_dir):
		return False
	config_path = os.path.join(model_dir, "config.json")
	has_config = os.path.exists(config_path)
	has_pt_weights = os.path.exists(os.path.join(model_dir, "pytorch_model.bin"))
	has_safe_weights = os.path.exists(os.path.join(model_dir, "model.safetensors"))
	return has_config and (has_pt_weights or has_safe_weights)


def load_bird_model():
	"""
	Load the bird classifier model and processor from disk.

	Expected layout (populated outside this repository by the user):
	    models/birds/Birds-Classifier-EfficientNetB2/
	        config.json
	        pytorch_model.bin
	        preprocessor_config.json (or image_processor_config.json)

	The model should be compatible with AutoImageProcessor and
	AutoModelForImageClassification.
	"""
	global _bird_model, _bird_processor, _bird_device

	if _bird_model is not None and _bird_processor is not None and _bird_device is not None:
		return _bird_model, _bird_processor, _bird_device

	if not _bird_model_available():
		raise FileNotFoundError(
			f"Bird model directory not found or incomplete at {CFG.BIRD_MODEL_DIR}. "
			"Download dennisjooo/Birds-Classifier-EfficientNetB2 (or equivalent) "
			"and save it there using AutoImageProcessor + AutoModelForImageClassification."
		)

	model_dir = CFG.BIRD_MODEL_DIR
	_bird_processor = AutoImageProcessor.from_pretrained(model_dir)
	_bird_model = AutoModelForImageClassification.from_pretrained(model_dir)
	_bird_device = "cuda" if torch.cuda.is_available() else "cpu"
	_bird_model.to(_bird_device)
	_bird_model.eval()
	return _bird_model, _bird_processor, _bird_device


def predict_bird_species(image: Image.Image, topk: int | None = None) -> List[Tuple[str, float]]:
	"""
	Predict bird species for a given PIL image using the specialist bird model.

	Returns a list of (species_name, probability) tuples, sorted by confidence.
	If the model or labels are not available, this function raises an exception
	so that callers can fall back to other mechanisms.
	"""
	topk = topk or getattr(CFG, "BIRD_TOPK", 3)
	model, processor, device = load_bird_model()

	# The AutoImageProcessor handles resizing/normalization as required by the model.
	inputs = processor(images=image, return_tensors="pt").to(device)
	with torch.no_grad():
		outputs = model(**inputs)
		probs = outputs.logits.softmax(dim=-1)[0]
		top_probs, top_indices = probs.topk(topk)

	id2label = model.config.id2label
	results: List[Tuple[str, float]] = []
	for idx, prob in zip(top_indices, top_probs):
		label = id2label.get(int(idx), str(int(idx)))
		results.append((label, float(prob)))
	return results
