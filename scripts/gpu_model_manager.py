#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpu_model_manager.py

Unified GPU model manager that loads all AI models once and keeps them in memory.
Supports parallel image processing through multiple models simultaneously.

GPU Memory Budget (RTX 3060 12GB):
- CLIP ViT-B/32: ~1GB
- BLIP: ~2GB
- LLaVA OneVision 0.5B: ~2GB
- Face Detection (dlib): ~0.5GB
- Total: ~5.5GB (leaving ~6GB for processing buffers)
"""

import os
import time
import threading
import psutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import torch
from PIL import Image

# Lazy imports to avoid loading everything at module import
_clip_model = None
_clip_preprocess = None
_blip_model = None
_blip_processor = None
_llava_model = None
_llava_processor = None


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time."""
    timestamp: float
    cpu_percent: float
    ram_mb: float
    ram_percent: float
    gpu_mb: float
    gpu_percent: float

    def __str__(self):
        return (f"CPU: {self.cpu_percent:.1f}% | "
                f"RAM: {self.ram_mb:.0f}MB ({self.ram_percent:.1f}%) | "
                f"GPU: {self.gpu_mb:.0f}MB ({self.gpu_percent:.1f}%)")


@dataclass
class ProcessingStats:
    """Statistics for image processing."""
    total_images: int = 0
    processed_images: int = 0
    failed_images: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    resource_snapshots: List[ResourceSnapshot] = field(default_factory=list)

    @property
    def elapsed_time(self) -> float:
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time if self.start_time else 0

    @property
    def images_per_second(self) -> float:
        if self.elapsed_time > 0:
            return self.processed_images / self.elapsed_time
        return 0

    @property
    def avg_time_per_image(self) -> float:
        if self.processed_images > 0:
            return self.elapsed_time / self.processed_images
        return 0

    def peak_resources(self) -> Optional[ResourceSnapshot]:
        """Get peak resource usage."""
        if not self.resource_snapshots:
            return None
        return max(self.resource_snapshots, key=lambda s: s.gpu_mb)


class ResourceMonitor:
    """Background thread that monitors system resources."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.snapshots: List[ResourceSnapshot] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Start monitoring in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[ResourceSnapshot]:
        """Stop monitoring and return snapshots."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            return list(self.snapshots)

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            snapshot = self._take_snapshot()
            with self._lock:
                self.snapshots.append(snapshot)
            time.sleep(self.interval)

    def _take_snapshot(self) -> ResourceSnapshot:
        """Take a resource snapshot."""
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        ram_mb = mem.used / (1024 * 1024)
        ram_percent = mem.percent

        gpu_mb, gpu_percent = self._get_gpu_usage()

        return ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            ram_mb=ram_mb,
            ram_percent=ram_percent,
            gpu_mb=gpu_mb,
            gpu_percent=gpu_percent
        )

    def _get_gpu_usage(self) -> Tuple[float, float]:
        """Get GPU memory usage in MB and percent."""
        try:
            result = subprocess.check_output([
                'nvidia-smi',
                '--query-gpu=memory.used,memory.total',
                '--format=csv,noheader,nounits'
            ], stderr=subprocess.DEVNULL)
            used, total = result.decode().strip().split(', ')
            used_mb = float(used)
            total_mb = float(total)
            percent = (used_mb / total_mb) * 100 if total_mb > 0 else 0
            return used_mb, percent
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return 0.0, 0.0

    def get_current(self) -> ResourceSnapshot:
        """Get current resource snapshot."""
        return self._take_snapshot()


class GPUModelManager:
    """
    Manages all GPU models and provides unified processing interface.

    Usage:
        manager = GPUModelManager()
        manager.load_models(['clip', 'blip', 'llava'])

        results = manager.process_image(image_path)
        # results = {'clip_labels': [...], 'blip_caption': '...', 'llava_description': '...'}

        manager.unload_models()
    """

    def __init__(self, device: str = None, max_image_size: int = 1024):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_image_size = max_image_size
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        self._models: Dict[str, Any] = {}
        self._processors: Dict[str, Any] = {}
        self._loaded = set()
        self._lock = threading.Lock()

        self.resource_monitor = ResourceMonitor(interval=0.5)
        self.stats = ProcessingStats()

    def load_models(self, models: List[str] = None, log_func: Callable = print):
        """
        Load specified models into GPU memory.

        Args:
            models: List of model names to load. Options: 'clip', 'blip', 'llava', 'face'
                   If None, loads all models.
            log_func: Function to call for logging (default: print)
        """
        if models is None:
            models = ['clip', 'blip', 'llava']

        log_func(f"Loading models on {self.device} ({self.dtype})...")
        initial_snapshot = self.resource_monitor.get_current()
        log_func(f"Initial resources: {initial_snapshot}")

        for model_name in models:
            if model_name in self._loaded:
                log_func(f"  {model_name}: already loaded")
                continue

            start = time.time()
            try:
                if model_name == 'clip':
                    self._load_clip()
                elif model_name == 'blip':
                    self._load_blip()
                elif model_name == 'llava':
                    self._load_llava()
                elif model_name == 'face':
                    self._load_face_detector()
                else:
                    log_func(f"  {model_name}: unknown model, skipping")
                    continue

                self._loaded.add(model_name)
                elapsed = time.time() - start
                snapshot = self.resource_monitor.get_current()
                log_func(f"  {model_name}: loaded in {elapsed:.1f}s | GPU: {snapshot.gpu_mb:.0f}MB")

            except Exception as e:
                log_func(f"  {model_name}: FAILED to load - {e}")

        final_snapshot = self.resource_monitor.get_current()
        log_func(f"All models loaded. Final resources: {final_snapshot}")

    def _load_clip(self):
        """Load CLIP model."""
        import clip
        model, preprocess = clip.load("ViT-B/32", device=self.device)
        self._models['clip'] = model
        self._processors['clip'] = preprocess

    def _load_blip(self):
        """Load BLIP model."""
        from transformers import BlipProcessor, BlipForConditionalGeneration
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            torch_dtype=self.dtype
        ).to(self.device)
        self._models['blip'] = model
        self._processors['blip'] = processor

    def _load_llava(self):
        """Load LLaVA OneVision model."""
        from transformers import AutoProcessor, AutoModelForVision2Seq
        MODEL_ID = "llava-hf/llava-onevision-qwen2-0.5b-ov-hf"
        processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModelForVision2Seq.from_pretrained(
            MODEL_ID,
            torch_dtype=self.dtype,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        ).to(self.device)
        self._models['llava'] = model
        self._processors['llava'] = processor

    def _load_face_detector(self):
        """Load face detector (dlib or alternative)."""
        try:
            import dlib
            detector = dlib.get_frontal_face_detector()
            self._models['face'] = detector
        except ImportError:
            # Fallback to opencv
            import cv2
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            detector = cv2.CascadeClassifier(cascade_path)
            self._models['face'] = detector

    def unload_models(self, models: List[str] = None):
        """Unload models from GPU memory."""
        if models is None:
            models = list(self._loaded)

        for model_name in models:
            if model_name in self._models:
                del self._models[model_name]
            if model_name in self._processors:
                del self._processors[model_name]
            self._loaded.discard(model_name)

        # Force garbage collection
        import gc
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to max size while preserving aspect ratio."""
        from PIL import ImageOps
        # Apply EXIF orientation
        image = ImageOps.exif_transpose(image)
        if max(image.size) > self.max_image_size:
            image.thumbnail((self.max_image_size, self.max_image_size), Image.Resampling.LANCZOS)
        return image

    def process_clip(self, image: Image.Image, concepts: List[str], top_k: int = 5, min_confidence: float = 0.05) -> List[str]:
        """Process image with CLIP and return top labels."""
        if 'clip' not in self._loaded:
            return []

        import clip
        model = self._models['clip']
        preprocess = self._processors['clip']

        img_tensor = preprocess(image).unsqueeze(0).to(self.device)
        text_tokens = clip.tokenize(concepts).to(self.device)

        with torch.no_grad():
            img_features = model.encode_image(img_tensor)
            txt_features = model.encode_text(text_tokens)
            img_features /= img_features.norm(dim=-1, keepdim=True)
            txt_features /= txt_features.norm(dim=-1, keepdim=True)
            similarity = (100.0 * img_features @ txt_features.T).softmax(dim=-1)

        topk = similarity[0].topk(min(top_k * 2, len(concepts)))
        top_indices = topk.indices.cpu().numpy()
        top_scores = topk.values.cpu().numpy()

        labels = []
        for idx, score in zip(top_indices, top_scores):
            if score >= min_confidence and len(labels) < top_k:
                labels.append(concepts[idx])
        return labels

    def process_blip(self, image: Image.Image, max_length: int = 60) -> str:
        """Generate caption using BLIP."""
        if 'blip' not in self._loaded:
            return ""

        model = self._models['blip']
        processor = self._processors['blip']

        inputs = processor(images=image, return_tensors="pt").to(self.device, self.dtype)

        with torch.no_grad():
            output = model.generate(**inputs, do_sample=True, top_k=50, max_length=max_length)

        caption = processor.decode(output[0], skip_special_tokens=True)
        return caption

    def process_llava(self, image: Image.Image, prompt: str = None, max_tokens: int = 256) -> str:
        """Generate detailed description using LLaVA."""
        if 'llava' not in self._loaded:
            return ""

        if prompt is None:
            prompt = "Describe this image in detail, covering subject, setting, lighting, and mood."

        model = self._models['llava']
        processor = self._processors['llava']

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
        inputs = processor(text=text_prompt, images=image, return_tensors="pt").to(self.device)

        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.1,
                do_sample=False
            )

        generated_text = processor.decode(output_ids[0], skip_special_tokens=True)
        if "assistant\n" in generated_text:
            generated_text = generated_text.split("assistant\n")[-1].strip()

        return generated_text

    def process_image_all(self, image_path: str, concepts: List[str] = None) -> Dict[str, Any]:
        """
        Process a single image through all loaded models.

        Returns:
            Dict with keys: 'clip_labels', 'blip_caption', 'llava_description', 'processing_time'
        """
        start = time.time()
        results = {
            'image_path': image_path,
            'clip_labels': [],
            'blip_caption': '',
            'llava_description': '',
            'error': None
        }

        try:
            image = Image.open(image_path).convert("RGB")
            image = self.resize_image(image)

            # Process through each loaded model
            if 'clip' in self._loaded and concepts:
                results['clip_labels'] = self.process_clip(image, concepts)

            if 'blip' in self._loaded:
                results['blip_caption'] = self.process_blip(image)

            if 'llava' in self._loaded:
                results['llava_description'] = self.process_llava(image)

        except Exception as e:
            results['error'] = str(e)

        results['processing_time'] = time.time() - start
        return results

    def process_batch(
        self,
        image_paths: List[str],
        concepts: List[str] = None,
        models_to_use: List[str] = None,
        callback: Callable = None,
        log_func: Callable = print
    ) -> Tuple[List[Dict[str, Any]], ProcessingStats]:
        """
        Process a batch of images through all specified models.

        Args:
            image_paths: List of image file paths
            concepts: CLIP concepts for labeling
            models_to_use: Which models to use (default: all loaded)
            callback: Called after each image with (index, total, result)
            log_func: Logging function

        Returns:
            Tuple of (results list, processing stats)
        """
        if models_to_use is None:
            models_to_use = list(self._loaded)

        self.stats = ProcessingStats(
            total_images=len(image_paths),
            start_time=time.time()
        )

        # Start resource monitoring
        self.resource_monitor.start()

        results = []
        log_func(f"Processing {len(image_paths)} images through models: {models_to_use}")

        for i, img_path in enumerate(image_paths, 1):
            try:
                image = Image.open(img_path).convert("RGB")
                image = self.resize_image(image)

                result = {
                    'image_path': img_path,
                    'filename': os.path.basename(img_path),
                    'clip_labels': [],
                    'blip_caption': '',
                    'llava_description': '',
                    'error': None
                }

                img_start = time.time()

                # Run models sequentially on same image (GPU memory efficient)
                if 'clip' in models_to_use and 'clip' in self._loaded and concepts:
                    result['clip_labels'] = self.process_clip(image, concepts)

                if 'blip' in models_to_use and 'blip' in self._loaded:
                    result['blip_caption'] = self.process_blip(image)

                if 'llava' in models_to_use and 'llava' in self._loaded:
                    result['llava_description'] = self.process_llava(image)

                result['processing_time'] = time.time() - img_start
                results.append(result)
                self.stats.processed_images += 1

                if callback:
                    callback(i, len(image_paths), result)

                # Log progress every 5 images
                if i % 5 == 0 or i == len(image_paths):
                    snapshot = self.resource_monitor.get_current()
                    log_func(f"  [{i}/{len(image_paths)}] {snapshot} | {self.stats.images_per_second:.2f} img/s")

            except Exception as e:
                results.append({
                    'image_path': img_path,
                    'filename': os.path.basename(img_path),
                    'error': str(e)
                })
                self.stats.failed_images += 1
                log_func(f"  [{i}/{len(image_paths)}] FAILED: {os.path.basename(img_path)} - {e}")

        # Stop monitoring and collect stats
        self.stats.end_time = time.time()
        self.stats.resource_snapshots = self.resource_monitor.stop()

        # Log final stats
        peak = self.stats.peak_resources()
        log_func(f"\nProcessing complete:")
        log_func(f"  Total time: {self.stats.elapsed_time:.1f}s")
        log_func(f"  Images processed: {self.stats.processed_images}/{self.stats.total_images}")
        log_func(f"  Failed: {self.stats.failed_images}")
        log_func(f"  Avg time/image: {self.stats.avg_time_per_image:.2f}s")
        log_func(f"  Throughput: {self.stats.images_per_second:.2f} img/s")
        if peak:
            log_func(f"  Peak GPU memory: {peak.gpu_mb:.0f}MB ({peak.gpu_percent:.1f}%)")

        return results, self.stats


# Singleton instance for reuse
_manager_instance: Optional[GPUModelManager] = None


def get_manager(device: str = None, max_image_size: int = 1024) -> GPUModelManager:
    """Get or create the singleton GPU model manager."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = GPUModelManager(device, max_image_size)
    return _manager_instance


if __name__ == "__main__":
    # Test the manager
    manager = GPUModelManager()

    print("Testing GPU Model Manager...")
    snapshot = manager.resource_monitor.get_current()
    print(f"Current resources: {snapshot}")

    # Load models
    manager.load_models(['clip', 'blip'])

    # Test with a sample image if available
    import glob
    test_images = glob.glob("data/trips/*/MemoGraph/thumbnails/*.jpg")[:3]
    if test_images:
        concepts = ["mountain", "beach", "city", "forest", "person", "animal", "building"]
        results, stats = manager.process_batch(test_images, concepts)
        for r in results:
            print(f"\n{r['filename']}:")
            print(f"  CLIP: {r['clip_labels']}")
            print(f"  BLIP: {r['blip_caption']}")

    manager.unload_models()
    print("\nTest complete.")
