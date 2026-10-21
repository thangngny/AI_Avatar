#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — Automated Cloud Asset Downloader.

Downloads all AI model weights (from official HuggingFace / PyTorch CDNs)
and pre-computed avatar assets (from GitHub Releases) so the workstation is
100% ready to render without manual file copying.

Usage:
    python tools/download_cloud_assets.py
    python tools/download_cloud_assets.py --models-only
    python tools/download_cloud_assets.py --avatars-only
"""
import os
import sys
import time
import json
import zipfile
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_REPO = "thangngny/AI_Avatar"
RELEASE_TAG = "v1.5.0-assets"

# Official open-source weights distribution (fast global CDN, no credentials needed)
MODEL_URLS = [
    # MuseTalk v1.5 UNet
    ("models/musetalkV15/unet.pth", "https://huggingface.co/TMElyralab/MuseTalk/resolve/main/musetalkV15/unet.pth"),
    ("models/musetalkV15/musetalk.json", "https://huggingface.co/TMElyralab/MuseTalk/resolve/main/musetalkV15/musetalk.json"),
    
    # SD-VAE
    ("models/sd-vae/diffusion_pytorch_model.bin", "https://huggingface.co/stabilityai/sd-vae-ft-mse/resolve/main/diffusion_pytorch_model.bin"),
    ("models/sd-vae/config.json", "https://huggingface.co/stabilityai/sd-vae-ft-mse/resolve/main/config.json"),

    # Whisper Tiny
    ("models/whisper/pytorch_model.bin", "https://huggingface.co/openai/whisper-tiny/resolve/main/pytorch_model.bin"),
    ("models/whisper/config.json", "https://huggingface.co/openai/whisper-tiny/resolve/main/config.json"),
    ("models/whisper/preprocessor_config.json", "https://huggingface.co/openai/whisper-tiny/resolve/main/preprocessor_config.json"),

    # Face Parsing BiSeNet
    ("models/face-parse-bisent/79999_iter.pth", "https://huggingface.co/TMElyralab/MuseTalk/resolve/main/face-parse-bisent/79999_iter.pth"),
    ("models/face-parse-bisent/resnet18-5c106cde.pth", "https://download.pytorch.org/models/resnet18-5c106cde.pth"),

    # DWPose
    ("models/dwpose/dw-ll_ucoco_384.pth", "https://huggingface.co/yisol/IDM-VTON/resolve/main/densepose/dw-ll_ucoco_384.pth"),
]

def format_bytes(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PB"

def format_time(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def download_http_with_progress(url, dest_path, desc=""):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    temp_path = dest_path + ".tmp"

    resume_pos = 0
    if os.path.isfile(temp_path):
        resume_pos = os.path.getsize(temp_path)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    if resume_pos > 0:
        req.add_header("Range", f"bytes={resume_pos}-")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = resp.headers.get("Content-Length")
            total_size = int(total_size) + resume_pos if total_size else None

            mode = "ab" if resume_pos > 0 else "wb"
            chunk_sz = 1024 * 1024
            downloaded = resume_pos
            start_t = time.time()
            last_t = 0

            with open(temp_path, mode) as f:
                while True:
                    chunk = resp.read(chunk_sz)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_t > 0.25:
                        last_t = now
                        elapsed = now - start_t
                        speed = (downloaded - resume_pos) / elapsed if elapsed > 0.5 else 0
                        pct = (downloaded / total_size * 100) if total_size else 0
                        eta = (total_size - downloaded) / speed if (total_size and speed > 1024) else 0

                        bar_len = 20
                        filled = int(bar_len * pct / 100)
                        bar = "=" * filled + (">" if filled < bar_len else "") + " " * (bar_len - filled - 1)
                        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}% | {format_bytes(downloaded)}/{format_bytes(total_size or 0)} | {format_bytes(speed)}/s | ETA: {format_time(eta):<8} | {desc}")
                        sys.stdout.flush()

        # Rename temp to target
        if os.path.isfile(dest_path):
            os.remove(dest_path)
        shutil.move(temp_path, dest_path)
        sys.stdout.write(f"\r  [OK] Đã tải xong: {desc} ({format_bytes(os.path.getsize(dest_path))}){' ' * 30}\n")
        sys.stdout.flush()
        return True
    except Exception as e:
        sys.stdout.write(f"\n  [!] Lỗi khi tải {desc}: {e}\n")
        return False

def sync_models():
    print("\n" + "=" * 66)
    print(" [1/2] ĐỒNG BỘ AI MODEL WEIGHTS (HUGGING FACE / PYTORCH CDN)")
    print("=" * 66)

    for rel_p, url in MODEL_URLS:
        dst = os.path.join(ROOT, rel_p.replace("/", os.sep))
        name = os.path.basename(rel_p)
        if os.path.isfile(dst) and os.path.getsize(dst) > 1000:
            print(f"  [BỎ QUA - ĐÃ CÓ] {rel_p} ({format_bytes(os.path.getsize(dst))})")
            continue

        print(f"\n---> Đang tải: {rel_p}...")
        download_http_with_progress(url, dst, desc=name)

def sync_avatars():
    print("\n" + "=" * 66)
    print(" [2/2] ĐỒNG BỘ AVATAR ASSETS (GITHUB RELEASES)")
    print("=" * 66)

    dist_dir = os.path.join(ROOT, "dist_assets")
    os.makedirs(dist_dir, exist_ok=True)

    # Check if gh CLI is available
    has_gh = shutil.which("gh") is not None
    if has_gh:
        print(f"[*] Sử dụng GitHub CLI (gh) để tải release {RELEASE_TAG}...")
        cmd = ["gh", "release", "download", RELEASE_TAG, "--repo", GITHUB_REPO, "--dir", dist_dir, "--clobber"]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[!] 'gh release download' trả về mã lỗi {res.returncode}. Thử tải dự phòng...")
    else:
        print("[*] GitHub CLI chưa được cài đặt. Đang kiểm tra release assets...")

    # Extract all downloaded zips
    zips = [f for f in os.listdir(dist_dir) if f.endswith(".zip")]
    if not zips:
        print("[!] Chưa tìm thấy tệp zip nào trong dist_assets để giải nén.")
        return

    for zfn in zips:
        zp = os.path.join(dist_dir, zfn)
        print(f"\n---> Đang giải nén: {zfn} ({format_bytes(os.path.getsize(zp))})...")
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                if "avatar_doTrang" in zfn or "avatar_mc_hamai" in zfn:
                    target = os.path.join(ROOT, "data", "avatars")
                elif "avatar_sources_and_inputs" in zfn:
                    target = os.path.join(ROOT, "data")
                elif "avatar_configs" in zfn:
                    target = os.path.join(ROOT)
                else:
                    target = ROOT
                os.makedirs(target, exist_ok=True)
                zf.extractall(target)
            print(f"  [OK] Đã giải nén vào {target}")
        except Exception as e:
            print(f"  [!] Lỗi giải nén {zfn}: {e}")

def verify_system():
    print("\n" + "=" * 66)
    print(" KIỂM ĐỊNH TÍNH SẴN SÀNG HỆ THỐNG")
    print("=" * 66)
    checks = [
        ("MuseTalk v1.5 UNet", os.path.join(ROOT, "models", "musetalkV15", "unet.pth")),
        ("Whisper Tiny", os.path.join(ROOT, "models", "whisper", "pytorch_model.bin")),
        ("Stable Diffusion VAE", os.path.join(ROOT, "models", "sd-vae", "diffusion_pytorch_model.bin")),
        ("Face Parse BiSeNet", os.path.join(ROOT, "models", "face-parse-bisent", "79999_iter.pth")),
        ("Avatar doTrang_closeup (avator_info.json)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "avator_info.json")),
        ("Avatar doTrang_closeup (latents.pt)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "latents.pt")),
        ("Avatar doTrang_closeup (coords.pkl)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "coords.pkl")),
    ]
    all_ok = True
    for name, path in checks:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print(f"  [OK] {name}: {format_bytes(os.path.getsize(path))}")
        else:
            print(f"  [THIẾU] {name} tại {path}")
            all_ok = False

    print("-" * 66)
    if all_ok:
        print("🎉 TẤT CẢ DỮ LIỆU ĐÃ SẴN SÀNG 100%!")
        print("Bây giờ bạn có thể chạy kiểm tra End-to-End trên máy mới:")
        print("    ..\\runtime\\venv\\Scripts\\python.exe tests/e2e_mouth_test.py")
    else:
        print("[!] Vẫn còn một số tệp bị thiếu. Hãy kiểm tra kết nối mạng và thử lại.")
    print("=" * 66)

def main():
    parser = argparse.ArgumentParser(description="Tự động tải toàn bộ Models & Avatars từ Cloud.")
    parser.add_argument("--models-only", action="store_true", help="Chỉ tải AI models")
    parser.add_argument("--avatars-only", action="store_true", help="Chỉ tải Avatars")
    args = parser.parse_args()

    print("=" * 66)
    print("   AI AVATAR STUDIO — AUTOMATED CLOUD ASSET DOWNLOADER")
    print("=" * 66)
    print(f"[*] Thư mục đích: {ROOT}")

    if not args.avatars_only:
        sync_models()

    if not args.models_only:
        sync_avatars()

    verify_system()

if __name__ == "__main__":
    main()
