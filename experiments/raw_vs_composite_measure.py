#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXPERIMENTAL — RAW_MUSETALK vs FINAL_COMPOSITE mouth-geometry + articulation
metrics for a given prepared avatar + audio. Diagnostic only; not production.

Runs the production MuseTalk v1.5 inference path (same as the renderer) but, for
a sampled set of frames, captures BOTH the raw 256x256 decoded face AND the
final pasted composite, then measures mouth vertical opening and width with
face_alignment (FAN, 68 landmarks). All measurement is numeric (script-side) —
no image is ever read by a language model.

Reports:
  RAW_MUSETALK   raw 256 mouth geometry (is narrowness at model output?)
  COMPOSITING    composite mouth vs raw (does paste-back compress it?)
  ARTICULATION   range / std / diversity of mouth opening across the clip
  CLOSURE        minimum inner-lip opening (do lips close?)

Locked to production truth: gain/ctx/offset are NOT changed here — this only
replays the same inference the renderer performs, for measurement.

Usage:
  python experiments/raw_vs_composite_measure.py --avatar_id close_up \
      --wav <wav> --out_json <path> [--step 3] [--gpu 0]
"""
import os, sys, json, argparse
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2, torch
from generate_video_from_script import setup_torch_flags, load_avatar_data
from avatars.musetalk.utils.utils import load_all_model
from avatars.musetalk.myutil import get_image_blending
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.device import initialize_device
import soundfile as sf
import face_alignment

ap = argparse.ArgumentParser()
ap.add_argument("--avatar_id", required=True)
ap.add_argument("--wav", required=True)
ap.add_argument("--out_json", required=True)
ap.add_argument("--step", type=int, default=3)
ap.add_argument("--gpu", type=int, default=0)
args = ap.parse_args()

device = initialize_device()
setup_torch_flags()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

vae, unet, pe = load_all_model()
pe = pe.half().to(device); vae.vae = vae.vae.half().to(device); unet.model = unet.model.half().to(device)
ap_ = Audio2Feature(model_path=os.path.join(ROOT, "models", "whisper"), device=device)
w, sr = sf.read(args.wav, dtype="float32"); w = w.mean(axis=1) if w.ndim > 1 else w
feat = ap_.audio2feat(w); n_feat = feat.shape[0]
print(f"[dump] {args.avatar_id} feat {n_feat}, audio {len(w)/sr:.2f}s")

frame_list, mask_list, coord_list, mask_coord_list, latents = load_avatar_data(args.avatar_id)
length = len(latents)
c0 = coord_list[0]; mc0 = mask_coord_list[0]
fh = c0[3] - c0[1]
print(f"[geom] face bbox {c0[2]-c0[0]}x{c0[3]-c0[1]} face_h={fh}px; mask crop {mc0[2]-mc0[0]}x{mc0[3]-mc0[1]}; lower-face margin ~{fh*0.2:.0f}px")

FA = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D, flip_input=False, device='cuda', verbose=False)
LIP_TOP_IN, LIP_BOT_IN = 62, 66
MOUTH_L, MOUTH_R = 48, 54
FACE_L, FACE_R = 0, 16
LIP_TOP_OUT, LIP_BOT_OUT = 51, 57


def mouth_metrics(bgr, crop_box=None):
    H, W = bgr.shape[:2]
    if crop_box is not None:
        cx1, cy1, cx2, cy2 = crop_box
        cx1 = max(0, cx1); cy1 = max(0, cy1); cx2 = min(W, cx2); cy2 = min(H, cy2)
        region = bgr[cy1:cy2, cx1:cx2]; ox, oy = cx1, cy1
    else:
        region = bgr; ox, oy = 0, 0
    preds = FA.get_landmarks(region)
    if not preds:
        return None
    lm = preds[0] + np.array([ox, oy])
    face_w = float(np.linalg.norm(lm[FACE_L] - lm[FACE_R]))
    vopen_inner = float(np.linalg.norm(lm[LIP_TOP_IN] - lm[LIP_BOT_IN]))
    vopen_outer = float(np.linalg.norm(lm[LIP_TOP_OUT] - lm[LIP_BOT_OUT]))
    width = float(np.linalg.norm(lm[MOUTH_L] - lm[MOUTH_R]))
    return dict(vopen_outer=vopen_outer, vopen_inner=vopen_inner, width=width, face_w=face_w,
                vopen_outer_n=vopen_outer/max(face_w, 1e-6), vopen_inner_n=vopen_inner/max(face_w, 1e-6),
                width_n=width/max(face_w, 1e-6))


num_frames = int(len(w) / sr * 25)
frames = list(range(0, num_frames, args.step))
rows = []
for i in frames:
    center = (i - 3) * 2  # production offset -3
    win = np.stack([feat[max(0, min(n_feat - 1, center + j))] for j in range(10)], 0).reshape(-1, 384)
    audio = pe(torch.from_numpy(win).to(device).half().unsqueeze(0))
    idx = i % length
    latb = latents[idx].to(device).half()
    with torch.no_grad():
        pred_lat = unet.model(latb, torch.zeros(1, device=device, dtype=torch.long),
                              encoder_hidden_states=audio, return_dict=False)[0]
    raw256 = vae.decode_latents(pred_lat)[0]
    x1, y1, x2, y2 = coord_list[idx]
    res = cv2.resize(raw256, (x2 - x1, y2 - y1))
    comp = get_image_blending(frame_list[idx].copy(), res, (x1, y1, x2, y2),
                              mask_list[idx], mask_coord_list[idx])
    rm = mouth_metrics(raw256)
    fw_ = x2 - x1; fh_ = y2 - y1; pad = int(0.35 * max(fw_, fh_))
    cb = (x1 - pad, y1 - pad, x2 + pad, y2 + pad)
    cm = mouth_metrics(comp, crop_box=cb)
    if rm is None or cm is None:
        rows.append(dict(frame=i, raw=None, comp=None)); continue
    rv, rw, rvi = rm['vopen_outer_n'], rm['width_n'], rm['vopen_inner_n']
    cv, cw, cvi = cm['vopen_outer_n'], cm['width_n'], cm['vopen_inner_n']
    rows.append(dict(frame=i, raw_vopen_n=rv, raw_width_n=rw, raw_vinner_n=rvi,
                     comp_vopen_n=cv, comp_width_n=cw, comp_vinner_n=cvi,
                     ratio_vopen=cv/max(rv, 1e-6), ratio_width=cw/max(rw, 1e-6)))
    print(f"  {i:4d}  raw_vopen={rv:.4f} raw_w={rw:.4f}  comp_vopen={cv:.4f} comp_w={cw:.4f}  ratio_vopen={rows[-1]['ratio_vopen']:.3f}")

del FA

ok = [r for r in rows if r.get("raw_vopen_n") is not None]


def stats(key):
    v = np.array([r[key] for r in ok], dtype=np.float64)
    return dict(min=float(v.min()), max=float(v.max()), mean=float(v.mean()), std=float(v.std()), range=float(v.max()-v.min()))


# articulation diversity: bin (vopen_outer_n, width_n) into a 6x6 grid, count occupied bins
def diversity(rows, key_v, key_w, nb=6):
    vv = np.array([r[key_v] for r in ok]); ww = np.array([r[key_w] for r in ok])
    if len(vv) == 0:
        return 0
    vb = np.linspace(min(vv.min(), 0), vv.max()+1e-9, nb+1); wb = np.linspace(ww.min(), ww.max()+1e-9, nb+1)
    occ = set()
    for a, b in zip(vv, ww):
        occ.add((min(nb-1, int((a-vb[0])/(vb[1]-vb[0]+1e-9))), min(nb-1, int((b-wb[0])/(wb[1]-wb[0]+1e-9)))))
    return len(occ)

summary = {
    "avatar_id": args.avatar_id,
    "wav": args.wav,
    "n_frames_sampled": len(ok),
    "geometry": {"face_h_px": int(fh), "face_bbox": [int(v) for v in c0], "mask_crop": [int(v) for v in mc0]},
    "raw_vopen_n": stats("raw_vopen_n"),
    "raw_width_n": stats("raw_width_n"),
    "raw_vinner_n": stats("raw_vinner_n"),
    "comp_vopen_n": stats("comp_vopen_n"),
    "comp_width_n": stats("comp_width_n"),
    "comp_vinner_n": stats("comp_vinner_n"),
    "ratio_vopen_mean": float(np.mean([r["ratio_vopen"] for r in ok])),
    "ratio_width_mean": float(np.mean([r["ratio_width"] for r in ok])),
    "articulation_vopen_range_n": stats("comp_vopen_n")["range"],
    "articulation_width_range_n": stats("comp_width_n")["range"],
    "diversity_raw": diversity(ok, "raw_vopen_n", "raw_width_n"),
    "diversity_comp": diversity(ok, "comp_vopen_n", "comp_width_n"),
    "closure_min_inner_n": stats("comp_vinner_n")["min"],  # near 0 => lips close
    "closure_pass": bool(stats("comp_vinner_n")["min"] < 0.012),
}
print("\n=== SUMMARY (normalized by face width; ratio = composite/raw) ===")
print(json.dumps(summary, indent=2))
os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
with open(args.out_json, "w") as f:
    json.dump({"summary": summary, "rows": rows}, f, indent=2)
print(f"[dump] wrote {args.out_json}")