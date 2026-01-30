#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_vision_llm.py

Runs the LLaVA OneVision model on all images in a trip to generate detailed
descriptions, saving them to the 'vision_caption' column in labels.csv.

Usage:
    python -m scripts.batch_vision_llm data/trips/MyTrip
"""

import os
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForVision2Seq

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

MODEL_ID = "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"
DEFAULT_PROMPT = "Describe this image in detail, covering subject, setting, lighting, and mood."

def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"Loading {MODEL_ID} on {device} ({dtype})...")
    try:
        model = AutoModelForVision2Seq.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        ).to(device)
        processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        return model, processor, device
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None, None

def process_trip(trip_folder: str):
    memo_dir, logs_dir = ensure_memograph_folder(trip_folder)
    log_path = os.path.join(logs_dir, "batch_vision_llm.log")
    init_log(log_path, "batch_vision_llm.py")

    csv_path = os.path.join(memo_dir, "labels.csv")
    if not os.path.exists(csv_path):
        log(f"CSV not found: {csv_path}", log_path)
        return

    rows = read_csv_dict(csv_path)
    if not rows:
        return

    # Filter rows that need processing
    to_process = []
    for i, r in enumerate(rows):
        if not r.get("vision_caption"):
            local_path = r.get("local_path", "")
            full_path = os.path.join(trip_folder, local_path)
            if os.path.exists(full_path):
                to_process.append((i, full_path))

    if not to_process:
        log("All images already have vision captions.", log_path)
        return

    log(f"Found {len(to_process)} images to caption with Vision LLM.", log_path)
    
    model, processor, device = load_model()
    if not model:
        log("Failed to load Vision LLM. Aborting.", log_path)
        return

    updated_count = 0
    for idx, (row_idx, img_path) in enumerate(to_process, 1):
        try:
            image = Image.open(img_path).convert("RGB")
            # Resize to max 1024 to keep VRAM usage reasonable
            if max(image.size) > 1024:
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": DEFAULT_PROMPT},
                    ],
                }
            ]
            text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=text_prompt, images=image, return_tensors="pt").to(device)

            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    temperature=0.1,
                    do_sample=False 
                )
            
            # Decode
            generated_text = processor.decode(output_ids[0], skip_special_tokens=True)
            
            # Post-process: remove system/user prompts if leaked (though decode usually handles this)
            if "assistant\n" in generated_text:
                generated_text = generated_text.split("assistant\n")[-1].strip()

            rows[row_idx]["vision_caption"] = generated_text
            updated_count += 1
            log(f"[{idx}/{len(to_process)}] {os.path.basename(img_path)}: {generated_text[:60]}...", log_path)

            if updated_count % 5 == 0:
                write_csv_dict(csv_path, rows, rows[0].keys())

        except Exception as e:
            log(f"Failed to caption {img_path}: {e}", log_path)

    if updated_count:
        write_csv_dict(csv_path, rows, rows[0].keys())
        log("Batch vision captioning complete.", log_path)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("trip_folder")
    args = p.parse_args()
    process_trip(args.trip_folder)
