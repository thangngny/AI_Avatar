#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 2: authoritative MuseTalk face size from coords.pkl + reliable frontal
proxy (inter-ocular / face-width, face_w/face_h) via FAN. Drops the broken
solvePnP euler angles from pass 1."""
import os, glob, json, pickle
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
import numpy as np, cv2
import face_alignment

ROOT = os.path.dirname(os.path.abspath(__file__))
FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                  flip_input=False, device='cuda', verbose=False)


def first_img_shape(d):
    fi = sorted(glob.glob(os.path.join(d, "full_imgs", "*")))
    if not fi:
        return None, 0
    im = cv2.imread(fi[0])
    return (im.shape[:2] if im is not None else None), len(fi)


out = []
for name in sorted(os.listdir(os.path.join(ROOT, "data", "avatars"))):
    d = os.path.join(ROOT, "data", "avatars", name)
    if not os.path.isdir(d) or name == ".uploads":
        continue
    shape, n = first_img_shape(d)
    rec = dict(name=name, n_frames=n, frame=f"{shape[1]}x{shape[0]}" if shape else "?")
    # MuseTalk authoritative face bbox (coords.pkl) — median over first ~20 frames
    try:
        coords = pickle.load(open(os.path.join(d, "coords.pkl"), "rb"))
        mc = pickle.load(open(os.path.join(d, "mask_coords.pkl"), "rb"))
        k = min(20, len(coords))
        fhs = []; fws = []; fracs = []; margins = []
        for i in range(k):
            x1, y1, x2, y2 = coords[i]
            fw = x2 - x1; fh = y2 - y1
            fws.append(fw); fhs.append(fh); fracs.append(fh / shape[0])
            m = mc[i]
            margins.append((m[3] - y2) / max(fh, 1))  # mask margin below face / face_h
        rec.update(
            mt_face_w=float(np.median(fws)), mt_face_h=float(np.median(fhs)),
            mt_face_h_over_frame_h=float(np.median(fracs)),
            mt_margin_below_face_frac=float(np.median(margins)),
        )
    except Exception as e:
        rec["coords_error"] = str(e)
    # FAN frontal proxy + talking (vopen std) on ~20 frames
    fi = sorted(glob.glob(os.path.join(d, "full_imgs", "*")))
    if fi and shape:
        H, W = shape
        idxs = [min(len(fi) - 1, int(len(fi) * i / 20.0)) for i in range(20)]
        iors = []; whs = []; vopens = []; sharp = []
        for i in idxs:
            im = cv2.imread(fi[i])
            if im is None:
                continue
            scale = 1.0
            if max(im.shape[:2]) > 1280:
                scale = 1280.0 / max(im.shape[:2])
                im = cv2.resize(im, (int(W * scale), int(H * scale)))
            preds = FA.get_landmarks(im)
            if not preds:
                continue
            lm = preds[0] / scale
            face_w = np.linalg.norm(lm[0] - lm[16])
            face_h = np.linalg.norm(lm[8] - lm[19])  # chin to brow
            # inter-ocular: distance between eye centers (landmarks 36-41 vs 42-47)
            le = lm[36:42].mean(axis=0); re = lm[42:48].mean(axis=0)
            ior = np.linalg.norm(le - re) / max(face_w, 1e-6)
            iors.append(ior)
            whs.append(face_w / max(face_h, 1e-6))
            vopens.append(np.linalg.norm(lm[62] - lm[66]) / max(face_w, 1e-6))
            g = cv2.cvtColor(cv2.imread(fi[i]), cv2.COLOR_BGR2GRAY)
            sharp.append(float(cv2.Laplacian(g, cv2.CV_64F).var()))
        rec.update(
            frontal_iormed=float(np.median(iors)) if iors else None,
            face_w_over_h=float(np.median(whs)) if whs else None,
            vopen_std=float(np.std(vopens)) if vopens else None,
            vopen_max=float(np.max(vopens)) if vopens else None,
            frame_sharpness=float(np.median(sharp)) if sharp else None,
        )
    out.append(rec)
    print("done", name)

with open(r"D:\CongThang_AI_Avatar\avatar_audit\avatar_audit2.json", "w") as f:
    json.dump(out, f, indent=2)
print("\n%-26s %8s %6s %6s %6s %6s %5s %5s %6s" % (
    "avatar", "frame", "fh/fH", "mtMrg", "IOR", "w/h", "vstd", "vmax", "sharp"))
for r in out:
    print("%-26s %8s %6.3f %6.2f %5.3f %5.3f %5.3f %5.3f %6.0f" % (
        r["name"], r["frame"], r.get("mt_face_h_over_frame_h", 0) or 0,
        r.get("mt_margin_below_face_frac", 0) or 0, r.get("frontal_iormed", 0) or 0,
        r.get("face_w_over_h", 0) or 0, r.get("vopen_std", 0) or 0,
        r.get("vopen_max", 0) or 0, r.get("frame_sharpness", 0) or 0))
del FA