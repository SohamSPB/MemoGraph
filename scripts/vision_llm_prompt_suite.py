#!/usr/bin/env python
"""
vision_llm_prompt_suite.py

Run a batch of curated prompts (5 "best of" + 1 structured template) across
multiple trips and images while keeping the multimodal model loaded once.
Outputs are saved per-image under <trip>/MemoGraph/llm_prompt_suite/.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import torch

from scripts.vision_llm_demo import _load_image, _load_model

# Core 5 prompts selected from the earlier study
BEST_PROMPTS: Sequence[Tuple[str, str]] = [
    (
        "travel_diary",
        "Write a vivid travel diary entry about this scene, noting season, ambiance, and what the traveler might feel.",
    ),
    (
        "doc_pitch",
        "Summarize this photo as if you were pitching it to a documentary narrator, focusing on geography and culture.",
    ),
    (
        "photo_critique",
        "Imagine you are a photography teacher critiquing this shot: discuss composition, lighting, and suggestions.",
    ),
    (
        "accessibility",
        "Describe the scene for someone who cannot see, emphasizing textures, sounds, and spatial layout.",
    ),
    (
        "field_naturalist",
        "Analyze the image like a field naturalist, calling out flora, fauna, geography, and weather cues.",
    ),
]

DEFAULT_PROMPT_TEMPLATE = Path("templates/vision_llm_prompt.txt")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".jfif"}


def iter_trip_images(trip_folder: Path, limit: int) -> List[Path]:
    images: List[Path] = []
    for path in sorted(trip_folder.rglob("*")):
        if len(images) >= limit:
            break
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS and "MemoGraph" not in path.parts:
            images.append(path)
    return images


def run_prompt(model, processor, device, image, question: str, max_new_tokens: int) -> Tuple[str, float]:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": question},
            ],
        }
    ]
    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)
    start = time.perf_counter()
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
        )
    elapsed = time.perf_counter() - start
    generated = processor.decode(output_ids[0], skip_special_tokens=True)
    return generated, elapsed


def process_trip(
    trip_folder: Path,
    model,
    processor,
    device,
    template_prompt: str,
    images_per_trip: int,
    max_new_tokens: int,
) -> None:
    images = iter_trip_images(trip_folder, images_per_trip)
    if not images:
        print(f"[WARN] No images found for trip {trip_folder}")
        return

    prompt_suite = list(BEST_PROMPTS) + [("full_analysis", template_prompt)]
    output_dir = trip_folder / "MemoGraph" / "llm_prompt_suite"
    output_dir.mkdir(parents=True, exist_ok=True)

    for image_path in images:
        print(f"[INFO] Processing {image_path}")
        image = _load_image(image_path)
        parts = [f"Image: {image_path}", ""]
        for prompt_id, question in prompt_suite:
            response, elapsed = run_prompt(model, processor, device, image, question, max_new_tokens)
            parts.extend(
                [
                    f"Prompt {prompt_id}: {question}",
                    f"Response ({elapsed:.1f}s):",
                    response,
                    "",
                ]
            )
        out_file = output_dir / f"{image_path.stem}.txt"
        out_file.write_text("\n".join(parts), encoding="utf-8")
        print(f"[INFO] Wrote {out_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a suite of prompts on multiple MemoGraph trips/images.")
    parser.add_argument("trips", nargs="+", help="Trip folders (e.g. data/trips/2025_Annapurna_Nepal)")
    parser.add_argument("--model-id", default="models/llava_onevision_qwen2_0.5b", help="Local or HF model ID.")
    parser.add_argument("--images-per-trip", type=int, default=5, help="How many images per trip to process.")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Max tokens for generation.")
    parser.add_argument(
        "--template-prompt",
        type=str,
        default=str(DEFAULT_PROMPT_TEMPLATE),
        help="Path to the structured template prompt.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_prompt = Path(args.template_prompt).read_text(encoding="utf-8")
    model, processor, device = _load_model(args.model_id)
    for trip in args.trips:
        trip_path = Path(trip)
        if not trip_path.is_dir():
            print(f"[WARN] Trip folder not found: {trip}")
            continue
        process_trip(
            trip_folder=trip_path,
            model=model,
            processor=processor,
            device=device,
            template_prompt=template_prompt,
            images_per_trip=args.images_per_trip,
            max_new_tokens=args.max_new_tokens,
        )


if __name__ == "__main__":
    main()
