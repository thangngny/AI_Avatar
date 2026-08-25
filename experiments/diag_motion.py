# TEMPORARY diagnostic — NOT production. Mouth-motion timeline on an existing MP4.
# Shows whether mouth-region motion collapses at a specific timestamp while audio
# RMS stays high. Uses the avatar coords.pkl face bbox (downscaled) as the ROI.
import os, sys, pickle, subprocess, json
import numpy as np

VIDEO = sys.argv[1] if len(sys.argv) > 1 else r"D:\CongThang_AI_Avatar\renders\test_5min.mp4"
AVATAR = "fullbody_30_7_25fps"
ROOT = os.path.dirname(os.path.abspath(__file__))

# downscale factor the renderer applied (2160x3840 -> 1080x1920 = 0.5)
MAXDIM = 1920
import cv2
cap = cv2.VideoCapture(VIDEO)
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
FPS = cap.get(cv2.CAP_PROP_FPS)
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"video {W}x{H} {FPS}fps {N}frames")

# load coords.pkl (original resolution) and scale to output
with open(os.path.join(ROOT, "data", "avatars", AVATAR, "coords.pkl"), "rb") as f:
    coords = pickle.load(f)
# original frame size
import glob
first_img = glob.glob(os.path.join(ROOT, "data", "avatars", AVATAR, "full_imgs", "*"))
first_img.sort()
im0 = cv2.imread(first_img[0])
oh, ow = im0.shape[:2]
scale = MAXDIM / float(max(oh, ow))
c0 = coords[0]
x1,y1,x2,y2 = [int(round(v*scale)) for v in c0]
# mouth = lower 45% of the face crop
mouth_y1 = y1 + int((y2-y1)*0.55)
mouth_y2 = y2
mouth_x1, mouth_x2 = x1, x2
print(f"face bbox(scaled)=({x1},{y1},{x2},{y2}) mouth ROI=({mouth_x1},{mouth_y1},{mouth_x2},{mouth_y2})")

# stream frames, sample every 5th (=5fps), compute mouth ROI mean abs diff
step = 5
prev = None
per_sec = {}  # sec -> list of diffs
fi = 0
while True:
    ret, frame = cap.read()
    if not ret: break
    if fi % step == 0:
        crop = frame[mouth_y1:mouth_y2, mouth_x1:mouth_x2]
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            d = float(np.mean(cv2.absdiff(g, prev)))
            sec = int(fi / FPS)
            per_sec.setdefault(sec, []).append(d)
        prev = g
    fi += 1
cap.release()

# audio RMS per second (extract audio from mp4)
import soundfile as sf
awav = os.path.join(os.environ.get("TEMP", "/tmp"), "diag_audio.wav")
subprocess.run(["ffmpeg","-y","-i",VIDEO,"-ar","16000","-ac","1",awav],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
a, sr = sf.read(awav, dtype="float32")
def rms(block): return float(np.sqrt(np.mean(block**2)+1e-12))
audio_per_sec = {}
for s in range(int(len(a)/sr)+1):
    blk = a[s*sr:(s+1)*sr]
    if len(blk): audio_per_sec[s] = rms(blk)

print("\n=== motion vs audio timeline (5s buckets) ===")
print("time   mouth_motion   audio_rms   note")
for s0 in range(0, int(N/FPS), 5):
    diffs = []
    for s in range(s0, s0+5):
        diffs.extend(per_sec.get(s, []))
    mot = float(np.mean(diffs)) if diffs else 0.0
    arms = [audio_per_sec.get(s,0) for s in range(s0, s0+5)]
    arms = float(np.mean(arms)) if arms else 0.0
    flag = ""
    if mot < 1.0 and arms > 0.02: flag = " <-- MOUTH FROZEN but audio active"
    print(f"{s0:3d}s   {mot:8.3f}   {arms:8.4f}{flag}")