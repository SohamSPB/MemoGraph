#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_stats.py

Compare per-step resource usage across multiple MemoGraph outputs
for a given trip folder.

Example:
    python -m scripts.compare_stats data/trips/2025_Annapurna_Nepal \
        --variants MemoGraph_256_2 MemoGraph_512_2 MemoGraph_1024_2
"""

import argparse
import csv
import os
from typing import Dict, List


def load_step_stats(trip_folder: str, variant: str) -> Dict[str, Dict[str, float]]:
    """
    Load step -> {cpu_percent, ram_mb, gpu_mb} from resource_usage.csv
    inside the given MemoGraph variant.
    """
    path = os.path.join(trip_folder, variant, "logs", "resource_usage.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"resource_usage.csv not found for {variant}: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        stats: Dict[str, Dict[str, float]] = {}
        for row in reader:
            step = row["step"]
            stats[step] = {
                "cpu_percent": float(row["cpu_percent"]),
                "ram_mb": float(row["ram_mb"]),
                "gpu_mb": float(row.get("gpu_mb", 0.0)),
            }
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare MemoGraph per-step resource stats across variants."
    )
    parser.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
    parser.add_argument(
        "--variants",
        nargs="+",
        required=True,
        help="Names of MemoGraph folders under the trip folder (e.g. MemoGraph_256 MemoGraph_256_2).",
    )
    args = parser.parse_args()

    variant_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
    for variant in args.variants:
        variant_stats[variant] = load_step_stats(args.trip_folder, variant)

    # Collect union of step names across all variants
    all_steps: List[str] = sorted(
        {step for stats in variant_stats.values() for step in stats.keys()}
    )

    # Print a simple CSV-like table to stdout
    header_cells: List[str] = ["step"]
    for variant in args.variants:
        header_cells.extend(
            [f"{variant}:cpu_percent", f"{variant}:ram_mb", f"{variant}:gpu_mb"]
        )
    print(",".join(header_cells))

    for step in all_steps:
        row_cells: List[str] = [step]
        for variant in args.variants:
            stats = variant_stats[variant].get(step)
            if stats:
                row_cells.append(f"{stats['cpu_percent']:.1f}")
                row_cells.append(f"{stats['ram_mb']:.1f}")
                row_cells.append(f"{stats['gpu_mb']:.1f}")
            else:
                row_cells.extend(["", "", ""])
        print(",".join(row_cells))


if __name__ == "__main__":
    main()

