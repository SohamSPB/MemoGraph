#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bird_species_refiner.py

Refines bird species detection using targeted CLIP prompts.
Runs after initial species_detector to improve accuracy for bird images.

Key features:
1. Uses bird-specific prompts including bee-eaters, flycatchers, etc.
2. Cross-references AI vision captions for color/size hints
3. Updates species_tags with more accurate species names
"""

import os
import re
from typing import Dict, List, Tuple

import torch
import clip
from PIL import Image

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import init_log, log
from scripts.utils.utils_image import resize_image
from memograph_config import ensure_memograph_folder

# Bird-specific prompts organized by category
BIRD_PROMPTS = {
    # Bee-eaters (common in India/Nepal)
    "bee-eaters": [
        "Green Bee-eater", "Asian Green Bee-eater", "Bee-eater bird",
        "Blue-tailed Bee-eater", "Chestnut-headed Bee-eater",
        "Small green bird on branch", "Green bird with long tail",
    ],
    # Kingfishers
    "kingfishers": [
        "Kingfisher", "Common Kingfisher", "White-throated Kingfisher",
        "Pied Kingfisher", "Blue kingfisher on branch",
    ],
    # Flycatchers and small birds
    "flycatchers": [
        "Flycatcher", "Paradise Flycatcher", "Asian Paradise Flycatcher",
        "Verditer Flycatcher", "Blue flycatcher",
    ],
    # Bulbuls
    "bulbuls": [
        "Bulbul", "Red-vented Bulbul", "Red-whiskered Bulbul",
        "Black Bulbul", "Himalayan Bulbul",
    ],
    # Other small colorful birds
    "others": [
        "Sunbird", "Purple Sunbird", "Crimson Sunbird",
        "Drongo", "Black Drongo", "Racket-tailed Drongo",
        "Wagtail", "White Wagtail", "Yellow Wagtail",
        "Robin", "Magpie Robin",
        "Shrike", "Long-tailed Shrike",
    ],
    # Generic bird descriptors
    "generic": [
        "Bird on branch", "Small bird in tree",
        "Bird perched on twig", "Colorful bird",
    ],
}

# Flatten prompts for CLIP
ALL_BIRD_PROMPTS = []
for category, prompts in BIRD_PROMPTS.items():
    ALL_BIRD_PROMPTS.extend(prompts)


def extract_color_hints(text: str) -> List[str]:
    """Extract color mentions from caption text."""
    colors = ["green", "blue", "red", "yellow", "orange", "brown", "black", "white", "grey", "gray"]
    text_lower = text.lower()
    found = [c for c in colors if c in text_lower]
    return found


def detect_bird_species(image_path: str, model, preprocess, device, topk: int = 5) -> List[Tuple[str, float]]:
    """Detect bird species using CLIP with specialized prompts."""
    try:
        image = Image.open(image_path).convert("RGB")
        image = resize_image(image)
        image = preprocess(image).unsqueeze(0).to(device)
        text_tokens = clip.tokenize(ALL_BIRD_PROMPTS).to(device)

        with torch.no_grad():
            img_features = model.encode_image(image)
            txt_features = model.encode_text(text_tokens)
            img_features /= img_features.norm(dim=-1, keepdim=True)
            txt_features /= txt_features.norm(dim=-1, keepdim=True)
            similarity = (100.0 * img_features @ txt_features.T).softmax(dim=-1)

        scores = similarity[0].cpu().numpy()
        results = list(zip(ALL_BIRD_PROMPTS, scores))
        results.sort(key=lambda x: -x[1])

        return results[:topk]

    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return []


def is_bird_image(row: Dict) -> bool:
    """Check if this image likely contains a bird (strict mode to avoid false positives)."""
    detected = str(row.get("detected_objects", "")).lower()
    species = str(row.get("species_tags", "")).lower()
    caption_ai = str(row.get("vision_caption", "")).lower()
    image_type = str(row.get("image_type", "")).lower()

    # Skip non-natural photos
    if image_type in ("meme_or_graphic", "document_scan", "chart_or_plot", "screenshot"):
        return False

    # Skip astrophotography (galaxy, stars, etc.)
    astro_keywords = {"astrophotography", "galaxy", "nebula", "star cluster", "milky way", "stars"}
    detected_tokens = set(re.findall(r"\w+", detected))
    if not astro_keywords.isdisjoint(detected_tokens):
        return False

    # Skip butterfly/insect images
    insect_keywords = {"butterfly", "butterflies", "mud-puddling", "insect", "moth", "bee", "dragonfly"}
    if not insect_keywords.isdisjoint(detected_tokens):
        return False

    # Now check for positive bird indicators
    bird_keywords = {"bird", "sparrow", "eagle", "owl", "kingfisher", "crow", "pigeon",
                     "parrot", "heron", "duck", "swan", "vulture", "hawk", "bee-eater",
                     "bulbul", "drongo", "myna", "flycatcher", "sunbird"}

    # Check detected objects for bird keywords
    if not bird_keywords.isdisjoint(detected_tokens):
        return True

    # Check AI caption for bird mentions (must explicitly mention bird)
    if "bird" in caption_ai and ("perch" in caption_ai or "branch" in caption_ai or "tree" in caption_ai):
        return True

    return False


def refine_bird_species(trip_folder: str):
    """Main function to refine bird species detection."""
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    log_path = os.path.join(logs_dir, "bird_species_refiner.log")
    csv_path = os.path.join(memo_dir, "labels.csv")

    init_log(log_path, "bird_species_refiner.py")
    log(f"Processing: {trip_folder}", log_path)

    rows = read_csv_dict(csv_path)
    if not rows:
        log("No rows found in CSV.", log_path)
        return

    # Load CLIP model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    log(f"Using device: {device}", log_path)

    updated_count = 0

    for row in rows:
        if not is_bird_image(row):
            continue

        img_path = os.path.join(trip_folder, row.get("local_path", ""))
        if not os.path.exists(img_path):
            continue

        image_name = row.get("image_name", "")

        # Get bird species predictions
        predictions = detect_bird_species(img_path, model, preprocess, device, topk=5)

        if not predictions:
            continue

        # Get color hints from AI caption
        caption_ai = str(row.get("vision_caption", ""))
        color_hints = extract_color_hints(caption_ai)

        # Find best matching specific species (not generic descriptions)
        best_species = None
        best_score = 0.0

        generic_terms = {"bird on branch", "small bird in tree", "bird perched on twig", "colorful bird"}

        for species, score in predictions:
            if species.lower() in generic_terms:
                continue
            if score > best_score:
                best_species = species
                best_score = score

        # Only update if we found a specific species with reasonable confidence
        if best_species and best_score > 0.08:  # 8% threshold
            old_species = row.get("species_tags", "")

            # Check if this is a new/better detection
            if best_species.lower() not in old_species.lower():
                # Add new species to existing tags
                if old_species and "bird" not in old_species.lower():
                    new_species = f"{best_species}; {old_species}"
                else:
                    new_species = best_species

                row["species_tags"] = new_species
                updated_count += 1

                log(f"{image_name}: {old_species} → {new_species} ({best_score*100:.1f}%)", log_path)
                print(f"  {image_name}: '{best_species}' ({best_score*100:.1f}%)")

    # Save updated CSV
    if updated_count > 0:
        write_csv_dict(csv_path, rows, rows[0].keys())
        log(f"Updated {updated_count} bird images", log_path)
        print(f"\nUpdated {updated_count} bird images")
    else:
        log("No updates needed", log_path)
        print("No updates needed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m scripts.bird_species_refiner <trip_folder>")
        print("Example: python -m scripts.bird_species_refiner data/trips/2025_Annapurna_Nepal")
        sys.exit(1)

    trip_folder = sys.argv[1]
    refine_bird_species(trip_folder)
