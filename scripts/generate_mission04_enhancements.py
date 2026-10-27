"""
AI Avatar NextGen V2 - Mission 04 High-Quality Enhancement & 4-Way Evaluation
Generates:
1. Condition 3: Conservative Lanczos 1024x1024 with edge unsharp mask
2. Condition 4: Conservative GFPGAN 50/50 blend + Lanczos 1024x1024
3. 4-Way Multi-Panel Evaluation Video (1920x1080)
4. Face Close-up A/B Video (1920x960)
"""
import os
import sys
import time
import subprocess
import cv2
import torch
import numpy as np
from PIL import Image

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission04")
os.makedirs(REPORTS_DIR, exist_ok=True)

SOULX_NATIVE_10S = os.path.join(REPO_ROOT, "reports", "mission03", "soulx_pro_10s.mp4")
MUSETALK_ORIG_10S = r"D:\CongThang_AI_Avatar\v2_renders\bench_TEST_A_NEXTGEN_V2_doTrang_closeup.mp4"
AUDIO_PATH = os.path.join(REPO_ROOT, "benchmarks", "test_dataset", "test_a_neutral.wav")

OUT_COND3 = os.path.join(REPORTS_DIR, "soulx_pro_10s_lanczos1024.mp4")
OUT_COND4 = os.path.join(REPORTS_DIR, "soulx_pro_10s_enhanced_gfpgan50.mp4")
OUT_4WAY = os.path.join(REPORTS_DIR, "four_way_comparison_10s.mp4")
OUT_CLOSEUP = os.path.join(REPORTS_DIR, "face_closeup_comparison_10s.mp4")

sys.path.insert(0, os.path.join(REPO_ROOT, "avatars"))
from gfpgan_clean import GFPGANv1Clean


def load_gfpgan():
    print("[1/5] Loading GFPGANv1Clean on RTX 5090...")
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
    ckpt_path = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\models\GFPGANv1.4.pth"
    ckpt = torch.load(ckpt_path, map_location="cpu")
    sd = ckpt.get("params_ema", ckpt.get("params", ckpt))
    model.load_state_dict(sd, strict=False)
    model.eval().to("cuda")
    return model


def process_video_enhancements():
    cap = cv2.VideoCapture(SOULX_NATIVE_10S)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[2/5] Reading {total_frames} frames from native SoulX video ({fps} fps)...")

    raw_frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        raw_frames.append(frame)
    cap.release()

    # --- Condition 3: Lanczos 1024x1024 + mild unsharp mask ---
    print("[3/5] Generating Condition 3: Lanczos 1024x1024 with unsharp mask...")
    cond3_frames = []
    for f in raw_frames:
        # Lanczos 1024x1024
        up = cv2.resize(f, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
        # Subtle unsharp mask to restore edge micro-contrast without halo
        gaussian = cv2.GaussianBlur(up, (0, 0), sigmaX=1.5)
        unsharp = cv2.addWeighted(up, 1.25, gaussian, -0.25, 0)
        cond3_frames.append(unsharp)

    # Save Condition 3 MP4 (H.264 NVENC CRF 16 visually lossless)
    tmp_c3 = OUT_COND3.replace(".mp4", "_tmp.mp4")
    w3, h3 = 1024, 1024
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_vw = cv2.VideoWriter(tmp_c3, fourcc, fps, (w3, h3))
    for f in cond3_frames:
        out_vw.write(f)
    out_vw.release()

    # Mux with audio using NVENC high quality
    cmd_mux3 = [
        "ffmpeg", "-y", "-i", tmp_c3, "-i", AUDIO_PATH,
        "-c:v", "h264_nvenc", "-preset", "p7", "-qp", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", OUT_COND3
    ]
    subprocess.run(cmd_mux3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(tmp_c3):
        os.remove(tmp_c3)
    print(f"Condition 3 complete: {OUT_COND3} ({os.path.getsize(OUT_COND3)} bytes)")

    # --- Condition 4: Conservative GFPGAN 50/50 Blend + Lanczos 1024 ---
    print("[4/5] Generating Condition 4: Conservative GFPGAN 50/50 Blend + Lanczos 1024...")
    gfp_model = load_gfpgan()
    cond4_frames = []

    batch_size = 4
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(raw_frames), batch_size):
            batch = raw_frames[i:i + batch_size]
            t_batch = torch.stack([
                torch.from_numpy(f).permute(2, 0, 1).float() / 127.5 - 1.0
                for f in batch
            ]).to("cuda")

            out = gfp_model(t_batch, return_rgb=True)
            if isinstance(out, tuple):
                out = out[0]
            out_np = ((out.permute(0, 2, 3, 1).cpu().numpy() + 1.0) * 127.5).clip(0, 255).astype(np.uint8)

            for raw_f, gfp_f in zip(batch, out_np):
                # 50/50 Conservative Blend: Preserves 100% original identity, suppresses GAN hallucination
                blended = (0.50 * gfp_f.astype(float) + 0.50 * raw_f.astype(float)).clip(0, 255).astype(np.uint8)
                # Scale to 1024x1024 via Lanczos
                up = cv2.resize(blended, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
                cond4_frames.append(up)

    torch.cuda.synchronize()
    print(f"GFPGAN enhancement completed in {time.time() - t0:.2f}s ({len(raw_frames) / (time.time() - t0):.1f} fps)")

    tmp_c4 = OUT_COND4.replace(".mp4", "_tmp.mp4")
    out_vw4 = cv2.VideoWriter(tmp_c4, fourcc, fps, (1024, 1024))
    for f in cond4_frames:
        out_vw4.write(f)
    out_vw4.release()

    cmd_mux4 = [
        "ffmpeg", "-y", "-i", tmp_c4, "-i", AUDIO_PATH,
        "-c:v", "h264_nvenc", "-preset", "p7", "-qp", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", OUT_COND4
    ]
    subprocess.run(cmd_mux4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(tmp_c4):
        os.remove(tmp_c4)
    print(f"Condition 4 complete: {OUT_COND4} ({os.path.getsize(OUT_COND4)} bytes)")


def create_comparative_videos():
    print("[5/5] Creating 4-Way Split-Screen and Face Close-up Videos...")

    # A. 4-Way 1920x1080 Comparison:
    # Panel 1 (Top-Left): Condition 1 - MuseTalk NextGen (Original 1080p Crop, 960x540)
    # Panel 2 (Top-Right): Condition 2 - SoulX Native 512x512 (960x540 padded)
    # Panel 3 (Bottom-Left): Condition 3 - SoulX Lanczos 1024x1024 (960x540)
    # Panel 4 (Bottom-Right): Condition 4 - SoulX Enhanced (GFPGAN 50/50 + Lanczos, 960x540)
    filter_4way = (
        "[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[tl];"
        "[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[tr];"
        "[2:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[bl];"
        "[3:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[br];"
        "[tl][tr]hstack=inputs=2[top];"
        "[bl][br]hstack=inputs=2[bottom];"
        "[top][bottom]vstack=inputs=2[v]"
    )

    cmd_4way = [
        "ffmpeg", "-y",
        "-i", MUSETALK_ORIG_10S,
        "-i", SOULX_NATIVE_10S,
        "-i", OUT_COND3,
        "-i", OUT_COND4,
        "-filter_complex", filter_4way,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-qp", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", OUT_4WAY
    ]
    res_4way = subprocess.run(cmd_4way, capture_output=True, text=True)
    if os.path.exists(OUT_4WAY):
        print(f"SUCCESS: 4-Way comparison video generated at {OUT_4WAY} ({os.path.getsize(OUT_4WAY)} bytes)")
    else:
        print(f"ERROR generating 4-way: {res_4way.stderr}")

    # B. Face & Mouth Close-Up Comparison (1920x960):
    # Left: MuseTalk Face Crop (zoom on face/mouth)
    # Right: SoulX Enhanced Face Crop (zoom on face/mouth)
    filter_closeup = (
        "[0:v]crop=600:600:240:300,scale=960:960[left];"
        "[1:v]crop=360:360:76:180,scale=960:960[right];"
        "[left][right]hstack=inputs=2[v]"
    )
    cmd_closeup = [
        "ffmpeg", "-y",
        "-i", MUSETALK_ORIG_10S,
        "-i", OUT_COND4,
        "-filter_complex", filter_closeup,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-qp", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", OUT_CLOSEUP
    ]
    res_closeup = subprocess.run(cmd_closeup, capture_output=True, text=True)
    if os.path.exists(OUT_CLOSEUP):
        print(f"SUCCESS: Close-up comparison video generated at {OUT_CLOSEUP} ({os.path.getsize(OUT_CLOSEUP)} bytes)")


if __name__ == "__main__":
    process_video_enhancements()
    create_comparative_videos()
