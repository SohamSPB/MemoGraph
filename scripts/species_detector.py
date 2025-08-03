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

from scripts.utils.utils_io import read_csv_dict, write_csv_dict, ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

# ------------------------------
# Species prompts
# ------------------------------
species_prompts = {
	"birds": ["Sparrow", "Pigeon", "Eagle", "Vulture", "Kingfisher", "Bulbul",
			  "Indian Roller", "Crow", "Peacock", "Parrot", "Owl", "Woodpecker", "Hornbill", "Duck"],
	"plants": ["Rose", "Lotus", "Tulsi", "Bamboo", "Ficus", "Fern", "Banana plant", "Sunflower"],
	"insects": ["Butterfly", "Bee", "Dragonfly", "Ant", "Beetle", "Grasshopper"],
	"animals": ["Dog", "Cat", "Elephant", "Tiger", "Leopard", "Horse", "Cow", "Goat", "Sheep", "Yak", "Deer"]
}

all_species = [item for sublist in species_prompts.values() for item in sublist]


def detect_species(image_path, model, preprocess, device):
	"""Detect species using CLIP by comparing image features with text prompts."""
	image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
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
	"""Updates CSV with detected species tags."""
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

		if not os.path.exists(image_path):
			log(f"Missing image: {image_path}", log_path)
			row["species_tags"] = ""
			updated_rows.append(row)
			continue

		try:
			tags = detect_species(image_path, model, preprocess, device)
			species_tags = tags[:3]
			row["species_tags"] = ", ".join(species_tags)
			log(f"{os.path.basename(image_path)} → {row['species_tags']}", log_path)
		except Exception as e:
			log(f"Failed to process {image_path} - {e}", log_path)
			row["species_tags"] = ""

		updated_rows.append(row)

	write_csv_dict(csv_path, updated_rows, updated_rows[0].keys())
	log("Species detection complete.", log_path)


if __name__ == "__main__":
	trip_folder = "data/trips/test_trip"
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(memo_dir, "logs", "species_labeler.log")

	init_log(log_path, "species_labeler.py")
	process_species(csv_path, trip_folder, log_path)
