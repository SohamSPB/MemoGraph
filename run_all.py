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
import signal
import multiprocessing
import time
import psutil
import csv
import subprocess
import shutil
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Graceful interrupt handling
# ---------------------------------------------------------------------------
# First Ctrl+C  → set flag, let current step finish, flush CSV, show summary
# Second Ctrl+C → force-kill all child processes and exit immediately
_interrupted = False
_ctrl_c_count = 0

def _interrupt_handler(signum, frame):
	"""Handle Ctrl+C: first press = graceful stop, second = force exit."""
	global _interrupted, _ctrl_c_count
	_ctrl_c_count += 1
	_interrupted = True

	if _ctrl_c_count == 1:
		print("\n\n  [Ctrl+C] Graceful shutdown requested. Finishing current image and saving progress...")
		print("  Press Ctrl+C again to force-quit immediately.\n")
	else:
		print("\n  [Ctrl+C] Force shutdown! Killing all child processes...")
		# Kill all child processes
		try:
			parent = psutil.Process(os.getpid())
			for child in parent.children(recursive=True):
				try:
					child.kill()
				except psutil.NoSuchProcess:
					pass
		except Exception:
			pass
		os._exit(1)

def is_interrupted():
	"""Check if pipeline was interrupted by Ctrl+C."""
	return _interrupted

_STEP_COUNTER = 0

def _step_banner(name, category=""):
	"""Print a visible banner to separate pipeline steps in terminal output."""
	global _STEP_COUNTER
	_STEP_COUNTER += 1
	cat_label = f"  [{category}]" if category else ""
	line = f"  Step {_STEP_COUNTER}: {name}{cat_label}"
	width = max(60, len(line) + 4)
	bar = "=" * width
	print(f"\n{bar}")
	print(line)
	print(f"{bar}\n")

def _step_done(name, elapsed):
	"""Print a compact completion line after a step finishes."""
	print(f"  >> {name} done in {elapsed:.1f}s\n")

def _kill_child_processes():
	"""Kill all child processes of the current process."""
	try:
		parent = psutil.Process(os.getpid())
		children = parent.children(recursive=True)
		for child in children:
			try:
				child.kill()
			except psutil.NoSuchProcess:
				pass
		# Wait briefly for processes to actually terminate
		psutil.wait_procs(children, timeout=3)
	except Exception:
		pass

import memograph_config as CFG
from scripts.utils.utils_log import get_logger
from scripts.utils.utils_io import backup_csv
from scripts.utils.utils_resources import check_resources
from scripts.pipeline_preflight import (
    display_preflight, confirm_proceed, display_postflight,
    count_images, get_resume_progress, estimate_time,
)

# pipeline steps
import scripts.image_scanner as image_scanner
import scripts.trip_day_assigner as trip_day_assigner
import scripts.location_resolver as location_resolver
import scripts.face_detector as face_detector
import scripts.face_recognizer as face_recognizer
import scripts.image_labeler as image_labeler
import scripts.caption_filler as caption_filler
import scripts.species_detector as species_detector
import scripts.generate_ai_captions as generate_ai_captions
import scripts.image_type_detector as image_type_detector
import scripts.image_quality as image_quality
import scripts.image_colors as image_colors
import scripts.blog_generator as blog_generator
import scripts.map_visualizer as map_visualizer
import scripts.build_blog_context as build_blog_context
import scripts.build_webapp as build_webapp
import scripts.build_trip_index as build_trip_index
import scripts.batch_vision_llm as batch_vision_llm
import scripts.similar_image_grouper as similar_image_grouper
import scripts.bird_species_refiner as bird_species_refiner
import scripts.build_search_index as build_search_index
import scripts.dedup_broadcast as dedup_broadcast

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
    """Sample CPU/RAM/GPU usage of the parent process and its descendants.

    psutil's cpu_percent(interval=None) returns 0.0 on the FIRST call to any
    given process object because it has no prior sample to compute a delta
    against. ProcessPoolExecutor worker children are short-lived, so they
    almost always hit this 0.0 case — the old implementation silently
    undercounted child CPU usage, making resource_usage.csv unreliable.

    Fix: prime each process with a no-op call (returns 0 but registers a
    baseline timestamp inside psutil), wait briefly while the work continues,
    then re-sample to get a real percentage. One short sleep covers all
    processes, so the per-call overhead is constant rather than O(N children).
    """
    ram_mb = p.memory_info().rss / (1024 * 1024)
    children = p.children(recursive=True)

    # Prime psutil so the second call returns a meaningful delta.
    p.cpu_percent(interval=None)
    primed: list = []
    for child in children:
        try:
            child.cpu_percent(interval=None)
            primed.append(child)
        except psutil.NoSuchProcess:
            continue

    time.sleep(0.2)

    cpu_percent = p.cpu_percent(interval=None)
    for child in primed:
        try:
            cpu_percent += child.cpu_percent(interval=None)
            ram_mb += child.memory_info().rss / (1024 * 1024)
        except psutil.NoSuchProcess:
            continue

    gpu_mb = get_gpu_memory_usage()
    return cpu_percent, ram_mb, gpu_mb

def run_pipeline(trip_folder: str, parallel: bool, auto_yes: bool = False,
                  is_reset: bool = False):
	global _interrupted, _ctrl_c_count, _STEP_COUNTER
	_interrupted = False
	_ctrl_c_count = 0
	_STEP_COUNTER = 0

	# Install graceful interrupt handler
	signal.signal(signal.SIGINT, _interrupt_handler)

	# Always use 'spawn' for multiprocessing, even in sequential top-level mode.
	# face_detector and gpu_model_manager can spawn child processes internally
	# (when FACE_DETECTION_PARALLEL_WORKERS > 1, batch GPU work, etc.), and on
	# Linux the default 'fork' start method is unsafe with CUDA — the GPU
	# context can't be inherited across fork(). force=True is safe to call
	# repeatedly within the same process.
	multiprocessing.set_start_method('spawn', force=True)

	if not os.path.isdir(trip_folder):
		print(f"Trip folder does not exist: {trip_folder}")
		return

	# --- PRE-FLIGHT SCREEN ---
	display_preflight(trip_folder, is_reset, parallel)
	if not confirm_proceed(auto_yes):
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
	step_results = []
	main_process = psutil.Process(os.getpid())
	main_process.cpu_percent(interval=None) # first call returns 0, so we call it once before the loop

	# Compute estimated time for post-flight comparison
	image_count, _ = count_images(trip_folder)
	progress = {} if is_reset else get_resume_progress(csv_path)
	estimated_time = estimate_time(image_count, progress, is_reset)
	pipeline_start_time = time.time()
	interrupted_at = None

	def _record_step(name, status, elapsed, items_processed=None, items_skipped=0):
		step_results.append({
			"name": name, "status": status, "time": elapsed,
			"items_processed": items_processed, "items_skipped": items_skipped,
		})

	try:
		# --- PRE-FLIGHT CHECKS ---
		if parallel:
			if not check_resources(min_ram_mb=CFG.MIN_AVAILABLE_RAM_MB, min_gpu_mb=CFG.MIN_AVAILABLE_GPU_MEM_MB):
				logger.error("System does not meet minimum resource requirements for parallel execution. Aborting.")
				sys.exit(1)
			logger.info("Resource check passed.")

		# --- SEQUENTIAL PRE-PROCESSING ---
		_step_banner("Scanning Images", "EXIF")
		start_time = time.time()
		logger.info("--- STEP 1: Scanning Images ---")
		image_scanner.scan_images(trip_folder)
		elapsed = time.time() - start_time
		logger.info(f"STEP 1 finished in {elapsed:.2f} seconds.")
		_step_done("Scan Images", elapsed)
		resource_data.append(("STEP 1", *get_resource_usage(main_process)))
		_record_step("Scan Images", "completed", elapsed)

		_step_banner("Assigning Day Numbers", "CPU")
		start_time = time.time()
		logger.info("--- STEP 2: Assigning Day Numbers ---")
		trip_day_assigner.assign_days(trip_folder)
		elapsed = time.time() - start_time
		logger.info(f"STEP 2 finished in {elapsed:.2f} seconds.")
		_step_done("Assign Days", elapsed)
		resource_data.append(("STEP 2", *get_resource_usage(main_process)))
		_record_step("Assign Days", "completed", elapsed)

		_step_banner("Resolving Locations", "GPS")
		start_time = time.time()
		logger.info("--- STEP 3: Resolving Locations ---")
		location_resolver.fill_location(trip_folder)
		elapsed = time.time() - start_time
		logger.info(f"STEP 3 finished in {elapsed:.2f} seconds.")
		_step_done("Resolve Locations", elapsed)
		resource_data.append(("STEP 3", *get_resource_usage(main_process)))
		_record_step("Resolve Locations", "completed", elapsed)

		_step_banner("Map Preview", "HTML")
		start_time = time.time()
		logger.info("--- STEP 4: Creating Initial Map Preview ---")
		points_preview = map_visualizer.load_geo_points(csv_path, trip_folder)
		map_visualizer.create_map(points_preview, map_path)
		elapsed = time.time() - start_time
		logger.info(f"STEP 4 finished in {elapsed:.2f} seconds.")
		_step_done("Map Preview", elapsed)
		resource_data.append(("STEP 4 (map_preview)", *get_resource_usage(main_process)))
		_record_step("Map Preview", "completed", elapsed)

		# --- CORE PROCESSING (PARALLEL OR SEQUENTIAL) ---
		analysis_steps = {
			"Faces": face_detector.process_faces,
		}

		# Optionally recognise known people in images that contain faces,
		# using a gallery built from models/faces/known/* (see build_face_gallery.py).
		if getattr(CFG, "ENABLE_FACE_RECOGNITION", False):
			analysis_steps["Face Recognition"] = face_recognizer.recognise_faces

		analysis_steps.update(
			{
				"Labels": image_labeler.label_images,
				"Captions": caption_filler.fill_captions,
				"AI Captions": generate_ai_captions.generate_ai_captions,
			}
		)

		# Top-level "parallel" mode now means: allow internal parallelism inside
		# each step (threads/processes within scripts), but run the high-level
		# steps sequentially to avoid race conditions on labels.csv.
		logger.info("--- Starting analysis steps (%s top-level) ---", "PARALLEL" if parallel else "SEQUENTIAL")

		# Always back up the CSV once before core analysis steps.
		backup_csv(csv_path, max_backups=CFG.MAX_BACKUPS, log_path=log_path)

		# GPU-bound steps (must run sequentially due to GPU memory constraints)
		gpu_steps = {
			**analysis_steps,
			"Species": species_detector.process_species,
			"Image Type": image_type_detector.detect_image_types,
		}

		# Vision LLM step (if enabled)
		if getattr(CFG, "ENABLE_VISION_LLM", False):
			gpu_steps["Vision LLM"] = batch_vision_llm.process_trip

		# Run GPU tasks sequentially (main thread)
		for name, func in gpu_steps.items():
			if _interrupted:
				logger.warning("Pipeline interrupted before step: %s", name)
				raise KeyboardInterrupt
			_step_banner(name, "GPU")
			start_time_step = time.time()
			logger.info(f"--- Running GPU Step: {name} ---")
			try:
				if name == "Species":
					func(csv_path, trip_folder, log_path)
				else:
					func(trip_folder)
				elapsed = time.time() - start_time_step
				logger.info(f"GPU Step '{name}' finished in {elapsed:.2f} seconds.")
				_step_done(name, elapsed)
				resource_data.append((name, *get_resource_usage(main_process)))
				_record_step(name, "completed", elapsed)
			except KeyboardInterrupt:
				elapsed = time.time() - start_time_step
				logger.warning(f"GPU Step '{name}' interrupted after {elapsed:.2f}s.")
				_record_step(name, "interrupted", elapsed)
				raise
			except Exception as e:
				elapsed = time.time() - start_time_step
				logger.error(f"GPU Step '{name}' failed: {e}")
				_record_step(name, "failed", elapsed)
				raise

		# CPU-only steps run AFTER GPU steps and SEQUENTIALLY to avoid
		# CSV race conditions (both read/write labels.csv).
		cpu_steps = {
			"Image Quality": image_quality.evaluate_image_quality,
			"Image Colors": image_colors.process_colors,
		}

		for name, func in cpu_steps.items():
			if _interrupted:
				raise KeyboardInterrupt
			_step_banner(name, "CPU")
			start_time_step = time.time()
			logger.info(f"--- Running CPU Step: {name} ---")
			try:
				func(trip_folder)
				elapsed = time.time() - start_time_step
				logger.info(f"CPU Step '{name}' finished in {elapsed:.2f} seconds.")
				_step_done(name, elapsed)
				resource_data.append((name, *get_resource_usage(main_process)))
				_record_step(name, "completed", elapsed)
			except KeyboardInterrupt:
				elapsed = time.time() - start_time_step
				_record_step(name, "interrupted", elapsed)
				raise
			except Exception as e:
				elapsed = time.time() - start_time_step
				logger.error(f"CPU Step '{name}' failed: {e}")
				_record_step(name, "failed", elapsed)

		# --- LABEL REFINEMENT STEPS ---
		# These steps improve detection accuracy by grouping similar images
		# and using specialized prompts for specific subjects like birds.

		if _interrupted:
			raise KeyboardInterrupt
		_step_banner("Grouping Similar Images", "GPU")
		start_time = time.time()
		logger.info("--- STEP 7a: Grouping Similar Images ---")
		try:
			similar_image_grouper.process_similar_images(trip_folder)
			elapsed = time.time() - start_time
			logger.info(f"STEP 7a finished in {elapsed:.2f} seconds.")
			_step_done("Similar Grouping", elapsed)
			resource_data.append(("Similar Image Grouper", *get_resource_usage(main_process)))
			_record_step("Similar Grouping", "completed", elapsed)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error(f"Similar image grouping failed: {e}")
			_record_step("Similar Grouping", "failed", elapsed)

		if _interrupted:
			raise KeyboardInterrupt
		_step_banner("Refining Bird Species", "GPU")
		start_time = time.time()
		logger.info("--- STEP 7b: Refining Bird Species ---")
		try:
			bird_species_refiner.refine_bird_species(trip_folder)
			elapsed = time.time() - start_time
			logger.info(f"STEP 7b finished in {elapsed:.2f} seconds.")
			_step_done("Bird Refiner", elapsed)
			resource_data.append(("Bird Species Refiner", *get_resource_usage(main_process)))
			_record_step("Bird Refiner", "completed", elapsed)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error(f"Bird species refinement failed: {e}")
			_record_step("Bird Refiner", "failed", elapsed)

		# --- DEDUP BROADCAST ---
		# Copy analysis columns from canonical rows (one per md5 group) to
		# their md5-identical duplicates. Must run after every analysis step
		# is done and before blog/map/webapp build, since those consume the
		# analysis columns and would otherwise render duplicates as blank.
		if _interrupted:
			raise KeyboardInterrupt
		_step_banner("Dedup Broadcast", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 8: Broadcasting analysis to duplicate rows ---")
		try:
			dup_count = dedup_broadcast.broadcast_dedup(trip_folder)
			elapsed = time.time() - start_time
			logger.info(f"STEP 8 finished in {elapsed:.2f} seconds. Duplicates filled: {dup_count}")
			_step_done("Dedup Broadcast", elapsed)
			resource_data.append(("STEP 8 (dedup_broadcast)", *get_resource_usage(main_process)))
			_record_step("Dedup Broadcast", "completed", elapsed, items_processed=dup_count)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error(f"Dedup broadcast failed: {e}")
			_record_step("Dedup Broadcast", "failed", elapsed)

		# --- SEQUENTIAL POST-PROCESSING ---
		if _interrupted:
			raise KeyboardInterrupt
		_step_banner("Generating Blog", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 9: Generating Blog ---")
		blog_generator.generate_blog(trip_folder)
		elapsed = time.time() - start_time
		logger.info(f"STEP 9 finished in {elapsed:.2f} seconds.")
		_step_done("Generate Blog", elapsed)
		resource_data.append(("STEP 9", *get_resource_usage(main_process)))
		_record_step("Generate Blog", "completed", elapsed)

		_step_banner("Final Map + Overview", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 10: Creating Final Map ---")
		points = map_visualizer.load_geo_points(csv_path, trip_folder)
		map_visualizer.create_map(points, map_path)
		elapsed = time.time() - start_time
		logger.info(f"STEP 10 finished in {elapsed:.2f} seconds.")
		_step_done("Final Map", elapsed)
		resource_data.append(("STEP 10 (map_final)", *get_resource_usage(main_process)))
		_record_step("Final Map", "completed", elapsed)

		# Generate an overview page that embeds the final map and shows any
		# photos that still lack GPS coordinates in a sidebar, so the user
		# can see all trip photos on a single page.
		try:
			map_visualizer.create_overview_page(trip_folder)
		except Exception as e:
			logger.error("Failed to create overview page: %s", e)

		_step_banner("Blog Context", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 11: Building Blog Context ---")
		build_blog_context.build_blog_context(
			trip_folder,
			include_extras=getattr(CFG, "BLOG_CONTEXT_INCLUDE_EXTRAS", False),
		)
		elapsed = time.time() - start_time
		logger.info(f"STEP 11 finished in {elapsed:.2f} seconds.")
		_step_done("Blog Context", elapsed)
		resource_data.append(("STEP 11 (blog_context)", *get_resource_usage(main_process)))
		_record_step("Blog Context", "completed", elapsed)

		_step_banner("Building Web App", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 12: Building Web App ---")
		try:
			build_webapp.build_webapp(trip_folder)
			elapsed = time.time() - start_time
			logger.info(f"STEP 12 finished in {elapsed:.2f} seconds.")
			_step_done("Build Webapp", elapsed)
			resource_data.append(("STEP 12 (webapp)", *get_resource_usage(main_process)))
			_record_step("Build Webapp", "completed", elapsed)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error("Failed to build web app: %s", e)
			_record_step("Build Webapp", "failed", elapsed)

		_step_banner("Updating Trip Index", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 13: Updating Trip Index ---")
		try:
			index_path = build_trip_index.build_trip_index(CFG.DATA_ROOT)
			elapsed = time.time() - start_time
			logger.info(f"STEP 13 finished in {elapsed:.2f} seconds.")
			_step_done("Trip Index", elapsed)
			logger.info("Trip index updated at: %s", index_path)
			resource_data.append(("STEP 13 (trip_index)", *get_resource_usage(main_process)))
			_record_step("Trip Index", "completed", elapsed)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error("Failed to update trip index: %s", e)
			_record_step("Trip Index", "failed", elapsed)

		_step_banner("Global Search Index", "OUTPUT")
		start_time = time.time()
		logger.info("--- STEP 14: Building Global Search Index ---")
		try:
			search_index_path = build_search_index.build_search_index(CFG.DATA_ROOT)
			elapsed = time.time() - start_time
			logger.info(f"STEP 14 finished in {elapsed:.2f} seconds.")
			_step_done("Search Index", elapsed)
			logger.info("Search index updated at: %s", search_index_path)
			resource_data.append(("STEP 14 (search_index)", *get_resource_usage(main_process)))
			_record_step("Search Index", "completed", elapsed)
		except Exception as e:
			elapsed = time.time() - start_time
			logger.error("Failed to build search index: %s", e)
			_record_step("Search Index", "failed", elapsed)

		logger.info("[OK] All steps completed for: %s", trip_folder)
		logger.info("Artifacts:")
		logger.info("  CSV:     %s", csv_path)
		logger.info("  Blog MD: %s", blog_path)
		logger.info("  Summary: %s", summary_path)
		logger.info("  Map:     %s", map_path)
		logger.info("  Context: %s", os.path.join(memo_dir, "blog_context.json"))
		logger.info("  Webapp:  %s", os.path.join(memo_dir, "webapp", "index.html"))
		logger.info("  Trips Hub: %s", os.path.join(CFG.DATA_ROOT, "index.html"))
		logger.info("  Search Index: %s", os.path.join(CFG.DATA_ROOT, "search_index.json"))

	except KeyboardInterrupt:
		# Determine which step was interrupted
		if step_results:
			last = step_results[-1]["name"]
			interrupted_at = f"after {last}"
		else:
			interrupted_at = "before first step"
		logger.warning("Pipeline interrupted by user at: %s", interrupted_at)

		# Kill any lingering child processes (e.g. face_recognition's
		# internal multiprocessing workers) so they don't keep printing
		# output after the pipeline has stopped.
		_kill_child_processes()
	except Exception as e:
		logger.exception("[ERROR] Pipeline failed: %s", e)
		raise
	finally:
		# --- POST-FLIGHT SUMMARY ---
		display_postflight(trip_folder, step_results, interrupted_at,
		                   pipeline_start_time, estimated_time)

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
		print("Usage: python run_all.py <trip_folder_path> [--reset | --reset-only] [-y | --yes]")
		sys.exit(1)

	parallel_mode = os.environ.get('MEMOGRAPH_PARALLEL_EXECUTION', 'false').lower() == 'true'

	trip_folder_path = sys.argv[1]
	args = sys.argv[2:]
	reset_requested = "--reset" in args
	reset_only = "--reset-only" in args
	auto_yes = "--yes" in args or "-y" in args

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

	run_pipeline(trip_folder_path, parallel_mode, auto_yes=auto_yes,
	             is_reset=reset_requested)
