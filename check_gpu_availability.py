# check_gpu_availability.py
import torch
print(torch.cuda.is_available())