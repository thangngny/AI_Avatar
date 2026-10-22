import os
import sys
import time
import shutil

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
from huggingface_hub import hf_hub_download

staging_dir = r"D:\CongThang_AI_Avatar\staging_weights\SoulX-FlashHead-1_3B"
final_dir = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B"
os.makedirs(staging_dir, exist_ok=True)
os.makedirs(final_dir, exist_ok=True)

EXPECTED_SIZE = 6030864656
final_file = os.path.join(final_dir, "Model_Pro", "diffusion_pytorch_model.safetensors")

if os.path.exists(final_file) and os.path.getsize(final_file) == EXPECTED_SIZE:
    print(f"[EXISTS] SoulX Pro weights already complete at {final_file} ({EXPECTED_SIZE} bytes)")
    sys.exit(0)

print("=" * 60)
print("STARTING SOULX-FLASHHEAD MODEL_PRO WEIGHT DOWNLOAD")
print(f"Target size: {EXPECTED_SIZE} bytes ({EXPECTED_SIZE / (1024*1024):.2f} MB)")
print("=" * 60, flush=True)

t0 = time.time()
try:
    downloaded_path = hf_hub_download(
        repo_id="Soul-AILab/SoulX-FlashHead-1_3B",
        filename="Model_Pro/diffusion_pytorch_model.safetensors",
        local_dir=staging_dir
    )
    dt = time.time() - t0
    actual_sz = os.path.getsize(downloaded_path)
    print(f"\n[DOWNLOAD COMPLETE] Downloaded {actual_sz} bytes in {dt:.2f}s ({actual_sz/(1024*1024)/dt:.2f} MB/s)", flush=True)

    if actual_sz == EXPECTED_SIZE:
        print(f"Size verified! Copying to final destination {final_file} ...", flush=True)
        os.makedirs(os.path.dirname(final_file), exist_ok=True)
        shutil.copy2(downloaded_path, final_file)
        print("[SUCCESS] SoulX-FlashHead Model_Pro is 100% staged and ready for inference!")
    else:
        print(f"[ERROR] Size mismatch: got {actual_sz}, expected {EXPECTED_SIZE}")
except Exception as e:
    print(f"\n[ERROR] Download encountered exception: {e}", flush=True)
