# TEMPORARY diagnostic — NOT production. Per-5s mouth-shape diversity.
# Diversity = mean over pixels of the temporal std of the mouth crop within the
# window. High => mouth opens/closes (lip-sync active). Low => static mouth.
import os, sys, pickle, glob, subprocess
import numpy as np, cv2

VIDEO = sys.argv[1]
LABEL = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(VIDEO)
AVATAR = "fullbody_30_7_25fps"
ROOT = os.path.dirname(os.path.abspath(__file__))
MAXDIM = 1920; FPS = 25.0

with open(os.path.join(ROOT, "data", "avatars", AVATAR, "coords.pkl"), "rb") as f:
    coords = pickle.load(f)
first_img = sorted(glob.glob(os.path.join(ROOT, "data", "avatars", AVATAR, "full_imgs", "*")))
im0 = cv2.imread(first_img[0]); oh, ow = im0.shape[:2]
scale = MAXDIM / float(max(oh, ow))
x1,y1,x2,y2 = [int(round(v*scale)) for v in coords[0]]
my1 = y1 + int((y2-y1)*0.55); my2 = y2; mx1, mx2 = x1, x2

cap = cv2.VideoCapture(VIDEO)
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
# collect mouth crops at 5fps (every 5th frame)
crops_by_sec = {}
fi = 0
while True:
    ret, fr = cap.read()
    if not ret: break
    if fi % 5 == 0:
        g = cv2.cvtColor(fr[my1:my2, mx1:mx2], cv2.COLOR_BGR2GRAY)
        crops_by_sec.setdefault(int(fi/FPS), []).append(g)
    fi += 1
cap.release()

# audio rms per sec
awav = os.path.join(os.environ.get("TEMP","/tmp"),"diag_a.wav")
subprocess.run(["ffmpeg","-y","-i",VIDEO,"-ar","16000","-ac","1",awav],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import soundfile as sf
a, sr = sf.read(awav, dtype="float32")
arms = {}
for s in range(int(len(a)/sr)+1):
    b = a[s*sr:(s+1)*sr]
    if len(b): arms[s] = float(np.sqrt(np.mean(b**2)+1e-12))

print(f"\n=== {LABEL}  ({N} frames, {N/FPS:.1f}s) ===")
print("time   mouth_diversity   audio_rms   flag")
for s0 in range(0, int(N/FPS), 5):
    cs = []
    for s in range(s0, s0+5):
        cs.extend(crops_by_sec.get(s, []))
    if len(cs) >= 2:
        stack = np.stack(cs, axis=0).astype(np.float32)
        div = float(np.mean(np.std(stack, axis=0)))
    else:
        div = 0.0
    ar = float(np.mean([arms.get(s,0) for s in range(s0, s0+5)]))
    flag = ""
    if div < 3.0 and ar > 0.02: flag = " <-- mouth STATIC while audio active"
    print(f"{s0:3d}s   {div:12.3f}   {ar:8.4f}{flag}")