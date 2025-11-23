#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_face_gallery.py

Build a gallery of known face encodings from reference images stored under:

    models/faces/known/<PersonName>/*.jpg|*.jpeg|*.png

For each person folder:
- Uses face_recognition to detect faces in each image.
- Keeps encodings only when it finds exactly one clear face.
- Aggregates encodings and labels and writes them to a gallery file:

    models/faces/face_gallery.pkl

This gallery can then be used by face_recognizer.py to recognise people
in trip images and populate the people_tags column in labels.csv.
"""

import os
import glob
import pickle
from typing import Dict, List, Tuple

import numpy as np
import face_recognition

import memograph_config as CFG


def _iter_person_folders(root: str) -> List[Tuple[str, str]]:
    """Yield (person_name, folder_path) for each person under the root."""
    out: List[Tuple[str, str]] = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            out.append((name, path))
    return out


def build_face_gallery(
    known_root: str = os.path.join("models", "faces", "known"),
    gallery_path: str = CFG.FACE_GALLERY_PATH,
) -> str:
    encodings: List[np.ndarray] = []
    labels: List[str] = []

    persons = _iter_person_folders(known_root)
    if not persons:
        raise RuntimeError(f"No person folders found under {known_root}.")

    for person_name, folder in persons:
        image_paths = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
            image_paths.extend(glob.glob(os.path.join(folder, ext)))
        image_paths = sorted(set(image_paths))
        if not image_paths:
            continue

        print(f"[build_face_gallery] Processing {person_name} ({len(image_paths)} images)...")

        for img_path in image_paths:
            try:
                image = face_recognition.load_image_file(img_path)
                # Use HOG for compatibility and speed.
                locations = face_recognition.face_locations(image, model="hog")
                if len(locations) != 1:
                    # Skip images with 0 or >1 faces to avoid ambiguity.
                    continue
                encoding = face_recognition.face_encodings(image, known_face_locations=locations)[0]
                encodings.append(encoding)
                labels.append(person_name)
            except Exception as e:
                print(f"[build_face_gallery] Skipping {img_path} due to error: {e}")

    if not encodings:
        raise RuntimeError("No valid face encodings were extracted; gallery is empty.")

    gallery = {
        "encodings": encodings,
        "labels": labels,
    }

    os.makedirs(os.path.dirname(gallery_path), exist_ok=True)
    with open(gallery_path, "wb") as f:
        pickle.dump(gallery, f)

    print(f"[build_face_gallery] Gallery written to: {gallery_path}")
    print(f"[build_face_gallery] Total encodings: {len(encodings)} for {len(set(labels))} people.")
    return gallery_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Build a face gallery from models/faces/known/* reference photos.")
    p.add_argument(
        "--known-root",
        default=os.path.join("models", "faces", "known"),
        help="Root folder containing per-person subfolders with face images.",
    )
    p.add_argument(
        "--gallery-path",
        default=CFG.FACE_GALLERY_PATH,
        help="Output path for the face gallery pickle.",
    )
    args = p.parse_args()

    build_face_gallery(args.known_root, args.gallery_path)

