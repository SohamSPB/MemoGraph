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
2.  **Run the pipeline:**

    ```bash
    python run_all.py /path/to/your/trip/folder
    ```

    For example:
    ```bash
    python run_all.py data/trips/my_awesome_trip
    ```

3.  **Check the output:** All generated files (CSV, logs, blog, map) will be placed in a `MemoGraph` folder inside your trip directory.

## Parallel Execution and Resource Monitoring

MemoGraph supports parallel execution for computationally intensive steps (face detection, image labeling, caption generation, species detection).

To enable parallel execution, set the environment variable `MEMOGRAPH_PARALLEL_EXECUTION` to `true`:

```bash
export MEMOGRAPH_PARALLEL_EXECUTION=true
python run_all.py data/trips/my_awesome_trip
```

When running in parallel mode, the pipeline also monitors CPU, RAM, and GPU usage, logging the data to `data/trips/<trip_folder>/MemoGraph/logs/resource_usage.csv`. This helps in understanding the resource consumption of different pipeline stages.

## Configuration

You can customize the behavior of the scripts by editing `memograph_config.py`. This file contains settings for:
- File paths and extensions
- CSV headers
- Logging and backup options


## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.