import os
import sys
import time
import torch
import numpy as np

# Ensure NextGen workspace
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

print("=" * 60)
print("   NEXTGEN RTX 5090 BLACKWELL BENCHMARK & TEST")
print("=" * 60)
print(f"PyTorch: {torch.__version__} | GPU: {torch.cuda.get_device_name(0)}")
print(f"Total VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")

from utils.device import initialize_device
from avatars.musetalk.utils.utils import load_all_model

device = initialize_device()
vae, unet, pe = load_all_model()

# Set to half precision for Blackwell Tensor Cores
unet.model = unet.model.to(device=device, dtype=torch.float16)
pe = pe.to(device=device, dtype=torch.float16)
dtype = torch.float16

BATCH_SIZES = [16, 32, 48, 64]

print("\n--- 1. BENCHMARKING BATCH SIZES ON RTX 5090 ---")
for bs in BATCH_SIZES:
    static_audio = torch.zeros((bs, 50, 384), device=device, dtype=dtype)
    static_latent = torch.zeros((bs, 8, 32, 32), device=device, dtype=dtype)
    static_ts = torch.zeros((bs,), device=device, dtype=torch.long)
    
    # Warmup
    with torch.no_grad():
        for _ in range(3):
            emb = pe(static_audio)
            _ = unet.model(static_latent, static_ts, encoder_hidden_states=emb, return_dict=False)[0]
    
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    ITERS = 20
    with torch.no_grad():
        for _ in range(ITERS):
            emb = pe(static_audio)
            _ = unet.model(static_latent, static_ts, encoder_hidden_states=emb, return_dict=False)[0]
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    total_frames = bs * ITERS
    fps = total_frames / elapsed
    vram_alloc = torch.cuda.memory_allocated() / (1024**2)
    vram_reserved = torch.cuda.memory_reserved() / (1024**2)
    print(f"Batch Size {bs:2d}: {fps:6.1f} FPS | {total_frames:4d} frames in {elapsed:.3f}s | VRAM: {vram_alloc:.1f} MB (Reserved: {vram_reserved:.1f} MB)")

print("\n[SUCCESS] Benchmark complete!")
