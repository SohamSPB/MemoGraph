#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_labels_variants.py

Print a CSV-style comparison of labels.csv content across multiple
MemoGraph variants for a given trip.

Example:
    python -m scripts.compare_labels_variants data/trips/2025_Annapurna_Nepal \
        --variants MemoGraph_256 MemoGraph_256_2 MemoGraph_512 MemoGraph_512_2 MemoGraph_1024 MemoGraph_1024_2 \
        --fields detected_objects species_tags caption caption_ai
"""

import argparse
import csv
import os
from typing import Dict, List


def load_labels(trip_folder: str, variant: str) -> Dict[str, dict]:
    """
    Load labels.csv for a given MemoGraph variant as
    image_name -> row dict.
    """
    path = os.path.join(trip_folder, variant, "labels.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"labels.csv not found for {variant}: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["image_name"]: row for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare labels.csv fields across MemoGraph variants."
    )
    parser.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
    parser.add_argument(
        "--variants",
        nargs="+",
        required=True,
        help="Names of MemoGraph folders under the trip folder to compare.",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["detected_objects", "species_tags", "caption", "caption_ai"],
        help="CSV fields to compare for each image.",
    )
    args = parser.parse_args()

    labels_by_variant: Dict[str, Dict[str, dict]] = {}
    for variant in args.variants:
        labels_by_variant[variant] = load_labels(args.trip_folder, variant)

    # Intersection of image names across variants
    image_name_sets = [set(d.keys()) for d in labels_by_variant.values()]
    common_images = sorted(set.intersection(*image_name_sets))
    if not common_images:
        print("No common images across variants.")
        return

    # Header: image_name, then for each variant/field: <variant>:<field>
    header_cells: List[str] = ["image_name"]
    for variant in args.variants:
        for field in args.fields:
            header_cells.append(f"{variant}:{field}")
    print(",".join(header_cells))

    # Rows
    for name in common_images:
        row_cells: List[str] = [name]
        for variant in args.variants:
            row = labels_by_variant[variant].get(name, {})
            for field in args.fields:
                value = row.get(field, "")
                # Escape double quotes for CSV output
                value = value.replace('"', '""')
                row_cells.append(f"\"{value}\"")
        print(",".join(row_cells))


if __name__ == "__main__":
    main()

