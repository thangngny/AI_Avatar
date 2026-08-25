#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 3 — automated temporal-offset sweep for offline MuseTalk lip-sync.

Loads the MuseTalk model + avatar ONCE, generates the master TTS WAV ONCE, then
renders the same clip at every requested audio-feature offset and scores each
with the SyncNet harness (subprocess). Writes a CSV + JSON ranking.

Reuses the production renderer (generate_video_from_script.render_video) — does
NOT duplicate inference logic. The offset only shifts the audio-conditioning
feature window in time; the final audio track, WAV, fps, resolution, model and
CUDA graph are identical across candidates.

Usage (latentsync_env, GPU1):
  set CUDA_VISIBLE_DEVICES=1
  python sweep_musetalk_audio_offset.py --script script_20s.txt \
      --avatar_id fullbody_30_7_25fps --offsets -5 -4 -3 -2 -1 0 1 2 3 4 5
"""
import argparse, os, sys, json, subprocess, time, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

import torch
import generate_video_from_script as gvs
from avatars.musetalk.utils.utils import load_all_model
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.device import initialize_device

SYNCNET = r"C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py"
SYNCNET_PY = r"C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"


def score_with_syncnet(video, out_json):
    """Run the SyncNet scorer (face_crop) on one video, return metrics dict."""
    cmd = [SYNCNET_PY, SYNCNET, "--video", video, "--preprocess", "face_crop",
           "--device", "cuda:0", "--stride", "2", "--batch", "32",
           "--out_json", out_json]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.exists(out_json):
        # scorer may have logged to stderr; surface it
        print(f"[syncnet] FAILED for {video}\n{r.stderr[-1500:]}")
        return None
    return json.load(open(out_json, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--avatar_id", required=True)
    ap.add_argument("--offsets", type=int, nargs="+", default=[-5,-4,-3,-2,-1,0,1,2,3,4,5])
    ap.add_argument("--out_dir", default=r"D:\CongThang_AI_Avatar\sweep")
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--face_enhance", action="store_true")
    ap.add_argument("--voice", default="vi-VN-HoaiMyNeural")
    ap.add_argument("--tag", default="sweep20s")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    device = initialize_device()
    gvs.setup_torch_flags()

    # --- master WAV (generated once, reused for every offset) ---
    with open(args.script, encoding="utf-8") as f:
        raw = f.read()
    full_text = " ".join(gvs.split_script(raw, "sentence"))
    master_wav = os.path.join(args.out_dir, f"master_{args.tag}.wav")
    tts_mp3 = master_wav + ".mp3"
    print(f"[sweep] generating master TTS ({len(full_text)} chars)...")
    gvs.generate_audio_edge_tts(full_text, tts_mp3, voice=args.voice)
    gvs.convert_audio_to_wav(tts_mp3, master_wav)
    os.remove(tts_mp3)
    import soundfile as sf
    w, sr = sf.read(master_wav, dtype="float32")
    print(f"[sweep] master wav: {len(w)/sr:.2f}s")

    # --- model + avatar (loaded once) ---
    print("[sweep] loading MuseTalk model + avatar...")
    vae, unet, pe = load_all_model()
    pe = pe.half().to(device); vae.vae = vae.vae.half().to(device); unet.model = unet.model.half().to(device)
    audio_processor = Audio2Feature(model_path=os.path.join(os.path.dirname(__file__), "models", "whisper"))
    model = (vae, unet, pe, torch.tensor([0], device=device), audio_processor)
    avatar_data = gvs.load_avatar_data(args.avatar_id)

    fps = 25
    rows = []
    for off in args.offsets:
        out_mp4 = os.path.join(args.out_dir, f"{args.tag}_off{off:+d}.mp4")
        out_json = os.path.join(args.out_dir, f"{args.tag}_off{off:+d}.json")
        t0 = time.perf_counter()
        print(f"\n[sweep] === offset {off:+d} ({off*1000/fps:+.0f} ms) -> {out_mp4} ===")
        try:
            gvs.render_video(master_wav, avatar_data, model, out_mp4, fps=fps,
                             batch_size=args.batch_size, face_enhance=args.face_enhance,
                             audio_feature_offset_frames=off)
        except Exception as exc:
            print(f"[sweep] render FAILED offset {off}: {exc}")
            rows.append({"offset": off, "offset_ms": off*1000/fps, "error": str(exc)})
            continue
        render_sec = time.perf_counter() - t0
        m = score_with_syncnet(out_mp4, out_json)
        if m is None:
            rows.append({"offset": off, "offset_ms": off*1000/fps, "render_sec": round(render_sec,1), "error": "syncnet failed"})
            continue
        rows.append({
            "offset": off,
            "offset_ms": off*1000/fps,
            "sync_confidence": m["sync_confidence"],
            "lse_c": m["lse_c"],
            "lse_d_min": m["lse_d_min"],
            "av_offset_frames": m["av_offset_frames"],
            "n_windows": m["n_windows"],
            "render_sec": round(render_sec, 1),
        })
        print(f"[sweep] offset {off:+d}: conf={m['sync_confidence']:.4f} lse_c={m['lse_c']:.4f} "
              f"lse_d={m['lse_d_min']:.4f} av_off={m['av_offset_frames']:+d} render={render_sec:.1f}s")

    # --- write CSV + JSON, rank ---
    csv_path = os.path.join(args.out_dir, f"{args.tag}_results.csv")
    json_path = os.path.join(args.out_dir, f"{args.tag}_results.json")
    fields = ["offset","offset_ms","sync_confidence","lse_c","lse_d_min","av_offset_frames","n_windows","render_sec","error"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader()
        for r in rows: wr.writerow({k: r.get(k,"") for k in fields})
    json.dump({"tag": args.tag, "master_wav": master_wav, "rows": rows}, open(json_path,"w",encoding="utf-8"), indent=2)

    valid = [r for r in rows if "lse_c" in r]
    if valid:
        # primary: highest lse_c (confidence over chance); tiebreak: smallest |av_offset|
        ranked = sorted(valid, key=lambda r: (-r["lse_c"], abs(r["av_offset_frames"])))
        print("\n=== RANKING (by lse_c desc, then |av_offset| asc) ===")
        for r in ranked:
            print(f"  off {r['offset']:+d} ({r['offset_ms']:+4.0f}ms): lse_c={r['lse_c']:.4f} "
                  f"conf={r['sync_confidence']:.4f} av_off={r['av_offset_frames']:+d}")
        print(f"\nBEST: offset {ranked[0]['offset']:+d} ({ranked[0]['offset_ms']:+.0f} ms)")
    print(f"\n[sweep] CSV: {csv_path}")
    print(f"[sweep] JSON: {json_path}")

if __name__ == "__main__":
    main()