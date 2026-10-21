#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — High-Speed LAN Data Sync Server.

Serves heavy AI models (~8.6 GB) and prepared avatars (~12.9 GB) over the local network (LAN)
to a new workstation (e.g. RTX 5090 Blackwell machine).

Features:
- Pure Python standard library (no extra pip packages required).
- Supports Range requests (fast resuming if connection drops).
- Serves manifest of models, avatars, raw sources, and config files.
- High-throughput chunk streaming (buffer size 1MB).
"""
import os
import sys
import json
import time
import socket
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8089

SYNC_ROOTS = [
    "models",
    os.path.join("data", "avatars"),
    os.path.join("data", "input"),
    os.path.join("gfpgan", "weights"),
    os.path.join("avatars", "wav2lip"),
    "input4_9",
    os.path.join("data", "avatar_sources.json"),
    os.path.join("data", "custom_config.json"),
    os.path.join("data", "avatar_quality_audit.json"),
    ".env",
    os.path.join("data", "studio.db"),
    os.path.join("data", "recordings"),
]

def get_lan_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    # Fallback via connection trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]

def build_manifest():
    files_list = []
    total_bytes = 0
    models_bytes = 0
    avatars_bytes = 0

    for item in SYNC_ROOTS:
        full_p = os.path.join(ROOT, item)
        if os.path.isfile(full_p):
            sz = os.path.getsize(full_p)
            rel = os.path.relpath(full_p, ROOT).replace("\\", "/")
            files_list.append({"path": rel, "size": sz, "mtime": int(os.path.getmtime(full_p))})
            total_bytes += sz
        elif os.path.isdir(full_p):
            for dirpath, dirs, files in os.walk(full_p):
                # Ignore .cache, .tmp
                dirs[:] = [d for d in dirs if d not in (".cache", ".tmp", "__pycache__")]
                for fn in files:
                    if fn.endswith((".tmp", ".crdownload")):
                        continue
                    fp = os.path.join(dirpath, fn)
                    sz = os.path.getsize(fp)
                    rel = os.path.relpath(fp, ROOT).replace("\\", "/")
                    files_list.append({"path": rel, "size": sz, "mtime": int(os.path.getmtime(fp))})
                    total_bytes += sz
                    if rel.startswith("models/"):
                        models_bytes += sz
                    elif rel.startswith("data/avatars/"):
                        avatars_bytes += sz

    return {
        "status": "ready",
        "hostname": socket.gethostname(),
        "total_files": len(files_list),
        "total_bytes": total_bytes,
        "models_bytes": models_bytes,
        "avatars_bytes": avatars_bytes,
        "files": files_list
    }

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class SyncRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Keep console output minimal, only log downloads of large files or errors
        msg = format % args
        if "GET /api/download" in msg or "error" in msg.lower():
            sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            sys.stdout.flush()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ips = get_lan_ips()
            primary_ip = ips[0] if ips else "127.0.0.1"
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Avatar Studio - Data Sync Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; background: #0f172a; color: #f8fafc; }}
        h1 {{ color: #38bdf8; }}
        .card {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }}
        pre {{ background: #090d16; padding: 15px; border-radius: 6px; overflow-x: auto; color: #4ade80; font-size: 14px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; background: #0284c7; color: white; margin-right: 8px; }}
    </style>
</head>
<body>
    <h1>⚡ AI Avatar Studio — LAN Data Sync Server</h1>
    <div class="card">
        <h3>📡 Server Info</h3>
        <p><strong>Máy chủ:</strong> {socket.gethostname()}</p>
        <p><strong>Địa chỉ IP khả dụng:</strong> {' '.join(f'<span class=\"badge\">{ip}</span>' for ip in ips)}</p>
        <p><strong>Cổng (Port):</strong> {PORT}</p>
    </div>
    <div class="card">
        <h3>🚀 Cách nhận dữ liệu trên Máy mới (RTX 5090)</h3>
        <p>Mở terminal trên máy mới tại thư mục <code>C:\\Users\\phuongpn\\AI_Avatar</code> và chạy lệnh sau:</p>
        <pre>python tools\\sync_from_old_machine.py --server http://{primary_ip}:{PORT}</pre>
        <p>Hoặc nhấp đúp vào tệp <strong>Nhan_Data_Tu_May_Cu.bat</strong> trên máy mới.</p>
    </div>
    <div class="card">
        <h3>📊 API Endpoints</h3>
        <ul>
            <li><a style="color: #38bdf8" href="/api/status">/api/status</a> — Thông tin trạng thái dữ liệu</li>
            <li><a style="color: #38bdf8" href="/api/manifest">/api/manifest</a> — Danh sách toàn bộ các file cần đồng bộ</li>
        </ul>
    </div>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
            return

        if path == "/api/status":
            m = build_manifest()
            summary = {
                "status": "ready",
                "hostname": m["hostname"],
                "total_files": m["total_files"],
                "total_gb": round(m["total_bytes"] / (1024**3), 2),
                "models_gb": round(m["models_bytes"] / (1024**3), 2),
                "avatars_gb": round(m["avatars_bytes"] / (1024**3), 2),
            }
            body = json.dumps(summary, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/manifest":
            m = build_manifest()
            body = json.dumps(m).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/download":
            rel_path = query.get("file", [""])[0]
            if not rel_path:
                self.send_error(400, "Missing 'file' parameter")
                return

            # Normalize and security check (prevent directory traversal)
            norm_rel = os.path.normpath(rel_path).replace("\\", "/")
            if norm_rel.startswith("..") or os.path.isabs(norm_rel):
                self.send_error(403, "Forbidden path")
                return

            full_p = os.path.join(ROOT, norm_rel)
            if not os.path.isfile(full_p):
                self.send_error(404, f"File not found: {norm_rel}")
                return

            file_size = os.path.getsize(full_p)
            range_header = self.headers.get("Range")

            start = 0
            end = file_size - 1

            if range_header and range_header.startswith("bytes="):
                range_spec = range_header[6:].strip()
                parts = range_spec.split("-")
                try:
                    if parts[0]:
                        start = int(parts[0])
                    if len(parts) > 1 and parts[1]:
                        end = int(parts[1])
                except ValueError:
                    start = 0
                    end = file_size - 1

                if start > end or start >= file_size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return

                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            else:
                self.send_response(200)

            content_length = end - start + 1
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(content_length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            # Stream chunks (1MB buffer for high throughput)
            chunk_size = 1024 * 1024
            try:
                with open(full_p, "rb") as f:
                    if start > 0:
                        f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        to_read = min(chunk_size, remaining)
                        chunk = f.read(to_read)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass
            return

        self.send_error(404, "Unknown endpoint")

def main():
    ips = get_lan_ips()
    primary_ip = ips[0] if ips else "127.0.0.1"

    print("=" * 66)
    print("   AI AVATAR STUDIO — HIGH-SPEED LAN DATA SYNC SERVER")
    print("=" * 66)
    print(f"[*] Thư mục nguồn: {ROOT}")
    print(f"[*] Cổng lắng nghe (Port): {PORT}")
    print(f"[*] Địa chỉ IP máy cũ:")
    for ip in ips:
        print(f"    -> http://{ip}:{PORT}")
    print("-" * 66)
    print("[*] Đang kiểm kê dữ liệu (models, avatars, inputs)...")
    manifest = build_manifest()
    total_gb = round(manifest["total_bytes"] / (1024**3), 2)
    models_gb = round(manifest["models_bytes"] / (1024**3), 2)
    avatars_gb = round(manifest["avatars_bytes"] / (1024**3), 2)
    print(f"    - Tổng số tệp: {manifest['total_files']} files")
    print(f"    - Tổng dung lượng: {total_gb} GB (Models: {models_gb} GB, Avatars: {avatars_gb} GB)")
    print("=" * 66)
    print(">>> TRÊN MÁY MỚI (RTX 5090), BẠN HÃY CHẠY LỆNH:")
    print(f"    python tools\\sync_from_old_machine.py --server http://{primary_ip}:{PORT}")
    print("    (Hoặc nhấp đúp vào Nhan_Data_Tu_May_Cu.bat trên máy mới)")
    print("=" * 66)
    print("[*] Server đang mở... Nhấn Ctrl+C để dừng khi hoàn tất.\n")

    server = ThreadedHTTPServer(("0.0.0.0", PORT), SyncRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Đang tắt server...")
    finally:
        server.server_close()
        print("[*] Server đã dừng an toàn.")

if __name__ == "__main__":
    main()
