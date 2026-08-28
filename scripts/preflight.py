#!/usr/bin/env python3
"""AI Avatar Studio — PRE-FLIGHT CHECK (read-only).

Operator-facing readiness check. NEVER renders, prepares, installs, deletes,
or changes production config. Exit codes: 0 READY, 1 READY_WITH_WARNINGS,
2 BLOCKED. Run via AI_Avatar_Studio_Preflight.bat (torch-env python) or:
    python scripts/preflight.py [--detail]
"""
import os, sys, json, subprocess, shutil, sqlite3
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from studio import config, runtime

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; RST = "\033[0m"
# Disable color under dumb terminals
if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
    GREEN = RED = YEL = CYAN = RST = ""

checks = []  # (name, status, detail)  status: ok/warn/block
warnings = []
blocks = []

def ok(name, detail=""): checks.append((name, "ok", detail))
def warn(name, detail=""): checks.append((name, "warn", detail)); warnings.append((name, detail))
def block(name, detail=""): checks.append((name, "block", detail)); blocks.append((name, detail))

def have(p):
    return os.path.exists(p)

# 1. Python interpreter (the torch-capable one used for rendering)
tp = runtime.torch_python()
try:
    v = subprocess.run([tp, "--version"], capture_output=True, text=True, timeout=15)
    pyver = (v.stdout or v.stderr).strip()
    ok("Python (runtime)", f"{tp}  {pyver}")
except Exception as e:
    block("Python (runtime)", f"{tp} không chạy được: {e}")

# 2. Production renderer + truth config
if have(config.RENDERER): ok("Production renderer", os.path.basename(config.RENDERER))
else: block("Production renderer", f"thiếu {config.RENDERER}")
if have(config.TRUTH_PATH):
    try:
        t = json.load(open(config.TRUTH_PATH, encoding="utf-8"))
        ok("Production config (render_truth)", f"pipeline={t.get('pipeline')} {t.get('resolution_width')}x{t.get('resolution_height')} {t.get('fps')}fps")
    except Exception as e:
        block("Production config (render_truth)", f"không đọc được: {e}")
else:
    block("Production config (render_truth)", f"thiếu {config.TRUTH_PATH}")

# 3. Database
if have(config.DB_PATH):
    try:
        conn = sqlite3.connect(config.DB_PATH, timeout=10)
        r = conn.execute("PRAGMA integrity_check").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] if have(config.DB_PATH) else 0
        av = conn.execute("SELECT COUNT(*) FROM avatars").fetchone()[0]
        conn.close()
        if r == "ok": ok("Database", f"integrity=ok  jobs={jobs} avatars={av}")
        else: block("Database", f"integrity_check={r}")
    except Exception as e:
        block("Database", f"không mở được: {e}")
else:
    warn("Database", "chưa có studio.db (sẽ tạo khi khởi động Studio)")

# 4. Models (critical base models)
critical_models = [
    "models/musetalkV15/unet.pth", "models/musetalkV15/musetalk.json",
    "models/whisper/pytorch_model.bin", "models/whisper/config.json",
    "models/sd-vae/diffusion_pytorch_model.bin", "models/sd-vae/config.json",
    "models/face-parse-bisent/79999_iter.pth", "models/face-parse-bisent/resnet18-5c106cde.pth",
]
missing_models = [m for m in critical_models if not have(os.path.join(ROOT, m))]
if not missing_models: ok("Models", f"{len(critical_models)} base models present")
else: block("Models", "thiếu: " + ", ".join(missing_models))
# optional GFPGAN
if not have(os.path.join(ROOT, "models/GFPGANv1.4.pth")):
    warn("GFPGAN (tùy chọn)", "models/GFPGANv1.4.pth thiếu — chỉ cần khi bật phục hồi mặt")

# 5. GPU(s)
try:
    r = subprocess.run(["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0 and r.stdout.strip():
        gpus = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        ok("GPU", f"{len(gpus)} GPU: " + " | ".join(gpus))
    else:
        block("GPU", "nvidia-smi không trả GPU — không render được")
except Exception as e:
    block("GPU", f"nvidia-smi lỗi: {e}")

# 6. FFmpeg / ffprobe
ff = shutil.which("ffprobe") or shutil.which("ffmpeg")
if shutil.which("ffmpeg"): ok("FFmpeg", shutil.which("ffmpeg"))
elif ff: warn("FFmpeg", f"chỉ có {ff} — nên có ffmpeg trên PATH")
else:
    # fallback imageio-ffmpeg
    try:
        import imageio_ffmpeg
        ok("FFmpeg", f"imageio-ffmpeg bundled: {imageio_ffmpeg.get_ffmpeg_exe()}")
    except Exception:
        block("FFmpeg", "không tìm thấy ffmpeg/ffprobe")

# 7. Disk space (renders drive + repo drive)
def free_gb(path):
    try:
        import ctypes
        free = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(os.path.dirname(path) or ".", None, None, ctypes.byref(free))
        return free.value / 1e9
    except Exception:
        return None
renders_free = free_gb(config.RENDERS_DIR) if have(os.path.dirname(config.RENDERS_DIR) or "D:\\") else None
repo_free = free_gb(ROOT)
if renders_free is not None and renders_free < 20:
    block("Disk (renders)", f"{config.RENDERS_DIR} chỉ còn {renders_free:.1f} GB — quá thấp")
elif renders_free is not None:
    ok("Disk (renders)", f"{config.RENDERS_DIR}  còn {renders_free:.1f} GB")
else:
    warn("Disk (renders)", f"{config.RENDERS_DIR} không xác định được dung lượng")
if repo_free is not None and repo_free < 15:
    warn("Disk (repo)", f"{ROOT} chỉ còn {repo_free:.1f} GB (avatars/models nằm đây)")
elif repo_free is not None:
    ok("Disk (repo)", f"{ROOT}  còn {repo_free:.1f} GB")

# 8. ElevenLabs configured (key presence, NOT value)
try:
    from studio import envutil
    envutil.load_env()
    key = envutil.env_str("ELEVENLABS_API_KEY")
    if key: ok("ElevenLabs configured", "API key đã cấu hình (.env)")
    else: warn("ElevenLabs configured", "chưa có ELEVENLABS_API_KEY — render production cần key")
except Exception:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key: ok("ElevenLabs configured", "API key đã cấu hình (env)")
    else: warn("ElevenLabs configured", "chưa có ELEVENLABS_API_KEY")

# 9. Edge TTS (import check — actual use needs Internet)
try:
    import importlib
    importlib.import_module("edge_tts")
    ok("Edge TTS", "package sẵn sàng (cần Internet khi dùng)")
except Exception:
    warn("Edge TTS", "không import được edge_tts trong env này")

# 10. Studio port 8077 free?
import socket
s = socket.socket(); s.settimeout(1)
try:
    s.bind(("127.0.0.1", 8077)); ok("Studio port", "8077 đang свободен")
except OSError:
    ok("Studio port", "8077 đang bận (Studio đang chạy)")
finally:
    s.close()

# 11. Cloudflared (warning-only — only needed for remote sharing)
if shutil.which("cloudflared"): ok("Cloudflare Quick Tunnel", "cloudflared đã cài (chỉ cần khi chia sẻ từ xa)")
else: warn("Cloudflare Quick Tunnel", "cloudflared thiếu — chỉ cần khi chia sẻ từ xa")

# ---- report ----
print("\n" + "=" * 50)
print("AI AVATAR STUDIO — KIỂM TRA TRƯỚC KHI CHẠY")
print("=" * 50)
print("\nHỆ THỐNG:", end=" ")
if blocks:
    print(RED + "KHÔNG THỂ CHẠY" + RST)
elif warnings:
    print(YEL + "SẴN SÀNG (có cảnh báo)" + RST)
else:
    print(GREEN + "SẴN SÀNG" + RST)
print()
def icon(st): return GREEN + "✓" + RST if st == "ok" else (YEL + "⚠" + RST if st == "warn" else RED + "✗" + RST)
for name, st, detail in checks:
    print(f" {icon(st)} {name}" + (f"\n     {detail}" if detail and (st!='ok' or '--detail' in sys.argv) else ""))
if warnings and '--detail' not in sys.argv:
    print("\n Cảnh báo:")
    for n, d in warnings: print(f"   ⚠ {n}: {d}")
if blocks:
    print("\n Lỗi chặn:")
    for n, d in blocks: print(f"   ✗ {n}: {d}")
print("\n" + "=" * 50)
if '--detail' in sys.argv:
    print("CHI TIẾT KỸ THUẬT")
    print(f"  Repo: {ROOT}")
    print(f"  Torch python: {tp}")
    print(f"  Renders dir: {config.RENDERS_DIR}")
    print(f"  DB: {config.DB_PATH}")
    print(f"  Truth: {config.TRUTH_PATH}")
    print("=" * 50)

sys.exit(2 if blocks else (1 if warnings else 0))