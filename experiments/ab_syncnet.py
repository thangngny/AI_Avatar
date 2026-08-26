#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXPERIMENTAL — A/B SyncNet scorer. Runs the LatentSync SyncNet scorer
(syncnet_score.py) on each candidate composite render and collects
sync_confidence / LSE-D / AV offset. Diagnostic only; not production.

Uses the latentsync_env python (torch+latentsync) via subprocess; orchestrator
itself only needs stdlib so it runs on plain python.
"""
import argparse, json, os, subprocess, sys

ENV_PY = r"C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
SYNCNET = r"C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py"


def score(video):
    cmd = [ENV_PY, SYNCNET, "--video", video, "--preprocess", "face_crop"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    out = r.stdout
    # scorer prints log lines (with single-quoted dicts) then a pretty JSON object.
    # find the real JSON: a '{' on its own line followed by an indented "video": key.
    i = out.find('{\n  "video"')
    if i < 0:
        i = out.rfind('\n{')  # fallback: last brace at line start
        if i >= 0:
            i += 1
    if i < 0:
        return {"error": "no JSON", "stderr": r.stderr[-400:]}
    try:
        d = json.loads(out[i:])
    except Exception as e:
        return {"error": f"json: {e}", "stderr": r.stderr[-400:]}
    sc = d.get("s_curve", {})
    # s_curve is sync confidence per integer AV offset (frames); peak = best sync
    av_offset = int(max(sc, key=sc.get)) if sc else None
    sync_conf = max(sc.values()) if sc else None
    lse_d_min = min(sc.values()) if sc else None
    return {
        "video": video, "n_frames": d.get("n_frames"), "fps": d.get("fps"),
        "s_off_avg": d.get("s_off_avg"), "sync_confidence": sync_conf,
        "lse_d_min": lse_d_min, "av_offset_frames": av_offset, "s_curve": sc,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="+", required=True, help="label=path pairs")
    ap.add_argument("--out_json", required=True)
    args = ap.parse_args()
    res = {}
    for vp in args.videos:
        if "=" in vp:
            label, path = vp.split("=", 1)
        else:
            label, path = os.path.splitext(os.path.basename(vp))[0], vp
        print(f"--- syncnet {label}: {path} ---", flush=True)
        m = score(path)
        res[label] = m
        if "error" not in m:
            print(f"  sync_confidence={m['sync_confidence']:.4f}  lse_d_min={m['lse_d_min']:.4f}  av_offset={m['av_offset_frames']:+d}  s_off_avg={m['s_off_avg']:.4f}")
        else:
            print("  FAILED:", m.get("error"), m.get("stderr", "")[-200:])
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("wrote", args.out_json)


if __name__ == "__main__":
    main()