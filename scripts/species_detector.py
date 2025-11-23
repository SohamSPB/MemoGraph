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

# ------------------------------
# Species prompts
# ------------------------------
species_prompts = {
	"birds": [
		"Sparrow",
		"Pigeon",
		"Eagle",
		"Vulture",
		"Kingfisher",
		"Bulbul",
		"Indian Roller",
		"Crow",
		"Peacock",
		"Parrot",
		"Owl",
		"Woodpecker",
		"Hornbill",
		"Duck",
	],
	"plants": [
		"Rose",
		"Lotus",
		"Tulsi",
		"Bamboo",
		"Ficus",
		"Fern",
		"Banana plant",
		"Sunflower",
	],
	"insects": [
		"Butterfly",
		"Bee",
		"Dragonfly",
		"Ant",
		"Beetle",
		"Grasshopper",
	],
	"animals": [
		"Dog",
		"Cat",
		"Elephant",
		"Tiger",
		"Leopard",
		"Horse",
		"Cow",
		"Goat",
		"Sheep",
		"Yak",
		"Deer",
	],
}

all_species = [item for sublist in species_prompts.values() for item in sublist]


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

	matches = [(all_species[i], conf) for i, conf in enumerate(confidences) if conf > 20.0]
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
	for row in rows:
		local_path = row.get("local_path", "")
		image_path = os.path.join(trip_folder, local_path)

		# Decide if this image is a good candidate for biological species
		# detection. If the coarse labels / captions do not mention any
		# bird/animal/plant/insect concepts, we skip the specialist CLIP
		# species matching entirely to avoid hallucinating birds on space
		# images or purely inanimate scenes.
		coarse_text = " ".join(
			str(row.get(field, "")) for field in ("detected_objects", "caption", "caption_ai")
		).lower()
		bio_keywords = [
			"bird",
			"insect",
			"animal",
			"dog",
			"cat",
			"horse",
			"cow",
			"goat",
			"sheep",
			"yak",
			"deer",
			"plant",
			"flower",
			"tree",
			"forest",
			"grass",
			"leaf",
		]
		has_bio_hint = any(keyword in coarse_text for keyword in bio_keywords)

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
		else:
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
			except Exception as e:
				log(f"Failed to process {image_path} - {e}", log_path)
				row["species_tags"] = row.get("species_tags", "")

		updated_rows.append(row)

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
