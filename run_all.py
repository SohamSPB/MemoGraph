#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all.py

Runs the entire MemoGraph image processing pipeline for a given trip folder.
Supports both sequential and parallel execution modes based on the
MEMOGRAPH_PARALLEL_EXECUTION environment variable.

Includes resource checking to prevent system overload.
"""

import os
import sys
import multiprocessing
import time
import psutil
import csv
import subprocess
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

import memograph_config as CFG
from scripts.utils.utils_log import get_logger
from scripts.utils.utils_io import backup_csv
from scripts.utils.utils_resources import check_resources

# pipeline steps
import scripts.image_scanner as image_scanner
import scripts.trip_day_assigner as trip_day_assigner
import scripts.location_resolver as location_resolver
import scripts.face_detector as face_detector
import scripts.image_labeler as image_labeler
import scripts.caption_filler as caption_filler
import scripts.species_detector as species_detector
import scripts.generate_ai_captions as generate_ai_captions
import scripts.image_type_detector as image_type_detector
import scripts.blog_generator as blog_generator
import scripts.map_visualizer as map_visualizer
# import scripts.uploader_gcs  # optional

def get_gpu_memory_usage():
    """Returns the GPU memory usage in MB."""
    try:
        result = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits']
        )
        return float(result.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0.0

def get_resource_usage(p):
    """Gets the resource usage of a process and its children."""
    cpu_percent = p.cpu_percent(interval=None)
    ram_mb = p.memory_info().rss / (1024 * 1024)
    
    children = p.children(recursive=True)
    for child in children:
        try:
            cpu_percent += child.cpu_percent(interval=None)
            ram_mb += child.memory_info().rss / (1024 * 1024)
        except psutil.NoSuchProcess:
            continue

    gpu_mb = get_gpu_memory_usage()
    return cpu_percent, ram_mb, gpu_mb

def run_pipeline(trip_folder: str, parallel: bool):
	if parallel:
		multiprocessing.set_start_method('spawn', force=True)

	if not os.path.isdir(trip_folder):
		print(f"✗ Trip folder does not exist: {trip_folder}")
		return

	# Prepare MemoGraph + logs folder
	memo_dir, logs_dir = CFG.ensure_memograph_folder(trip_folder)
	log_path = os.path.join(logs_dir, "run_all.log")
	logger = get_logger("run_all", log_path)
	logger.info("--- MemoGraph pipeline start ---")
	logger.info(f"Execution mode: {'PARALLEL' if parallel else 'SEQUENTIAL'}")

	# All artifacts live inside MemoGraph
	csv_path = os.path.join(memo_dir, "labels.csv")
	blog_path = os.path.join(memo_dir, "blog.md")
	summary_path = os.path.join(memo_dir, "trip_summary.json")
	map_path = os.path.join(memo_dir, "trip_map.html")

	resource_data = []
	main_process = psutil.Process(os.getpid())
	main_process.cpu_percent(interval=None) # first call returns 0, so we call it once before the loop

	try:
		# --- PRE-FLIGHT CHECKS ---
		if parallel:
			if not check_resources(min_ram_mb=CFG.MIN_AVAILABLE_RAM_MB, min_gpu_mb=CFG.MIN_AVAILABLE_GPU_MEM_MB):
				logger.error("System does not meet minimum resource requirements for parallel execution. Aborting.")
				sys.exit(1)
			logger.info("Resource check passed.")

		# --- SEQUENTIAL PRE-PROCESSING ---
		start_time = time.time()
		logger.info("--- STEP 1: Scanning Images ---")
		image_scanner.scan_images(trip_folder)
		logger.info(f"STEP 1 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 1", *get_resource_usage(main_process)))

		start_time = time.time()
		logger.info("--- STEP 2: Assigning Day Numbers ---")
		trip_day_assigner.assign_days(trip_folder)
		logger.info(f"STEP 2 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 2", *get_resource_usage(main_process)))

		start_time = time.time()
		logger.info("--- STEP 3: Resolving Locations ---")
		location_resolver.fill_location(trip_folder)
		logger.info(f"STEP 3 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 3", *get_resource_usage(main_process)))

		# --- EARLY MAP PREVIEW ---
		# Generate an initial map as soon as GPS/locations are available so
		# users can start exploring the trip while heavier steps are running.
		start_time = time.time()
		logger.info("--- STEP 4: Creating Initial Map Preview ---")
		points_preview = map_visualizer.load_geo_points(csv_path, trip_folder)
		map_visualizer.create_map(points_preview, map_path)
		logger.info(f"STEP 4 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 4 (map_preview)", *get_resource_usage(main_process)))

		# --- CORE PROCESSING (PARALLEL OR SEQUENTIAL) ---
		analysis_steps = {
			"Faces": face_detector.process_faces,
			"Labels": image_labeler.label_images,
			"Captions": caption_filler.fill_captions,
			"AI Captions": generate_ai_captions.generate_ai_captions,
		}

		# Top-level "parallel" mode now means: allow internal parallelism inside
		# each step (threads/processes within scripts), but run the high-level
		# steps sequentially to avoid race conditions on labels.csv.
		logger.info("--- Starting analysis steps (%s top-level) ---", "PARALLEL" if parallel else "SEQUENTIAL")

		# Always back up the CSV once before core analysis steps.
		backup_csv(csv_path, max_backups=CFG.MAX_BACKUPS, log_path=log_path)

		all_steps = {
			**analysis_steps,
			"Species": species_detector.process_species,
			"Image Type": image_type_detector.detect_image_types,
		}
		for name, func in all_steps.items():
			start_time_step = time.time()
			logger.info(f"--- Running Step: {name} ---")
			if name == "Species":
				func(csv_path, trip_folder, log_path)
			else:
				func(trip_folder)
			elapsed = time.time() - start_time_step
			logger.info(f"Step '{name}' finished in {elapsed:.2f} seconds.")
			resource_data.append((name, *get_resource_usage(main_process)))

		# --- SEQUENTIAL POST-PROCESSING ---
		start_time = time.time()
		logger.info("--- STEP 9: Generating Blog ---")
		blog_generator.generate_blog(trip_folder)
		logger.info(f"STEP 9 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 9", *get_resource_usage(main_process)))

		start_time = time.time()
		logger.info("--- STEP 10: Creating Final Map ---")
		points = map_visualizer.load_geo_points(csv_path, trip_folder)
		map_visualizer.create_map(points, map_path)
		logger.info(f"STEP 10 finished in {time.time() - start_time:.2f} seconds.")
		resource_data.append(("STEP 10 (map_final)", *get_resource_usage(main_process)))

		logger.info("[OK] All steps completed for: %s", trip_folder)
		logger.info("Artifacts:")
		logger.info("  CSV:     %s", csv_path)
		logger.info("  Blog MD: %s", blog_path)
		logger.info("  Summary: %s", summary_path)
		logger.info("  Map:     %s", map_path)

	except Exception as e:
		logger.exception("[ERROR] Pipeline failed: %s", e)
		raise
	finally:
		logger.info(f"Resource data: {resource_data}")
		monitor_log_path = os.path.join(logs_dir, "resource_usage.csv")
		logger.info(f"Saving resource usage data to {monitor_log_path}")
		try:
			with open(monitor_log_path, "w", newline="") as f:
				writer = csv.writer(f)
				writer.writerow(["step", "cpu_percent", "ram_mb", "gpu_mb"])
				writer.writerows(resource_data)
			logger.info(f"Resource usage data saved to {monitor_log_path}")
		except Exception as e:
			logger.error(f"Failed to save resource usage data: {e}")

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python run_all.py <trip_folder_path> [--reset | --reset-only]")
		sys.exit(1)
	
	parallel_mode = os.environ.get('MEMOGRAPH_PARALLEL_EXECUTION', 'false').lower() == 'true'

	trip_folder_path = sys.argv[1]
	args = sys.argv[2:]
	reset_requested = "--reset" in args
	reset_only = "--reset-only" in args

	if reset_requested or reset_only:
		# Remove the MemoGraph folder for this trip so the pipeline
		# can regenerate labels.csv and all artifacts from scratch.
		memo_dir = os.path.join(trip_folder_path, CFG.MEMOGRAPH_FOLDER_NAME)
		if os.path.isdir(memo_dir):
			print(f"Reset requested: removing existing MemoGraph folder at {memo_dir}")
			shutil.rmtree(memo_dir)
		else:
			print(f"No MemoGraph folder to reset at {memo_dir}")

	if reset_only:
		# Only clean existing data; do not start the pipeline.
		sys.exit(0)

	run_pipeline(trip_folder_path, parallel_mode)
