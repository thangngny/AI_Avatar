import os
import sys
import time
import urllib.request
import ssl
import shutil

ssl._create_default_https_context = ssl._create_unverified_context

class RangeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if "Range" in req.headers:
            new_req.add_header("Range", req.headers["Range"])
        return new_req

opener = urllib.request.build_opener(RangeRedirectHandler)

URL = "https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B/resolve/main/Model_Pro/diffusion_pytorch_model.safetensors"
EXPECTED_SIZE = 6030864656

staging_dir = r"D:\CongThang_AI_Avatar\staging_weights\SoulX-FlashHead-1_3B\Model_Pro"
final_dir = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\weights\SoulX-FlashHead-1_3B\Model_Pro"
os.makedirs(staging_dir, exist_ok=True)
os.makedirs(final_dir, exist_ok=True)

staged_part = os.path.join(staging_dir, "diffusion_pytorch_model.safetensors.part")
staged_final = os.path.join(staging_dir, "diffusion_pytorch_model.safetensors")
final_file = os.path.join(final_dir, "diffusion_pytorch_model.safetensors")

if os.path.exists(final_file) and os.path.getsize(final_file) == EXPECTED_SIZE:
    print(f"[EXISTS] Weights already verified at {final_file}")
    sys.exit(0)

if os.path.exists(staged_final) and os.path.getsize(staged_final) == EXPECTED_SIZE:
    print(f"Staged file verified! Copying to {final_file}...")
    shutil.copy2(staged_final, final_file)
    print("[SUCCESS] Staged file copied to production!")
    sys.exit(0)

current_size = 0
if os.path.exists(staged_part):
    current_size = os.path.getsize(staged_part)
    print(f"[RESUME] Found partial download of {current_size} bytes ({current_size / (1024*1024):.2f} MB)...")

max_retries = 200
retries = 0

while current_size < EXPECTED_SIZE and retries < max_retries:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    if current_size > 0:
        headers["Range"] = f"bytes={current_size}-"
        print(f"[CONNECT] Requesting Range: bytes={current_size}- ...", flush=True)
    else:
        print(f"[CONNECT] Starting new connection to {URL} ...", flush=True)

    try:
        req = urllib.request.Request(URL, headers=headers)
        with opener.open(req, timeout=30) as resp:
            status = resp.status
            content_range = resp.headers.get("Content-Range")
            print(f"[CONNECTED] Status: {status}, Content-Range: {content_range}", flush=True)

            if current_size > 0 and status != 206:
                print(f"[ERROR] Expected 206 Partial Content but got {status}! Aborting append to prevent corruption.")
                sys.exit(1)

            mode = "ab" if current_size > 0 else "wb"
            with open(staged_part, mode) as out_f:
                chunk_sz = 256 * 1024 # 256 KB
                last_log = time.time()
                bytes_since_log = 0

                while current_size < EXPECTED_SIZE:
                    chunk = resp.read(chunk_sz)
                    if not chunk:
                        print("\n[INFO] End of stream received.", flush=True)
                        break
                    out_f.write(chunk)
                    current_size += len(chunk)
                    bytes_since_log += len(chunk)

                    now = time.time()
                    if now - last_log >= 5.0:
                        speed_mb = (bytes_since_log / 1024 / 1024) / (now - last_log)
                        pct = (current_size / EXPECTED_SIZE) * 100
                        print(f"Progress: {current_size/(1024*1024):.1f}/{EXPECTED_SIZE/(1024*1024):.1f} MB ({pct:.2f}%) | Speed: {speed_mb:.2f} MB/s", flush=True)
                        last_log = now
                        bytes_since_log = 0

    except Exception as e:
        retries += 1
        print(f"\n[WARN] Connection dropped: {e}. Retrying ({retries}/{max_retries}) in 5 seconds...", flush=True)
        time.sleep(5)

if current_size == EXPECTED_SIZE:
    print(f"\nDownload completed! Renaming {staged_part} -> {staged_final}...")
    if os.path.exists(staged_final):
        os.remove(staged_final)
    os.rename(staged_part, staged_final)
    print(f"Copying {staged_final} -> {final_file}...")
    shutil.copy2(staged_final, final_file)
    print("\n[SUCCESS] Model_Pro safetensors is 100% downloaded and ready for GPU inference!")
else:
    print(f"\n[INCOMPLETE] Final size: {current_size} / {EXPECTED_SIZE}")
