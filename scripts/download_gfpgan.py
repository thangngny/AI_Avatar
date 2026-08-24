#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download GFPGANv1.4.pth for optional face restoration (face_enhance).

MuseTalk/Wav2Lip produce the lip-synced face at 256x256; GFPGAN restores fine
details (eyes, teeth, skin) so the upscaled paste-back stays sharp. It is
OPTIONAL — the pipeline runs fine without it (LIVETALKING_FACE_ENHANCE defaults
to false). Enable only when you want higher-quality faces and have GPU
headroom (offline render always has headroom; realtime needs CUDA Graphs +
batch_size 16 to fit the 25fps budget).

This script only downloads the model file. Run it once:
    python scripts/download_gfpgan.py

Then enable:
    - Realtime: set LIVETALKING_FACE_ENHANCE=true (watch telemetry
      gfpgan_sec / inference_batch_sec / res_frame_queue_size — if res_frame_queue
      runs dry, the face enhance is pushing inference below 25fps; lower
      LIVETALKING_FACE_ENHANCE_WEIGHT or disable).
    - Offline:  `python generate_video_from_script.py ... --face_enhance`
      (offline has no 25fps budget, always safe).

Source: https://github.com/TencentARC/GFPGAN (v1.4, ~333MB).
"""
import os
import sys
import urllib.request

URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
# Default target matches avatars/face_enhance._default_model.
DEFAULT_OUT = os.path.join("models", "GFPGANv1.4.pth")


def _progress(blocks, block_size, total):
    done = blocks * block_size
    if total > 0:
        pct = min(100.0, done * 100.0 / total)
        mb_done = done / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        sys.stdout.write(f"\r  {mb_done:.1f}/{mb_total:.1f} MB ({pct:.0f}%)")
        sys.stdout.flush()


def main():
    out = DEFAULT_OUT
    if os.path.isfile(out) and os.path.getsize(out) > 10 * 1024 * 1024:
        print(f"GFPGANv1.4.pth already present: {out} ({os.path.getsize(out)/1024/1024:.0f} MB)")
        return
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    print(f"Downloading GFPGANv1.4.pth -> {out}")
    print(f"  URL: {URL}")
    try:
        urllib.request.urlretrieve(URL, out, reporthook=_progress)
    except Exception as exc:
        print(f"\nDownload failed: {exc}")
        print("Download manually from https://github.com/TencentARC/GFPGAN/releases")
        print(f"and place the file at: {os.path.abspath(out)}")
        sys.exit(1)
    print(f"\nDone: {out} ({os.path.getsize(out)/1024/1024:.0f} MB)")


if __name__ == "__main__":
    main()