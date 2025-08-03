# utils_io.py
# Common IO helpers for MemoGraph scripts (CSV read/write, backups, paths).

import csv
import os
import shutil
from typing import List, Dict, Iterable, Tuple, Optional

from scripts.utils.utils_log import log

def ensure_dir(path: str) -> None:
	"""Create directory (recursively) if it doesn't exist."""
	os.makedirs(path, exist_ok=True)

def ensure_parent_dir(path: str) -> None:
	"""Create the parent directory for a file path if it doesn't exist."""
	parent = os.path.dirname(path)
	if parent:
		os.makedirs(parent, exist_ok=True)

def ensure_memograph_folder(trip_folder: str, subfolder_name: str = "MemoGraph") -> str:
	"""
	Ensure we have a dedicated MemoGraph folder inside the trip_folder.

	Returns
	-------
	str
		The absolute path to the MemoGraph folder.
	"""
	memo_dir = os.path.join(trip_folder, subfolder_name)
	ensure_dir(memo_dir)
	return memo_dir

def read_csv_dict(csv_path: str) -> List[Dict[str, str]]:
	"""Read a CSV file into a list of dict rows. Returns [] if file does not exist."""
	if not os.path.exists(csv_path):
		return []
	with open(csv_path, newline="", encoding="utf-8") as f:
		return list(csv.DictReader(f))

def write_csv_dict(csv_path: str, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
	"""Write dict rows to CSV with given fieldnames."""
	ensure_parent_dir(csv_path)
	with open(csv_path, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fieldnames)
		w.writeheader()
		w.writerows(rows)

def rotate_backups(backups: List[str], max_backups: int) -> None:
	"""
	Keep only the newest 'max_backups' files (they are assumed sorted newest->oldest outside).
	Extras are deleted.
	"""
	for extra in backups[max_backups:]:
		try:
			os.remove(extra)
		except OSError:
			pass

def backup_csv(csv_path: str, max_backups: int = 3, log_path: Optional[str] = None) -> Optional[str]:
	"""
	Create a timestamped backup of csv_path next to it.

	Returns
	-------
	Optional[str]
		The backup path created (or None if original didn't exist).
	"""
	if not os.path.exists(csv_path):
		log(f"[backup_csv] No CSV to backup at {csv_path}", log_path)
		return None

	base_dir = os.path.dirname(csv_path)
	base_name = os.path.basename(csv_path)
	name_no_ext, ext = os.path.splitext(base_name)

	# A small 'backups' folder under same directory
	backup_dir = os.path.join(base_dir, "backups")
	ensure_dir(backup_dir)

	from datetime import datetime
	ts = datetime.now().strftime("%Y%m%d_%H%M%S")
	backup_name = f"{name_no_ext}_{ts}{ext}"
	backup_path = os.path.join(backup_dir, backup_name)

	shutil.copy2(csv_path, backup_path)
	log(f"[backup_csv] Created backup: {backup_path}", log_path)

	# Rotate: keep only newest `max_backups`
	existing = sorted(
		(os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith(name_no_ext) and f.endswith(ext)),
		key=lambda p: os.path.getmtime(p),
		reverse=True
	)
	rotate_backups(existing, max_backups)
	return backup_path
