#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline EXPERIMENTAL source-quality gate for raw avatar-input videos.

Evaluates a candidate RAW source video (the file BEFORE MuseTalk preprocessing)
and reports PASS / WARN / FAIL per category plus a machine-readable JSON.

Categories:
  VIDEO_INTEGRITY, FACE_SIZE, FACE_SHARPNESS, FRONTALNESS, MOUTH_VISIBILITY,
  CHIN_VISIBILITY, SOURCE_MOUTH_STATE, MOTION, LIGHTING

Design rules (per lip-sync source-optimization task):
  * Offline only: no internet, no OCR, no model downloads.
  * Never mutates the source.
  * Does NOT depend on the torch/MuseTalk env; OpenCV + NumPy only.
  * Resolution alone does NOT dominate: a 4K full-body source with a tiny face
    scores WORSE than a sharp 1080p close-up. Usable face pixels, lip detail,
    frontalness, neutral mouth, chin/jaw visibility and stability are weighted.

Usage:
  python tools/avatar_source_quality/validator.py --video <path> [--json out.json]
  python tools/avatar_source_quality/validator.py --video <path> --strict

Exit code: 0 = overall PASS, 1 = overall WARN, 2 = overall FAIL, 3 = error.

NOTE: This is a SOURCE gate, not a render-quality tool. It is NOT wired into
production and uses no production config.
"""
import argparse, json, os, sys
import cv2
import numpy as np

FACE_CASCADE = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_alt2.xml"))
FACE_CASCADE_DEF = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
PROFILE_CASCADE = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_profileface.xml"))
EYE_CASCADE = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml"))


def detect_face(gray):
    for c in (FACE_CASCADE, FACE_CASCADE_DEF):
        f = c.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(60, 60))
        if len(f):
            return sorted(f, key=lambda b: b[2] * b[3], reverse=True)[0]
    p = PROFILE_CASCADE.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(60, 60))
    if len(p):
        return sorted(p, key=lambda b: b[2] * b[3], reverse=True)[0]
    return None


def laplacian_var(img):
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def analyze(path, n=8):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"error": "cannot open video", "overall": "FAIL"}
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS); fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = fc / fps if fps else 0
    integrity = {"width": W, "height": H, "fps": round(fps, 3), "frames": fc, "duration": round(dur, 2)}
    if not (W and H and fc > 0 and dur > 0):
        integrity["status"] = "FAIL"; return {"integrity": integrity, "overall": "FAIL", "error": "unreadable/empty"}
    if dur < 5:
        integrity["status"] = "WARN"
    else:
        integrity["status"] = "PASS"

    pts = [int(i * (fc - 1) / max(n - 1, 1)) for i in range(n)]
    rows = []
    prev_gray = None
    for fr in pts:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok or img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = {"frame": fr, "luma": float(np.mean(gray)), "frame_sharp": laplacian_var(gray)}
        g = detect_face(gray)
        if g is not None:
            x, y, w, h = g
            m = int(h * 0.15)
            fc_crop = gray[max(0, y - m):min(H, y + h + m), max(0, x - m):min(W, x + w + m)]
            r["face"] = [int(x), int(y), int(w), int(h)]
            r["face_h_ratio"] = h / float(H)
            r["face_sharp"] = laplacian_var(fc_crop) if fc_crop.size else 0
            aspect = w / float(h)
            r["aspect"] = aspect
            # frontal proxy: aspect near 0.78 and both eyes detected in upper face
            eyes = EYE_CASCADE.detectMultiScale(gray[y:y + int(h * 0.55), x:x + w], scaleFactor=1.1,
                                                minNeighbors=6, minSize=(int(w * 0.08), int(w * 0.08)))
            r["eyes"] = len(eyes)
            r["yaw_est"] = max(0.0, (0.78 - aspect) / 0.28) * 70.0
            # mouth region (lower third of face)
            my0, my1 = y + int(h * 0.62), y + int(h * 0.92)
            mx0, mx1 = x + int(w * 0.18), x + int(w * 0.82)
            mouth_in = (my1 < H) and (my0 < my1)
            r["mouth_in"] = bool(mouth_in)
            mouth = gray[my0:my1, mx0:mx1] if mouth_in else None
            r["mouth_mean"] = float(np.mean(mouth)) if mouth is not None and mouth.size else None
            r["chin_ratio"] = (H - (y + h)) / float(h)  # space below face / face_h
        if prev_gray is not None:
            r["motion"] = float(np.mean(cv2.absdiff(gray, prev_gray)))
        rows.append(r)
        prev_gray = gray
    cap.release()

    faces = [r for r in rows if r.get("face")]
    res = {"path": os.path.abspath(path), **integrity, "samples": len(rows), "faces_detected": len(faces)}
    cats = {}
    if not faces:
        for c in ("FACE_SIZE", "FACE_SHARPNESS", "FRONTALNESS", "MOUTH_VISIBILITY", "CHIN_VISIBILITY", "SOURCE_MOUTH_STATE", "MOTION", "LIGHTING"):
            cats[c] = {"status": "FAIL", "value": None, "note": "no face detected"}
        res["categories"] = cats; res["overall"] = "FAIL"; return res

    fh = float(np.median([r["face_h_ratio"] for r in faces]))
    fsh = float(np.median([r["face_sharp"] for r in faces]))
    yaws = [r["yaw_est"] for r in faces]
    frontal = sum(1 for y in yaws if y < 18) / float(len(yaws))
    mouth_in = sum(1 for r in faces if r.get("mouth_in")) / float(len(faces))
    chin = float(np.median([r["chin_ratio"] for r in faces]))
    motions = [r["motion"] for r in rows if "motion" in r]
    medmot = float(np.median(motions)) if motions else 0
    lums = [r["luma"] for r in rows]
    flick = float(np.std(lums))
    mouth_means = [r["mouth_mean"] for r in faces if r.get("mouth_mean") is not None]
    # source mouth state: temporal std of mouth-region brightness + motion there
    mouth_state_std = float(np.std(mouth_means)) if len(mouth_means) > 2 else 0
    # combined talking proxy: mouth_state_std normalized
    talking_proxy = mouth_state_std / max(1.0, float(np.mean(mouth_means))) if mouth_means else 0

    def band(v, pass_v, warn_v, lower_better=False):
        if lower_better:
            return "PASS" if v <= pass_v else ("WARN" if v <= warn_v else "FAIL")
        return "PASS" if v >= pass_v else ("WARN" if v >= warn_v else "FAIL")

    # FACE_SIZE: face_h_ratio
    if fh >= 0.16: fs = "PASS"; fs_note = "large face (close-up)"
    elif fh >= 0.10: fs = "PASS"; fs_note = "good face size"
    elif fh >= 0.07: fs = "WARN"; fs_note = "small face"
    else: fs = "FAIL"; fs_note = "very small face (full-body/distant)"
    cats["FACE_SIZE"] = {"status": fs, "value": round(fh, 4), "note": fs_note}

    cats["FACE_SHARPNESS"] = {"status": band(fsh, 150, 60), "value": round(fsh, 1),
                              "note": "Laplacian var on face crop"}
    cats["FRONTALNESS"] = {"status": "PASS" if frontal >= 0.8 else ("WARN" if frontal >= 0.4 else "FAIL"),
                           "value": round(frontal, 3), "note": f"frontal_ratio; median_yaw={float(np.median(yaws)):.1f}"}
    cats["MOUTH_VISIBILITY"] = {"status": "PASS" if mouth_in >= 0.9 else ("WARN" if mouth_in >= 0.5 else "FAIL"),
                                 "value": round(mouth_in, 3), "note": "mouth region in frame across samples"}
    if chin >= 1.0: cs = "PASS"; cn = "full chin/jaw room"
    elif chin >= 0.3: cs = "WARN"; cn = "limited chin room"
    else: cs = "FAIL"; cn = "chin cropped"
    cats["CHIN_VISIBILITY"] = {"status": cs, "value": round(chin, 3), "note": cn}
    # SOURCE_MOUTH_STATE: talking detection via temporal mouth-region variation.
    # Static/very-short sources (fc ≤ 2) have no real temporal data → UNKNOWN.
    # cv2.VideoCapture reads a 1-frame image 8× (same frame) but face-detection
    # noise produces a non-zero talking_proxy → false positive. Guard with fc.
    if fc <= 2:
        cats["SOURCE_MOUTH_STATE"] = {"status": "UNKNOWN", "value": 0.0,
                                       "note": "insufficient frames for mouth-state analysis (static/short)"}
        cats["MOTION"] = {"status": "UNKNOWN", "value": 0.0,
                          "note": "insufficient frames for motion analysis"}
        cats["LIGHTING"] = {"status": "UNKNOWN", "value": 0.0,
                            "note": "insufficient frames for lighting analysis"}
    else:
        # Lowered PASS threshold from 0.02 → 0.003 to catch subtle talking.
        # Test set: test17_8/Close Up.mp4 talking_proxy=0.0052 (KNOWN TALKING)
        # was falsely PASS at 0.02; now correctly WARN at 0.003.
        if talking_proxy < 0.003:
            ms, mn = "PASS", "STILL/neutral (ideal — no talking detected)"
        elif talking_proxy < 0.02:
            ms, mn = "WARN", "POSSIBLE_TALKING — mouth articulation detected"
        elif talking_proxy < 0.09:
            ms, mn = "WARN", "TALKING — subject speaking in source"
        else:
            ms, mn = "FAIL", "STRONG_TALKING/HIGH_EXPRESSION (poor master)"
        cats["SOURCE_MOUTH_STATE"] = {"status": ms, "value": round(talking_proxy, 4), "note": mn}
        cats["MOTION"] = {"status": band(medmot, 3.0, 6.0, lower_better=True), "value": round(medmot, 2),
                          "note": "median frame-to-frame diff (low=stable)" if medmot <= 6 else "high motion/shake risk"}
        cats["LIGHTING"] = {"status": band(flick, 2.0, 4.0, lower_better=True), "value": round(flick, 2),
                            "note": "luma std across samples (low=stable)"}

    res["categories"] = cats
    # overall: FAIL if any FAIL; else WARN if any WARN; else PASS
    statuses = [c["status"] for c in cats.values()]
    if "FAIL" in statuses:
        res["overall"] = "FAIL"
    elif "WARN" in statuses:
        res["overall"] = "WARN"
    else:
        res["overall"] = "PASS"
    res["face_h_ratio"] = round(fh, 4)
    res["face_sharpness"] = round(fsh, 1)
    res["frontal_ratio"] = round(frontal, 3)
    res["mouth_in_frame_ratio"] = round(mouth_in, 3)
    res["chin_ratio"] = round(chin, 3)
    res["median_motion"] = round(medmot, 2)
    res["luma_flicker"] = round(flick, 2)
    res["source_mouth_talking_proxy"] = round(talking_proxy, 4)
    return res


def main():
    # Be safe with non-ASCII paths (e.g. Vietnamese folder names) on cp1252 consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Offline raw avatar-source quality gate (EXPERIMENTAL)")
    ap.add_argument("--video", required=True)
    ap.add_argument("--json", default=None, help="write machine-readable JSON to this path")
    ap.add_argument("--strict", action="store_true", help="treat WARN as FAIL (exit 2)")
    args = ap.parse_args()
    if not os.path.isfile(args.video):
        print("FAIL: file not found:", args.video); sys.exit(3)
    r = analyze(args.video)
    if "error" in r and "overall" in r and r["overall"] == "FAIL" and "categories" not in r:
        print("FAIL:", r.get("error")); sys.exit(2)
    print(f"SOURCE: {r.get('path')}")
    print(f"  {r.get('width')}x{r.get('height')} {r.get('fps')}fps {r.get('duration')}s {r.get('frames')} frames  faces={r.get('faces_detected')}/{r.get('samples')}")
    print(f"  face_h_ratio={r.get('face_h_ratio')} sharp={r.get('face_sharpness')} frontal={r.get('frontal_ratio')} mouth_in={r.get('mouth_in_frame_ratio')} chin={r.get('chin_ratio')} motion={r.get('median_motion')} flicker={r.get('luma_flicker')} talking_proxy={r.get('source_mouth_talking_proxy')}")
    print(f"  OVERALL: {r['overall']}")
    for c in ("VIDEO_INTEGRITY", "FACE_SIZE", "FACE_SHARPNESS", "FRONTALNESS", "MOUTH_VISIBILITY", "CHIN_VISIBILITY", "SOURCE_MOUTH_STATE", "MOTION", "LIGHTING"):
        cat = r["categories"].get(c)
        if cat:
            print(f"    {c:20} {cat['status']:6}  {cat.get('value','')}  {cat.get('note','')}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, ensure_ascii=False)
        print("  json ->", args.json)
    code = {"PASS": 0, "WARN": 1, "FAIL": 2}[r["overall"]]
    if args.strict and r["overall"] == "WARN":
        code = 2
    sys.exit(code)


if __name__ == "__main__":
    main()