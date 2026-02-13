#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
species_labeler.py

Detects species (birds, plants, insects, animals) in images using CLIP.
Updates `species_tags` in the labels CSV.

Logs: <trip_folder>/MemoGraph/logs/species_labeler.log
"""

import os
import torch
import clip
from PIL import Image

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG
from scripts.utils.utils_image import resize_image
from scripts.species_models import (
	predict_bird_species,
	detect_and_classify,
	format_species_boxes,
	_gdino_available,
	_bioclip_available,
	unload_grounding_dino,
	unload_bioclip,
)

# ------------------------------
# Species prompts - Expanded for better coverage
# ------------------------------
species_prompts = {
	"birds": [
		# Common birds
		"Sparrow", "House Sparrow", "Tree Sparrow",
		"Pigeon", "Rock Pigeon", "Dove",
		"Crow", "House Crow", "Jungle Crow", "Raven",
		"Eagle", "Golden Eagle", "Bald Eagle",
		"Vulture", "Griffon Vulture",
		"Hawk", "Kite", "Black Kite",
		# Bee-eaters (common in India/Nepal)
		"Bee-eater", "Green Bee-eater", "Asian Green Bee-eater",
		"Blue-tailed Bee-eater", "Chestnut-headed Bee-eater",
		"Small green bird on branch", "Green bird with long tail",
		# Colorful birds
		"Kingfisher", "Common Kingfisher", "White-throated Kingfisher",
		"Bulbul", "Red-vented Bulbul", "Red-whiskered Bulbul",
		"Indian Roller", "Blue Jay",
		"Peacock", "Peafowl",
		"Parrot", "Parakeet", "Rose-ringed Parakeet",
		# Flycatchers and small birds
		"Flycatcher", "Paradise Flycatcher", "Asian Paradise Flycatcher",
		"Wagtail", "White Wagtail", "Yellow Wagtail",
		"Shrike", "Long-tailed Shrike",
		# Other common birds
		"Owl", "Barn Owl", "Spotted Owlet",
		"Woodpecker", "Golden-backed Woodpecker",
		"Hornbill", "Great Hornbill", "Indian Grey Hornbill",
		"Duck", "Mallard", "Spot-billed Duck",
		"Swan", "Goose", "Bar-headed Goose",
		"Heron", "Egret", "Grey Heron", "Pond Heron",
		"Stork", "Painted Stork", "Asian Openbill",
		"Myna", "Common Myna", "Hill Myna", "Jungle Myna",
		"Starling", "Asian Pied Starling",
		"Robin", "Magpie Robin", "Oriental Magpie Robin",
		"Sunbird", "Purple Sunbird", "Crimson Sunbird",
		"Drongo", "Black Drongo", "Greater Racket-tailed Drongo",
		"Cuckoo", "Koel", "Asian Koel",
		"Warbler", "Tailorbird", "Common Tailorbird",
		"Flamingo",
		"Pelican",
		"Cormorant", "Little Cormorant",
		# Himalayan birds
		"Laughingthrush", "White-crested Laughingthrush",
		"Barbet", "Coppersmith Barbet", "Blue-throated Barbet",
		"Minivet", "Scarlet Minivet",
		"Nuthatch", "Chestnut-bellied Nuthatch",
		"Tit", "Great Tit", "Green-backed Tit",
	],
	"plants": [
		# Flowers
		"Rose", "Red Rose", "White Rose", "Pink Rose",
		"Lotus", "Water Lily",
		"Sunflower",
		"Marigold",
		"Hibiscus",
		"Jasmine",
		"Orchid",
		"Tulip",
		"Dahlia",
		"Bougainvillea",
		"Lily", "Tiger Lily",
		"Chrysanthemum",
		"Lavender",
		"Daisy",
		# Trees & Plants
		"Tulsi", "Holy Basil",
		"Bamboo",
		"Ficus", "Banyan Tree", "Peepal Tree",
		"Fern",
		"Banana plant", "Banana Tree",
		"Coconut Palm", "Palm Tree",
		"Mango Tree",
		"Neem Tree",
		"Pine Tree",
		"Oak Tree",
		"Eucalyptus",
		"Rhododendron",
		"Moss",
		"Cactus",
		"Aloe Vera",
	],
	"insects": [
		# Butterflies - various species and behaviors
		"Butterfly", "Monarch Butterfly", "Swallowtail Butterfly",
		"Common Mormon", "Blue Mormon", "Painted Lady",
		# Yellow/Sulphur butterflies (common in Asia)
		"Grass Yellow Butterfly", "Common Grass Yellow", "Sulphur Butterfly",
		"Common Emigrant", "Mottled Emigrant", "Lemon Emigrant",
		# Mud-puddling behavior (butterflies drinking minerals from soil)
		"Mud-puddling butterflies", "Butterflies feeding on minerals",
		"Yellow butterfly", "Small yellow butterfly",
		"Moth", "Hawkmoth", "Silk Moth",
		# Flying insects
		"Bee", "Honeybee", "Bumblebee",
		"Wasp", "Hornet",
		"Dragonfly", "Damselfly",
		"Fly", "Housefly",
		"Mosquito",
		# Crawling insects
		"Ant", "Red Ant", "Black Ant",
		"Beetle", "Ladybug", "Ladybird",
		"Grasshopper", "Cricket",
		"Cockroach",
		"Caterpillar",
		"Praying Mantis",
		"Termite",
		# Arachnids
		"Spider", "Orb Weaver Spider", "Jumping Spider",
		"Scorpion",
		"Tick",
	],
	"animals": [
		# Domestic animals
		"Dog", "Puppy", "Stray Dog",
		"Cat", "Kitten",
		"Horse", "Pony", "Donkey", "Mule",
		"Cow", "Bull", "Calf", "Buffalo", "Water Buffalo",
		"Goat", "Sheep", "Lamb",
		# Mountain animals
		"Yak", "Himalayan Yak",
		"Mountain Goat", "Blue Sheep", "Bharal",
		"Marmot",
		# Wild animals
		"Elephant", "Indian Elephant",
		"Tiger", "Bengal Tiger",
		"Leopard", "Snow Leopard",
		"Lion",
		"Bear", "Black Bear", "Brown Bear",
		"Deer", "Spotted Deer", "Sambar",
		"Antelope", "Nilgai", "Blackbuck",
		# Primates
		"Monkey", "Macaque", "Rhesus Macaque", "Langur",
		"Ape",
		# Other mammals
		"Squirrel",
		"Rabbit", "Hare",
		"Rat", "Mouse",
		"Bat",
		"Fox", "Jackal",
		"Wild Boar", "Pig",
		"Camel",
		# Reptiles & Amphibians
		"Snake", "Cobra", "Python",
		"Lizard", "Gecko", "Monitor Lizard",
		"Crocodile", "Alligator",
		"Turtle", "Tortoise",
		"Frog", "Toad",
		# Fish
		"Fish", "Goldfish", "Carp",
	],
}

all_species = [item for sublist in species_prompts.values() for item in sublist]


def _row_has_species(row) -> bool:
	"""Return True if this row already has species_tags populated."""
	return bool((row.get("species_tags") or "").strip())


def detect_species(image_path, model, preprocess, device):
	"""Detect species using CLIP by comparing image features with text prompts."""
	image = Image.open(image_path).convert("RGB")
	image = resize_image(image)
	image = preprocess(image).unsqueeze(0).to(device)
	text = clip.tokenize(all_species).to(device)

	with torch.no_grad():
		image_features = model.encode_image(image)
		text_features = model.encode_text(text)
		image_features /= image_features.norm(dim=-1, keepdim=True)
		text_features /= text_features.norm(dim=-1, keepdim=True)
		similarity = (100.0 * image_features @ text_features.T).squeeze(0)
		confidences = similarity.tolist()

	# Lower threshold to 15.0 for more permissive species detection
	matches = [(all_species[i], conf) for i, conf in enumerate(confidences) if conf > 15.0]
	matches.sort(key=lambda x: -x[1])
	return [match for match, _ in matches]


def _get_fieldnames(rows):
	"""Get all unique fieldnames across all rows."""
	seen = set()
	fields = []
	for row in rows:
		for key in row.keys():
			if key not in seen:
				fields.append(key)
				seen.add(key)
	return fields


def process_species(csv_path, trip_folder, log_path):
	"""Updates CSV with detected species tags and bounding boxes.

	Two-stage pipeline when OWLv2 + BioCLIP 2 are available:
	  1. OWLv2 detects wildlife bounding boxes
	  2. BioCLIP 2 classifies each crop to species level
	  3. Results stored in species_tags + species_boxes columns

	Falls back to CLIP + bird model when advanced models not available.
	"""
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV.", log_path)
		return

	device = "cuda" if torch.cuda.is_available() else "cpu"

	# Check if advanced models are available
	use_advanced = (
		getattr(CFG, "ENABLE_SPECIES_DETECTION", False)
		and getattr(CFG, "ENABLE_BIOCLIP", False)
		and _bioclip_available()
	)

	if use_advanced:
		log("Advanced species pipeline: OWLv2 + BioCLIP 2", log_path)
	else:
		log("Using classic CLIP + bird model pipeline", log_path)
		if not _bioclip_available():
			log("  BioCLIP 2 not found. Run: python -m scripts.download_species_models --model bioclip2", log_path)

	model, preprocess = clip.load("ViT-B/32", device=device)
	log(f"Using device: {device}", log_path)

	updated_rows = []
	updated_count = 0

	def _flush():
		"""Incrementally flush current species tags to CSV."""
		if not updated_rows:
			return
		write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
		log("Incremental save: species_tags flushed to CSV.", log_path)

	try:
		for row in rows:
			# Skip rows that already have species_tags so that re-running the script
			# acts as a resume operation, only filling in missing tags.
			if _row_has_species(row):
				updated_rows.append(row)
				continue

			local_path = row.get("local_path", "")
			image_path = os.path.join(trip_folder, local_path)

			# Decide if this image is a good candidate for biological species
			# detection.
			image_type = str(row.get("image_type", "")).strip()
			if image_type in ("meme_or_graphic", "document_scan", "chart_or_plot", "screenshot"):
				log(f"{os.path.basename(image_path)} -> skipped species detection (image_type={image_type})", log_path)
				row["species_tags"] = row.get("species_tags", "")
				updated_rows.append(row)
				continue

			coarse_text = " ".join(
				str(row.get(field, "")) for field in ("detected_objects", "caption", "caption_ai")
			).lower()

			# Tokenize for safer keyword matching (avoid "bowl" matching "owl")
			import re
			tokens = set(re.findall(r"\w+", coarse_text))

			bio_keywords = {
				"bird", "insect", "animal", "dog", "cat", "horse", "cow", "goat",
				"sheep", "yak", "deer", "plant", "flower", "tree", "forest",
				"grass", "leaf", "nature", "wildlife", "butterfly", "mud", "puddling"
			}
			has_bio_hint = not bio_keywords.isdisjoint(tokens)

			# Bird keywords - be more strict to avoid false positives
			# Only trigger bird model if detected_objects explicitly contains bird-related terms
			detected_objects_text = str(row.get("detected_objects", "")).lower()
			detected_tokens = set(re.findall(r"\w+", detected_objects_text))
			bird_keywords = {"bird", "sparrow", "eagle", "owl", "duck", "peacock", "kingfisher", "crow",
							 "pigeon", "parrot", "heron", "swan", "vulture", "hawk"}
			# Only use bird model if detected_objects has bird hints (not just captions which can hallucinate)
			has_bird_hint = not bird_keywords.isdisjoint(detected_tokens)

			if not os.path.exists(image_path):
				log(f"Missing image: {image_path}", log_path)
				# Preserve any existing coarse species tags from image_labeler
				row["species_tags"] = row.get("species_tags", "")
				updated_rows.append(row)
				continue

			# If there is no biological hint, do not run species matching;
			# keep whatever coarse tags are already present.
			if not has_bio_hint:
				log(
					f"{os.path.basename(image_path)} -> skipped species detection (no bio hints)",
					log_path,
				)
				row["species_tags"] = row.get("species_tags", "")
				row["species_boxes"] = row.get("species_boxes", "")
				updated_count += 1
			elif use_advanced:
				# --- Advanced pipeline: OWLv2 + BioCLIP 2 ---
				try:
					raw_image = Image.open(image_path).convert("RGB")
					detections = detect_and_classify(raw_image)
					if detections:
						# Extract unique species names
						species_names = []
						seen = set()
						for det in detections:
							name = det.get("best_species", "")
							if name and name.lower() not in seen:
								species_names.append(name)
								seen.add(name.lower())
						row["species_tags"] = ", ".join(species_names[:5])
						row["species_boxes"] = format_species_boxes(detections)
						log(
							f"{os.path.basename(image_path)} -> advanced: {len(detections)} detections, "
							f"species: {row['species_tags']}",
							log_path,
						)
					else:
						# No detections from OWLv2 - fall back to CLIP
						tags = detect_species(image_path, model, preprocess, device)
						species_tags = tags[:3]
						row["species_tags"] = ", ".join(species_tags) if species_tags else row.get("species_tags", "")
						row["species_boxes"] = ""
						log(f"{os.path.basename(image_path)} -> CLIP fallback: {row.get('species_tags', '')}", log_path)
					updated_count += 1
				except Exception as e:
					log(f"{os.path.basename(image_path)} -> advanced pipeline failed ({e}), trying CLIP", log_path)
					try:
						tags = detect_species(image_path, model, preprocess, device)
						row["species_tags"] = ", ".join(tags[:3]) if tags else row.get("species_tags", "")
					except Exception:
						row["species_tags"] = row.get("species_tags", "")
					row["species_boxes"] = ""
			else:
				# --- Classic pipeline: bird model + CLIP ---
				bird_tags_used = False
				if CFG.ENABLE_BIRD_MODEL and has_bird_hint:
					try:
						raw_image = Image.open(image_path).convert("RGB")
						raw_image = resize_image(raw_image)
						bird_preds = predict_bird_species(raw_image, topk=getattr(CFG, "BIRD_TOPK", 3))
						if bird_preds:
							bird_names = [name for name, _ in bird_preds]
							row["species_tags"] = ", ".join(bird_names)
							log(
								f"{os.path.basename(image_path)} -> bird model: {row.get('species_tags', '')}",
								log_path,
							)
							bird_tags_used = True
							updated_count += 1
					except Exception as e:
						log(
							f"{os.path.basename(image_path)} -> bird model failed ({e}), falling back to CLIP.",
							log_path,
						)

				if not bird_tags_used:
					try:
						tags = detect_species(image_path, model, preprocess, device)
						species_tags = tags[:3]
						if species_tags:
							row["species_tags"] = ", ".join(species_tags)
						else:
							row["species_tags"] = row.get("species_tags", "")
						log(f"{os.path.basename(image_path)} -> {row.get('species_tags', '')}", log_path)
						if species_tags:
							updated_count += 1
					except Exception as e:
						log(f"Failed to process {image_path} - {e}", log_path)
						row["species_tags"] = row.get("species_tags", "")

			updated_rows.append(row)

			# Periodic incremental save so that long runs can resume with minimal loss.
			if updated_count and updated_count % 10 == 0:
				_flush()
	except KeyboardInterrupt:
		log(f"[INTERRUPTED] Species detection interrupted after {updated_count} images. Saving progress...", log_path)
		if updated_rows:
			write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
		raise
	finally:
		# Free GPU memory from advanced models
		if use_advanced:
			try:
				unload_grounding_dino()
				unload_bioclip()
			except Exception:
				pass

	write_csv_dict(csv_path, updated_rows, _get_fieldnames(updated_rows))
	log("Species detection complete.", log_path)


if __name__ == "__main__":
	import sys

	trip_folder = sys.argv[1] if len(sys.argv) > 1 else "data/trips/test_trip"
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "species_labeler.log")

	init_log(log_path, "species_labeler.py")

	process_species(csv_path, trip_folder, log_path)
