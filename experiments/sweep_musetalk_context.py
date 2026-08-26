#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 4 — joint audio-context × temporal-offset sweep for offline MuseTalk.

Loads model + avatar ONCE, generates the master TTS WAV ONCE, then renders every
(context_left, offset) combination and scores each with SyncNet (face_crop).
Context_left = how many of the 10 conditioning features sit BEFORE the aligned
center (0=future-only [0,+10); 4=realtime [-4,+6); 5=symmetric [-5,+5)). Total
stays 10 -> MuseTalk conditioning [50,384] unchanged.

Reuses the production renderer (generate_video_from_script.render_video). Writes
CSV + JSON ranked by lse_c with av_offset guardrail.

Usage (latentsync_env, GPU1):
  set CUDA_VISIBLE_DEVICES=1
  python sweep_musetalk_context.py --script data/input/scripts/script_artic.txt --avatar_id fullbody_30_7_25fps \
      --contexts 0 3 4 5 6 --offsets -5 -4 -3 -2 -1 0 1
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
    cmd=[SYNCNET_PY, SYNCNET, "--video", video, "--preprocess", "face_crop",
         "--device", "cuda:0", "--stride", "2", "--batch", "32", "--out_json", out_json]
    r=subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.exists(out_json):
        print(f"[syncnet] FAILED {video}\n{r.stderr[-1000:]}"); return None
    return json.load(open(out_json, encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--avatar_id", required=True)
    ap.add_argument("--contexts", type=int, nargs="+", default=[0,3,4,5,6])
    ap.add_argument("--offsets", type=int, nargs="+", default=[-5,-4,-3,-2,-1,0,1])
    ap.add_argument("--out_dir", default=r"D:\CongThang_AI_Avatar\sweep_ctx")
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--voice", default="vi-VN-HoaiMyNeural")
    ap.add_argument("--tag", default="ctx")
    args=ap.parse_args(); os.makedirs(args.out_dir, exist_ok=True)
    device=initialize_device(); gvs.setup_torch_flags()
    with open(args.script, encoding="utf-8") as f: raw=f.read()
    full_text=" ".join(gvs.split_script(raw,"sentence"))
    master_wav=os.path.join(args.out_dir, f"master_{args.tag}.wav"); tts_mp3=master_wav+".mp3"
    print(f"[ctx] master TTS ({len(full_text)} chars)...")
    gvs.generate_audio_edge_tts(full_text, tts_mp3, voice=args.voice)
    gvs.convert_audio_to_wav(tts_mp3, master_wav); os.remove(tts_mp3)
    import soundfile as sf; w,sr=sf.read(master_wav, dtype="float32")
    print(f"[ctx] master wav: {len(w)/sr:.2f}s")
    print("[ctx] loading model + avatar...")
    vae,unet,pe=load_all_model()
    pe=pe.half().to(device); vae.vae=vae.vae.half().to(device); unet.model=unet.model.half().to(device)
    ap2=Audio2Feature(model_path=os.path.join(os.path.dirname(__file__),"models","whisper"))
    model=(vae,unet,pe,torch.tensor([0],device=device),ap2)
    avatar_data=gvs.load_avatar_data(args.avatar_id)
    fps=25; rows=[]
    for ctx in args.contexts:
        for off in args.offsets:
            tag=f"c{ctx}_o{off:+d}"
            out_mp4=os.path.join(args.out_dir, f"{args.tag}_{tag}.mp4")
            out_json=os.path.join(args.out_dir, f"{args.tag}_{tag}.json")
            t0=time.perf_counter()
            print(f"\n[ctx] === context_left={ctx} (win [{ -ctx },{10-ctx}) ) offset={off:+d} ===")
            try:
                gvs.render_video(master_wav, avatar_data, model, out_mp4, fps=fps,
                                 batch_size=args.batch_size, face_enhance=False,
                                 audio_feature_offset_frames=off, audio_context_left=ctx)
            except Exception as e:
                print(f"[ctx] render FAIL {tag}: {e}"); rows.append({"ctx":ctx,"off":off,"error":str(e)}); continue
            rs=time.perf_counter()-t0
            m=score_with_syncnet(out_mp4,out_json)
            if m is None:
                rows.append({"ctx":ctx,"off":off,"render_sec":round(rs,1),"error":"syncnet fail"}); continue
            rows.append({"ctx":ctx,"off":off,"offset_ms":off*1000/fps,
                         "sync_confidence":m["sync_confidence"],"lse_c":m["lse_c"],
                         "lse_d_min":m["lse_d_min"],"av_offset_frames":m["av_offset_frames"],
                         "n_windows":m["n_windows"],"render_sec":round(rs,1)})
            print(f"[ctx] {tag}: conf={m['sync_confidence']:.4f} lse_c={m['lse_c']:.4f} "
                  f"av_off={m['av_offset_frames']:+d} render={rs:.1f}s")
    csv_path=os.path.join(args.out_dir, f"{args.tag}_results.csv")
    json_path=os.path.join(args.out_dir, f"{args.tag}_results.json")
    fields=["ctx","off","offset_ms","sync_confidence","lse_c","lse_d_min","av_offset_frames","n_windows","render_sec","error"]
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        wr=csv.DictWriter(f,fieldnames=fields); wr.writeheader()
        for r in rows: wr.writerow({k:r.get(k,"") for k in fields})
    json.dump({"tag":args.tag,"rows":rows}, open(json_path,"w",encoding="utf-8"), indent=2)
    valid=[r for r in rows if "lse_c" in r]
    if valid:
        # rank: among av_offset==0 (aligned), highest lse_c; if none at 0, allow |av|<=1
        aligned=[r for r in valid if abs(r["av_offset_frames"])==0]
        pool=aligned if aligned else [r for r in valid if abs(r["av_offset_frames"])<=1]
        ranked=sorted(pool, key=lambda r:-r["lse_c"]) if pool else sorted(valid,key=lambda r:-r["lse_c"])
        print("\n=== RANKING (av_off==0 preferred, then lse_c desc) ===")
        for r in ranked[:12]:
            print(f"  ctx={r['ctx']} off={r['off']:+d}: lse_c={r['lse_c']:.4f} conf={r['sync_confidence']:.4f} av_off={r['av_offset_frames']:+d}")
        print(f"\nBEST: context_left={ranked[0]['ctx']} offset={ranked[0]['off']:+d}")
    print(f"\n[ctx] CSV: {csv_path}\n[ctx] JSON: {json_path}")

if __name__=="__main__":
    main()