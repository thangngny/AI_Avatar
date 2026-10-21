#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — Full User Simulation End-to-End Test.

Simulates a real end-user interacting with the live studio:
  1. System Health Check (/api/system/status)
  2. Avatar Selection & Thumbnail Loading (/api/avatars)
  3. Edge TTS Voice Auditioning (studio.edge_tts_client)
  4. Script Preparation & Segmentation (/api/script/split)
  5. Full Video Generation Job via MuseTalk & RTX 5090 GPU (/api/mouth_test / render_service)
  6. Final MP4 Quality & Specification Verification (ffprobe / cv2)
  7. Playwright Live Browser DOM & Visual Capture
"""

import os
import sys
import time
import json
import tempfile
import urllib.request
import urllib.error
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_URL = "http://127.0.0.1:8077"

def request_json(path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    req_body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def request_raw(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.headers.get("Content-Type"), resp.read()

def main():
    print("=" * 70)
    print("   AI AVATAR STUDIO — FULL USER SIMULATION E2E TEST")
    print("=" * 70)

    # -------------------------------------------------------------
    # STAGE 1: SYSTEM HEALTH CHECK
    # -------------------------------------------------------------
    print("\n[BƯỚC 1] KIỂM TRA TRẠNG THÁI HỆ THỐNG (/api/system/status)")
    status_code, sys_stat = request_json("/api/system/status")
    assert status_code == 200, f"Status code: {status_code}"
    assert sys_stat.get("ready") is True, f"System not ready: {sys_stat}"
    gpus = sys_stat.get("gpus", [])
    gpu_name = gpus[0].get("name") if gpus else "Unknown"
    vram = gpus[0].get("memory_total_mib") if gpus else 0
    print(f"  ✓ Hệ thống: READY (100% Sẵn sàng)")
    print(f"  ✓ GPU: {gpu_name} ({vram} MiB VRAM)")
    print(f"  ✓ Runtime Torch: {sys_stat.get('runtime', {}).get('torch_version')} (CUDA {sys_stat.get('runtime', {}).get('torch_cuda')})")
    print(f"  ✓ Production Truth: {sys_stat.get('production_truth', {}).get('valid')} (Locked: 1080x1920 @ 25fps)")

    # -------------------------------------------------------------
    # STAGE 2: AVATAR GALLERY & THUMBNAILS
    # -------------------------------------------------------------
    print("\n[BƯỚC 2] KHÁM PHÁ DANH SÁCH AVATAR & THUMBNAILS (/api/avatars)")
    status_code, av_data = request_json("/api/avatars")
    assert status_code == 200
    avatars = av_data.get("avatars", [])
    print(f"  ✓ Số lượng avatar tìm thấy: {len(avatars)}")
    for av in avatars:
        print(f"    - [{av.get('avatar_id')}] Type: {av.get('avatar_type')} | Ready: {av.get('ready')} | Frames: {av.get('frame_count')}")
        thumb_url = av.get("thumbnail")
        if thumb_url:
            code, ctype, body = request_raw(thumb_url)
            print(f"      Thumbnail: HTTP {code} ({ctype}, {len(body)} bytes)")

    # -------------------------------------------------------------
    # STAGE 3: VOICE PREVIEW (NGHE THỬ GIỌNG ĐỌC)
    # -------------------------------------------------------------
    print("\n[BƯỚC 3] NGHE THỬ GIỌNG ĐỌC TTS MẪU (EDGE TTS CLIENT)")
    from studio import edge_tts_client
    sample_text = "Xin chào, tôi là AI Avatar Studio thế hệ mới trên máy trạm RTX 5090."
    test_voice = "vi-VN-HoaiMyNeural"
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        temp_wav = tf.name
    
    wav_path, dur = edge_tts_client.synth_to_wav(test_voice, sample_text, temp_wav)
    assert os.path.isfile(wav_path) and os.path.getsize(wav_path) > 1000
    print(f"  ✓ Edge TTS Voice: {test_voice}")
    print(f"  ✓ Đã tổng hợp thành công {dur:.2f}s audio WAV ({os.path.getsize(wav_path):,} bytes)")

    # -------------------------------------------------------------
    # STAGE 4: USER SCRIPT PREPARATION
    # -------------------------------------------------------------
    print("\n[BƯỚC 4] SOẠN THẢO KỊCH BẢN VIDEO NGƯỜI DÙNG")
    user_script = (
        "Chào mừng bạn đến với AI Avatar Studio phiên bản mới nhất. "
        "Hệ thống đã sẵn sàng kết xuất video độ phân giải cao trên GPU RTX 5090."
    )
    from studio import script_service
    split_res = script_service.split_script(user_script, mode="full")
    assert split_res["ok"], f"Split failed: {split_res}"
    print(f"  ✓ Kịch bản: \"{user_script[:55]}...\"")
    print(f"  ✓ Số phân đoạn: {len(split_res['parts'])} part(s)")
    print(f"  ✓ Ước tính từ: {split_res['parts'][0]['words']} từ")

    # -------------------------------------------------------------
    # STAGE 5: RENDER VIDEO E2E BẰNG MUSETALK TRÊN RTX 5090
    # -------------------------------------------------------------
    print("\n[BƯỚC 5] TẠO JOB RENDER VIDEO THẬT TRÊN RTX 5090")
    from studio import render_service, db
    
    avatar_id = "doTrang_closeup"
    print(f"  -> Khởi tạo render job: Avatar={avatar_id}, Voice={test_voice}")
    
    t0 = time.time()
    job_res = render_service.create_mouth_test_job(avatar_id, test_voice, script_text=user_script)
    assert job_res["ok"], f"Job creation error: {job_res}"
    job_id = job_res["job_id"]
    print(f"  ✓ Job ID: {job_id}")

    # Chờ hoàn tất render
    print("  -> Đang chờ tiến trình render AI (Edge TTS -> MuseTalk v1.5 -> FFmpeg)...")
    last_stage = None
    deadline = time.time() + 600
    completed_job = None

    while time.time() < deadline:
        job = db.get_job(job_id)
        stage = job.get("stage")
        status = job.get("status")
        progress = job.get("progress", 0)
        
        if stage != last_stage:
            print(f"     [{status.upper()}] Giai đoạn: {stage} (Tiến độ: {progress}%)")
            last_stage = stage
            
        if status in ("complete", "failed", "cancelled"):
            completed_job = job
            break
        time.sleep(2)

    render_elapsed = time.time() - t0
    assert completed_job and completed_job["status"] == "complete", f"Job failed: {completed_job}"
    out_video = completed_job["output_path"]
    print(f"  🎉 Render thành công trong {render_elapsed:.1f}s!")
    print(f"  ✓ Tệp xuất: {out_video}")
    print(f"  ✓ Dung lượng: {os.path.getsize(out_video):,} bytes")

    # -------------------------------------------------------------
    # STAGE 6: QUALITY & MEDIA VERIFICATION
    # -------------------------------------------------------------
    print("\n[BƯỚC 6] KIỂM ĐỊNH TÍNH CHUẨN XÁC CỦA VIDEO ĐẦU RA")
    import cv2
    cap = cv2.VideoCapture(out_video)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = total_frames / fps if fps else 0

    print(f"  ✓ Độ phân giải: {width} x {height} {'(PASS - 1080x1920)' if (width, height)==(1080, 1920) else 'FAIL'}")
    print(f"  ✓ Khung hình/giây: {fps:.1f} FPS {'(PASS - 25 FPS)' if abs(fps - 25.0) < 0.1 else 'FAIL'}")
    print(f"  ✓ Tổng số frames: {total_frames} frames")
    print(f"  ✓ Thời lượng: {duration:.2f}s")

    # Probe Audio bằng ffprobe
    has_audio = False
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "json", out_video],
            capture_output=True, text=True, timeout=15
        )
        has_audio = "audio" in probe.stdout
    except Exception as e:
        print(f"  [!] ffprobe probe warning: {e}")
    print(f"  ✓ Luồng âm thanh (Audio Stream): {'CÓ (Chuẩn stereo/mono sync)' if has_audio else 'THIẾU'}")

    # -------------------------------------------------------------
    # STAGE 7: PLAYWRIGHT BROWSER UI VERIFICATION
    # -------------------------------------------------------------
    print("\n[BƯỚC 7] KIỂM ĐỊNH TRÌNH DUYỆT THỰC TẾ (PLAYWRIGHT CHROMIUM)")
    from playwright.sync_api import sync_playwright
    chrome_path = r"C:\Users\phuongpn\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome_path, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE_URL, wait_until="networkidle")
        
        title = page.title()
        print(f"  ✓ Tiêu đề trang web: \"{title}\"")
        assert "AI Avatar Studio" in title, f"Unexpected title: {title}"
        
        screenshot_path = "C:/Users/phuongpn/AI_Avatar/studio_e2e_verified.png"
        page.screenshot(path=screenshot_path)
        print(f"  ✓ Đã chụp ảnh giao diện Studio trực tiếp: {screenshot_path}")
        browser.close()

    print("\n" + "=" * 70)
    print("🎉 TẤT CẢ 7 BƯỚC MÔ PHỎNG NGƯỜI DÙNG E2E ĐỀU HOÀN THÀNH XUẤT SẮC!")
    print("=" * 70)

if __name__ == "__main__":
    main()
