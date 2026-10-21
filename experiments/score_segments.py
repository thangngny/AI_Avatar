#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 3 segment-level SyncNet scorer. Crops a video into segments and scores
each with the SyncNet harness (face_crop). Used to check sync consistency across
the full duration and around WOLA boundaries."""
import argparse, os, sys, json, subprocess, tempfile

SYNCNET = r"C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py"
SYNCNET_PY = r"C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"

def crop_segment(video, start, end, out):
    # re-encode for frame-accurate start (keyframe copy would misalign SyncNet)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",video,
                    "-ss",str(start),"-t",str(end-start),
                    "-c:v","libx264","-preset","ultrafast","-crf","18",
                    "-c:a","aac","-b:a","128k", out],
                   check=True)

def score(video, out_json):
    cmd=[SYNCNET_PY, SYNCNET, "--video",video,"--preprocess","face_crop",
         "--device","cuda:0","--stride","2","--batch","32","--out_json",out_json]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if not os.path.exists(out_json):
        print("  syncnet FAILED:", r.stderr[-800:]); return None
    return json.load(open(out_json,encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--video",required=True)
    ap.add_argument("--label",default="")
    ap.add_argument("--segments",nargs="+",default=["0-10","10-20","20-30","30-40","40-50"])
    ap.add_argument("--whole",action="store_true")
    args=ap.parse_args()
    tmp=tempfile.mkdtemp()
    print(f"\n=== {args.label or args.video} ===")
    print(f"{'segment':>10} | {'conf':>7} | {'lse_c':>7} | {'lse_d':>7} | {'av_off':>6}")
    print("-"*52)
    if args.whole:
        j=os.path.join(tmp,"whole.json"); m=score(args.video,j)
        if m: print(f"{'WHOLE':>10} | {m['sync_confidence']:.4f} | {m['lse_c']:.4f} | {m['lse_d_min']:.4f} | {m['av_offset_frames']:+d}")
    for seg in args.segments:
        s,e=seg.split("-"); s=float(s); e=float(e)
        out=os.path.join(tmp,f"seg_{s}.mp4")
        crop_segment(args.video,s,e,out)
        j=os.path.join(tmp,f"seg_{s}.json"); m=score(out,j)
        if m: print(f"{seg:>10} | {m['sync_confidence']:.4f} | {m['lse_c']:.4f} | {m['lse_d_min']:.4f} | {m['av_offset_frames']:+d}")
        else: print(f"{seg:>10} | FAILED")

if __name__=="__main__":
    main()