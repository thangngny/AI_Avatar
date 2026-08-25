#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Input avatar audit. Numeric only (no image read by a model). For each prepared
avatar folder: face size, head pose (solvePnP), mouth/chin visibility, sharpness,
source-mouth motion (neutral vs talking), frame/lighting stability, and the
prepared mask/coords lower-face margin. Also writes contact sheets (5 frames)
for human review."""
import os, sys, glob, json, pickle
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
import numpy as np, cv2
import face_alignment

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTDIR = r"D:\CongThang_AI_Avatar\avatar_audit"
os.makedirs(OUTDIR, exist_ok=True)

FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                  flip_input=False, device='cuda', verbose=False)

MODEL_3D = np.array([
    (0.0, 0.0, 0.0), (0.0, -330.0, -65.0),
    (-225.0, 170.0, -135.0), (225.0, 170.0, -135.0),
    (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0),
], dtype=np.float64)
LMK_2D_IDX = [30, 8, 45, 36, 48, 54]


def pose(lm):
    image_points = np.array([lm[i] for i in LMK_2D_IDX], dtype=np.float64)
    cam = np.array([[1000, 0, 500], [0, 1000, 500], [0, 0, 1]], dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(MODEL_3D, image_points, cam, np.zeros((4, 1)),
                                 flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None
    rmat, _ = cv2.Rodrigues(rvec)
    pitch = float(np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2])))
    yaw = float(np.degrees(np.arctan2(-rmat[2, 0], np.sqrt(rmat[2, 1] ** 2 + rmat[2, 2] ** 2))))
    roll = float(np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0])))
    return yaw, pitch, roll


def face_bbox_from_lmk(lm):
    return float(lm[:, 0].min()), float(lm[:, 1].min()), float(lm[:, 0].max()), float(lm[:, 1].max())


def measure_avatar(name):
    d = os.path.join(ROOT, "data", "avatars", name)
    fi = sorted(glob.glob(os.path.join(d, "full_imgs", "*")))
    if not fi:
        return None
    n = len(fi)
    sample_idx = [min(n - 1, int(n * f)) for f in (0.10, 0.25, 0.50, 0.75, 0.90)]
    motion_idx = [min(n - 1, int(n * (i / 24.0))) for i in range(24)]
    load_idx = sorted(set(sample_idx + motion_idx))
    cache = {}
    for i in load_idx:
        im = cv2.imread(fi[i])
        if im is None:
            cache[i] = None
            continue
        h, w = im.shape[:2]
        scale = 1.0
        if max(h, w) > 1280:
            scale = 1280.0 / max(h, w)
            im_small = cv2.resize(im, (int(w * scale), int(h * scale)))
        else:
            im_small = im
        cache[i] = (im, im_small, scale)
    geo = []; poses = []; vopens = []; centers = []; scales = []; sharp = []; luma = []
    for i in load_idx:
        c = cache[i]
        if c is None:
            continue
        im, im_small, scale = c
        preds = FA.get_landmarks(im_small)
        if not preds:
            continue
        lm = preds[0] / scale
        x1, y1, x2, y2 = face_bbox_from_lmk(lm)
        fw = x2 - x1; fh = y2 - y1
        H, W = im.shape[:2]
        geo.append(dict(fw=fw, fh=fh, frame_h=H, frame_a=W * H))
        p = pose(lm)
        if p:
            poses.append(p)
        face_w = np.linalg.norm(lm[0] - lm[16])
        vopens.append(float(np.linalg.norm(lm[62] - lm[66]) / max(face_w, 1e-6)))
        centers.append((float((x1 + x2) / 2), float((y1 + y2) / 2)))
        scales.append(fh / H)
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        sharp.append(float(cv2.Laplacian(gray[int(max(0, y1)):int(min(H, y2)),
                                             int(max(0, x1)):int(min(W, x2))], cv2.CV_64F).var()))
        luma.append(float(gray[int(max(0, y1)):int(min(H, y2)), int(max(0, x1)):int(min(W, x2))].mean()))
    if not geo:
        return None
    chin_margins = []; mouth_in_frame = True
    for i in sample_idx:
        c = cache.get(i)
        if c is None:
            continue
        im, im_small, scale = c
        preds = FA.get_landmarks(im_small)
        if not preds:
            continue
        lm = preds[0] / scale
        H = im.shape[0]
        face_w = np.linalg.norm(lm[0] - lm[16])
        chin_margins.append((H - float(lm[8][1])) / max(face_w, 1e-6))
        if lm[66][1] > H - 2 or lm[8][1] > H - 2:
            mouth_in_frame = False
    prep = {}
    try:
        coords = pickle.load(open(os.path.join(d, "coords.pkl"), "rb"))
        mc = pickle.load(open(os.path.join(d, "mask_coords.pkl"), "rb"))
        c0 = coords[0]; m0 = mc[0]
        prep["face_bbox0"] = list(int(v) for v in c0)
        prep["mask_crop0"] = list(int(v) for v in m0)
        prep["margin_below_face_px"] = int(m0[3] - c0[3])
        prep["margin_below_face_frac"] = float((m0[3] - c0[3]) / max(c0[3] - c0[1], 1))
    except Exception as e:
        prep["error"] = str(e)
    fh_arr = np.array([g['fh'] for g in geo])
    res = dict(
        name=name, n_frames=n,
        resolution=f"{int(im.shape[1])}x{int(im.shape[0])}" if cache else "?",
        face_w_med=float(np.median([g['fw'] for g in geo])),
        face_h_med=float(np.median(fh_arr)),
        face_h_over_frame_h=float(np.median(fh_arr / np.array([g['frame_h'] for g in geo]))),
        face_area_frac=float(np.median(np.array([g['fw'] * g['fh'] for g in geo]) /
                                       np.array([g['frame_a'] for g in geo]))),
        face_h_range=(float(fh_arr.min()), float(fh_arr.max())),
        yaw_med=float(np.median([abs(p[0]) for p in poses])) if poses else None,
        pitch_med=float(np.median([abs(p[1]) for p in poses])) if poses else None,
        roll_med=float(np.median([abs(p[2]) for p in poses])) if poses else None,
        yaw_max=float(np.max([abs(p[0]) for p in poses])) if poses else None,
        pitch_max=float(np.max([abs(p[1]) for p in poses])) if poses else None,
        chin_margin_med=float(np.median(chin_margins)) if chin_margins else None,
        mouth_in_frame=mouth_in_frame,
        sharpness_med=float(np.median(sharp)),
        vopen_mean=float(np.mean(vopens)),
        vopen_std=float(np.std(vopens)),
        vopen_max=float(np.max(vopens)),
        center_std_y=float(np.std([c[1] for c in centers])),
        center_std_x=float(np.std([c[0] for c in centers])),
        scale_std=float(np.std(scales)),
        luma_std=float(np.std(luma)),
        prep=prep,
    )
    try:
        sheets = []
        for i in sample_idx:
            c = cache.get(i)
            if c is None:
                continue
            im = c[0]
            sh = int(480 * im.shape[0] / im.shape[1])
            sheets.append(cv2.resize(im, (480, sh)))
        if sheets:
            row = np.hstack(sheets)
            cv2.imwrite(os.path.join(OUTDIR, f"contact_{name}.jpg"), row,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    except Exception as e:
        res["sheet_error"] = str(e)
    return res


folders = [n for n in sorted(os.listdir(os.path.join(ROOT, "data", "avatars")))
           if os.path.isdir(os.path.join(ROOT, "data", "avatars", n)) and n != ".uploads"]
results = []
for n in folders:
    r = measure_avatar(n)
    if r:
        results.append(r)
    print("done", n)
with open(os.path.join(OUTDIR, "avatar_audit.json"), "w") as f:
    json.dump(results, f, indent=2)
print("\n%-26s %6s %6s %5s %5s %5s %6s %6s %5s %5s %6s %6s %5s %5s" % (
    "avatar", "fh/fH", "fac%", "yaw", "pth", "roll", "chinM", "sharp", "vstd", "vmax", "cyStd", "scStd", "luma", "mrgM"))
for r in results:
    print("%-26s %6.3f %5.2f %4.0f %4.0f %4.0f %5.2f %6.0f %4.3f %4.3f %5.0f %5.4f %4.0f %4.2f" % (
        r["name"], r["face_h_over_frame_h"], r["face_area_frac"] * 100,
        r["yaw_med"] or 0, r["pitch_med"] or 0, r["roll_med"] or 0,
        r["chin_margin_med"] or 0, r["sharpness_med"], r["vopen_std"], r["vopen_max"],
        r["center_std_y"] or 0, r["scale_std"], r["luma_std"],
        r.get("prep", {}).get("margin_below_face_frac", 0) or 0))
del FA