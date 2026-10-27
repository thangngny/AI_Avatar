import os
import subprocess
import shutil

VID_BASELINE = r"G:\My Drive\AI_Avatar_Outputs\doTrang_chuan_truyen_hinh_10s.mp4"
VID_ENHANCED = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\doTrang_photoreal_enamel_10s.mp4"

OUT_LOCAL = r"D:\CongThang_AI_Avatar\v2_renders\so_sanh_macro_mieng_rang_10s.mp4"
OUT_GDRIVE = r"G:\My Drive\AI_Avatar_Outputs\so_sanh_macro_mieng_rang_10s.mp4"

filter_complex = (
    "[0:v]crop=480:480:300:340,scale=960:960:flags=lanczos,"
    "drawtext=text='TIÊU CHUẨN BAN ĐẦU (MuseTalk V1.5)':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.7:x=30:y=30,"
    "drawtext=text='- Răng dạng sáp mờ\\, thiếu kẽ răng':fontcolor=yellow:fontsize=22:box=1:boxcolor=black@0.6:x=30:y=80,"
    "drawtext=text='- Viền môi mờ\\, gờ chuyển tiếp cằm':fontcolor=yellow:fontsize=22:box=1:boxcolor=black@0.6:x=30:y=115[left];"
    "[1:v]crop=480:480:300:340,scale=960:960:flags=lanczos,"
    "drawtext=text='NEXTGEN PHOTOREAL (Men Răng + Độ Sâu 3D)':fontcolor=green:fontsize=28:box=1:boxcolor=black@0.7:x=30:y=30,"
    "drawtext=text='+ Tách rõ từng kẽ răng men sứ':fontcolor=white:fontsize=22:box=1:boxcolor=black@0.6:x=30:y=80,"
    "drawtext=text='+ Khoang miệng tối sâu 3D':fontcolor=white:fontsize=22:box=1:boxcolor=black@0.6:x=30:y=115,"
    "drawtext=text='+ Viền cằm liền mạch 100% C1 smooth':fontcolor=white:fontsize=22:box=1:boxcolor=black@0.6:x=30:y=150[right];"
    "[left][right]hstack=inputs=2[v]"
)

cmd = [
    "ffmpeg", "-y",
    "-r", "25", "-i", VID_BASELINE,
    "-r", "25", "-i", VID_ENHANCED,
    "-filter_complex", filter_complex,
    "-map", "[v]",
    "-map", "1:a",
    "-c:v", "h264_nvenc",
    "-preset", "p7",
    "-tune", "hq",
    "-b:v", "16M",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    OUT_LOCAL
]

print("Rendering Macro Close-up Comparison video...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0 and os.path.exists(OUT_LOCAL):
    size_mb = os.path.getsize(OUT_LOCAL) / (1024 * 1024)
    print(f"SUCCESS: Saved local macro comparison: {OUT_LOCAL} ({size_mb:.2f} MB)")
    
    # Sync to Google Drive
    shutil.copyfile(OUT_LOCAL, OUT_GDRIVE)
    print(f"SUCCESS: Synced to Google Drive: {OUT_GDRIVE}")
else:
    print(f"FFmpeg failed with code {res.returncode}:\n{res.stderr}")
