"""
AI Avatar NextGen V2 - Professional Aspect-Preserving A/B Test Compositor
Compares Condition A (MuseTalk NextGen V2) against Condition B (SoulX-FlashHead Pro 1.3B)
in a side-by-side 1920x960 video with zero aspect-ratio distortion.
"""
import os
import sys
import subprocess
import json

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission03")

vid_muse = r"D:\CongThang_AI_Avatar\v2_renders\bench_TEST_A_NEXTGEN_V2_doTrang_closeup.mp4"
vid_soulx = os.path.join(REPORTS_DIR, "soulx_pro_10s.mp4")
out_cmp = os.path.join(REPORTS_DIR, "musetalk_vs_soulx_pro.mp4")

def composite():
    if not os.path.exists(vid_soulx):
        print(f"ERROR: SoulX video not found at {vid_soulx}")
        return False

    if not os.path.exists(vid_muse):
        print(f"ERROR: MuseTalk baseline video not found at {vid_muse}")
        return False

    print("Compositing true aspect-ratio side-by-side video...")
    filter_complex = (
        "[0:v]scale=540:960,pad=960:960:(960-540)/2:0:black,"
        "drawtext=text='Condition A\\: MuseTalk NextGen (Mouth Patch)':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:x=40:y=40[left];"
        "[1:v]scale=960:960,"
        "drawtext=text='Condition B\\: SoulX-FlashHead Pro (Full DiT Head)':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:x=40:y=40[right];"
        "[left][right]hstack=inputs=2[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", vid_muse,
        "-i", vid_soulx,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "h264_nvenc",
        "-preset", "p7",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_cmp
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(out_cmp):
        sz = os.path.getsize(out_cmp)
        print(f"SUCCESS: Composite video generated at {out_cmp} ({sz} bytes)")
        return True
    else:
        print(f"FFmpeg failed with code {res.returncode}:\n{res.stderr}")
        return False

if __name__ == "__main__":
    composite()
