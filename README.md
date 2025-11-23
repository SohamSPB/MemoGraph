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

MemoGraph’s `run_all.py` runs the following steps sequentially (each step calls
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
10. Blog + summary (`blog_generator.py`)
11. Final map + overview page (`map_visualizer.py`)
12. `blog_context.json` builder (`build_blog_context.py`)
13. Static Leaflet gallery/map web app + thumbnails (`build_webapp.py`)

Every run writes a complete `MemoGraph` folder containing `labels.csv`, `blog.md`,
`trip_summary.json`, `trip_map.html`, `trip_overview.html`, `blog_context.json`,
`webapp/index.html`, per-step logs, and JPEG thumbnails under `MemoGraph/thumbnails`.

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

These files can be:
- Used as-is for quick trip overviews.
- Fed into an external LLM (see `blog_generation_prompt.md`) if you want to generate a longer, more narrative travel blog using MemoGraph’s captions, locations, and species as input.
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
  `build_webapp.py` reads `blog_context.json`, generates thumbnails in `MemoGraph/thumbnails`, and emits a single-page app with:
  - A search box that scans captions, AI captions, species tags, detected_objects, Places tags, people_tags, and locations across the entire trip.
  - Chip filters (birds, plants, landscapes, astro, wildlife, selfie/group, etc.) with a collapse/expand toggle plus a preset toolbar that ships with "Birds", "Landscapes", "Astro", "People" and lets you store custom filter combinations per trip via `localStorage`.
  - A thumbnail gallery that uses the generated JPEG thumbnails (falls back to originals if needed), shows day/location context, and opens a modern lightbox with keyboard shortcuts (←/→/Esc), copy/open buttons, device info, face counts, species/object/scene tags, and a mini-map when GPS is available.
  - A bottom-aligned filmstrip so you can scrub through photos like a native photo app while keeping the main hero image + metadata panel in view.
  - A right-hand Leaflet map whose markers mirror the active filters/search; nearby points are clustered (rounded lat/lon) so dense GPS data stays readable, and marker popups include thumbnails/captions.
  - Header includes a back button to the trips hub and shows the current trip name so you always know which dataset you're viewing.
  - All assets are local; no external backend is required to browse processed trips.

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
- Cross-trip search: load a compact manifest on the hub so you can search for themes/species/people (e.g., “Bulbul”, “snow”, “Mom”) and jump directly into the relevant trip/photo.
- Semantic search ideas: optionally store CLIP embeddings to support fuzzy queries like “snowy yak on a mountain pass” without pre-defined tags.

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
