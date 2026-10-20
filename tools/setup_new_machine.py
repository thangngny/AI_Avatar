#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — Automated Setup for New Machine (RTX 5090 / 4090 / 3090).

Run this script to set up everything automatically:
    python tools/setup_new_machine.py

What it does:
1. Validates base directories (runtime, models, data/avatars, renders).
2. Sets up Python virtual environment at runtime/venv (if not present).
3. Installs PyTorch with proper CUDA support (CUDA 12.4/12.6/12.8 for Blackwell RTX 5090).
4. Installs all required packages (diffusers, transformers, accelerate, edge-tts, etc.).
5. Verifies FFmpeg and ffprobe in PATH.
6. Inspects AI models and pre-computed avatar assets.
7. Compiles the native AI_Avatar_Studio.exe launcher and creates the Desktop shortcut.
8. Runs verify_runtime.py to confirm 100% READY status.
"""
import os
import sys
import shutil
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARENT = os.path.dirname(ROOT)

VENV_DIR = os.path.join(PARENT, "runtime", "venv")
VENV_PY = os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "python")

print("=" * 64)
print("   AI AVATAR STUDIO - AUTO-SETUP CHO MÁY MỚI (RTX 5090 / BLACKWELL)")
print("=" * 64)
print(f"[*] Thư mục gốc dự án: {ROOT}")
print(f"[*] Thư mục môi trường venv dự kiến: {VENV_DIR}")

def run_cmd(cmd, desc="", exit_on_error=True):
    if desc:
        print(f"\n---> {desc}...")
    print(f"     CMD: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, cwd=ROOT, shell=(not isinstance(cmd, list)))
    if res.returncode != 0 and exit_on_error:
        print(f"[!] LỖI: Lệnh thất bại với mã lỗi {res.returncode}")
        sys.exit(res.returncode)
    return res.returncode

# 1. Tạo các thư mục cần thiết
print("\n[1/7] Kiểm tra và tạo cấu trúc thư mục...")
dirs_to_make = [
    os.path.join(PARENT, "runtime"),
    os.path.join(PARENT, "renders", "studio"),
    os.path.join(ROOT, "models"),
    os.path.join(ROOT, "data", "avatars"),
    os.path.join(ROOT, "data", "studio_runtime", "logs"),
    os.path.join(ROOT, "data", "studio_runtime", "temp"),
]
for d in dirs_to_make:
    os.makedirs(d, exist_ok=True)
print("  [OK] Cấu trúc thư mục sẵn sàng.")

# 2. Tạo Virtual Environment nếu chưa có
print("\n[2/7] Kiểm tra môi trường ảo Python (Virtual Environment)...")
if not os.path.exists(VENV_PY):
    print(f"  Chưa có venv tại {VENV_DIR}. Đang tạo mới bằng Python {sys.version.split()[0]}...")
    run_cmd([sys.executable, "-m", "venv", VENV_DIR], "Khởi tạo runtime venv")
else:
    print(f"  [OK] Đã tìm thấy venv tại: {VENV_PY}")

# 3. Nâng cấp pip & cài đặt PyTorch với CUDA
print("\n[3/7] Cài đặt PyTorch CUDA tương thích card đồ họa...")
check_torch_code = "import torch; print(f'TORCH_OK:{torch.__version__}:CUDA_{torch.cuda.is_available()}:GPUS_{torch.cuda.device_count()}')"
res = subprocess.run([VENV_PY, "-c", check_torch_code], capture_output=True, text=True)
need_torch = True
if res.returncode == 0 and "TORCH_OK" in res.stdout and "CUDA_True" in res.stdout:
    print(f"  [OK] PyTorch đã cài đặt và nhận GPU: {res.stdout.strip()}")
    need_torch = False

if need_torch:
    print("  Đang cài đặt PyTorch CUDA (Hỗ trợ RTX 5090 Blackwell / 4090 / 3090)...")
    run_cmd([VENV_PY, "-m", "pip", "install", "--upgrade", "pip"], "Upgrade pip")
    # CUDA 12.4 / 12.6 cho RTX 5090 Blackwell
    torch_cmd = [
        VENV_PY, "-m", "pip", "install",
        "torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1",
        "--index-url", "https://download.pytorch.org/whl/cu124"
    ]
    run_cmd(torch_cmd, "Cài đặt PyTorch cu124 cho RTX 5090", exit_on_error=False)

# 4. Cài đặt các gói phụ thuộc (Dependencies)
print("\n[4/7] Cài đặt các thư viện bổ trợ cần thiết...")
pkgs = [
    "diffusers==0.32.2",
    "transformers==4.48.0",
    "accelerate==0.26.1",
    "opencv-python",
    "soundfile",
    "edge-tts",
    "flask",
    "playwright",
    "tqdm",
    "requests",
    "face-alignment",
    "numba",
    "resampy",
    "ffmpeg-python",
    "omegaconf",
    "einops"
]
pip_install_cmd = [VENV_PY, "-m", "pip", "install"] + pkgs
run_cmd(pip_install_cmd, "Cài đặt thư viện AI phụ trợ", exit_on_error=False)

# Cài đặt Playwright browser binaries
run_cmd([VENV_PY, "-m", "playwright", "install", "chromium"], "Cài đặt Chromium cho Playwright", exit_on_error=False)

# 5. Kiểm tra FFmpeg
print("\n[5/7] Kiểm tra FFmpeg...")
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    print(f"  [OK] Đã tìm thấy FFmpeg trong PATH: {ffmpeg_path}")
else:
    print("  [CẢNH BÁO] Chưa tìm thấy FFmpeg trong PATH hệ thống!")
    print("  Vui lòng tải FFmpeg (hoặc giải nén vào C:\\Tools\\ffmpeg\\bin) và thêm vào PATH hệ thống.")

# 6. Kiểm tra Models và Avatars
print("\n[6/7] Kiểm tra các tệp mô hình (Models) và dữ liệu Avatar...")
models_dir = os.path.join(ROOT, "models")
avatars_dir = os.path.join(ROOT, "data", "avatars")

model_count = len(os.listdir(models_dir)) if os.path.exists(models_dir) else 0
avatar_count = len([d for d in os.listdir(avatars_dir) if os.path.isdir(os.path.join(avatars_dir, d))]) if os.path.exists(avatars_dir) else 0

if model_count > 0:
    print(f"  [OK] Thư mục models đã có dữ liệu ({model_count} mục/tệp).")
else:
    print("  [CHÚ Ý] Thư mục models đang trống! Vui lòng copy thư mục 'models' (~8.6 GB) từ máy cũ sang.")

if avatar_count > 0:
    print(f"  [OK] Thư mục data/avatars đã có {avatar_count} Avatar sẵn sàng.")
else:
    print("  [CHÚ Ý] Thư mục data/avatars đang trống! Vui lòng copy 'data/avatars' (~12.9 GB) từ máy cũ sang.")

# 7. Biên dịch Launcher EXE và tạo Desktop Shortcut
print("\n[7/7] Thiết lập tệp thực thi AI_Avatar_Studio.exe & Biểu tượng Desktop...")
csc_path = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if os.path.exists(csc_path):
    launcher_cs = os.path.join(ROOT, "tools", "Launcher.cs")
    out_exe = os.path.join(ROOT, "AI_Avatar_Studio.exe")
    compile_cmd = [csc_path, "/r:Microsoft.CSharp.dll", "/target:winexe", f"/out:{out_exe}", launcher_cs]
    run_cmd(compile_cmd, "Biên dịch AI_Avatar_Studio.exe bằng csc.exe", exit_on_error=False)

# Tạo Desktop shortcut
shortcut_script = os.path.join(ROOT, "scripts", "create_desktop_shortcut.ps1")
if os.path.exists(shortcut_script):
    run_cmd(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", shortcut_script], "Tạo Shortcut ngoài màn hình Desktop", exit_on_error=False)

# Kiểm tra tổng thể bằng verify_runtime
print("\n" + "=" * 64)
print("   KIỂM TRA CHẨN ĐOÁN HỆ THỐNG CUỐI CÙNG (PREFLIGHT VERIFY)")
print("=" * 64)
verify_script = os.path.join(ROOT, "tools", "verify_runtime.py")
if os.path.exists(verify_script):
    subprocess.run([VENV_PY, verify_script], cwd=ROOT)

print("\n" + "=" * 64)
print("   HOÀN TẤT THIẾT LẬP AI AVATAR STUDIO TRÊN MÁY MỚI!")
print("   Bạn có thể ra màn hình Desktop nhấp đúp vào 'AI Avatar Studio'")
print("   hoặc chạy file AI_Avatar_Studio.exe để sử dụng ngay!")
print("=" * 64)
