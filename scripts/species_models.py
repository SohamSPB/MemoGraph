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
			"a flower", "a cow", "a goat", "a horse", "a yak",
			"a turtle",
			"a bee", "a wasp", "an ant",
			"a flowering plant", "a potted plant", "a tree with flowers",
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
			left_pct = round(x1 / w * 100, 1)
			top_pct = round(y1 / h * 100, 1)
			right_pct = round(x2 / w * 100, 1)
			bottom_pct = round(y2 / h * 100, 1)
			# Skip boxes that cover less than 0.5% of the image area (false positives)
			box_area = (right_pct - left_pct) * (bottom_pct - top_pct)
			if box_area < 50:  # 50 in (0-100)^2 units = 0.5% of image
				continue
			label = queries[int(label_idx)]
			detections.append({
				"box": (x1, y1, x2, y2),
				"box_norm": (left_pct, top_pct, right_pct, bottom_pct),
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

def _crop_color_hint(crop: Image.Image) -> str:
	"""Return a color hint string based on the dominant hue of a crop.

	Used to select the right butterfly candidate sub-list before BioCLIP
	classification, since BioCLIP's embedding space can confuse morphologically
	similar species of different colours (e.g. orange Tawny Rajah vs. black
	Common Mormon).
	"""
	from PIL import ImageStat
	try:
		stat = ImageStat.Stat(crop.convert("RGB"))
		r, g, b = stat.mean[:3]
		# Orange: red channel dominant, clearly above green and blue
		if r > 140 and r > g + 30 and r > b + 50:
			return "orange"
		# Yellow: high red AND green, low blue
		if r > 160 and g > 140 and b < r - 40 and b < g - 30:
			return "yellow"
		# White / pale: all channels high
		if r > 180 and g > 180 and b > 180:
			return "white"
		# Dark / black-dominant: all channels low
		if r < 80 and g < 80 and b < 80:
			return "dark"
	except Exception:
		pass
	return ""


def detect_and_classify(
	image: Image.Image,
	text_prompt: Optional[str] = None,
	detected_objects: str = "",
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

		# Choose candidate labels based on detection category + coarse context
		label_lower = det["label"].lower()
		if "bird" in label_lower:
			candidates = _get_bird_labels()
		elif "butterfly" in label_lower or "moth" in label_lower:
			# Combine coarse text context with direct crop colour analysis
			color_hint = _crop_color_hint(crop)
			candidates = _get_butterfly_labels(detected_objects + " " + color_hint)
		elif any(k in label_lower for k in ("insect", "dragonfly", "beetle", "spider", "bee", "wasp", "ant")):
			candidates = _get_insect_labels()
		elif any(k in label_lower for k in ("flower", "plant")):
			candidates = _get_flower_labels()
		elif "fish" in label_lower:
			candidates = _get_fish_labels()
		else:
			candidates = _get_default_species_labels()

		species = classify_species_bioclip(crop, candidates, topk=topk, min_confidence=min_conf)
		det["species"] = species
		det["best_species"] = species[0][0] if species else det["label"]

	return detections


def _get_bird_labels() -> List[str]:
	"""Common Indian + global bird species for BioCLIP classification."""
	return [
		# Very common Indian urban/suburban birds (listed first for faster matching)
		"Common Myna", "Jungle Myna", "Bank Myna", "Hill Myna",
		"House Crow", "Large-billed Crow", "Jungle Crow",
		"Rock Pigeon", "Spotted Dove", "Laughing Dove", "Eurasian Collared Dove",
		"House Sparrow", "Eurasian Tree Sparrow",
		"Rose-ringed Parakeet", "Plum-headed Parakeet", "Alexandrine Parakeet",
		# Kingfishers
		"White-throated Kingfisher", "Common Kingfisher", "Pied Kingfisher",
		"Stork-billed Kingfisher",
		# Bee-eaters
		"Asian Green Bee-eater", "Blue-tailed Bee-eater", "Chestnut-headed Bee-eater",
		# Rollers, bulbuls, drongos
		"Indian Roller", "Red-vented Bulbul", "Red-whiskered Bulbul",
		"Black Drongo", "Greater Racket-tailed Drongo", "Ashy Drongo",
		# Sunbirds
		"Purple Sunbird", "Crimson Sunbird", "Loten's Sunbird",
		# Barbets and woodpeckers (on trees)
		"Coppersmith Barbet", "Blue-throated Barbet", "Brown-headed Barbet",
		"Lineated Barbet", "Great Barbet",
		"Golden-backed Woodpecker", "Greater Flameback", "Lesser Flameback",
		"Rufous Woodpecker", "Brown-capped Pygmy Woodpecker",
		"Yellow-crowned Woodpecker", "Streak-throated Woodpecker",
		"Grey-headed Woodpecker", "Himalayan Woodpecker",
		# Flycatchers and robins
		"Asian Paradise Flycatcher", "Indian Robin", "Oriental Magpie Robin",
		"Verditer Flycatcher", "Ultramarine Flycatcher",
		"White-rumped Shama", "Pied Bushchat",
		# Cuckoos and koels
		"Asian Koel", "Greater Coucal", "Common Hawk-Cuckoo", "Pied Cuckoo",
		# Tailorbirds, warblers, prinias
		"Common Tailorbird", "Plain Prinia", "Jungle Prinia",
		# Wagtails and shrikes
		"White Wagtail", "Grey Wagtail", "Citrine Wagtail", "Yellow Wagtail",
		"Long-tailed Shrike", "Brown Shrike", "Bay-backed Shrike",
		# Raptors
		"Black Kite", "Brahminy Kite", "Shikra", "White-eyed Buzzard",
		"Crested Serpent Eagle",
		# Hornbills
		"Indian Grey Hornbill", "Great Hornbill", "Malabar Pied Hornbill",
		# Owls
		"Spotted Owlet", "Barn Owl", "Indian Scops Owl", "Jungle Owlet",
		# Waterbirds
		"Grey Heron", "Indian Pond Heron", "Cattle Egret", "Great Egret",
		"Little Egret", "Purple Heron",
		"Painted Stork", "Asian Openbill", "Black-necked Stork",
		"Little Cormorant", "Indian Cormorant", "Great Cormorant",
		"Bar-headed Goose", "Spot-billed Duck", "Lesser Whistling Duck",
		# Peacock
		"Indian Peafowl",
		# Tits and nuthatches
		"Great Tit", "Green-backed Tit",
		"Chestnut-bellied Nuthatch", "Velvet-fronted Nuthatch",
		# Himalayan specialties
		"Himalayan Monal", "Kalij Pheasant", "Blood Pheasant",
		"Fire-tailed Sunbird", "Mrs. Gould's Sunbird",
		"Blue Whistling Thrush", "Chestnut Thrush",
		"White-crested Laughingthrush", "Rufous Sibia",
		"Scarlet Minivet", "Long-tailed Minivet",
		"Spiny Babbler", "Nepal Wren-Babbler",
		"Yellow-billed Blue Magpie", "Red-billed Blue Magpie",
		"Wallcreeper", "White-capped Redstart",
		# Global common birds
		"Bald Eagle", "Golden Eagle", "Peregrine Falcon",
		"European Robin", "Blue Tit", "Great Spotted Woodpecker",
		"Flamingo", "Pelican", "Toucan", "Hummingbird",
	]


def _get_fish_labels() -> List[str]:
	"""Common fish and aquatic species for BioCLIP classification."""
	return [
		"Common Carp", "Rohu", "Catla", "Tilapia",
		"Goldfish", "Koi", "Betta Fish",
		"Mahseer", "Golden Mahseer",
		"Trout", "Salmon",
		"Clownfish", "Angelfish",
		"Eel", "Moray Eel",
		"Catfish", "Snakehead",
	]


def _get_butterfly_labels(context: str = "") -> List[str]:
	"""Common butterfly and moth species.

	When coarse detection context (detected_objects / caption text) is provided,
	re-orders candidates so colour-matched species come first, improving BioCLIP
	accuracy for orange/yellow vs. dark/patterned butterflies.
	"""
	ctx = context.lower()

	# Orange / tawny / rusty-coloured butterflies
	orange_labels = [
		"Tawny Rajah", "Common Rajah",          # Charaxes - orange with dark striping
		"Plain Tiger", "Striped Tiger",           # Danaid tigers - orange/black
		"Tawny Coster",                           # Orange/tawny with black
		"Indian Fritillary", "Acraea Butterfly",
		"Common Sailer",                          # Brown/rusty tones
		"Tamil Yeoman", "Common Yeoman",
		"Rustic", "Common Rustic",
		"Orange Oakleaf",                         # Dead-leaf mimic, orange inside
		"Autumn Leaf",                            # Bright orange
		"Orange Tip", "Great Orange Tip",
	]

	# Yellow / sulphur / grass-yellow butterflies
	yellow_labels = [
		"Common Grass Yellow", "Three-spot Grass Yellow",
		"Common Emigrant", "Mottled Emigrant", "Lemon Emigrant",
		"Small Grass Yellow", "Spotless Grass Yellow",
		"Psyche", "Common Albatross",
		"Common Gull", "Pioneer",
		"Common Jezebel", "Painted Jezebel",
	]

	# Dark / black / patterned swallowtails and crows
	dark_labels = [
		"Common Mormon", "Blue Mormon", "Lime Butterfly",
		"Common Rose", "Crimson Rose", "Krishna Peacock",
		"Common Mime", "Common Bluebottle", "Tailed Jay",
		"Golden Birdwing", "Southern Birdwing", "Common Birdwing",
		"Common Crow", "Blue Tiger", "Common Indian Crow",
		"Blue Pansy", "Lemon Pansy", "Chocolate Pansy", "Grey Pansy",
		"Commander", "Clipper",
		"Common Leopard", "Common Baron", "Common Sergeant",
		"Common Castor", "Common Lacewing",
		"Painted Lady", "Red Admiral",
	]

	# Blues and small butterflies
	small_labels = [
		"Common Cerulean", "Gram Blue", "Plains Cupid",
		"Common Pierrot", "Zebra Blue",
		"Pale Grass Blue", "Dark Grass Blue",
		"Common Dartlet", "Rice Swift",
	]

	# Moths
	moth_labels = [
		"Atlas Moth", "Luna Moth", "Oleander Hawk-Moth",
		"Hummingbird Hawk-Moth", "Death's-head Hawkmoth",
		"Indian Moon Moth", "Tussar Silk Moth",
	]

	# General fallback labels
	general_labels = ["Monarch Butterfly", "Swallowtail Butterfly", "Cabbage White"]

	# Context-aware candidate FILTERING (not just reordering) for better BioCLIP accuracy.
	# When we have a clear colour signal, return ONLY that colour group so BioCLIP
	# cannot confuse e.g. an orange Tawny Rajah with the black Common Mormon.
	if any(k in ctx for k in ("orange", "tawny", "rusty", "brown butterfly", "rajah", "coster", "autumn")):
		# Strong orange signal → restrict to orange/warm candidates only
		return orange_labels + dark_labels + yellow_labels + small_labels + moth_labels + general_labels
	elif any(k in ctx for k in ("yellow", "sulphur", "grass yellow", "emigrant", "lemon")):
		# Strong yellow/sulphur signal
		return yellow_labels + orange_labels + dark_labels + small_labels + moth_labels + general_labels
	elif any(k in ctx for k in ("dark", "black", "white")):
		# Dark or white butterfly → swallowtails and whites first
		return dark_labels + small_labels + orange_labels + yellow_labels + moth_labels + general_labels
	elif any(k in ctx for k in ("mud-puddling", "mud puddling")):
		# Mud-puddling shots often contain yellows and tigers mixed together
		return yellow_labels + orange_labels + dark_labels + small_labels + moth_labels + general_labels
	else:
		# No clear colour signal: use full list, dark/patterned first
		return dark_labels + orange_labels + yellow_labels + small_labels + moth_labels + general_labels


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


def _get_flower_labels() -> List[str]:
	"""Common Indian and global flower species for BioCLIP classification."""
	return [
		# Indian garden flowers
		"Marigold", "Hibiscus", "Jasmine", "Mogra Jasmine",
		"Bougainvillea", "Gulmohar", "Plumeria", "Frangipani",
		"Night-blooming Jasmine", "Parijat",
		"Champa", "Champaka",
		# Lotus & water flowers
		"Indian Lotus", "Sacred Lotus", "Water Lily",
		# Roses
		"Red Rose", "White Rose", "Yellow Rose", "Pink Rose",
		"Rose", "Climbing Rose",
		# Common garden flowers
		"Sunflower", "Dahlia", "Chrysanthemum",
		"Lily", "Asiatic Lily", "Spider Lily",
		"Orchid", "Dendrobium Orchid", "Vanda Orchid",
		"Tulip", "Daisy", "Lavender",
		"Zinnia", "Petunia", "Cosmos",
		"Periwinkle", "Sadabahar",
		"Ixora", "Lantana", "Crossandra",
		"Canna Lily", "Bird of Paradise",
		# Indian wildflowers
		"Rhododendron", "Neelakurinji",
		"Indian Blanket Flower", "Gaillardia",
		"Allamanda", "Golden Trumpet",
		"Oleander", "Kaner",
		"Crown Flower", "Aak", "Calotropis",
		# Temple flowers
		"Tuberose", "Rajnigandha",
		"Palash", "Flame of the Forest",
		"Indian Cork Tree", "Millingtonia",
		# Trees in bloom
		"Gulmohar Flower", "Amaltas", "Golden Shower Tree",
		"Jacaranda", "Bauhinia", "Kachnar",
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
