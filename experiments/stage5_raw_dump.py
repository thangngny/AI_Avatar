#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 Phase 3/4 — root-limitation audit + mouth-range measurement.

Runs the PRODUCTION inference path (same as render_video) but, for a sampled
set of frames, captures BOTH the raw MuseTalk 256x256 decoded face AND the
final pasted composite, then measures mouth vertical opening and width with
mediapipe FaceMesh on each. All measurement is numeric (script-side) — no
image is ever read by a language model.

Classifies whether narrow articulation originates at:
  RAW_MUSETALK   -> raw 256 mouth itself is small/narrow
  COMPOSITING    -> raw 256 mouth is wide but composite mouth is compressed
  (also records avatar bbox / mask geometry for the AVATAR_PREPARATION check)

Output: prints a per-frame table + summary to stdout and writes a JSON.
"""
import os, sys, json, glob, pickle
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2, torch
from generate_video_from_script import setup_torch_flags, load_avatar_data
from avatars.musetalk.utils.utils import load_all_model
from avatars.musetalk.myutil import get_image_blending
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.device import initialize_device
import soundfile as sf

device = initialize_device()
setup_torch_flags()
AV = "fullbody_30_7_25fps"
ROOT = os.path.dirname(os.path.abspath(__file__))
WAV = sys.argv[1] if len(sys.argv) > 1 else r"D:\CongThang_AI_Avatar\stage5\master_continuous.wav"
STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 6
OUT_JSON = r"D:\CongThang_AI_Avatar\stage5\stage5_raw_vs_composite.json"

# ---- models ----
vae, unet, pe = load_all_model()
pe = pe.half().to(device); vae.vae = vae.vae.half().to(device); unet.model = unet.model.half().to(device)
ap = Audio2Feature(model_path=os.path.join(ROOT, "models", "whisper"), device=device)
w, sr = sf.read(WAV, dtype="float32"); w = w.mean(axis=1) if w.ndim > 1 else w
feat = ap.audio2feat(w); n_feat = feat.shape[0]
print(f"[dump] feat {n_feat}, audio {len(w)/sr:.2f}s")

# ---- avatar (production downscale path) ----
frame_list, mask_list, coord_list, mask_coord_list, latents = load_avatar_data(AV)
length = len(latents)
print(f"[dump] avatar frames {length}, bbox0 {coord_list[0]}")
# bbox geometry report (Phase 3C — avatar preparation)
c0 = coord_list[0]; print(f"[geom] face bbox (1080x1920) = {c0} -> {c0[2]-c0[0]}x{c0[3]-c0[1]}")
mc0 = mask_coord_list[0]; print(f"[geom] mask crop_box = {mc0} -> {mc0[2]-mc0[0]}x{mc0[3]-mc0[1]}")
# how much lower-face room below the mouth? mouth center ~ 80% down the face bbox
fh = c0[3] - c0[1]; print(f"[geom] face height {fh}px; lower-face margin below mid-mouth ~ {fh*0.2:.0f}px")

# ---- face_alignment (FAN, 68 landmarks). mediapipe FaceMesh is broken in this
# env (returns no landmarks even on a clear face). FAN is reliable and offline.
import face_alignment
FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                  flip_input=False, device='cuda', verbose=False)
# dlib-68 mouth indices: outer mouth 48..67; inner upper lip top = 62, inner
# lower lip bottom = 66; outer corners = 48 (left), 54 (right). Face width ref =
# distance(0,16) (jaw sides).
LIP_TOP_IN = 62
LIP_BOT_IN = 66
MOUTH_L = 48
MOUTH_R = 54
FACE_L = 0
FACE_R = 16
# outer-lip vertical (includes lip thickness): top of upper lip = 51, bottom of lower = 57
LIP_TOP_OUT = 51
LIP_BOT_OUT = 57


def mouth_metrics(bgr, crop_box=None):
    """Run FAN, return normalized mouth metrics or None. If crop_box (x1,y1,x2,y2)
    with padding is given, only that region is searched (faster + more robust for
    the composite full frame). All metrics normalized by face_w = dist(0,16)."""
    H, W = bgr.shape[:2]
    if crop_box is not None:
        cx1, cy1, cx2, cy2 = crop_box
        cx1 = max(0, cx1); cy1 = max(0, cy1); cx2 = min(W, cx2); cy2 = min(H, cy2)
        region = bgr[cy1:cy2, cx1:cx2]
        ox, oy = cx1, cy1
    else:
        region = bgr; ox, oy = 0, 0
    preds = FA.get_landmarks(region)
    if not preds:
        return None
    lm = preds[0] + np.array([ox, oy])  # back to full-frame coords if cropped
    face_w = float(np.linalg.norm(lm[FACE_L] - lm[FACE_R]))
    vopen_inner = float(np.linalg.norm(lm[LIP_TOP_IN] - lm[LIP_BOT_IN]))
    vopen_outer = float(np.linalg.norm(lm[LIP_TOP_OUT] - lm[LIP_BOT_OUT]))
    width = float(np.linalg.norm(lm[MOUTH_L] - lm[MOUTH_R]))
    return dict(vopen_outer=vopen_outer, vopen_inner=vopen_inner, width=width,
               face_w=face_w,
               vopen_outer_n=vopen_outer / max(face_w, 1e-6),
               vopen_inner_n=vopen_inner / max(face_w, 1e-6),
               width_n=width / max(face_w, 1e-6))

num_frames = int(len(w) / sr * 25)
frames = list(range(0, num_frames, STEP))
rows = []
print(f"\n[frame]  raw_vopen_n  raw_width_n  comp_vopen_n  comp_width_n  comp/raw_vopen  comp/raw_width")
for i in frames:
    center = (i - 3) * 2
    win = np.stack([feat[max(0, min(n_feat - 1, center + j))] for j in range(10)], 0).reshape(-1, 384)
    audio = pe(torch.from_numpy(win).to(device).half().unsqueeze(0))
    idx = i % length
    latb = latents[idx].to(device).half()
    with torch.no_grad():
        pred_lat = unet.model(latb, torch.zeros(1, device=device, dtype=torch.long),
                             encoder_hidden_states=audio, return_dict=False)[0]
    raw256 = vae.decode_latents(pred_lat)[0]  # 256x256 uint8 BGR
    x1, y1, x2, y2 = coord_list[idx]
    res = cv2.resize(raw256, (x2 - x1, y2 - y1))
    comp = get_image_blending(frame_list[idx].copy(), res, (x1, y1, x2, y2),
                              mask_list[idx], mask_coord_list[idx])
    rm = mouth_metrics(raw256)
    # composite: pad the face bbox ~35% so FAN has context (also covers chin)
    fw_ = x2 - x1; fh_ = y2 - y1; pad = int(0.35 * max(fw_, fh_))
    cb = (x1 - pad, y1 - pad, x2 + pad, y2 + pad)
    cm = mouth_metrics(comp, crop_box=cb)
    if rm is None or cm is None:
        print(f"  {i:4d}    (no face: raw={'ok' if rm else 'X'} comp={'ok' if cm else 'X'})"); continue
    rv = rm['vopen_outer_n']; rw = rm['width_n']; rvi = rm['vopen_inner_n']
    cv = cm['vopen_outer_n']; cw = cm['width_n']; cvi = cm['vopen_inner_n']
    rows.append(dict(frame=i, raw_vopen_n=rv, raw_width_n=rw, raw_vinner_n=rvi,
                     comp_vopen_n=cv, comp_width_n=cw, comp_vinner_n=cvi,
                     ratio_vopen=cv / max(rv, 1e-6), ratio_width=cw / max(rw, 1e-6)))
    print(f"  {i:4d}    {rv:.4f}      {rw:.4f}      {cv:.4f}        {cw:.4f}      {rows[-1]['ratio_vopen']:.3f}        {rows[-1]['ratio_width']:.3f}")

del FA

def stats(key):
    vals = np.array([r[key] for r in rows], dtype=np.float64)
    return dict(min=float(vals.min()), max=float(vals.max()), mean=float(vals.mean()),
                std=float(vals.std()), range=float(vals.max() - vals.min()))

summary = {
    "n_frames_sampled": len(rows),
    "raw_vopen_n": stats("raw_vopen_n"),
    "raw_width_n": stats("raw_width_n"),
    "raw_vinner_n": stats("raw_vinner_n"),
    "comp_vopen_n": stats("comp_vopen_n"),
    "comp_width_n": stats("comp_width_n"),
    "comp_vinner_n": stats("comp_vinner_n"),
    "ratio_vopen_mean": float(np.mean([r["ratio_vopen"] for r in rows])),
    "ratio_width_mean": float(np.mean([r["ratio_width"] for r in rows])),
}
print("\n=== SUMMARY (all normalized by face width; ratio = composite/raw) ===")
print(json.dumps(summary, indent=2))
with open(OUT_JSON, "w") as f:
    json.dump({"summary": summary, "rows": rows}, f, indent=2)
print(f"[dump] wrote {OUT_JSON}")