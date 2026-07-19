#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedup_broadcast.py

Copy analysis columns from canonical rows to their md5-identical siblings.

image_scanner.py groups rows by md5sum and marks all but one in each group
with duplicate_of=<canonical_image_name>. Analysis scripts (face_detector,
image_labeler, caption_filler, species_detector, etc.) skip rows whose
duplicate_of is non-empty, so the canonical does the AI work once and the
duplicates stay empty until this step runs.

This script is run by run_all.py just before blog generation (which needs
duplicates to carry the same captions/species/tags as their canonical so the
blog and webapp render them correctly).

Run standalone:
    python -m scripts.dedup_broadcast data/trips/<trip>
"""

from __future__ import annotations

import os
from typing import Dict, List

import memograph_config as CFG
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from scripts.utils.utils_log import init_log, log


def _get_fieldnames(rows: List[Dict[str, str]]) -> List[str]:
	"""Preserve existing column order while ensuring every present key is written.

	Mirrors the helper pattern used by face_detector / species_detector so a
	dynamically-added column never gets dropped on save.
	"""
	if not rows:
		return list(CFG.CSV_HEADERS)
	seen: set = set()
	fields: List[str] = []
	for key in rows[0].keys():
		if key not in seen:
			fields.append(key)
			seen.add(key)
	for row in rows:
		for key in row.keys():
			if key not in seen:
				fields.append(key)
				seen.add(key)
	# Make sure any newly-added header is present even if no row carries it yet.
	for key in CFG.CSV_HEADERS:
		if key not in seen:
			fields.append(key)
			seen.add(key)
	return fields


def broadcast_dedup(trip_folder: str) -> int:
	"""Copy analysis columns from canonical rows to their duplicates.

	Returns the count of rows that received any value from their canonical.
	"""
	memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
	csv_path = os.path.join(memo_dir, "labels.csv")
	log_path = os.path.join(logs_dir, "dedup_broadcast.log") if CFG.LOG_TO_FILE else None

	init_log(log_path, "dedup_broadcast.py")

	if not os.path.exists(csv_path):
		log(f"ERROR: labels.csv not found at {csv_path}", log_path)
		return 0

	rows = read_csv_dict(csv_path)
	if not rows:
		log("No rows in labels.csv; nothing to do.", log_path)
		return 0

	# Build a lookup from image_name → row so duplicates can find their canonical.
	by_name: Dict[str, Dict[str, str]] = {
		r.get("image_name", ""): r for r in rows if r.get("image_name")
	}

	broadcast_columns = list(getattr(CFG, "ANALYSIS_COLUMNS", []))
	if not broadcast_columns:
		log("ANALYSIS_COLUMNS not configured; nothing to broadcast.", log_path)
		return 0

	rows_touched = 0
	for r in rows:
		dup_of = (r.get("duplicate_of") or "").strip()
		if not dup_of:
			continue
		canonical = by_name.get(dup_of)
		if canonical is None:
			log(
				f"WARN: {r.get('image_name')} marked duplicate_of={dup_of} "
				f"but no such canonical row exists; skipping.",
				log_path,
			)
			continue
		any_copied = False
		for col in broadcast_columns:
			canonical_value = canonical.get(col, "")
			row_value = r.get(col, "")
			# Don't overwrite a value already on the duplicate (in practice
			# duplicates start empty because analysis steps skip them, but
			# this guard prevents a stale value being clobbered if the user
			# manually edited the CSV).
			if canonical_value and not row_value:
				r[col] = canonical_value
				any_copied = True
		if any_copied:
			rows_touched += 1

	if rows_touched:
		write_csv_dict(csv_path, rows, _get_fieldnames(rows))
		log(
			f"Broadcast analysis from canonicals to {rows_touched} duplicate row(s). "
			f"Columns copied: {len(broadcast_columns)}.",
			log_path,
		)
	else:
		log("No duplicates needed broadcast (none in CSV, or all already filled).", log_path)

	return rows_touched


if __name__ == "__main__":
	import argparse

	p = argparse.ArgumentParser(
		description="Copy analysis columns from canonical rows to their md5-duplicate siblings."
	)
	p.add_argument("trip_folder", help="Trip folder (e.g. data/trips/SyntheticTrip)")
	args = p.parse_args()

	count = broadcast_dedup(args.trip_folder)
	print(f"Broadcast complete: {count} duplicate row(s) updated.")
