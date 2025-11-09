#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resource_monitor.py

A simple script to monitor CPU, RAM, and GPU usage for a given process ID.
"""

import os
import sys
import time
import psutil
import subprocess
import threading

class ResourceMonitor(threading.Thread):
    def __init__(self, pid, log_file):
        super().__init__()
        self.pid = pid
        self.log_file = log_file
        self.should_stop = threading.Event()

    def get_gpu_memory_usage(self):
        """Returns the GPU memory usage in MB."""
        try:
            result = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits']
            )
            return float(result.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 0.0

    def run(self):
        """Monitors the resource usage of a process and its children."""
        try:
            parent = psutil.Process(self.pid)
            with open(self.log_file, "w") as f:
                f.write("timestamp,cpu_percent,ram_mb,gpu_mb\n")
                while not self.should_stop.is_set() and parent.is_running():
                    cpu_percent = parent.cpu_percent(interval=1)
                    ram_mb = parent.memory_info().rss / (1024 * 1024)
                    
                    # Include children processes
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            cpu_percent += child.cpu_percent(interval=None)
                            ram_mb += child.memory_info().rss / (1024 * 1024)
                        except psutil.NoSuchProcess:
                            continue

                    gpu_mb = self.get_gpu_memory_usage()
                    
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{timestamp},{cpu_percent},{ram_mb},{gpu_mb}\n")
                    f.flush()
                    time.sleep(1)
        except psutil.NoSuchProcess:
            pass

    def stop(self):
        self.should_stop.set()

