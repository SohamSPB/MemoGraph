#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
species_models.py

Specialist species models used by species_detector:
  1. Bird classifier (EfficientNet-B2, 525 species)
  2. Grounding DINO  (open-vocabulary object detection for bounding boxes)
  3. BioCLIP 2       (species classification from cropped detections, 952K taxa)

This module is designed so that models can be added incrementally without
breaking the rest of the pipeline.
"""

import os
from typing import List, Tuple, Dict, Any, Optional

import torch
from PIL import Image, ImageOps
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


# -------------------------------------------------------
# OWLv2 - Zero-shot object detection (replaces Grounding DINO)
# -------------------------------------------------------
_owlv2_model = None
_owlv2_processor = None

# Keep old name for API compatibility
_gdino_available = _owlv2_available = lambda: True  # OWLv2 always available via HF


def _owlv2_model_dir() -> str:
	"""Return local OWLv2 dir if it exists, else HF hub ID."""
	local_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "owlv2")
	if os.path.isdir(local_dir) and os.path.exists(os.path.join(local_dir, "config.json")):
		return local_dir
	return "google/owlv2-base-patch16-ensemble"


def load_owlv2():
	"""Load OWLv2 for zero-shot object detection (155M params, ~591MB VRAM)."""
	global _owlv2_model, _owlv2_processor
	if _owlv2_model is not None:
		return _owlv2_model, _owlv2_processor

	from transformers import Owlv2Processor, Owlv2ForObjectDetection

	source = _owlv2_model_dir()
	_owlv2_processor = Owlv2Processor.from_pretrained(source)
	_owlv2_model = Owlv2ForObjectDetection.from_pretrained(source)

	device = "cuda" if torch.cuda.is_available() else "cpu"
	_owlv2_model.to(device)
	_owlv2_model.eval()
	return _owlv2_model, _owlv2_processor


# Backward-compatible alias
load_grounding_dino = load_owlv2


def detect_wildlife_boxes(
	image: Image.Image,
	text_prompt: Optional[str] = None,
	box_threshold: float = 0.15,
	**kwargs,
) -> List[Dict[str, Any]]:
	"""
	Detect wildlife in an image using OWLv2 zero-shot object detection.

	Returns a list of detections, each with:
	  - "box": (left, top, right, bottom) in pixels
	  - "box_norm": (left%, top%, right%, bottom%) normalized 0-100
	  - "label": detected category (e.g., "a bird")
	  - "score": detection confidence
	"""
	model, processor = load_owlv2()
	device = next(model.parameters()).device

	box_threshold = getattr(CFG, "SPECIES_DETECTION_THRESHOLD", box_threshold)

	if text_prompt is not None:
		queries = [p.strip().rstrip(".") for p in text_prompt.split(".") if p.strip()]
	else:
		queries = [
			"a bird", "a butterfly", "a moth", "an insect", "a dragonfly",
			"a beetle", "a spider", "a lizard", "a snake", "a frog",
			"a squirrel", "a monkey", "a deer", "a cat", "a dog",
		]

	w, h = image.size

	inputs = processor(text=[queries], images=image, return_tensors="pt").to(device)

	with torch.no_grad():
		outputs = model(**inputs)

	target_sizes = torch.Tensor([[h, w]]).to(device)
	results = processor.post_process_object_detection(
		outputs=outputs, target_sizes=target_sizes, threshold=box_threshold
	)

	detections = []
	if results and len(results) > 0:
		result = results[0]
		for box, score, label_idx in zip(result["boxes"], result["scores"], result["labels"]):
			x1, y1, x2, y2 = box.tolist()
			label = queries[int(label_idx)]
			detections.append({
				"box": (x1, y1, x2, y2),
				"box_norm": (
					round(x1 / w * 100, 1),
					round(y1 / h * 100, 1),
					round(x2 / w * 100, 1),
					round(y2 / h * 100, 1),
				),
				"label": label,
				"score": float(score),
			})

	# Remove duplicate detections (overlapping boxes from similar categories)
	detections = _nms_detections(detections, iou_threshold=0.5)

	# Sort by confidence descending
	detections.sort(key=lambda d: -d["score"])
	return detections


def _nms_detections(detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
	"""Non-maximum suppression: remove overlapping boxes, keeping highest score."""
	if not detections:
		return []

	dets = sorted(detections, key=lambda d: -d["score"])
	keep = []

	for det in dets:
		is_dup = False
		for kept in keep:
			iou = _box_iou(det["box"], kept["box"])
			if iou > iou_threshold:
				is_dup = True
				break
		if not is_dup:
			keep.append(det)
	return keep


def _box_iou(box1, box2) -> float:
	"""Compute IoU between two (x1,y1,x2,y2) boxes."""
	x1 = max(box1[0], box2[0])
	y1 = max(box1[1], box2[1])
	x2 = min(box1[2], box2[2])
	y2 = min(box1[3], box2[3])
	inter = max(0, x2 - x1) * max(0, y2 - y1)
	area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
	area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
	union = area1 + area2 - inter
	return inter / union if union > 0 else 0


def unload_grounding_dino():
	"""Free GPU memory used by OWLv2 (backward-compatible name)."""
	unload_owlv2()


def unload_owlv2():
	"""Free GPU memory used by OWLv2."""
	global _owlv2_model, _owlv2_processor
	if _owlv2_model is not None:
		del _owlv2_model
		_owlv2_model = None
	_owlv2_processor = None
	if torch.cuda.is_available():
		torch.cuda.empty_cache()


# -------------------------------------------------------
# BioCLIP 2 - Species classification (952K taxa)
# -------------------------------------------------------
_bioclip_model = None
_bioclip_preprocess = None
_bioclip_tokenizer = None


def _bioclip_available() -> bool:
	"""Return True if BioCLIP 2 model directory exists."""
	model_dir = getattr(CFG, "BIOCLIP2_DIR", "")
	if not model_dir or not os.path.isdir(model_dir):
		return False
	# Check for open_clip model file
	return (
		os.path.exists(os.path.join(model_dir, "open_clip_pytorch_model.bin"))
		or os.path.exists(os.path.join(model_dir, "open_clip_model.safetensors"))
	)


def load_bioclip():
	"""Load BioCLIP 2 for species classification."""
	global _bioclip_model, _bioclip_preprocess, _bioclip_tokenizer
	if _bioclip_model is not None:
		return _bioclip_model, _bioclip_preprocess, _bioclip_tokenizer

	import open_clip

	model_dir = getattr(CFG, "BIOCLIP2_DIR", "")
	device = "cuda" if torch.cuda.is_available() else "cpu"

	# hf-hub: prefix auto-resolves local cache or downloads from HF
	model, _, preprocess = open_clip.create_model_and_transforms(
		"hf-hub:imageomics/bioclip-2",
	)

	model.to(device)
	model.eval()
	tokenizer = open_clip.get_tokenizer("hf-hub:imageomics/bioclip-2")

	_bioclip_model = model
	_bioclip_preprocess = preprocess
	_bioclip_tokenizer = tokenizer
	return model, preprocess, tokenizer


def classify_species_bioclip(
	image: Image.Image,
	candidate_labels: Optional[List[str]] = None,
	topk: int = 3,
	min_confidence: float = 0.1,
) -> List[Tuple[str, float]]:
	"""
	Classify a (cropped) image to species level using BioCLIP 2.

	Args:
		image: PIL Image (typically a crop from Grounding DINO detection)
		candidate_labels: Optional list of species names to choose from.
			If None, uses a broad set of common species labels.
		topk: Number of top predictions to return
		min_confidence: Minimum probability to include in results

	Returns:
		List of (species_name, probability) tuples sorted by confidence.
	"""
	model, preprocess, tokenizer = load_bioclip()
	device = next(model.parameters()).device

	if candidate_labels is None:
		candidate_labels = _get_default_species_labels()

	# Prepare image
	img_tensor = preprocess(image).unsqueeze(0).to(device)

	# Prepare text
	text_inputs = tokenizer(candidate_labels).to(device)

	with torch.no_grad():
		image_features = model.encode_image(img_tensor)
		text_features = model.encode_text(text_inputs)
		image_features /= image_features.norm(dim=-1, keepdim=True)
		text_features /= text_features.norm(dim=-1, keepdim=True)
		similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)[0]

	top_probs, top_indices = similarity.topk(min(topk, len(candidate_labels)))
	results = []
	for prob, idx in zip(top_probs, top_indices):
		p = float(prob)
		if p >= min_confidence:
			results.append((candidate_labels[int(idx)], p))

	return results


def unload_bioclip():
	"""Free GPU memory used by BioCLIP 2."""
	global _bioclip_model, _bioclip_preprocess, _bioclip_tokenizer
	if _bioclip_model is not None:
		del _bioclip_model
		_bioclip_model = None
	_bioclip_preprocess = None
	_bioclip_tokenizer = None
	if torch.cuda.is_available():
		torch.cuda.empty_cache()


# -------------------------------------------------------
# Two-stage pipeline: Detect + Classify
# -------------------------------------------------------

def detect_and_classify(
	image: Image.Image,
	text_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
	"""
	Full two-stage pipeline:
	  1. Grounding DINO detects wildlife bounding boxes
	  2. BioCLIP 2 classifies each crop to species

	Returns list of detections with species classification added:
	  - "box_norm": (left%, top%, right%, bottom%)
	  - "label": detection category (e.g., "a bird")
	  - "score": detection confidence
	  - "species": [(name, prob), ...] top species predictions
	  - "best_species": top species name
	"""
	# Apply EXIF orientation
	image = ImageOps.exif_transpose(image)

	# Stage 1: Detect
	detections = detect_wildlife_boxes(image, text_prompt)
	if not detections:
		return []

	# Stage 2: Classify each crop
	topk = getattr(CFG, "BIOCLIP_TOPK", 3)
	min_conf = getattr(CFG, "BIOCLIP_MIN_CONFIDENCE", 0.15)
	w, h = image.size

	for det in detections:
		x1, y1, x2, y2 = det["box"]
		# Expand crop by 10% for context
		pad_x = (x2 - x1) * 0.1
		pad_y = (y2 - y1) * 0.1
		cx1 = max(0, int(x1 - pad_x))
		cy1 = max(0, int(y1 - pad_y))
		cx2 = min(w, int(x2 + pad_x))
		cy2 = min(h, int(y2 + pad_y))

		crop = image.crop((cx1, cy1, cx2, cy2))

		# Choose candidate labels based on detection category
		label_lower = det["label"].lower()
		if "bird" in label_lower:
			candidates = _get_bird_labels()
		elif "butterfly" in label_lower or "moth" in label_lower:
			candidates = _get_butterfly_labels()
		elif "insect" in label_lower or "dragonfly" in label_lower or "beetle" in label_lower:
			candidates = _get_insect_labels()
		else:
			candidates = _get_default_species_labels()

		species = classify_species_bioclip(crop, candidates, topk=topk, min_confidence=min_conf)
		det["species"] = species
		det["best_species"] = species[0][0] if species else det["label"]

	return detections


def _get_bird_labels() -> List[str]:
	"""Common Indian + global bird species for BioCLIP classification."""
	return [
		# Indian subcontinent birds
		"Indian Peafowl", "Asian Green Bee-eater", "Blue-tailed Bee-eater",
		"White-throated Kingfisher", "Common Kingfisher", "Pied Kingfisher",
		"Indian Roller", "Red-vented Bulbul", "Red-whiskered Bulbul",
		"Asian Paradise Flycatcher", "Indian Robin", "Oriental Magpie Robin",
		"Black Drongo", "Greater Racket-tailed Drongo", "White-bellied Drongo",
		"Common Myna", "Jungle Myna", "Hill Myna",
		"Purple Sunbird", "Crimson Sunbird",
		"Rose-ringed Parakeet", "Plum-headed Parakeet",
		"Coppersmith Barbet", "Blue-throated Barbet", "Brown-headed Barbet",
		"Asian Koel", "Greater Coucal", "Common Hawk-Cuckoo",
		"White-crested Laughingthrush", "Rufous Sibia",
		"Scarlet Minivet", "Long-tailed Minivet",
		"Black Kite", "Brahminy Kite", "Shikra",
		"Indian Grey Hornbill", "Great Hornbill", "Malabar Pied Hornbill",
		"Spotted Owlet", "Barn Owl", "Indian Scops Owl",
		"Painted Stork", "Asian Openbill", "Black-necked Stork",
		"Grey Heron", "Indian Pond Heron", "Cattle Egret", "Great Egret",
		"Little Cormorant", "Indian Cormorant",
		"Bar-headed Goose", "Spot-billed Duck", "Lesser Whistling Duck",
		"House Sparrow", "Eurasian Tree Sparrow",
		"House Crow", "Large-billed Crow", "Jungle Crow",
		"Rock Pigeon", "Spotted Dove", "Laughing Dove",
		"White Wagtail", "Grey Wagtail", "Citrine Wagtail",
		"Long-tailed Shrike", "Brown Shrike",
		"Golden-backed Woodpecker", "Greater Flameback",
		"Common Tailorbird", "Plain Prinia",
		"Great Tit", "Green-backed Tit",
		"Chestnut-bellied Nuthatch", "Velvet-fronted Nuthatch",
		# Himalayan specialties
		"Himalayan Monal", "Kalij Pheasant", "Blood Pheasant",
		"Fire-tailed Sunbird", "Mrs. Gould's Sunbird",
		"Verditer Flycatcher", "Ultramarine Flycatcher",
		"Blue Whistling Thrush", "Chestnut Thrush",
		"Spiny Babbler", "Nepal Wren-Babbler",
		"Yellow-billed Blue Magpie", "Red-billed Blue Magpie",
		"Wallcreeper", "White-capped Redstart",
		# Global common birds
		"Bald Eagle", "Golden Eagle", "Peregrine Falcon",
		"European Robin", "Blue Tit", "Great Spotted Woodpecker",
		"Flamingo", "Pelican", "Toucan", "Hummingbird",
	]


def _get_butterfly_labels() -> List[str]:
	"""Common butterfly and moth species."""
	return [
		# Swallowtails
		"Common Mormon", "Blue Mormon", "Lime Butterfly",
		"Common Rose", "Crimson Rose", "Krishna Peacock",
		"Common Mime", "Common Bluebottle", "Tailed Jay",
		"Golden Birdwing", "Southern Birdwing", "Common Birdwing",
		# Whites and Yellows
		"Common Grass Yellow", "Three-spot Grass Yellow",
		"Common Emigrant", "Mottled Emigrant", "Lemon Emigrant",
		"Common Jezebel", "Painted Jezebel",
		"Common Gull", "Pioneer",
		"Psyche", "Common Albatross",
		# Brush-footed
		"Painted Lady", "Red Admiral", "Common Leopard",
		"Common Crow", "Blue Tiger", "Striped Tiger",
		"Plain Tiger", "Common Indian Crow",
		"Blue Pansy", "Lemon Pansy", "Chocolate Pansy", "Grey Pansy",
		"Common Castor", "Common Baron", "Common Sergeant",
		"Tawny Coster", "Common Lacewing",
		"Commander", "Clipper",
		# Blues
		"Common Cerulean", "Gram Blue", "Plains Cupid",
		"Common Pierrot", "Zebra Blue",
		"Pale Grass Blue", "Dark Grass Blue",
		# Skippers
		"Common Dartlet", "Rice Swift",
		# Moths
		"Atlas Moth", "Luna Moth", "Oleander Hawk-Moth",
		"Hummingbird Hawk-Moth", "Death's-head Hawkmoth",
		"Indian Moon Moth", "Tussar Silk Moth",
		# General
		"Monarch Butterfly", "Swallowtail Butterfly",
		"Cabbage White", "Orange Tip",
	]


def _get_insect_labels() -> List[str]:
	"""Common insect species."""
	return [
		# Dragonflies & Damselflies
		"Blue Dasher Dragonfly", "Flame Skimmer Dragonfly",
		"Common Hawker Dragonfly", "Emperor Dragonfly",
		"Azure Damselfly", "Common Blue Damselfly",
		"Scarlet Skimmer", "Globe Skimmer",
		# Beetles
		"Ladybird Beetle", "Stag Beetle", "Jewel Beetle",
		"Rhinoceros Beetle", "Longhorn Beetle", "Dung Beetle",
		"Tiger Beetle", "Ground Beetle",
		# Bees & Wasps
		"Honeybee", "Bumblebee", "Carpenter Bee",
		"Paper Wasp", "Potter Wasp", "Mud Dauber",
		"Asian Giant Hornet",
		# Flies
		"Hoverfly", "Robber Fly", "Crane Fly",
		# Mantids
		"Praying Mantis", "Orchid Mantis", "Dead Leaf Mantis",
		# Others
		"Walking Stick Insect", "Leaf Insect",
		"Grasshopper", "Katydid", "Cricket",
		"Cicada", "Lantern Bug", "Planthopper",
		"Shield Bug", "Assassin Bug",
		"Ant", "Termite",
		"Caterpillar", "Inchworm",
		# Spiders (technically arachnids)
		"Orb Weaver Spider", "Jumping Spider", "Wolf Spider",
		"Garden Spider", "Crab Spider", "Lynx Spider",
	]


def _get_default_species_labels() -> List[str]:
	"""General wildlife labels for unknown detection categories."""
	return [
		# Mammals
		"Rhesus Macaque", "Langur", "Squirrel",
		"Deer", "Spotted Deer", "Sambar Deer",
		"Wild Boar", "Mongoose", "Civet",
		"Leopard", "Tiger",
		# Reptiles
		"Monitor Lizard", "Garden Lizard", "Gecko",
		"Cobra", "Rat Snake", "Python",
		"Freshwater Turtle", "Star Tortoise",
		# Amphibians
		"Common Frog", "Tree Frog", "Toad",
		# Domestic
		"Dog", "Cat", "Cow", "Goat", "Horse", "Donkey",
		"Buffalo", "Yak", "Sheep",
	]


def format_species_boxes(detections: List[Dict[str, Any]]) -> str:
	"""
	Format detection results into a CSV-safe string.

	Format: "label:species@left,top,right,bottom;label:species@left,top,right,bottom"
	Each detection has: detection_label:best_species_name@left%,top%,right%,bottom%
	"""
	if not detections:
		return ""
	parts = []
	for det in detections:
		label = det.get("label", "unknown").replace(":", "-").replace(";", "-").replace("@", "-")
		species = det.get("best_species", label).replace(":", "-").replace(";", "-").replace("@", "-")
		left, top, right, bottom = det["box_norm"]
		parts.append(f"{label}:{species}@{left},{top},{right},{bottom}")
	return "; ".join(parts)
