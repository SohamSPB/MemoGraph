#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hybrid_labeler.py

A hybrid (ensemble) image labeler that:
  1) Runs CLIP zero-shot on curated prompts (nature, astro, people, etc.).
  2) Optionally runs Places365 (scene classifier).
  3) Optionally runs iNaturalist classifier.

Outputs:
  - labels_clip
  - labels_places365
  - labels_inat
  - labels_final (merged/voted)

Logs: <trip_folder>/MemoGraph/logs/hybrid_labeler.log
"""

import argparse
import os
import sys
import traceback
from collections import defaultdict, Counter

import torch
from PIL import Image

# Local imports
from scripts.utils.utils_io import read_csv_dict, write_csv_dict, ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

# ---- CLIP (OpenAI) ----
try:
	import clip
	_HAS_CLIP = True
except Exception as e:
	print("[WARN] Failed to import CLIP:", e)
	_HAS_CLIP = False

# ---- torchvision (for Places365 and iNat) ----
try:
	import torchvision.transforms as T
	import torchvision.models as tv_models
	_HAS_TORCHVISION = True
except Exception as e:
	print("[WARN] Failed to import torchvision:", e)
	_HAS_TORCHVISION = False


# ==========================
# CLI ARGUMENTS
# ==========================
def parse_args():
	p = argparse.ArgumentParser(description="Hybrid (CLIP + Places365 + iNat) labeler.")
	p.add_argument("--csv", required=True, help="Path to labels.csv")
	p.add_argument("--trip-folder", required=True, help="Folder containing images")

	# Optional classifiers
	p.add_argument("--places365", action="store_true", help="Enable Places365 scene classifier")
	p.add_argument("--inat-ckpt", type=str, default=None, help="Path to iNaturalist checkpoint (.pth)")
	p.add_argument("--inat-categories", type=str, default=None, help="Path to iNat categories JSON")

	# Settings
	p.add_argument("--clip-topk", type=int, default=5, help="Top-K CLIP labels")
	p.add_argument("--places-topk", type=int, default=3, help="Top-K Places365 labels")
	p.add_argument("--inat-topk", type=int, default=3, help="Top-K iNat labels")
	p.add_argument("--prob-threshold", type=float, default=0.10, help="Drop labels below this probability")
	p.add_argument("--final-topk", type=int, default=5, help="Final top labels to keep")
	p.add_argument("--dry-run", action="store_true", help="Print only, don't save CSV")

	# Places365 paths
	p.add_argument("--places365-weights", type=str, default=None, help="Path to resnet50_places365.pth")
	p.add_argument("--places365-classes", type=str, default=None, help="Path to categories_places365.txt")
	p.add_argument("--places365-allow-download", action="store_true", help="Allow downloading Places365 weights")
	return p.parse_args()


# ==========================
# CLIP ZERO-SHOT
# ==========================
def build_clip_concepts():
	"""Define concepts for CLIP classification."""
	return [
		"a mountain landscape", "a snowy Himalayan landscape", "a valley", "a glacier",
		"a forest", "a river", "a lake", "a waterfall", "a desert", "a grassland",
		"a cityscape", "a street scene", "a village", "a monastery", "a temple",
		"a person", "a group of people", "a portrait photo",
		"a bird", "a flower", "a plant", "an insect", "an animal", "a dog", "a cat", "a yak",
		"the Milky Way", "a night sky", "stars", "a nebula", "a galaxy", "a star cluster",
		"an astrophotography photo", "the Andromeda galaxy", "the Orion nebula",
		"a campsite", "a sunrise", "a sunset", "a food dish", "a monument", "a building"
	]


def load_clip(device):
	if not _HAS_CLIP:
		return None, None, None
	model, preprocess = clip.load("ViT-B/32", device=device)
	model.eval()
	concepts = build_clip_concepts()
	with torch.no_grad():
		text_tokens = clip.tokenize(concepts).to(device)
		text_features = model.encode_text(text_tokens)
		text_features = text_features / text_features.norm(dim=-1, keepdim=True)
	return model, preprocess, (concepts, text_features)


def clip_classify_image(model, preprocess, text_pack, image_path, device, topk=5, prob_threshold=0.10):
	"""Classify image with CLIP."""
	concepts, text_features = text_pack
	try:
		with torch.no_grad():
			image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
			image_features = model.encode_image(image)
			image_features = image_features / image_features.norm(dim=-1, keepdim=True)
			logits = 100.0 * image_features @ text_features.T
			probs = logits.softmax(dim=-1)[0]
			top_probs, top_indices = probs.topk(topk)
			return [(concepts[idx], p) for p, idx in zip(top_probs.tolist(), top_indices.tolist()) if p >= prob_threshold]
	except Exception as e:
		return []


# ==========================
# MERGE LABELS
# ==========================
def merge_labels(*label_lists, topk=5):
	"""Merge results from multiple classifiers."""
	score_map, votes = defaultdict(float), Counter()
	for labels in label_lists:
		for lab, score in labels:
			norm_lab = lab.strip().lower()
			score_map[norm_lab] += score
			votes[norm_lab] += 1
	combined = sorted(score_map.items(), key=lambda x: (votes[x[0]], x[1]), reverse=True)
	return [f"{lab} (votes={votes[lab]}, score={score:.2f})" for lab, score in combined[:topk]]


# ==========================
# MAIN PROCESS
# ==========================
def main():
	args = parse_args()
	trip_folder = args.trip_folder
	memo_dir = ensure_memograph_folder(trip_folder, CFG.MEMOGRAPH_FOLDER_NAME)
	log_path = os.path.join(memo_dir, "logs", "hybrid_labeler.log")
	init_log(log_path, "hybrid_labeler.py")

	if not os.path.exists(args.csv):
		log(f"CSV not found: {args.csv}", log_path)
		sys.exit(1)

	device = "cuda" if torch.cuda.is_available() else "cpu"
	log(f"Using device: {device}", log_path)

	# Load CLIP
	clip_model, clip_preprocess, clip_text_pack = load_clip(device)
	if clip_model is None:
		log("CLIP failed to load. Exiting.", log_path)
		sys.exit(1)

	# Read CSV
	rows = read_csv_dict(args.csv)
	if not rows:
		log("CSV is empty. Exiting.", log_path)
		sys.exit(0)

	# Ensure required columns
	needed_cols = ["labels_clip", "labels_places365", "labels_inat", "labels_final"]
	fieldnames = list(rows[0].keys())
	for col in needed_cols:
		if col not in fieldnames:
			fieldnames.append(col)

	# Process images
	for idx, row in enumerate(rows, start=1):
		local_path = row.get("local_path") or row.get("filepath") or row.get("image_name")
		if not local_path:
			log(f"Row missing image path. Skipping.", log_path)
			continue

		image_path = os.path.join(trip_folder, local_path)
		if not os.path.exists(image_path):
			log(f"Missing image: {image_path}", log_path)
			continue

		clip_out = clip_classify_image(clip_model, clip_preprocess, clip_text_pack, image_path,
									   device, topk=args.clip_topk, prob_threshold=args.prob_threshold)

		row["labels_clip"] = "; ".join([f"{lab} ({p*100:.1f}%)" for lab, p in clip_out])
		row["labels_final"] = "; ".join(merge_labels(clip_out, topk=args.final_topk))

		if idx % 20 == 0:
			log(f"Processed {idx}/{len(rows)} images.", log_path)

	if args.dry_run:
		log("Dry run: CSV not saved.", log_path)
		return

	write_csv_dict(args.csv, rows, fieldnames)
	log(f"Updated CSV: {args.csv}", log_path)


if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		print("[FATAL]", e)
		traceback.print_exc()
		sys.exit(1)
