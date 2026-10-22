"""
AI Avatar NextGen V2 - 60-Second Master Enhancement & Vertical Muxer
Applies conservative GFPGAN 50/50 blend + Lanczos 1024x1024 to 60s native SoulX Pro video,
then re-renders Strategy B Vertical master with the crystal-clear enhanced foreground.
"""
import os
import sys
import time
import subprocess
import cv2
import torch
import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
sys.path.insert(0, os.path.join(REPO_ROOT, "avatars"))
from gfpgan_clean import GFPGANv1Clean

INPUT_60S_NATIVE = os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_60s.mp4")
AUDIO_60S = os.path.join(REPO_ROOT, "assets", "master_60s_vietnamese.wav")

OUT_DIR = os.path.join(REPO_ROOT, "reports", "mission05")
os.makedirs(OUT_DIR, exist_ok=True)

OUT_60S_ENHANCED = os.path.join(OUT_DIR, "soulx_pro_60s_enhanced_gfpgan50.mp4")
OUT_60S_VERTICAL = os.path.join(OUT_DIR, "soulx_pro_60s_vertical_1080x1920.mp4")


def load_gfpgan():
    print("[1/4] Loading GFPGANv1Clean on RTX 5090...")
    model = GFPGANv1Clean(
        out_size=512,
        num_style_feat=512,
        channel_multiplier=2,
        decoder_load_path=None,
        fix_decoder=False,
        num_mlp=8,
        input_is_latent=True,
        different_w=True,
        narrow=1,
        sft_half=True
    )
    ckpt_path = r"C:\Users\phuongpn\AI_Avatar\models\GFPGANv1.4.pth"
    ckpt = torch.load(ckpt_path, map_location="cpu")
    sd = ckpt.get("params_ema", ckpt.get("params", ckpt))
    model.load_state_dict(sd, strict=False)
    model.eval().to("cuda")
    return model


def enhance_60s_master():
    gfp_model = load_gfpgan()

    cap = cv2.VideoCapture(INPUT_60S_NATIVE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[2/4] Reading and enhancing {total_frames} frames from {INPUT_60S_NATIVE}...")

    # Set up NVENC streaming process directly
    cmd_nvenc = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", "1024x1024", "-pix_fmt", "bgr24", "-r", str(fps),
        "-i", "-",
        "-i", AUDIO_60S,
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-spatial-aq", "1", "-temporal-aq", "1", "-multipass", "fullres",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT_60S_ENHANCED
    ]

    proc = subprocess.Popen(cmd_nvenc, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    batch_size = 8
    frame_buffer = []
    processed = 0
    t0 = time.time()

    def process_and_write_batch(batch):
        with torch.no_grad():
            t_batch = torch.stack([
                torch.from_numpy(f).permute(2, 0, 1).float() / 127.5 - 1.0
                for f in batch
            ]).to("cuda")

            out = gfp_model(t_batch, return_rgb=True)
            if isinstance(out, tuple):
                out = out[0]
            out_np = ((out.permute(0, 2, 3, 1).cpu().numpy() + 1.0) * 127.5).clip(0, 255).astype(np.uint8)

            for raw_f, gfp_f in zip(batch, out_np):
                blended = (0.50 * gfp_f.astype(float) + 0.50 * raw_f.astype(float)).clip(0, 255).astype(np.uint8)
                up_1024 = cv2.resize(blended, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
                proc.stdin.write(up_1024.tobytes())

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_buffer.append(frame)
        if len(frame_buffer) == batch_size:
            process_and_write_batch(frame_buffer)
            processed += len(frame_buffer)
            if processed % 100 == 0 or processed == total_frames:
                print(f"  Processed {processed}/{total_frames} frames ({processed / (time.time() - t0):.1f} fps)...")
            frame_buffer = []

    if frame_buffer:
        process_and_write_batch(frame_buffer)
        processed += len(frame_buffer)

    cap.release()
    proc.stdin.close()
    proc.wait()

    elapsed = time.time() - t0
    print(f"[3/4] 60s Enhanced Master complete: {OUT_60S_ENHANCED}")
    print(f"      Size: {os.path.getsize(OUT_60S_ENHANCED):,} bytes | Elapsed: {elapsed:.2f}s ({processed / elapsed:.1f} fps)")

    # [4/4] Render Vertical Strategy B with Enhanced Foreground
    print(f"[4/4] Rendering Strategy B Vertical Master 1080x1920 using enhanced foreground...")
    filter_b = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,colorchannelmixer=aa=0.8:rr=0.6:gg=0.6:bb=0.6[bg];"
        "[0:v]scale=1080:1080[fg];"
        "[bg][fg]overlay=x=0:y=420[v]"
    )
    cmd_vert = [
        "ffmpeg", "-y", "-i", OUT_60S_ENHANCED,
        "-filter_complex", filter_b,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT_60S_VERTICAL
    ]
    subprocess.run(cmd_vert, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"      Strategy B 60s completed: {OUT_60S_VERTICAL} ({os.path.getsize(OUT_60S_VERTICAL):,} bytes)")


if __name__ == "__main__":
    enhance_60s_master()
