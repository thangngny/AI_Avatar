#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — High-Speed LAN Data Sync Client.

Downloads heavy AI models (~8.6 GB) and prepared avatars (~12.9 GB) directly from
the source machine over LAN.

Usage on new machine:
    python tools/sync_from_old_machine.py
    python tools/sync_from_old_machine.py --server http://192.168.2.12:8089
"""
import os
import sys
import time
import json
import socket
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OLD_PC_IP = "192.168.2.12"
DEFAULT_PORT = 8089

def probe_server(url, timeout=1.5):
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/status")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ready":
                    return data
    except Exception:
        pass
    return None

def discover_server():
    # 1. Try known IP first
    direct_url = f"http://{DEFAULT_OLD_PC_IP}:{DEFAULT_PORT}"
    print(f"[*] Đang kiểm tra máy nguồn tại {direct_url}...")
    status = probe_server(direct_url)
    if status:
        return direct_url, status

    # 2. Try localhost in case testing on same machine
    local_url = f"http://127.0.0.1:{DEFAULT_PORT}"
    status = probe_server(local_url)
    if status:
        return local_url, status

    # 3. Quick scan local subnet on port 8089
    print(f"[*] Quét tìm máy chủ trong mạng LAN (Port {DEFAULT_PORT})...")
    # Find current subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
        s.close()
        subnet_prefix = ".".join(my_ip.split(".")[:3])
    except Exception:
        subnet_prefix = "192.168.2"

    candidates = [f"http://{subnet_prefix}.{i}:{DEFAULT_PORT}" for i in range(1, 255)]
    found = None
    found_status = None

    def check_candidate(u):
        nonlocal found, found_status
        if found:
            return
        st = probe_server(u, timeout=0.8)
        if st and not found:
            found = u
            found_status = st

    with ThreadPoolExecutor(max_workers=40) as pool:
        pool.map(check_candidate, candidates)

    if found:
        return found, found_status

    return None, None

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

def download_file(server_url, rel_path, expected_size, progress_tracker):
    dst_path = os.path.join(ROOT, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    # Check if already fully downloaded
    if os.path.isfile(dst_path):
        current_sz = os.path.getsize(dst_path)
        if current_sz == expected_size:
            progress_tracker.add_bytes(expected_size)
            return True, "skipped"
        elif current_sz < expected_size:
            # Can resume
            resume_pos = current_sz
        else:
            resume_pos = 0
    else:
        resume_pos = 0

    url = f"{server_url.rstrip('/')}/api/download?file={urllib.parse.quote(rel_path)}"
    req = urllib.request.Request(url)
    if resume_pos > 0:
        req.add_header("Range", f"bytes={resume_pos}-")
        progress_tracker.add_bytes(resume_pos)

    mode = "ab" if resume_pos > 0 else "wb"
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(dst_path, mode) as f:
                chunk_sz = 256 * 1024
                while True:
                    chunk = resp.read(chunk_sz)
                    if not chunk:
                        break
                    f.write(chunk)
                    progress_tracker.add_bytes(len(chunk))
    except Exception as e:
        return False, str(e)

    # Final verify
    if os.path.isfile(dst_path) and os.path.getsize(dst_path) == expected_size:
        return True, "downloaded"
    return False, f"Size mismatch: {os.path.getsize(dst_path)} vs {expected_size}"

class ProgressTracker:
    def __init__(self, total_bytes, total_files):
        self.total_bytes = total_bytes
        self.total_files = total_files
        self.downloaded_bytes = 0
        self.completed_files = 0
        self.start_time = time.time()
        self.last_update = 0
        import threading
        self.lock = threading.Lock()

    def add_bytes(self, n):
        with self.lock:
            self.downloaded_bytes += n

    def file_done(self):
        with self.lock:
            self.completed_files += 1

    def print_progress(self, current_file=""):
        now = time.time()
        if now - self.last_update < 0.2:
            return
        self.last_update = now

        elapsed = now - self.start_time
        speed = self.downloaded_bytes / elapsed if elapsed > 0.5 else 0
        remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
        eta = remaining_bytes / speed if speed > 1024 else 0

        pct = (self.downloaded_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 100
        bar_len = 28
        filled = int(bar_len * pct / 100)
        bar = "=" * filled + (">" if filled < bar_len else "") + " " * (bar_len - filled - 1)

        filename = os.path.basename(current_file) if current_file else ""
        if len(filename) > 22:
            filename = filename[:19] + "..."

        line = (f"\r[{bar}] {pct:5.1f}% | "
                f"{format_bytes(self.downloaded_bytes)}/{format_bytes(self.total_bytes)} | "
                f"{format_bytes(speed)}/s | ETA: {format_time(eta):<8} | {filename:<22}")
        sys.stdout.write(line)
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description="Đồng bộ dữ liệu AI Avatar qua mạng LAN.")
    parser.add_argument("--server", type=str, default="", help="Địa chỉ server máy cũ (ví dụ: http://192.168.2.12:8089)")
    args = parser.parse_args()

    print("=" * 66)
    print("   AI AVATAR STUDIO — LAN DATA SYNC CLIENT")
    print("=" * 66)
    print(f"[*] Thư mục đích trên máy này: {ROOT}")

    server_url = args.server
    status = None
    if server_url:
        print(f"[*] Kết nối đến địa chỉ chỉ định: {server_url}...")
        status = probe_server(server_url)
        if not status:
            print(f"[!] Không thể kết nối tới {server_url}. Hãy chắc chắn server trên máy cũ đang chạy.")
            sys.exit(1)
    else:
        server_url, status = discover_server()
        if not server_url:
            print("\n[!] Không tự động tìm thấy server máy cũ trong mạng LAN.")
            print("[*] Vui lòng chạy lệnh kèm địa chỉ IP cụ thể của máy cũ:")
            print(f"    python tools\\sync_from_old_machine.py --server http://{DEFAULT_OLD_PC_IP}:{DEFAULT_PORT}")
            sys.exit(1)

    print(f"  [OK] Đã kết nối thành công tới Máy chủ: {status.get('hostname', 'N/A')} ({server_url})")
    print(f"  [OK] Dữ liệu nguồn: Models ({status.get('models_gb')} GB), Avatars ({status.get('avatars_gb')} GB)")

    # Lấy manifest
    print("\n[*] Đang tải danh sách tệp (manifest)...")
    manifest_url = f"{server_url.rstrip('/')}/api/manifest"
    req = urllib.request.Request(manifest_url)
    with urllib.request.urlopen(req) as resp:
        manifest = json.loads(resp.read().decode("utf-8"))

    files = manifest.get("files", [])
    total_bytes = manifest.get("total_bytes", 0)
    print(f"  [OK] Tìm thấy {len(files)} tệp, tổng dung lượng: {format_bytes(total_bytes)}")

    tracker = ProgressTracker(total_bytes, len(files))

    # Tách tệp lớn (>10MB) và tệp nhỏ (<=10MB) để tối ưu download
    large_files = [f for f in files if f["size"] > 10 * 1024 * 1024]
    small_files = [f for f in files if f["size"] <= 10 * 1024 * 1024]

    print(f"\n[*] Bắt đầu truyền dữ liệu ({len(large_files)} tệp lớn, {len(small_files)} tệp nhỏ)...")
    print("-" * 66)

    # 1. Tải các tệp lớn (lần lượt hoặc 2 luồng để tận dụng tối đa băng thông mà không nghẽn)
    for idx, f in enumerate(large_files, 1):
        rel_p = f["path"]
        sz = f["size"]
        tracker.print_progress(rel_p)
        ok, msg = download_file(server_url, rel_p, sz, tracker)
        if not ok:
            print(f"\n[!] Lỗi khi tải {rel_p}: {msg}")
        tracker.file_done()

    # 2. Tải các tệp nhỏ song song (8 threads)
    def worker(item):
        rel_p = item["path"]
        sz = item["size"]
        tracker.print_progress(rel_p)
        ok, msg = download_file(server_url, rel_p, sz, tracker)
        tracker.file_done()
        return ok

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, small_files))

    tracker.print_progress("Hoàn tất!")
    print("\n" + "-" * 66)
    print(f"  [OK] Tải thành công! Toàn bộ {len(files)} tệp đã được đồng bộ.")

    # 3. Kiểm tra tiền điều kiện e2e_mouth_test
    print("\n[*] Kiểm tra tính toàn vẹn của mô hình & Avatar:")
    checks = [
        ("Model UNet v1.5", os.path.join(ROOT, "models", "musetalkV15", "unet.pth")),
        ("Model Whisper", os.path.join(ROOT, "models", "whisper", "pytorch_model.bin")),
        ("Model SD-VAE", os.path.join(ROOT, "models", "sd-vae", "diffusion_pytorch_model.bin")),
        ("Avatar doTrang_closeup (avator_info.json)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "avator_info.json")),
        ("Avatar doTrang_closeup (latents.pt)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "latents.pt")),
        ("Avatar doTrang_closeup (coords.pkl)", os.path.join(ROOT, "data", "avatars", "doTrang_closeup", "coords.pkl")),
    ]
    all_ok = True
    for name, path in checks:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print(f"  [OK] {name}: {format_bytes(os.path.getsize(path))}")
        else:
            print(f"  [MISSING] {name} tại {path}")
            all_ok = False

    print("=" * 66)
    if all_ok:
        print("🎉 TẤT CẢ DỮ LIỆU ĐÃ ĐẦY ĐỦ VÀ SẴN SÀNG!")
        print("Bây giờ bạn có thể chạy kiểm tra End-to-End trên RTX 5090:")
        print("    ..\\runtime\\venv\\Scripts\\python.exe tests/e2e_mouth_test.py")
    else:
        print("[!] Có một số tệp quan trọng chưa đầy đủ. Hãy kiểm tra lại.")
    print("=" * 66)

if __name__ == "__main__":
    main()
