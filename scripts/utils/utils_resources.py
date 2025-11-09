#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils_resources.py

Provides utility functions for checking system resources like CPU, RAM, and GPU memory.
This helps in preventing crashes by ensuring sufficient resources are available before
running intensive tasks.
"""

import psutil
import torch
from .utils_log import get_logger

logger = get_logger(__name__)

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except (ImportError, pynvml.NVMLError):
    NVML_AVAILABLE = False

def get_cpu_info():
    """Returns the number of logical CPU cores and current system-wide CPU usage."""
    cores = psutil.cpu_count(logical=True)
    usage = psutil.cpu_percent(interval=1)
    return {"cores": cores, "usage_percent": usage}

def get_ram_info():
    """Returns the available RAM in MB."""
    memory = psutil.virtual_memory()
    return {"available_mb": memory.available / (1024 * 1024)}

def get_gpu_info():
    """
    Returns information about available GPU resources.
    Uses pynvml for NVIDIA GPUs if available, otherwise falls back to torch.
    """
    if not torch.cuda.is_available():
        return {"gpus": [], "error": "PyTorch reports no CUDA-enabled GPU."}

    if not NVML_AVAILABLE:
        logger.warning("pynvml not available. GPU memory check will be less precise.")
        # Fallback if pynvml is not installed - can't check memory accurately
        gpu_count = torch.cuda.device_count()
        gpus = [{"id": i, "name": torch.cuda.get_device_name(i)} for i in range(gpu_count)]
        return {"gpus": gpus, "warning": "Cannot read available memory without pynvml."}

    try:
        gpu_count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append({
                "id": i,
                "name": pynvml.nvmlDeviceGetName(handle),
                "free_mb": mem_info.free / (1024 * 1024),
                "total_mb": mem_info.total / (1024 * 1024),
            })
        return {"gpus": gpus}
    except pynvml.NVMLError as e:
        return {"gpus": [], "error": f"Failed to query GPU with pynvml: {e}"}

def check_resources(min_ram_mb=2048, min_gpu_mb=4096):
    """
    Checks if the system meets minimum resource requirements.
    Returns True if resources are sufficient, False otherwise.
    """
    logger.info("Checking system resources...")
    
    # Check RAM
    ram_info = get_ram_info()
    if ram_info["available_mb"] < min_ram_mb:
        logger.error(f"Insufficient RAM: {ram_info['available_mb']:.2f}MB available, but {min_ram_mb}MB required.")
        return False
    logger.info(f"RAM check OK: {ram_info['available_mb']:.2f}MB available.")

    # Check GPU
    if torch.cuda.is_available() and NVML_AVAILABLE:
        gpu_info = get_gpu_info()
        if "error" in gpu_info:
            logger.error(f"GPU check failed: {gpu_info['error']}")
            return False
        
        if not gpu_info["gpus"]:
            logger.warning("No GPUs found by pynvml, skipping GPU memory check.")
            return True

        # For simplicity, we check the first GPU. A more complex setup could check all.
        gpu = gpu_info["gpus"][0]
        if gpu["free_mb"] < min_gpu_mb:
            logger.error(f"Insufficient GPU Memory on GPU {gpu['id']} ({gpu['name']}): {gpu['free_mb']:.2f}MB free, but {min_gpu_mb}MB required.")
            return False
        logger.info(f"GPU check OK: {gpu['free_mb']:.2f}MB free on GPU {gpu['id']} ({gpu['name']}).")

    elif torch.cuda.is_available():
        logger.warning("pynvml is not installed. Cannot verify available GPU memory. Proceeding with caution.")
    
    else:
        logger.info("No CUDA-enabled GPU detected. Skipping GPU checks.")

    return True

if __name__ == '__main__':
    print("--- System Resource Info ---")
    print("CPU:", get_cpu_info())
    print("RAM:", get_ram_info())
    print("GPU:", get_gpu_info())
    
    # Example check
    check_resources(min_ram_mb=1024, min_gpu_mb=2048)
