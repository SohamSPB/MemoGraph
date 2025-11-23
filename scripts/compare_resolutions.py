#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_resolutions.py

Utility to compare MemoGraph CSV outputs across different MAX_IMAGE_SIZE runs.

Example:
    python -m scripts.compare_resolutions data/trips/2025_Annapurna_Nepal
"""

import argparse
import csv
import os
from typing import Dict, List


def load_labels(trip_folder: str, folder_name: str) -> Dict[str, dict]:
	csv_path = os.path.join(trip_folder, folder_name, "labels.csv")
	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"labels.csv not found for {folder_name}: {csv_path}")
	with open(csv_path, newline="", encoding="utf-8") as f:
		rows = list(csv.DictReader(f))
	return {row["image_name"]: row for row in rows}


def compare_fields(
	image_names: List[str],
	labels_by_variant: Dict[str, Dict[str, dict]],
	fields: List[str],
) -> None:
	variants = list(labels_by_variant.keys())
	print(f"Variants: {variants}")
	print(f"Images: {len(image_names)}\n")

	for field in fields:
		all_equal = True
		first_mismatch = None

		for name in image_names:
			values = []
			for variant in variants:
				row = labels_by_variant[variant].get(name)
				values.append((variant, row.get(field, "") if row else ""))
			unique = {v for _, v in values}
			if len(unique) > 1:
				all_equal = False
				first_mismatch = (name, values)
				break

		print(f"Field '{field}': {'ALL EQUAL' if all_equal else 'DIFFERENCES FOUND'}")
		if first_mismatch:
			name, values = first_mismatch
			print(f"  First mismatch at image: {name}")
			for variant, val in values:
				print(f"    {variant}: {val}")
		print()


def main() -> None:
	p = argparse.ArgumentParser(description="Compare MemoGraph CSVs across resolutions.")
	p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
	p.add_argument(
		"--variants",
		nargs="+",
		default=["MemoGraph_256", "MemoGraph_512", "MemoGraph_1024"],
		help="Names of MemoGraph folders under the trip folder to compare.",
	)
	args = p.parse_args()

	labels_by_variant: Dict[str, Dict[str, dict]] = {}
	for variant in args.variants:
		labels_by_variant[variant] = load_labels(args.trip_folder, variant)

	# Use the intersection of image names across all variants
	image_name_sets = [set(d.keys()) for d in labels_by_variant.values()]
	common_images = sorted(set.intersection(*image_name_sets))
	if not common_images:
		print("No common images found across variants.")
		return

	print(f"Comparing {len(common_images)} common images across variants.")

	fields_to_check = [
		"faces_detected",
		"species_tags",
		"detected_objects",
		"caption",
		"caption_ai",
	]
	compare_fields(common_images, labels_by_variant, fields_to_check)


if __name__ == "__main__":
	main()

