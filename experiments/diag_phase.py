# TEMPORARY diagnostic — NOT production. Same-latent-phase mouth fingerprint.
# The offline renderer indexes the body latent with mirror_index(length=810, i),
# period = 2*810 = 1620 frames = 64.8s @ 25fps. Frames 64.8s apart share the SAME
# body latent. If audio features are correct, those same-latent mouth crops DIFFER
# (different audio). If the feature is clamped to a single value after 30s, the
# post-30s same-latent crops are ~IDENTICAL (same latent + same clamped feature).
import os, sys, pickle, glob, subprocess
import numpy as np, cv2

VIDEO = sys.argv[1] if len(sys.argv) > 1 else r"D:\CongThang_AI_Avatar\renders\test_5min.mp4"
AVATAR = "fullbody_30_7_25fps"
ROOT = os.path.dirname(os.path.abspath(__file__))
MAXDIM = 1920; FPS = 25.0

with open(os.path.join(ROOT, "data", "avatars", AVATAR, "coords.pkl"), "rb") as f:
    coords = pickle.load(f)
first_img = sorted(glob.glob(os.path.join(ROOT, "data", "avatars", AVATAR, "full_imgs", "*")))
im0 = cv2.imread(first_img[0]); oh, ow = im0.shape[:2]
scale = MAXDIM / float(max(oh, ow))
c0 = coords[0]
x1,y1,x2,y2 = [int(round(v*scale)) for v in c0]
my1 = y1 + int((y2-y1)*0.55); my2 = y2; mx1, mx2 = x1, x2
print(f"mouth ROI=({mx1},{my1},{mx2},{my2})")

def frame_at(t_sec):
    cap = cv2.VideoCapture(VIDEO)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_sec*FPS))
    ret, fr = cap.read(); cap.release()
    return fr

def mouth_crop(t):
    fr = frame_at(t)
    if fr is None: return None
    g = cv2.cvtColor(fr[my1:my2, mx1:mx2], cv2.COLOR_BGR2GRAY)
    return g

def diff(a, b):
    if a is None or b is None: return None
    return float(np.mean(cv2.absdiff(a, b)))

# Same-latent-phase set: 64.8s apart. t=2 (pre-30s, real feature), then 66.8, 131.6 (post-30s, clamped).
# Also a few arbitrary timestamps for contrast.
ts = [2.0, 10.0, 20.0, 28.0, 35.0, 66.8, 100.0, 131.6, 160.0]
crops = {t: mouth_crop(t) for t in ts}
print("\nPairwise mean-abs-diff of mouth crops (0-255):")
print("       " + "".join(f"{t:>7.1f}" for t in ts))
for ta in ts:
    row = []
    for tb in ts:
        d = diff(crops[ta], crops[tb])
        row.append(f"{d:>7.2f}" if d is not None else "     -")
    print(f"{ta:>5.1f} " + "".join(row))

print("\nSAME-LATENT-PHASE pairs (should DIFFER if lip-sync alive, ~IDENTICAL if clamped):")
pairs = [(2.0, 66.8), (2.0, 131.6), (66.8, 131.6)]
for ta, tb in pairs:
    print(f"  t={ta:>5.1f}s vs t={tb:>5.1f}s  ->  diff={diff(crops[ta], crops[tb]):.3f}")

print("\nControl: pre-30s pairs (should DIFFER, different audio):")
for ta, tb in [(2.0, 20.0), (10.0, 28.0)]:
    print(f"  t={ta:>5.1f}s vs t={tb:>5.1f}s  ->  diff={diff(crops[ta], crops[tb]):.3f}")