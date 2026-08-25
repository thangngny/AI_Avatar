#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 3: mask alpha coverage over the mouth region for top candidates.
If the parsing mask does not cover the mouth, the closed source mouth shows
through and articulation is hidden — a disqualifier regardless of face size."""
import os, glob, json, pickle
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
import numpy as np, cv2
import face_alignment

ROOT = os.path.dirname(os.path.abspath(__file__))
FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                  flip_input=False, device='cuda', verbose=False)

CAND = ["close_up", "close_up_16_7", "23_7_avt", "full_body_16_7",
        "fullbody_30_7_25fps", "fullbody_30_7_mouth_chin", "30_7close", "fulbody_2_8"]

out = []
for name in CAND:
    d = os.path.join(ROOT, "data", "avatars", name)
    if not os.path.isdir(d):
        continue
    fi = sorted(glob.glob(os.path.join(d, "full_imgs", "*")))
    masks = sorted(glob.glob(os.path.join(d, "mask", "*")))
    try:
        coords = pickle.load(open(os.path.join(d, "coords.pkl"), "rb"))
        mc = pickle.load(open(os.path.join(d, "mask_coords.pkl"), "rb"))
    except Exception:
        continue
    # sample 8 frames
    idxs = [min(len(fi) - 1, int(len(fi) * f)) for f in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 0.95, 0.5)]
    mouth_alphas = []; chin_alphas = []; lip_under_alphas = []
    for i in idxs:
        im = cv2.imread(fi[i])
        if im is None:
            continue
        H, W = im.shape[:2]
        scale = 1280.0 / max(H, W) if max(H, W) > 1280 else 1.0
        im_s = cv2.resize(im, (int(W * scale), int(H * scale))) if scale != 1 else im
        preds = FA.get_landmarks(im_s)
        if not preds:
            continue
        lm = preds[0] / scale
        # mouth bbox (landmarks 48-67)
        mx1, my1 = lm[48:68, 0].min(), lm[48:68, 1].min()
        mx2, my2 = lm[48:68, 0].max(), lm[48:68, 1].max()
        # mask in crop-box coords
        cx1, cy1, cx2, cy2 = mc[i % len(mc)]
        mask_im = cv2.imread(masks[i % len(masks)], cv2.IMREAD_GRAYSCALE)
        if mask_im is None:
            continue
        mask_resized = cv2.resize(mask_im, (cx2 - cx1, cy2 - cy1))
        # mouth in crop-frame coords -> mask index
        def region_alpha(rx1, ry1, rx2, ry2):
            ix1 = int(max(0, rx1 - cx1)); iy1 = int(max(0, ry1 - cy1))
            ix2 = int(min(mask_resized.shape[1], rx2 - cx1)); iy2 = int(min(mask_resized.shape[0], ry2 - cy1))
            if ix2 <= ix1 or iy2 <= iy1:
                return None
            return float(mask_resized[iy1:iy2, ix1:ix2].mean()) / 255.0
        ma = region_alpha(mx1, my1, mx2, my2)
        # chin (landmark 8) small region
        ca = region_alpha(lm[8][0] - 15, lm[8][1] - 8, lm[8][0] + 15, lm[8][1] + 15)
        # lips+under-lip strip (mouth to chin)
        ua = region_alpha(mx1, my2, mx2, lm[8][1] + 10)
        if ma is not None: mouth_alphas.append(ma)
        if ca is not None: chin_alphas.append(ca)
        if ua is not None: lip_under_alphas.append(ua)
    rec = dict(name=name,
               mouth_alpha_med=float(np.median(mouth_alphas)) if mouth_alphas else None,
               mouth_alpha_min=float(np.min(mouth_alphas)) if mouth_alphas else None,
               chin_alpha_med=float(np.median(chin_alphas)) if chin_alphas else None,
               underlip_alpha_med=float(np.median(lip_under_alphas)) if lip_under_alphas else None,
               n=len(mouth_alphas))
    out.append(rec)
    print("done", name)

print("\n%-26s %10s %10s %10s %9s" % ("avatar", "mouth_a", "mouth_min", "chin_a", "underlip"))
for r in out:
    print("%-26s %10.3f %10.3f %10.3f %9.3f" % (
        r["name"], r["mouth_alpha_med"] or 0, r["mouth_alpha_min"] or 0,
        r["chin_alpha_med"] or 0, r["underlip_alpha_med"] or 0))
with open(r"D:\CongThang_AI_Avatar\avatar_audit\avatar_audit3.json", "w") as f:
    json.dump(out, f, indent=2)
del FA