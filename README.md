# MemoGraph 📸

MemoGraph is an AI-driven photo management pipeline designed to automatically organize, analyze, and enrich your photo collections, turning them into structured and searchable memories.

It processes a folder of images, extracts metadata, generates descriptive captions, detects faces and species, resolves locations, and creates insightful reports like a daily blog summary and an interactive map.

## Features

- **EXIF Extraction:** Scans images and extracts metadata like date, time, and GPS coordinates.
- **Automated Tagging:** Uses AI to generate tags for objects, scenes, and even specific species.
- **AI Captioning:** Generates human-like captions for your photos.
- **Face Detection:** Identifies photos that contain people.
- **Location Resolution:** Converts GPS data into human-readable addresses.
- **Trip Organization:** Automatically groups photos by day.
- **Report Generation:** Creates a Markdown blog and a JSON summary of your trip.
- **Interactive Map:** Generates an HTML map plotting your geotagged photos.

## Installation

Follow these steps to set up your local environment.

### 1. Prerequisites

- **Python 3.12.3** (exact version used during development)
- **CMake:** Required for one of the Python dependencies (`dlib`).

  **Linux:**
  ```bash
  sudo apt-get update
  sudo apt-get install cmake
  ```

  **Windows:**

  You can install CMake on Windows using a package manager like Chocolatey or by downloading the installer from the official website.

  *   **Using Chocolatey:**
      ```bash
      choco install cmake
      ```
  *   **Manual Installation:**
      1.  Download the latest installer from the [CMake website](https://cmake.org/download/).
      2.  Run the installer and make sure to select the option "Add CMake to the system PATH for all users" or "Add CMake to the system PATH for the current user".

### 2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment to manage dependencies.

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Install Dependencies
 
 Install all the required packages from `requirements.txt`.
 
 ```bash
 pip install -r requirements.txt
 ```
 
 **Note:** The exact versions of the packages used during development are listed in `requirements.txt` to ensure compatibility.
 
+### dlib GPU Support (Postponed)
+
+Attempts to enable dlib GPU support encountered runtime issues. For now, dlib will run on CPU. GPU support will be addressed in future development.
+
 ## Usage
 
 The main pipeline is executed through the `run_all.py` script.
1.  **Place your photos** in a directory (e.g., `data/trips/my_awesome_trip`).
2.  **Run the pipeline (sequential mode by default):**

    ```bash
    python run_all.py data/trips/my_awesome_trip
    ```

3.  **Optional: enable internal parallelism** for heavy steps by setting an environment variable:

    ```bash
    # Linux/macOS
    export MEMOGRAPH_PARALLEL_EXECUTION=true
    python run_all.py data/trips/my_awesome_trip

    # Windows (PowerShell)
    $env:MEMOGRAPH_PARALLEL_EXECUTION = "true"
    python run_all.py data/trips/my_awesome_trip
    ```

    At the top level, steps like Faces → Labels → Captions → AI Captions → Species still run one after another to avoid race conditions on `labels.csv`, but each step is free to use threads / processes internally.

4.  **Reset and rerun a trip (clean MemoGraph):**

    ```bash
    # Remove <trip>/MemoGraph and then run the full pipeline
    python run_all.py data/trips/my_awesome_trip --reset
    ```

    To only clean the existing MemoGraph without starting the pipeline, use:

    ```bash
    python run_all.py data/trips/my_awesome_trip --reset-only
    ```

5.  **Check the output:** All generated files (CSV, logs, blog, map) will be placed in a `MemoGraph` folder inside your trip directory.
6.  **Web app & context (auto):** `run_all.py` now also writes `blog_context.json` and a static gallery at `MemoGraph/webapp/index.html`, generating JPEG thumbnails in `MemoGraph/thumbnails` so the UI loads quickly even on large trips.

## Pipeline Overview

MemoGraph's `run_all.py` runs the following steps sequentially (each step calls
the script named in parentheses):

1. Scan + EXIF ingest (`image_scanner.py`)
2. Day assignment (`trip_day_assigner.py`)
3. GPS resolution + early map preview (`location_resolver.py`)
4. Faces (`face_detector.py`, optional face recognition via `face_recognizer.py`)
5. Image labels (CLIP) (`image_labeler.py`)
6. BLIP captions (`caption_filler.py`)
7. BLIP AI captions (`generate_ai_captions.py`)
8. Species tags (CLIP + optional bird model) (`species_detector.py`)
9. Image type classification (CLIP prompts) (`image_type_detector.py`)
10. Image quality scoring (histogram/exposure/sharpness/noise heuristics) (`image_quality.py`)
11. Color palette extraction (`image_colors.py`)
12. Blog + summary (`blog_generator.py`)
13. Final map + overview page (`map_visualizer.py`)
14. `blog_context.json` builder (`build_blog_context.py`)
15. Static Leaflet gallery/map web app + thumbnails (`build_webapp.py`)

Every run writes a complete `MemoGraph` folder containing `labels.csv`, `blog.md`,
`trip_summary.json`, `trip_map.html`, `trip_overview.html`, `blog_context.json`,
`webapp/index.html`, per-step logs, and JPEG thumbnails under `MemoGraph/thumbnails`.

### Execution Order & Resource Type

| Step | Script | GPU | CPU | Network | Parallelizable |
|------|--------|:---:|:---:|:-------:|:--------------:|
| 1 | `image_scanner.py` | ❌ | ✅ | ❌ | No |
| 2 | `trip_day_assigner.py` | ❌ | ✅ | ❌ | No |
| 3 | `location_resolver.py` | ❌ | ✅ | ✅ | No (rate-limited) |
| 4 | `map_visualizer.py` (preview) | ❌ | ✅ | ❌ | No |
| 5 | `face_detector.py` | ✅ preferred | ✅ fallback | ❌ | **Yes** (ProcessPool) |
| 6 | `image_labeler.py` (CLIP) | ✅ required | ❌ | ❌ | No |
| 7 | `caption_filler.py` (BLIP) | ✅ required | ❌ | ❌ | **Yes** (ThreadPool) |
| 8 | `generate_ai_captions.py` (BLIP) | ✅ required | ❌ | ❌ | No |
| 9 | `species_detector.py` (CLIP) | ✅ required | ❌ | ❌ | No |
| 10 | `image_type_detector.py` (CLIP) | ✅ required | ❌ | ❌ | No |
| 11 | `image_quality.py` | ❌ | ✅ | ❌ | No |
| 12 | `image_colors.py` | ❌ | ✅ | ❌ | No |
| 13 | `blog_generator.py` | ❌ | ✅ | ❌ | No |
| 14 | `map_visualizer.py` (final) | ❌ | ✅ | ❌ | No |
| 15 | `build_blog_context.py` | ❌* | ✅ | ❌ | No |
| 16 | `build_webapp.py` | ❌ | ✅ | ❌ | No |

*Optional GPU if YOLO/Places365 extras enabled via `--include-extras`

### Image Sizes Used

| Script | Config Variable | Default | Purpose |
|--------|----------------|---------|---------|
| `face_detector.py` | `MAX_IMAGE_SIZE` | 512px | Face detection (CNN/HOG) |
| `image_labeler.py` | `MAX_IMAGE_SIZE` | 512px | CLIP object/scene detection |
| `caption_filler.py` | `MAX_IMAGE_SIZE` | 512px | BLIP captioning |
| `generate_ai_captions.py` | `MAX_IMAGE_SIZE` | 512px | BLIP AI captions |
| `species_detector.py` | `MAX_IMAGE_SIZE` | 512px | CLIP species detection |
| `image_type_detector.py` | `MAX_IMAGE_SIZE` | 512px | CLIP image classification |
| `image_quality.py` | `QUALITY_MAX_SIZE` | 512px | Histogram/quality analysis |
| `image_colors.py` | Hardcoded | 150px | Color quantization |
| `build_webapp.py` | `THUMBNAIL_MAX_SIZE` | 320px | Web gallery thumbnails |

### Pipeline Dependency Graph

```
image_scanner → trip_day_assigner → location_resolver → map_preview
                                                            ↓
                    ┌─────────────────────────────────────────┐
                    │     ANALYSIS SUITE (sequential)         │
                    │                                         │
                    │  GPU Tasks:          CPU Tasks:         │
                    │  ├─ face_detector    ├─ image_quality   │
                    │  ├─ image_labeler    └─ image_colors    │
                    │  ├─ caption_filler                      │
                    │  ├─ generate_ai_captions                │
                    │  ├─ species_detector                    │
                    │  └─ image_type_detector                 │
                    └─────────────────────────────────────────┘
                                        ↓
        blog_generator → map_final → build_blog_context → build_webapp
                                                              ↓
                                                        build_trip_index
```

### CSV Column Dependencies

| Column | Written By | Read By |
|--------|-----------|---------|
| `image_name`, `local_path`, `md5sum` | image_scanner | All scripts |
| `datetime_original`, `device_model` | image_scanner | day_assigner, blog, webapp |
| `gps_lat`, `gps_lon` | image_scanner, location_resolver | map_visualizer, webapp |
| `location_inferred` | location_resolver | blog_generator, webapp |
| `day_number` | trip_day_assigner | blog_generator, webapp |
| `faces_detected`, `faces_count` | face_detector | blog_context, webapp |
| `detected_objects` | image_labeler | species_detector, blog, webapp |
| `caption`, `caption_samples` | caption_filler | blog_generator, webapp |
| `caption_ai` | generate_ai_captions | blog_generator, webapp |
| `species_tags` | image_labeler (coarse), species_detector (refined) | blog, webapp |
| `image_type` | image_type_detector | species_detector, webapp |
| `quality_score`, `exposure_score`, etc. | image_quality | webapp |
| `color_palette` | image_colors | webapp |

## Parallel Execution and Resource Monitoring

MemoGraph supports internal parallelism for computationally intensive steps (face detection, image labeling, caption generation, species detection).

- When `MEMOGRAPH_PARALLEL_EXECUTION=true`, scripts like `face_detector.py` and `caption_filler.py` use multiple cores/threads where appropriate, but high-level steps are sequenced to keep CSV writes safe.
- The pipeline monitors CPU, RAM, and GPU usage in the main process and its children, logging per-step snapshots to:

  ```
  data/trips/<trip_folder>/MemoGraph/logs/resource_usage.csv
  ```

- **Why CPU% can exceed 100%:** the reported CPU value is the sum of CPU usage across all cores for the process tree. For example, ~600% means roughly 6 cores were busy at that sampling point.

## Configuration

You can customize the behavior of the scripts by editing `memograph_config.py`. This file contains settings for:
- File paths and extensions
- CSV headers
- Logging and backup options
- Image size and parallelism knobs (e.g., `MAX_IMAGE_SIZE`, `FACE_DETECTION_BATCH_SIZE`, `FACE_DETECTION_PARALLEL_WORKERS`, `CAPTION_PARALLEL_WORKERS`).
- Optional face recognition settings (`ENABLE_FACE_RECOGNITION`, `FACE_GALLERY_PATH`, `FACE_RECOGNITION_THRESHOLD`) that allow you to recognise known faces in images after you build a face gallery from reference photos.
- Image quality + context extras:
  - `ENABLE_IMAGE_QUALITY` + related knobs to control thumbnail-sized histogram analysis.
  - `BLOG_CONTEXT_INCLUDE_EXTRAS` to decide whether `build_blog_context` should run expensive YOLO/OCR/Places passes (default `False` to keep runs fast; override with CLI flags when needed).

The CSV schema includes an `image_type` column used for high-level content
classification (e.g., natural photo, document scan, meme/graphic, screenshot,
chart/plot). It is currently populated by `scripts/image_type_detector.py`
using CLIP zero-shot prompts and produces values such as `natural_photo`,
`document_scan`, `meme_or_graphic`, `screenshot`, and `chart_or_plot`.

## Analysis & Comparison Tools

The repository includes helper scripts for comparing runs and configurations:

- `scripts/compare_resolutions.py`  
  Compare `labels.csv` fields (faces, species, objects, captions) across multiple `MemoGraph_*` folders for a trip at different `MAX_IMAGE_SIZE` values.

- `scripts/compare_stats.py`  
  Compare per-step CPU/RAM/GPU metrics across multiple `MemoGraph_*` folders using their `resource_usage.csv` files.

- `scripts/compare_labels_variants.py`  
  Print a CSV-style table comparing chosen fields (e.g., `detected_objects`, `species_tags`, `caption`, `caption_ai`) across any set of `MemoGraph_*` variants.

These are documented in more detail in `working.txt` and `task.txt`, and are useful when deciding which resolution (e.g. 256, 512, 1024) gives acceptable accuracy for your models.

MemoGraph also produces:

- A first-pass human-readable trip blog (`blog.md`)
- A structured day summary (`trip_summary.json`)
- A rich context file (`blog_context.json`, generated automatically by `run_all.py`) that aggregates per-day themes/activities plus per-image captions, CLIP/YOLO/Places tags, species, faces, etc.
  - Heavy extras (YOLO detections, OCR text, Places365 scenes) are **disabled by default** to keep runs fast; set `BLOG_CONTEXT_INCLUDE_EXTRAS = True` in `memograph_config.py` or call `python -m scripts.build_blog_context <trip> --include-extras` when you specifically need them.

These files can be:
- Used as-is for quick trip overviews.
- Fed into an external LLM (see `blog_generation_prompt.md`) if you want to generate a longer, more narrative travel blog using MemoGraph's captions, locations, and species as input.
- Regenerated manually when needed via:

```bash
python -m scripts.build_blog_context data/trips/my_awesome_trip
```

This aggregates per-day times, locations, themes (mountains/roads/temples/markets/food/stays/astro/wildlife), CLIP labels, BLIP captions, YOLO objects, Places365 scene tags, and species into a single JSON file that is ideal for feeding into external text-generation models.


## Location Propagation and Overview Page

- **GPS propagation:**  
  `location_resolver.py` can infer GPS coordinates for photos that lack EXIF GPS by copying the last known coordinates from nearby-in-time images in the same trip. The time window is controlled by a config knob in `memograph_config.py` (e.g., `GPS_PROPAGATION_MAX_MINUTES`, default around 15 minutes). This helps fill in locations for images taken shortly before/after a geotagged photo on the same hike/drive.

- **Early map preview:**  
  After location resolution (including propagation), `run_all.py` calls `map_visualizer.create_map` once to generate an initial `trip_map.html` so you can open a basic map while heavier AI steps (faces, captions, species, etc.) continue in the background.

- **Final map and overview:**  
  At the end of the pipeline, the map is regenerated with full captions/species/image_type data. In addition, `map_visualizer.create_overview_page` builds a `trip_overview.html` file that:
  - Embeds the map on the left.
  - Shows non-geotagged photos in a right-hand sidebar as cards (lazy-loaded thumbnails).
  - Derives simple tags per image (e.g., people, birds, plants_flowers, insects, animals, landscapes, astro and the image_type categories).
  - Provides a chip-style filter bar so you can interactively filter sidebar photos by these tags.

- **Static Leaflet gallery + map (`MemoGraph/webapp/index.html`):**  
  `build_webapp.py` generates a modern, 3-column web application:
  - **Left Sidebar:** Interactive filters grouped by category (Nature, Structures, People, Tech, Food, etc.) and a "Clear Filters" button.
  - **Main Gallery:** Scrollable grid of photos with smart thumbnails, showing color palettes, key tags, and quality scores.
  - **Right Map Pane:** A sticky map that updates markers in real-time as you filter the gallery.
  - **Lightbox:** A detailed full-screen view with a filmstrip, metadata panel (location, faces, camera info), a mini-map, and color swatches.
  - All assets are local; no external backend is required.

This static webapp replaces the earlier baked overview-only experience and makes it easy to explore each trip offline.

- **Master trips hub (`data/trips/index.html`):**  
  Every time `run_all.py` completes, `build_trip_index.py` refreshes a landing page that lists every trip under `data/trips`. Each card shows stacked thumbnails (sourced from each trip's MemoGraph thumbnails), date ranges, photo/day counts, and top themes/species so you get a quick visual vibe before diving in. Cards link straight into `<trip>/MemoGraph/webapp/index.html`, effectively giving you a native-feeling photo library for multiple trips with a constant back button to return to the hub.

This ensures that every photo in a trip is visible somewhere (on the map if it has GPS, or in the sidebar if it does not), and that you can still explore large trips while processing is ongoing.

## Web App Roadmap

The current static viewer covers the basics (search, filters, lightbox, map, multi-trip hub), and the next batch of improvements we are tracking includes:

- Richer Material polish: chip ripples, card ripple effects, and smoother transitions when filters/map clusters update.
- Expanded EXIF/metadata: surface shutter/ISO/f-stop/device sensor info (requires parsing EXIF and extending `blog_context.json`).
- Share/export affordances: quick buttons to download filtered metadata CSVs, copy shareable file paths, or open the original folder.
- Smarter map clustering: switch from simple lat/lon rounding to a Leaflet clustering plugin and keep marker groups in sync with filter chips.
- Cross-trip search: load a compact manifest on the hub so you can search for themes/species/people (e.g., "Bulbul", "snow", "Mom") and jump directly into the relevant trip/photo.
- Semantic search ideas: optionally store CLIP embeddings to support fuzzy queries like "snowy yak on a mountain pass" without pre-defined tags.
- Quality-aware browsing: leverage the new per-image quality metrics (exposure/color/contrast/sharpness/noise) to highlight the most balanced photos in the UI.

## Batch GPU Processing (New!)

MemoGraph now includes a unified GPU model manager that loads all AI models (CLIP, BLIP, LLaVA) once and processes images through all models in a single pass. This is significantly more efficient than the traditional approach of loading/unloading models for each step.

### Quick Start

```bash
# Activate venv
source .venv/bin/activate

# Process all trips with all models
python -m scripts.batch_gpu_processor --all-trips

# Process a single trip
python -m scripts.batch_gpu_processor data/trips/my_awesome_trip

# Force reprocess all images (even if already processed)
python -m scripts.batch_gpu_processor --all-trips --force

# Use only specific models
python -m scripts.batch_gpu_processor --all-trips --models clip blip
```

Or use the convenience script:

```bash
./scan_all_trips.sh                    # Process all trips
./scan_all_trips.sh --reset            # Reset and reprocess all trips
./scan_all_trips.sh data/trips/MyTrip  # Process single trip
```

### Performance Benchmarks (RTX 3060 12GB)

| Metric | Value |
|--------|-------|
| **GPU VRAM Used** | ~4.4GB (36% of 12GB) |
| **System RAM** | ~7GB (45%) |
| **CPU Usage** | ~15% |
| **Throughput** | 0.29 images/second (~3.5s per image) |

### Sample Run (138 images across 3 trips)

| Trip | Images | Time | Speed |
|------|--------|------|-------|
| 2025_Annapurna_Nepal | 97 | 317s | 0.31 img/s |
| Home | 25 | 92s | 0.27 img/s |
| Vengurla | 16 | 52s | 0.31 img/s |
| **Total** | **138** | **8.0 min** | **0.29 img/s** |

### Models Loaded Simultaneously

| Model | VRAM | Purpose |
|-------|------|---------|
| CLIP ViT-B/32 | ~0.5GB | Object/scene detection |
| BLIP | ~0.5GB | Image captioning |
| LLaVA 0.5B | ~2GB | Detailed AI descriptions |
| Processing buffers | ~1.5GB | Tensor operations |

### New Files

- `scripts/gpu_model_manager.py` - Unified GPU model manager with resource monitoring
- `scripts/batch_gpu_processor.py` - Batch processor for all trips
- `scan_all_trips.sh` - Convenience script with venv activation

## Vision LLM (Batch & Demo)

You can use a small multimodal model (LLaVA OneVision 0.5B) to get rich, detailed descriptions for your photos.

### 1. Batch Captioning (Database Integration)
To generate detailed `vision_caption` fields for all images in a trip and save them to `labels.csv`:

```bash
python -m scripts.batch_vision_llm data/trips/my_awesome_trip
```

This runs systematically over the trip, skipping images that already have a vision caption.

### 2. Interactive Demo
To experiment with custom prompts on a single image:

```powershell
python -m scripts.vision_llm_demo data/trips/2025_Annapurna_Nepal `
  --model-id models/llava_onevision_qwen2_0.5b `
  --question "Describe this photo with any interesting objects or activities."
```

### Setup
1. Activate the venv:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. Log in to Hugging Face (one-time):
   ```powershell
   hf auth login --token <YOUR_HF_TOKEN>
   ```
3. Download the model locally (downloads ≈1.6 GB but expands to ~12.8 GB on disk, ~8–9 minutes on our link):
   ```powershell
   python - <<'PY'
   from huggingface_hub import snapshot_download
   snapshot_download(
       'llava-hf/llava-onevision-qwen2-0.5b-ov-hf',
       local_dir='models/llava_onevision_qwen2_0.5b'
   )
   PY
   ```

### Usage
Recommended starter model for GTX 1650-class GPUs: **`llava-hf/llava-onevision-qwen2-0.5b-ov-hf`** (~0.5B parameters, runs in ~3 GB VRAM). Heavier 7B+ vision models may exceed the 4 GB limit unless you use aggressive quantization or CPU inference.

- Inference on a GTX 1650 takes ~40 seconds per image (after the initial model load).

Sample output (Annapurna trip, first photo):

```
Model: models/llava_onevision_qwen2_0.5b
Image: data\trips\2025_Annapurna_Nepal\IMG20240816111741.jpg
Question: Describe this photo in detail. Mention setting, subjects, lighting, and any interesting objects.
Response:
…The image captures a serene outdoor scene, dominated by a lush green tree with vibrant orange fruits…white wall and green roof…overall scene exudes a sense of tranquility and natural beauty.
```

Another example (Home trip, IMG20251019232730):

```
…a white and black telescope mounted on a tripod… positioned in front of a window with a black-and-white checkered curtain… a wooden cabinet on the right with a pink blanket and striped pillow, making the room feel cozy, while the telescope adds intrigue.
```

You can change prompts or max tokens (`--max-new-tokens`) to explore different descriptions. Later we can wire this into the web app or blog generation flow if desired.

### Prompt study + integration plan

- A 10-prompt comparison run on `data/trips/2025_Annapurna_Nepal/IMG20240816111741.jpg` lives at `data/trips/2025_Annapurna_Nepal/MemoGraph/llm_vision_prompt_study.txt`. Because the helper script keeps the model in memory, the entire sweep took ~616 s on CPU (~35–90 s per prompt) and highlighted where prompts shine (structured diary/narrator perspectives) versus fail (casual Instagram requests led to repeated hashtags). Reviewing that file helps us pick a house prompt before wiring the model into production.
- Near-term roadmap (see `task.txt`/`working.txt` for details):
  1. Wrap the ad-hoc prompt sweep into a tiny CLI that accepts a prompt list and emits JSON so we can compare outputs systematically.
  2. Teach `run_all.py` (behind a flag like `--vision-llm` or via config) to load the model **once**, iterate over every photo in the trip, and stash the preferred VLM caption under new `vision_caption_*` columns plus `blog_context.json`.
  3. Surface those richer captions in the static web app (toggle between BLIP + VLM text) and optionally in the Markdown blog.
- Until that wiring exists, you can reproduce the study by calling `scripts/vision_llm_demo.py` repeatedly with different `--question` prompts or by adapting the inline example used for the saved study.

## Bird Species Model (optional)

MemoGraph can optionally use a specialist bird classifier (in addition to CLIP
prompts) to improve species recognition when an image clearly contains a bird.

- Recommended starting model:  
  `dennisjooo/Birds-Classifier-EfficientNetB2` on Hugging Face.

- To enable it:
  1. Install the necessary libraries (if not already installed):

     ```bash
     pip install transformers torch
     ```

  2. Download the model into the expected folder using the helper script:

     ```bash
     # Activate your venv first
     .venv\Scripts\Activate.ps1         # Windows PowerShell
     # or: source .venv/bin/activate    # Linux/macOS

     python -m scripts.download_bird_model
     ```

     This will download `dennisjooo/Birds-Classifier-EfficientNetB2` and save it under:
     `models/birds/Birds-Classifier-EfficientNetB2`.

  3. Edit `memograph_config.py` and set:

     ```python
     ENABLE_BIRD_MODEL = True
     ```

  4. Run the pipeline as usual (optionally with `--reset` to regenerate species tags):

     ```bash
     python run_all.py data/trips/my_awesome_trip --reset
     ```

- Behavior:
  - `image_labeler.py` + BLIP captions first detect whether an image likely
    contains birds/animals/plants/insects.
  - `species_detector.py`:
    - Skips species detection entirely when there are no biological hints (e.g., pure galaxy/nebula images).
    - When bird hints are present and `ENABLE_BIRD_MODEL=True`, it uses the bird classifier to propose top bird species and writes them into `species_tags`.
    - If the bird model is unavailable or fails, it falls back to the existing CLIP-based species prompts.


## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
