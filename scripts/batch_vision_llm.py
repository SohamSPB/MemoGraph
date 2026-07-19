#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_vision_llm.py

Runs Vision LLM(s) on all images in a trip to generate detailed descriptions.

By default uses LLaVA 0.5B (~2.5s/image) for fast captioning. Use --model both
to run Qwen 7B and LLaVA 0.5B sequentially for comparison (each writes to its
own column). The generic `vision_caption` column gets the best available caption
(7B preferred over 0.5B when both are present).

Available models:
- LLaVA OneVision 0.5B         ~2.5s/image, ~2 GB VRAM (default)
- Qwen2.5-VL-7B-Instruct-AWQ  ~13s/image, ~8-9 GB VRAM (richer descriptions)

Usage:
    python -m scripts.batch_vision_llm data/trips/MyTrip                    # LLaVA 0.5B (default)
    python -m scripts.batch_vision_llm data/trips/MyTrip --model qwen-7b    # Qwen 7B only
    python -m scripts.batch_vision_llm data/trips/MyTrip --model both       # both models
    python -m scripts.batch_vision_llm data/trips/MyTrip --model auto       # auto-select by VRAM
"""

import os
import torch
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from scripts.utils.utils_io import read_csv_dict, write_csv_dict
from memograph_config import ensure_memograph_folder
from scripts.utils.utils_log import init_log, log
import memograph_config as CFG

DEFAULT_PROMPT = "Describe this image in detail, covering subject, setting, lighting, and mood."

MODEL_COLUMN_MAP = {
    "qwen-7b": "vision_caption_qwen_7b",
    "llava-0.5b": "vision_caption_llava_05b",
}


def _load_llava_model(model_path, device, dtype):
    """Load LLaVA OneVision 0.5B."""
    from transformers import AutoProcessor, AutoModelForVision2Seq
    model = AutoModelForVision2Seq.from_pretrained(
        model_path,
        torch_dtype=dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).to(device)
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    return model, processor


def _load_qwen_model(model_path, device, dtype):
    """Load Qwen2.5-VL-7B-Instruct-AWQ."""
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_path,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    return model, processor


def load_model(model_type):
    """Load a specific Vision LLM by model_type ('qwen-7b' or 'llava-0.5b').

    Returns (model, processor, device, model_type) or (None, None, None, None).
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if model_type == "qwen-7b":
        model_path = _qwen_path()
        print(f"[VLM] Loading qwen-7b -> {model_path}")
        print(f"[VLM] Device: {device} | Dtype: {dtype}")
        try:
            model, processor = _load_qwen_model(model_path, device, dtype)
            return model, processor, device, "qwen-7b"
        except Exception as e:
            print(f"[VLM] Error loading qwen-7b: {e}")
            return None, None, None, None
    else:
        model_path = _llava_path()
        print(f"[VLM] Loading llava-0.5b -> {model_path}")
        print(f"[VLM] Device: {device} | Dtype: {dtype}")
        try:
            model, processor = _load_llava_model(model_path, device, dtype)
            return model, processor, device, "llava-0.5b"
        except Exception as e:
            print(f"[VLM] Error loading llava-0.5b: {e}")
            return None, None, None, None


def _llava_path():
    if os.path.isdir(CFG.VLM_LLAVA_05B_DIR) and os.path.exists(os.path.join(CFG.VLM_LLAVA_05B_DIR, "config.json")):
        return CFG.VLM_LLAVA_05B_DIR
    return CFG.VLM_LLAVA_05B_ID


def _qwen_path():
    if os.path.isdir(CFG.VLM_QWEN_7B_DIR) and os.path.exists(os.path.join(CFG.VLM_QWEN_7B_DIR, "config.json")):
        return CFG.VLM_QWEN_7B_DIR
    return CFG.VLM_QWEN_7B_ID


def _generate_caption_llava(model, processor, device, image, prompt, max_new_tokens):
    """Generate caption using LLaVA OneVision 0.5B."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=text_prompt, images=image, return_tensors="pt").to(device)

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False
        )

    generated_text = processor.decode(output_ids[0], skip_special_tokens=True)
    if "assistant\n" in generated_text:
        generated_text = generated_text.split("assistant\n")[-1].strip()
    return generated_text


def _generate_caption_qwen(model, processor, device, image, prompt, max_new_tokens):
    """Generate caption using Qwen2.5-VL-7B-Instruct-AWQ."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt", padding=True)
    # Move inputs to the device where model parameters live (handles device_map="auto")
    model_device = next(model.parameters()).device
    inputs = inputs.to(model_device)

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False
        )

    # Trim input tokens from output
    generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return generated_text.strip()


def _unload_model(model):
    """Delete model and free GPU memory."""
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _resolve_models_to_run(model_flag):
    """Return a list of model_type strings to run, based on the --model flag.

    For 'auto', uses select_vlm_model() to pick the best single model.
    For 'both', returns ['qwen-7b', 'llava-0.5b'].
    Otherwise returns the single requested model.
    """
    if model_flag == "both":
        return ["qwen-7b", "llava-0.5b"]
    if model_flag == "auto":
        _, model_type = CFG.select_vlm_model()
        return [model_type]
    return [model_flag]


def _run_single_model(model_type, rows, trip_folder, csv_path, log_path):
    """Load one model, caption all images missing that model's column, save CSV."""
    column = MODEL_COLUMN_MAP[model_type]
    max_new_tokens = CFG.VLM_MAX_NEW_TOKENS_QWEN if model_type == "qwen-7b" else CFG.VLM_MAX_NEW_TOKENS_LLAVA
    generate_fn = _generate_caption_qwen if model_type == "qwen-7b" else _generate_caption_llava

    # Find images that need captioning for this model
    to_process = []
    for i, r in enumerate(rows):
        if not r.get(column):
            local_path = r.get("local_path", "")
            full_path = os.path.join(trip_folder, local_path)
            if os.path.exists(full_path):
                to_process.append((i, full_path))

    if not to_process:
        log(f"[{model_type}] All images already have captions in '{column}'.", log_path)
        return 0

    log(f"[{model_type}] {len(to_process)} images to caption -> '{column}'", log_path)

    model, processor, device, loaded_type = load_model(model_type)
    if not model:
        log(f"[{model_type}] Failed to load model. Skipping.", log_path)
        return 0

    log(f"[{model_type}] Using {loaded_type} (max_new_tokens={max_new_tokens})", log_path)

    def _load_and_resize(path):
        """Load and resize image (runs in background thread while GPU is busy)."""
        img = Image.open(path).convert("RGB")
        if max(img.size) > 1024:
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        return img

    updated_count = 0
    try:
        # Preload first image
        prefetch = ThreadPoolExecutor(max_workers=1)
        next_future = prefetch.submit(_load_and_resize, to_process[0][1]) if to_process else None

        for idx, (row_idx, img_path) in enumerate(to_process, 1):
            try:
                # Get preloaded image (or wait if still loading)
                image = next_future.result()

                # Start preloading next image while GPU generates
                if idx < len(to_process):
                    next_future = prefetch.submit(_load_and_resize, to_process[idx][1])

                generated_text = generate_fn(model, processor, device, image, DEFAULT_PROMPT, max_new_tokens)

                rows[row_idx][column] = generated_text
                updated_count += 1
                log(f"[{model_type}] [{idx}/{len(to_process)}] {os.path.basename(img_path)}: {generated_text[:60]}...", log_path)

                if updated_count % 5 == 0:
                    write_csv_dict(csv_path, rows, rows[0].keys())

            except Exception as e:
                log(f"[{model_type}] Failed to caption {img_path}: {e}", log_path)
                # Reset prefetch for next image if current one failed
                if idx < len(to_process):
                    next_future = prefetch.submit(_load_and_resize, to_process[idx][1])

        prefetch.shutdown(wait=False)
    finally:
        # Always unload model to free VRAM for the next model
        _unload_model(model)
        del processor

    if updated_count:
        write_csv_dict(csv_path, rows, rows[0].keys())

    log(f"[{model_type}] Captioned {updated_count} images.", log_path)
    return updated_count


def _set_best_vision_caption(rows):
    """Set vision_caption = 7B caption if available, else 0.5B caption."""
    for r in rows:
        qwen = r.get("vision_caption_qwen_7b", "")
        llava = r.get("vision_caption_llava_05b", "")
        best = qwen or llava
        if best:
            r["vision_caption"] = best


def process_trip(trip_folder: str, model_flag: str = "llava-0.5b"):
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

    models_to_run = _resolve_models_to_run(model_flag)
    log(f"Models to run: {models_to_run}", log_path)

    total_updated = 0
    try:
        for model_type in models_to_run:
            count = _run_single_model(model_type, rows, trip_folder, csv_path, log_path)
            total_updated += count
    except KeyboardInterrupt:
        log(f"[INTERRUPTED] Vision LLM captioning interrupted after {total_updated} images. Saving progress...", log_path)
        _set_best_vision_caption(rows)
        write_csv_dict(csv_path, rows, rows[0].keys())
        raise

    # After all models, set the best available caption
    _set_best_vision_caption(rows)
    if total_updated:
        write_csv_dict(csv_path, rows, rows[0].keys())
    log("Batch vision captioning complete.", log_path)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run Vision LLM(s) on trip images.")
    p.add_argument("trip_folder", help="Path to trip folder")
    p.add_argument(
        "--model",
        choices=["auto", "qwen-7b", "llava-0.5b", "both"],
        default="llava-0.5b",
        help="Which model(s) to run (default: llava-0.5b)",
    )
    args = p.parse_args()
    process_trip(args.trip_folder, model_flag=args.model)
