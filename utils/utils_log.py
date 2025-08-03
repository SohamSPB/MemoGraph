# utils_log.py
# Lightweight file+console logger for MemoGraph scripts.

from datetime import datetime
import os

def _ts() -> str:
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_log(log_path: str, title: str | None = None) -> None:
	"""
	Create/append a header to the log file.

	Parameters
	----------
	log_path : str
		Path to the log file to open/append.
	title : str | None
		Optional title that will be written at the top (timestamped).
	"""
	os.makedirs(os.path.dirname(log_path), exist_ok=True)
	with open(log_path, "a", encoding="utf-8") as f:
		f.write("\n" + "=" * 80 + "\n")
		f.write(f"[{_ts()}] LOG START")
		if title:
			f.write(f" - {title}")
		f.write("\n" + "=" * 80 + "\n")

def log(msg: str, log_path: str | None = None, also_print: bool = True) -> None:
	"""
	Log a message to console and/or file.

	Parameters
	----------
	msg : str
		Message to log.
	log_path : str | None
		If provided, the message is appended to this file.
	also_print : bool
		If True, the message is printed to stdout as well.
	"""
	line = f"[{_ts()}] {msg}"
	if also_print:
		print(line)
	if log_path:
		os.makedirs(os.path.dirname(log_path), exist_ok=True)
		with open(log_path, "a", encoding="utf-8") as f:
			f.write(line + "\n")

import logging
import os

def get_logger(name, logfile=None, level=logging.INFO):
	"""Returns a logger that prints to both console and (optional) log file."""
	logger = logging.getLogger(name)
	logger.setLevel(level)

	if not logger.handlers:
		formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

		console = logging.StreamHandler()
		console.setFormatter(formatter)
		logger.addHandler(console)

		if logfile:
			os.makedirs(os.path.dirname(logfile), exist_ok=True)
			file_handler = logging.FileHandler(logfile)
			file_handler.setFormatter(formatter)
			logger.addHandler(file_handler)

	return logger
