#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_bird_model.py

Helper script to download the bird classifier model from Hugging Face and save
it under the expected models/birds directory so that species_detector can use it.

Default model: dennisjooo/Birds-Classifier-EfficientNetB2

Usage:
    .venv\Scripts\Activate.ps1        # on Windows
    python -m scripts.download_bird_model

    # or specify a different model and target directory:
    python -m scripts.download_bird_model \
        --model-id dennisjooo/Birds-Classifier-EfficientNetB2 \
        --output-dir models/birds/Birds-Classifier-EfficientNetB2
"""

import argparse
import os

from transformers import AutoImageProcessor, AutoModelForImageClassification

import memograph_config as CFG


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a bird classifier image model from Hugging Face."
    )
    parser.add_argument(
        "--model-id",
        default="dennisjooo/Birds-Classifier-EfficientNetB2",
        help="Hugging Face model id to download (default: dennisjooo/Birds-Classifier-EfficientNetB2).",
    )
    parser.add_argument(
        "--output-dir",
        default=CFG.BIRD_MODEL_DIR,
        help="Local directory to save the model and processor (default: memograph_config.BIRD_MODEL_DIR).",
    )
    args = parser.parse_args()

    model_id = args.model_id
    output_dir = args.output_dir

    os.makedirs(output_dir, exist_ok=True)
    print(f"Downloading bird model '{model_id}' to '{output_dir}' ...")

    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForImageClassification.from_pretrained(model_id)

    processor.save_pretrained(output_dir)
    model.save_pretrained(output_dir)

    print("Download complete.")
    print("Files saved under:", os.path.abspath(output_dir))


if __name__ == "__main__":
    main()

