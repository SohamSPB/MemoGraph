#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision_llm_demo.py

Quick utility to run a lightweight multimodal LLM (e.g., LLaVA OneVision 0.5B)
on a MemoGraph image. Useful for experimenting with richer captions or
question/answer behavior before wiring it into the main pipeline.

Example:
    python -m scripts.vision_llm_demo data/trips/2025_Annapurna_Nepal \
        --question "Describe the scene and key details."
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForVision2Seq

DEFAULT_MODEL_ID = "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"
DEFAULT_QUESTION = (
	"Describe this photo in detail. Mention setting, subjects, lighting, and any interesting objects."
)


def _find_first_image(trip_folder: Path) -> Optional[Path]:
	for ext in (".jpg", ".jpeg", ".png", ".jfif"):
		for path in sorted(trip_folder.rglob(f"*{ext}")):
			if "MemoGraph" in path.parts:
				continue
			return path
	return None


def _load_image(image_path: Path, max_size: int = 512) -> Image.Image:
	image = Image.open(image_path).convert("RGB")
	image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
	return image


def _load_model(model_id: str):
	device = "cuda" if torch.cuda.is_available() else "cpu"
	dtype = torch.float16 if device == "cuda" else torch.float32
	model = AutoModelForVision2Seq.from_pretrained(
		model_id,
		torch_dtype=dtype,
		trust_remote_code=True,
		low_cpu_mem_usage=True,
	).to(device)
	processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
	return model, processor, device


def run_demo(
	trip_folder: str,
	image_path: Optional[str],
	model_id: str,
	question: str,
	output_path: Optional[str],
	max_new_tokens: int,
) -> str:
	trip_folder_path = Path(trip_folder)
	if not trip_folder_path.is_dir():
		raise FileNotFoundError(f"Trip folder not found: {trip_folder}")

	image_file = Path(image_path) if image_path else _find_first_image(trip_folder_path)
	if not image_file:
		raise FileNotFoundError("No image found in trip folder and none supplied explicitly.")
	if not image_file.exists():
		raise FileNotFoundError(f"Image path does not exist: {image_file}")

	image = _load_image(image_file)
	model, processor, device = _load_model(model_id)

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
	inputs = processor(
		text=prompt,
		images=image,
		return_tensors="pt",
	).to(device)

	with torch.inference_mode():
		output_ids = model.generate(
			**inputs,
			max_new_tokens=max_new_tokens,
			temperature=0.1,
		)

	generated_text = processor.decode(output_ids[0], skip_special_tokens=True)
	result = (
		f"Model: {model_id}\n"
		f"Image: {image_file}\n"
		f"Question: {question}\n"
		f"Response:\n{generated_text}\n"
	)

	print(result)
	if output_path:
		out_file = Path(output_path)
		out_file.parent.mkdir(parents=True, exist_ok=True)
		out_file.write_text(result, encoding="utf-8")

	return result


def main():
	parser = argparse.ArgumentParser(description="Run a vision-language model demo on a MemoGraph image.")
	parser.add_argument("trip_folder", help="Trip folder (e.g. data/trips/2025_Annapurna_Nepal)")
	parser.add_argument("--image", help="Specific image path (defaults to the first non-MemoGraph photo).")
	parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help=f"Hugging Face model ID (default: {DEFAULT_MODEL_ID})")
	parser.add_argument("--question", default=DEFAULT_QUESTION, help="Prompt/question for the LLM.")
	parser.add_argument(
		"--output",
		help="Optional output file (default: <trip>/MemoGraph/llm_vision_demo.txt)",
	)
	parser.add_argument("--max-new-tokens", type=int, default=256, help="Max tokens to generate.")
	args = parser.parse_args()

	output_path = args.output
	if not output_path:
		output_path = os.path.join(args.trip_folder, "MemoGraph", "llm_vision_demo.txt")

	run_demo(
		trip_folder=args.trip_folder,
		image_path=args.image,
		model_id=args.model_id,
		question=args.question,
		output_path=output_path,
		max_new_tokens=args.max_new_tokens,
	)


if __name__ == "__main__":
	main()
