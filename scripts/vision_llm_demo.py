#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision_llm_demo.py

Quick utility to run a Vision LLM on a MemoGraph image. Auto-selects
Qwen2.5-VL-7B-Instruct-AWQ (>= 10 GB VRAM) or LLaVA OneVision 0.5B.

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

import memograph_config as CFG

DEFAULT_MODEL_ID = "auto"
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
	"""Load a Vision LLM.

	Returns (model, processor, device, model_type).
	model_type is 'qwen-7b' or 'llava-0.5b'.
	"""
	device = "cuda" if torch.cuda.is_available() else "cpu"
	dtype = torch.float16 if device == "cuda" else torch.float32

	if model_id == "auto":
		model_path, model_type = CFG.select_vlm_model()
	else:
		# Explicit model ID — infer type from name
		if "qwen" in model_id.lower():
			model_path, model_type = model_id, "qwen-7b"
		else:
			model_path, model_type = model_id, "llava-0.5b"

	print(f"[VLM] Loading {model_type} -> {model_path}")

	if model_type == "qwen-7b":
		try:
			from transformers import Qwen2_5_VLForConditionalGeneration
			model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
				model_path,
				torch_dtype=dtype,
				trust_remote_code=True,
				device_map="auto",
			)
			processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
			return model, processor, device, "qwen-7b"
		except Exception as e:
			print(f"[VLM] Failed to load Qwen 7B: {e}")
			print("[VLM] Falling back to LLaVA 0.5B...")
			model_path = CFG.VLM_LLAVA_05B_DIR if os.path.isdir(CFG.VLM_LLAVA_05B_DIR) else CFG.VLM_LLAVA_05B_ID
			model_type = "llava-0.5b"

	model = AutoModelForVision2Seq.from_pretrained(
		model_path,
		torch_dtype=dtype,
		trust_remote_code=True,
		low_cpu_mem_usage=True,
	).to(device)
	processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
	return model, processor, device, model_type


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
	model, processor, device, model_type = _load_model(model_id)

	if model_type == "qwen-7b":
		messages = [
			{
				"role": "user",
				"content": [
					{"type": "image", "image": image},
					{"type": "text", "text": question},
				],
			}
		]
		prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
		inputs = processor(text=[prompt], images=[image], return_tensors="pt", padding=True)
		model_device = next(model.parameters()).device
		inputs = inputs.to(model_device)

		with torch.inference_mode():
			output_ids = model.generate(
				**inputs,
				max_new_tokens=max_new_tokens,
				temperature=0.1,
			)

		generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
		generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
	else:
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

	from scripts.batch_vision_llm import MODEL_COLUMN_MAP
	target_column = MODEL_COLUMN_MAP.get(model_type, "vision_caption")

	result = (
		f"Model: {model_type}\n"
		f"CSV column: {target_column}\n"
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
	parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help=f"Model: 'auto', HF model ID, or local path (default: {DEFAULT_MODEL_ID})")
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
