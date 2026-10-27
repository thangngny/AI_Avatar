import os
import cv2
import numpy as np
import subprocess
import shutil

VID_BASELINE = r"G:\My Drive\AI_Avatar_Outputs\doTrang_chuan_truyen_hinh_10s.mp4"
VID_ENHANCED = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\doTrang_photoreal_enamel_10s.mp4"

OUT_LOCAL = r"D:\CongThang_AI_Avatar\v2_renders\so_sanh_macro_mieng_rang_10s.mp4"
OUT_GDRIVE = r"G:\My Drive\AI_Avatar_Outputs\so_sanh_macro_mieng_rang_10s.mp4"
TEMP_RAW = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\temp_macro_raw.mp4"

cap_b = cv2.VideoCapture(VID_BASELINE)
cap_e = cv2.VideoCapture(VID_ENHANCED)

fps = cap_b.get(cv2.CAP_PROP_FPS) or 25.0
total_frames = int(min(cap_b.get(cv2.CAP_PROP_FRAME_COUNT), cap_e.get(cv2.CAP_PROP_FRAME_COUNT)))
width_out, height_out = 1920, 960

print(f"Compositing {total_frames} frames @ {fps} fps ({width_out}x{height_out})...")

ffmpeg_cmd = [
    "ffmpeg", "-y", "-an",
    "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{width_out}x{height_out}", "-r", str(fps), "-i", "-",
    "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-b:v", "16M",
    "-pix_fmt", "yuv420p",
    TEMP_RAW
]

pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Coordinates for 480x480 head crop
# y from 340 to 820, x from 300 to 780
y1, y2 = 340, 820
x1, x2 = 300, 780

frame_idx = 0
while True:
    ret_b, frame_b = cap_b.read()
    ret_e, frame_e = cap_e.read()
    if not ret_b or not ret_e:
        break

    crop_b = frame_b[y1:y2, x1:x2]
    crop_e = frame_e[y1:y2, x1:x2]

    # Resize to 960x960
    left = cv2.resize(crop_b, (960, 960), interpolation=cv2.INTER_LANCZOS4)
    right = cv2.resize(crop_e, (960, 960), interpolation=cv2.INTER_LANCZOS4)

    # Combine into 1920x960 canvas
    canvas = np.zeros((960, 1920, 3), dtype=np.uint8)
    canvas[:, :960] = left
    canvas[:, 960:] = right

    # Draw vertical divider line
    canvas[:, 958:962] = [200, 200, 200]

    # Overlay HUD Headers
    # Left HUD Banner
    overlay = canvas.copy()
    cv2.rectangle(overlay, (20, 20), (940, 160), (20, 20, 20), -1)
    # Right HUD Banner
    cv2.rectangle(overlay, (980, 20), (1900, 160), (20, 30, 20), -1)
    cv2.addWeighted(overlay, 0.72, canvas, 0.28, 0, canvas)

    # Borders around banners
    cv2.rectangle(canvas, (20, 20), (940, 160), (80, 80, 180), 2)
    cv2.rectangle(canvas, (980, 20), (1900, 160), (60, 200, 80), 2)

    # Font rendering
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Left text
    cv2.putText(canvas, "TIEN CHUAN BAN DAU (MuseTalk V1.5)", (40, 60), font, 0.85, (220, 220, 220), 2, cv2.LINE_AA)
    cv2.putText(canvas, "- Rang sap mo, thieu ke rang rieng biet", (40, 100), font, 0.65, (100, 180, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "- Vien moi mo, go chuyen tiep vung cam", (40, 135), font, 0.65, (100, 180, 255), 1, cv2.LINE_AA)

    # Right text
    cv2.putText(canvas, "NEXTGEN PHOTOREAL (Men Rang + Sau 3D)", (1000, 60), font, 0.85, (80, 240, 120), 2, cv2.LINE_AA)
    cv2.putText(canvas, "+ Men rang trang sang, tach ro tung ke rang", (1000, 100), font, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "+ Khoang mieng toi sau 3D, cam lien mach 100%", (1000, 135), font, 0.65, (255, 255, 255), 1, cv2.LINE_AA)

    # Write to ffmpeg pipe
    pipe.stdin.write(canvas.tobytes())
    frame_idx += 1

cap_b.release()
cap_e.release()
pipe.stdin.close()
pipe.wait()

print(f"Video frames rendered ({frame_idx} frames). Muxing audio...")

# Mux audio from VID_ENHANCED
mux_cmd = [
    "ffmpeg", "-y",
    "-i", TEMP_RAW,
    "-i", VID_ENHANCED,
    "-map", "0:v",
    "-map", "1:a",
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    OUT_LOCAL
]

subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if os.path.exists(TEMP_RAW):
    os.remove(TEMP_RAW)

if os.path.exists(OUT_LOCAL):
    size_mb = os.path.getsize(OUT_LOCAL) / (1024 * 1024)
    print(f"SUCCESS: Saved local macro comparison video: {OUT_LOCAL} ({size_mb:.2f} MB)")
    shutil.copyfile(OUT_LOCAL, OUT_GDRIVE)
    print(f"SUCCESS: Synced to Google Drive: {OUT_GDRIVE}")
else:
    print("ERROR: Final video generation failed.")
