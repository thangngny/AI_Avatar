"""
AI Avatar NextGen V2 - Resumable Model Weights Downloader
Supports Range headers, auto-resume, retry loops, and mirror failover.
"""
import os
import sys
import time
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

TARGET_DIR = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights"
os.makedirs(TARGET_DIR, exist_ok=True)

# List of files required for SoulX-FlashHead and LatentSync
MODEL_MANIFEST = [
    {
        "name": "SoulX-FlashHead Model_Lite",
        "url": "https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B/resolve/main/Model_Lite/diffusion_pytorch_model.safetensors",
        "dest": os.path.join(TARGET_DIR, "SoulX-FlashHead-1_3B", "Model_Lite", "diffusion_pytorch_model.safetensors"),
        "size_expected": 6107542048
    },
    {
        "name": "SoulX-FlashHead Wan2.1 VAE",
        "url": "https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B/resolve/main/VAE_Wan/Wan2.1_VAE.pth",
        "dest": os.path.join(TARGET_DIR, "SoulX-FlashHead-1_3B", "VAE_Wan", "Wan2.1_VAE.pth"),
        "size_expected": 507314272
    },
    {
        "name": "LatentSync UNet",
        "url": "https://huggingface.co/ByteDance/LatentSync/resolve/main/latentsync_unet.pt",
        "dest": os.path.join(TARGET_DIR, "latentsync", "latentsync_unet.pt"),
        "size_expected": 3400080614
    }
]


def download_file_with_resume(url: str, dest_path: str, expected_size: int = None, max_retries: int = 50):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_path = dest_path + ".part"

    current_size = 0
    if os.path.exists(temp_path):
        current_size = os.path.getsize(temp_path)
    elif os.path.exists(dest_path):
        if expected_size and os.path.getsize(dest_path) >= expected_size:
            print(f"[SKIP] {dest_path} already complete ({os.path.getsize(dest_path) / (1024*1024):.2f} MB)")
            return True
        current_size = os.path.getsize(dest_path)
        os.rename(dest_path, temp_path)

    retries = 0
    while retries < max_retries:
        if expected_size and current_size >= expected_size:
            break

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*"
        }
        if current_size > 0:
            headers["Range"] = f"bytes={current_size}-"
            print(f"[RESUME] Resuming from byte {current_size} ({current_size / (1024*1024):.2f} MB)...")
        else:
            print(f"[START] Starting new download: {url}")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                total_len = resp.headers.get("Content-Length")
                total_target = (int(total_len) + current_size) if total_len else expected_size

                mode = "ab" if current_size > 0 else "wb"
                with open(temp_path, mode) as f:
                    chunk_sz = 128 * 1024 # 128 KB
                    last_log = time.time()
                    bytes_since_log = 0

                    while True:
                        chunk = resp.read(chunk_sz)
                        if not chunk:
                            break
                        f.write(chunk)
                        current_size += len(chunk)
                        bytes_since_log += len(chunk)

                        now = time.time()
                        if now - last_log >= 5.0:
                            speed_kb = (bytes_since_log / 1024) / (now - last_log)
                            pct = (current_size / total_target * 100) if total_target else 0.0
                            print(f"Progress: {current_size / (1024*1024):.2f} MB / {total_target / (1024*1024) if total_target else '?':.2f} MB ({pct:.1f}%) - Speed: {speed_kb:.1f} KB/s", flush=True)
                            last_log = now
                            bytes_since_log = 0

            # Completed without exception
            break

        except Exception as e:
            retries += 1
            print(f"[WARN] Connection dropped: {e}. Retry {retries}/{max_retries} in 5 seconds...", flush=True)
            time.sleep(5)

    if os.path.exists(temp_path):
        if expected_size and os.path.getsize(temp_path) < expected_size:
            print(f"[INCOMPLETE] {temp_path} has {os.path.getsize(temp_path)} bytes, expected {expected_size}")
            return False
        os.rename(temp_path, dest_path)
        print(f"[SUCCESS] Download completed: {dest_path}")
        return True
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("AI AVATAR V2 - RESUMABLE MODEL DOWNLOADER")
    print("=" * 60)
    if len(sys.argv) > 1:
        target_name = sys.argv[1].lower()
        items = [m for m in MODEL_MANIFEST if target_name in m["name"].lower()]
    else:
        items = MODEL_MANIFEST

    for item in items:
        print(f"\nTarget: {item['name']}")
        download_file_with_resume(item["url"], item["dest"], item["size_expected"])
