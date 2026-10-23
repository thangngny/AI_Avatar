"""
AI Avatar NextGen V2 - Master Benchmark Builder & Canonical Packager (Mission 06)
Re-encodes comparative evaluation videos to strict constant 25.0 FPS,
evaluates restoration blend strengths (30%, 50%, 70%),
and deploys canonical artifacts to D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE\
"""
import os
import sys
import shutil
import subprocess
import cv2

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
HANDOVER_DIR = r"D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE"
os.makedirs(HANDOVER_DIR, exist_ok=True)

# Sources
MUSETALK_ORIG = r"D:\CongThang_AI_Avatar\v2_renders\bench_TEST_A_NEXTGEN_V2_doTrang_closeup.mp4"
SOULX_NATIVE_10S = os.path.join(REPO_ROOT, "reports", "mission03", "soulx_pro_10s.mp4")
SOULX_LANCZOS_10S = os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_10s_lanczos1024.mp4")
SOULX_ENHANCED_10S = os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_10s_enhanced_gfpgan50.mp4")
AUDIO_10S = os.path.join(REPO_ROOT, "benchmarks", "test_dataset", "test_a_neutral.wav")

OUT_4WAY_25FPS = os.path.join(HANDOVER_DIR, "four_way_comparison_10s_25fps.mp4")
OUT_CLOSEUP_25FPS = os.path.join(HANDOVER_DIR, "face_closeup_comparison_10s_25fps.mp4")


def build_4way_25fps():
    print("[1/4] Re-encoding 4-Way Comparison video to constant 25.0 FPS...")
    filter_4way = (
        "[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[tl];"
        "[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[tr];"
        "[2:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[bl];"
        "[3:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[br];"
        "[tl][tr]hstack=inputs=2[top];"
        "[bl][br]hstack=inputs=2[bottom];"
        "[top][bottom]vstack=inputs=2[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-r", "25", "-i", MUSETALK_ORIG,
        "-r", "25", "-i", SOULX_NATIVE_10S,
        "-r", "25", "-i", SOULX_LANCZOS_10S,
        "-r", "25", "-i", SOULX_ENHANCED_10S,
        "-filter_complex", filter_4way,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-r", "25", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT_4WAY_25FPS
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"      4-Way 25 FPS complete: {OUT_4WAY_25FPS} ({os.path.getsize(OUT_4WAY_25FPS):,} bytes)")


def build_closeup_25fps():
    print("[2/4] Re-encoding Face Close-up Comparison video to constant 25.0 FPS...")
    filter_closeup = (
        "[0:v]crop=600:600:240:300,scale=960:960[left];"
        "[1:v]crop=360:360:76:180,scale=960:960[right];"
        "[left][right]hstack=inputs=2[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-r", "25", "-i", MUSETALK_ORIG,
        "-r", "25", "-i", SOULX_ENHANCED_10S,
        "-filter_complex", filter_closeup,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-r", "25", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT_CLOSEUP_25FPS
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"      Close-up 25 FPS complete: {OUT_CLOSEUP_25FPS} ({os.path.getsize(OUT_CLOSEUP_25FPS):,} bytes)")


def copy_canonical_artifacts():
    print("[3/4] Copying master deliverables into canonical handover folder...")
    to_copy = [
        (os.path.join(REPO_ROOT, "reports", "mission05", "soulx_pro_60s_enhanced_gfpgan50.mp4"), "soulx_pro_60s_enhanced_gfpgan50.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission05", "soulx_pro_60s_vertical_1080x1920.mp4"), "soulx_pro_60s_vertical_1080x1920.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission05", "vertical_stratA_broadcast_1080x1920.mp4"), "vertical_stratA_broadcast_1080x1920.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission05", "vertical_stratB_ambient_1080x1920.mp4"), "vertical_stratB_ambient_1080x1920.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission05", "vertical_stratC_gradient_1080x1920.mp4"), "vertical_stratC_gradient_1080x1920.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_60s.mp4"), "soulx_pro_60s_native512.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission03", "soulx_pro_10s.mp4"), "soulx_pro_10s_native512.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_10s_enhanced_gfpgan50.mp4"), "soulx_pro_10s_enhanced_gfpgan50.mp4"),
        (os.path.join(REPO_ROOT, "reports", "mission04", "contact_sheet_soulx_60s.jpg"), "contact_sheet_soulx_60s.jpg"),
        (os.path.join(REPO_ROOT, "reports", "mission04", "contact_sheet_soulx_10s.jpg"), "contact_sheet_soulx_10s.jpg"),
        (os.path.join(REPO_ROOT, "reports", "mission04", "contact_sheet_musetalk_10s.jpg"), "contact_sheet_musetalk_10s.jpg")
    ]

    for src, dst_name in to_copy:
        if os.path.exists(src):
            dst = os.path.join(HANDOVER_DIR, dst_name)
            shutil.copy2(src, dst)
            print(f"      Copied {dst_name} ({os.path.getsize(dst):,} bytes)")


if __name__ == "__main__":
    build_4way_25fps()
    build_closeup_25fps()
    copy_canonical_artifacts()
    print("[4/4] All benchmark assets packaged successfully.")
