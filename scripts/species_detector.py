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
from scripts.species_models import predict_bird_species

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
		# Colorful birds
		"Kingfisher", "Common Kingfisher",
		"Bulbul", "Red-vented Bulbul", "Red-whiskered Bulbul",
		"Indian Roller", "Blue Jay",
		"Peacock", "Peafowl",
		"Parrot", "Parakeet", "Rose-ringed Parakeet",
		# Other common birds
		"Owl", "Barn Owl", "Spotted Owlet",
		"Woodpecker",
		"Hornbill", "Great Hornbill",
		"Duck", "Mallard",
		"Swan", "Goose",
		"Heron", "Egret", "Grey Heron",
		"Stork", "Painted Stork",
		"Myna", "Common Myna", "Hill Myna",
		"Starling",
		"Robin", "Magpie Robin",
		"Sunbird", "Purple Sunbird",
		"Drongo", "Black Drongo",
		"Cuckoo", "Koel",
		"Warbler", "Tailorbird",
		"Flamingo",
		"Pelican",
		"Cormorant",
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
		# Butterflies
		"Butterfly", "Monarch Butterfly", "Swallowtail Butterfly",
		"Common Mormon", "Blue Mormon", "Painted Lady",
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


def process_species(csv_path, trip_folder, log_path):
	"""Updates CSV with detected species tags.

	This function refines any coarse species tags that may already be present
	(from image_labeler) but does not erase them when it cannot make a confident
	prediction.
	"""
	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows found in CSV.", log_path)
		return

	device = "cuda" if torch.cuda.is_available() else "cpu"
	model, preprocess = clip.load("ViT-B/32", device=device)
	log(f"Using device: {device}", log_path)

	updated_rows = []
	updated_count = 0

	def _flush():
		"""Incrementally flush current species tags to CSV."""
		if not updated_rows:
			return
		write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())
		log("Incremental save: species_tags flushed to CSV.", log_path)

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
			"grass", "leaf", "nature", "wildlife"
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

		# If there is no biological hint, do not run CLIP species matching;
		# keep whatever coarse tags are already present (often astrophotography
		# / galaxy related for space images).
		if not has_bio_hint:
			log(
				f"{os.path.basename(image_path)} -> skipped species detection (no bio hints)",
				log_path,
			)
			row["species_tags"] = row.get("species_tags", "")
			updated_count += 1
		else:
			bird_tags_used = False
			# Prefer the specialist bird model when enabled and the coarse text
			# clearly indicates a bird.
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

			# If bird model did not provide tags (not enabled, no hint, or failed),
			# fall back to CLIP species prompts.
			if not bird_tags_used:
				try:
					tags = detect_species(image_path, model, preprocess, device)
					species_tags = tags[:3]
					if species_tags:
						# Only override if we have confident species predictions; otherwise
						# keep whatever coarse tags were already present.
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

	write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())
	log("Species detection complete.", log_path)


if __name__ == "__main__":
	import multiprocessing

	trip_folder = "data/trips/test_trip"
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "species_labeler.log")

	init_log(log_path, "species_labeler.py")

	process_species(csv_path, trip_folder, log_path)
