"""
AI Avatar NextGen V2 - Vertical 1080x1920 Composition Studio
Evaluates:
Strategy A: Branded News/Broadcast Layout (1080x1920 with Upper Title & Lower Third)
Strategy B: Dynamic Ambient Motion Backdrop (1080x1920 with 2.5x Blurred Video Wings)
Strategy C: Golden-Ratio Centered Canvas with Studio Gradient (1080x1920)
"""
import os
import subprocess

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission05")
os.makedirs(REPORTS_DIR, exist_ok=True)

INPUT_ENHANCED_10S = os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_10s_enhanced_gfpgan50.mp4")
INPUT_NATIVE_60S = os.path.join(REPO_ROOT, "reports", "mission04", "soulx_pro_60s.mp4")

OUT_STRAT_A = os.path.join(REPORTS_DIR, "vertical_stratA_broadcast_1080x1920.mp4")
OUT_STRAT_B = os.path.join(REPORTS_DIR, "vertical_stratB_ambient_1080x1920.mp4")
OUT_STRAT_C = os.path.join(REPORTS_DIR, "vertical_stratC_gradient_1080x1920.mp4")
OUT_FINAL_60S_VERT = os.path.join(REPORTS_DIR, "soulx_pro_60s_vertical_1080x1920.mp4")


def render_strategy_a(input_mp4, output_mp4):
    print(f"Rendering Strategy A (Broadcast Canvas 1080x1920) to {output_mp4}...")
    # 1024x1024 placed at Y=380 (eye level at ~35% from top).
    # Upper banner: Y=0..380 with subtle dark slate background.
    # Lower third: Y=1404..1920.
    filter_a = (
        "[0:v]scale=1080:1080[fg];"
        "color=c=#0f111a:s=1080x1920:r=25[bg];"
        "[bg][fg]overlay=x=0:y=380[v1];"
        "[v1]drawbox=x=0:y=0:w=1080:h=380:color=#181b28@0.9:t=fill,"
        "drawbox=x=0:y=1460:w=1080:h=460:color=#181b28@0.9:t=fill,"
        "drawbox=x=40:y=1500:w=1000:h=6:color=#e056fd:t=fill[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_mp4,
        "-filter_complex", filter_a,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Strategy A completed: {os.path.getsize(output_mp4)} bytes")


def render_strategy_b(input_mp4, output_mp4):
    print(f"Rendering Strategy B (Dynamic Ambient Wings 1080x1920) to {output_mp4}...")
    # Background: zoomed 2.6x to cover 1080x1920, heavily boxblurred, dimmed 40%
    # Foreground: 1080x1080 placed cleanly at Y=420 with a drop-shadow border
    filter_b = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,colorchannelmixer=aa=0.8:rr=0.6:gg=0.6:bb=0.6[bg];"
        "[0:v]scale=1080:1080[fg];"
        "[bg][fg]overlay=x=0:y=420[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_mp4,
        "-filter_complex", filter_b,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Strategy B completed: {os.path.getsize(output_mp4)} bytes")


def render_strategy_c(input_mp4, output_mp4):
    print(f"Rendering Strategy C (Clean Studio Gradient 1080x1920) to {output_mp4}...")
    # Pure clean dark studio gradient matching professional mobile video presentation
    filter_c = (
        "color=c=#141622:s=1080x1920:r=25[bg];"
        "[0:v]scale=1080:1080[fg];"
        "[bg][fg]overlay=x=0:y=420[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_mp4,
        "-filter_complex", filter_c,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
        "-rc", "vbr", "-cq", "16", "-b:v", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Strategy C completed: {os.path.getsize(output_mp4)} bytes")


if __name__ == "__main__":
    render_strategy_a(INPUT_ENHANCED_10S, OUT_STRAT_A)
    render_strategy_b(INPUT_ENHANCED_10S, OUT_STRAT_B)
    render_strategy_c(INPUT_ENHANCED_10S, OUT_STRAT_C)
    # Render final 60s vertical master using the best-performing dynamic ambient backdrop (Strategy B)
    render_strategy_b(INPUT_NATIVE_60S, OUT_FINAL_60S_VERT)
