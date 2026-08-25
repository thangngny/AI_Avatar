#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 Phase 4/14 — mouth-range measurement on a rendered MP4.

Runs FAN (face_alignment, 68 landmarks) on sampled frames, using the avatar
coords.pkl face bbox (downscaled to 1080x1920) as a crop hint for fast+robust
detection. Reports mouth vertical opening, width, area, temporal std
(diversity) and frame-to-frame motion — overall and per-5s buckets. Pure
numeric measurement; no image is read by a language model.

Reusable: run on the baseline and every A/B/C candidate to compare ranges.

Usage:
  latentsync_env\\Scripts\\python.exe stage5_measure.py <video> <label> [out_json]
"""
import os, sys, json, glob, pickle
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
import numpy as np, cv2
import face_alignment

VIDEO = sys.argv[1]
LABEL = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(VIDEO)
OUT = sys.argv[3] if len(sys.argv) > 3 else VIDEO.replace(".mp4", "_mouth.json")
# avatar_id whose coords.pkl supplies the FAN face-bbox crop hint. MUST match
# the avatar that was rendered in VIDEO, otherwise the crop hint misses the
# face and FAN returns no landmarks. Defaults to the Stage 5 active avatar so
# all existing measurements stay bit-identical.
AV = sys.argv[4] if len(sys.argv) > 4 else "fullbody_30_7_25fps"
ROOT = os.path.dirname(os.path.abspath(__file__))
MAXDIM = 1920

# face bbox crop hint from coords.pkl (scaled like the renderer)
with open(os.path.join(ROOT, "data", "avatars", AV, "coords.pkl"), "rb") as f:
    coords = pickle.load(f)
first = sorted(glob.glob(os.path.join(ROOT, "data", "avatars", AV, "full_imgs", "*")))
im0 = cv2.imread(first[0]); oh, ow = im0.shape[:2]
scale = MAXDIM / float(max(oh, ow))
c0 = [int(round(v * scale)) for v in coords[0]]
x1, y1, x2, y2 = c0
fw_ = x2 - x1; fh_ = y2 - y1; pad = int(0.35 * max(fw_, fh_))
cb = (max(0, x1 - pad), max(0, y1 - pad), x2 + pad, y2 + pad)
print(f"[measure] avatar={AV} face bbox hint {c0} -> crop {cb}")

FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                  flip_input=False, device='cuda', verbose=False)
LIP_TOP_IN, LIP_BOT_IN = 62, 66
MOUTH_L, MOUTH_R = 48, 54
LIP_TOP_OUT, LIP_BOT_OUT = 51, 57
FACE_L, FACE_R = 0, 16
# non-mouth landmarks for identity-stability (should be ~constant across gains
# because paste-back keeps the mask-bound generated face; large std => the gain
# is distorting eyes/nose/jaw, i.e. identity leakage).
NOSE_TIP = 30
CHIN = 8
BROW_L = 19
BROW_R = 24
EYE_L = 36
EYE_R = 45

cap = cv2.VideoCapture(VIDEO)
FPS = cap.get(cv2.CAP_PROP_FPS) or 25.0
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"[measure] {LABEL}: {W}x{H} {FPS}fps {N} frames")
STEP = 2  # sample every 2nd frame (~12.5 fps) — enough for mouth range
rows = []
fi = 0
while True:
    ret, fr = cap.read()
    if not ret:
        break
    if fi % STEP == 0:
        cx1, cy1, cx2, cy2 = cb
        region = fr[max(0, cy1):min(H, cy2), max(0, cx1):min(W, cx2)]
        ox, oy = max(0, cx1), max(0, cy1)
        preds = FA.get_landmarks(region)
        if preds:
            lm = preds[0] + np.array([ox, oy])
            face_w = float(np.linalg.norm(lm[FACE_L] - lm[FACE_R]))
            vopen = float(np.linalg.norm(lm[LIP_TOP_IN] - lm[LIP_BOT_IN]))
            vopen_o = float(np.linalg.norm(lm[LIP_TOP_OUT] - lm[LIP_BOT_OUT]))
            width = float(np.linalg.norm(lm[MOUTH_L] - lm[MOUTH_R]))
            t = fi / FPS
            # non-mouth landmark positions (normalized by face_w, relative to
            # face center) for identity-stability tracking
            fc = (lm[FACE_L] + lm[FACE_R]) / 2.0
            def rel(i):
                d = lm[i] - fc
                return (d[0] / max(face_w, 1e-6), d[1] / max(face_w, 1e-6))
            rows.append(dict(frame=fi, t=t, vopen=vopen / max(face_w, 1e-6),
                             vopen_o=vopen_o / max(face_w, 1e-6),
                             width=width / max(face_w, 1e-6),
                             area=(vopen * width) / max(face_w * face_w, 1e-6),
                             nose=rel(NOSE_TIP), chin=rel(CHIN),
                             eye_l=rel(EYE_L), eye_r=rel(EYE_R),
                             brow_l=rel(BROW_L), brow_r=rel(BROW_R)))
    fi += 1
cap.release()
del FA
print(f"[measure] {len(rows)} frames measured")

def bucket(field):
    return dict(min=float(np.min([r[field] for r in rows])),
                max=float(np.max([r[field] for r in rows])),
                mean=float(np.mean([r[field] for r in rows])),
                std=float(np.std([r[field] for r in rows])),
                range=float(np.max([r[field] for r in rows]) - np.min([r[field] for r in rows])))

overall = {k: bucket(k) for k in ("vopen", "vopen_o", "width", "area")}
# motion = mean abs frame-to-frame delta of vopen (articulation activity)
vopens = np.array([r["vopen"] for r in rows])
motion = float(np.mean(np.abs(np.diff(vopens)))) if len(vopens) > 1 else 0.0
# per-5s buckets: mean + temporal std (diversity)
buckets = []
for s0 in range(0, int(N / FPS), 5):
    sub = [r for r in rows if s0 <= r["t"] < s0 + 5]
    if len(sub) >= 2:
        vals = np.array([r["vopen"] for r in sub]); widths = np.array([r["width"] for r in sub])
        buckets.append(dict(t0=s0, n=len(sub),
                            vopen_mean=float(vals.mean()), vopen_std=float(vals.std()),
                            vopen_range=float(vals.max() - vals.min()),
                            width_mean=float(widths.mean()), width_std=float(widths.std())))

print(f"\n=== {LABEL}  mouth range (normalized by face width) ===")
print(f"  vopen_inner: mean {overall['vopen']['mean']:.4f}  range {overall['vopen']['min']:.4f}-{overall['vopen']['max']:.4f} (span {overall['vopen']['range']:.4f})  std {overall['vopen']['std']:.4f}")
print(f"  vopen_outer: mean {overall['vopen_o']['mean']:.4f}  range {overall['vopen_o']['range']:.4f}")
print(f"  width     : mean {overall['width']['mean']:.4f}  range {overall['width']['min']:.4f}-{overall['width']['max']:.4f} (span {overall['width']['range']:.4f})  std {overall['width']['std']:.4f}")
print(f"  motion (mean|dV|): {motion:.5f}")
# identity stability: std of non-mouth landmark positions across frames.
# Low => eyes/nose/chin don't jitter with gain => identity preserved.
def lstd(key):
    vals = np.array([r[key] for r in rows])  # (N,2)
    return float(np.mean(np.std(vals, axis=0)))
ident = dict(nose=lstd("nose"), chin=lstd("chin"), eye_l=lstd("eye_l"),
             eye_r=lstd("eye_r"), brow_l=lstd("brow_l"), brow_r=lstd("brow_r"),
             mean=float(np.mean([lstd(k) for k in ("nose","chin","eye_l","eye_r","brow_l","brow_r")])))
print(f"  identity_std (non-mouth landmark pos, lower=more stable): mean {ident['mean']:.5f}  "
      f"nose {ident['nose']:.5f} chin {ident['chin']:.5f} eye_l {ident['eye_l']:.5f} eye_r {ident['eye_r']:.5f}")
print(f"  per-5s vopen_mean/vopen_std(vopen_range):")
for b in buckets:
    print(f"    {b['t0']:3d}s  mean {b['vopen_mean']:.4f}  std {b['vopen_std']:.4f}  range {b['vopen_range']:.4f}   width_mean {b['width_mean']:.4f} std {b['width_std']:.4f}")

out = dict(label=LABEL, video=VIDEO, n_measured=len(rows), overall=overall,
           motion=motion, identity_std=ident, buckets=buckets, rows=rows)
with open(OUT, "w") as f:
    json.dump(out, f, indent=2)
print(f"[measure] wrote {OUT}")