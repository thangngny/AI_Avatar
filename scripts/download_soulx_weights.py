"""
AI Avatar NextGen V2 - Model Weights Downloader for SoulX-FlashHead
Downloads official checkpoints from Hugging Face into isolated V2 weights directory.
"""
import os
import sys
import time
from huggingface_hub import hf_hub_download, snapshot_download

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

WEIGHTS_DIR = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights"
SOULX_DIR = os.path.join(WEIGHTS_DIR, "SoulX-FlashHead-1_3B")
WAV2VEC_DIR = os.path.join(WEIGHTS_DIR, "wav2vec2-base-960h")
os.makedirs(SOULX_DIR, exist_ok=True)
os.makedirs(WAV2VEC_DIR, exist_ok=True)


def download_soulx():
    print(f"\n=======================================================")
    print(f"DOWNLOADING SOULX-FLASHHEAD MODEL CHECKPOINTS")
    print(f"Target: {SOULX_DIR}")
    print(f"=======================================================")

    files = [
        "config.json",
        "model_index.json",
        "Model_Pro/config.json",
        "Model_Pro/diffusion_pytorch_model.safetensors",
        "VAE_Wan/Wan2.1_VAE.pth"
    ]

    for rel_path in files:
        dst = os.path.join(SOULX_DIR, rel_path)
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            print(f"[EXISTS] {rel_path} ({os.path.getsize(dst)/(1024*1024):.1f} MB)")
            continue
        print(f"[DOWNLOADING] {rel_path} from Soul-AILab/SoulX-FlashHead-1_3B...")
        t0 = time.time()
        p = hf_hub_download(
            repo_id="Soul-AILab/SoulX-FlashHead-1_3B",
            filename=rel_path,
            local_dir=SOULX_DIR,
            local_dir_use_symlinks=False
        )
        dt = time.time() - t0
        sz = os.path.getsize(p) / (1024 * 1024)
        print(f"[DONE] {rel_path}: {sz:.1f} MB in {dt:.1f}s ({sz/dt:.1f} MB/s)")

    print(f"\n=======================================================")
    print(f"DOWNLOADING WAV2VEC2-BASE-960H CHECKPOINTS")
    print(f"Target: {WAV2VEC_DIR}")
    print(f"=======================================================")

    w2v_files = [
        "config.json",
        "preprocessor_config.json",
        "pytorch_model.bin"
    ]

    for rel_path in w2v_files:
        dst = os.path.join(WAV2VEC_DIR, rel_path)
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            print(f"[EXISTS] {rel_path} ({os.path.getsize(dst)/(1024*1024):.1f} MB)")
            continue
        print(f"[DOWNLOADING] {rel_path} from facebook/wav2vec2-base-960h...")
        t0 = time.time()
        p = hf_hub_download(
            repo_id="facebook/wav2vec2-base-960h",
            filename=rel_path,
            local_dir=WAV2VEC_DIR,
            local_dir_use_symlinks=False
        )
        dt = time.time() - t0
        sz = os.path.getsize(p) / (1024 * 1024)
        print(f"[DONE] {rel_path}: {sz:.1f} MB in {dt:.1f}s ({sz/dt:.1f} MB/s)")

    print("\nALL WEIGHTS DOWNLOADED SUCCESSFULLY!")


if __name__ == "__main__":
    download_soulx()
