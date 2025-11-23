#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_places365.py

Helper script to download the Places365 ResNet-50 scene classifier weights
and category file into the local models/places folder so they can be used
by build_blog_context.py for richer scene tags.

This follows the official Places365 model layout:
- Weights URL (ResNet-50):    http://places2.csail.mit.edu/models_places365/resnet50_places365.pth.tar
- Categories text file URL:   https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt

Usage (from repo root, inside venv):

    python -m scripts.download_places365

You can override paths if desired:

    python -m scripts.download_places365 \\
        --weights-path models/places/resnet50_places365.pth.tar \\
        --categories-path models/places/categories_places365.txt
"""

import argparse
import os
import sys
from typing import Tuple

import requests


PLACES_WEIGHTS_URL = "http://places2.csail.mit.edu/models_places365/resnet50_places365.pth.tar"
PLACES_CATEGORIES_URL = "https://raw.githubusercontent.com/csailvision/places365/master/categories_places365.txt"


def _download(url: str, dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    chunk_size = 8192
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                done = int(50 * downloaded / total)
                sys.stdout.write("\r[{}{}] {:.1f}%".format("#" * done, "." * (50 - done), downloaded * 100 / total))
                sys.stdout.flush()
    sys.stdout.write("\n")


def download_places365(weights_path: str, categories_path: str) -> Tuple[str, str]:
    print(f"Downloading Places365 ResNet-50 weights to: {weights_path}")
    _download(PLACES_WEIGHTS_URL, weights_path)
    print(f"Downloading Places365 categories to: {categories_path}")
    _download(PLACES_CATEGORIES_URL, categories_path)
    return weights_path, categories_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Places365 ResNet-50 weights + categories.")
    parser.add_argument(
        "--weights-path",
        default=os.path.join("models", "places", "resnet50_places365.pth.tar"),
        help="Destination path for the Places365 ResNet-50 weights.",
    )
    parser.add_argument(
        "--categories-path",
        default=os.path.join("models", "places", "categories_places365.txt"),
        help="Destination path for the Places365 categories txt.",
    )
    args = parser.parse_args()

    w_path, c_path = download_places365(args.weights_path, args.categories_path)
    print("Places365 assets downloaded:")
    print("  Weights   :", os.path.abspath(w_path))
    print("  Categories:", os.path.abspath(c_path))

