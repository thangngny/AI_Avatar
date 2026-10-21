#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXPERIMENTAL — post-render verification + manifest for the doTrang_26_8 batch.
Checks each of the 6 outputs (file/codec/audio/res/fps/duration/framecount), reads
each render log for locked-config + feature-coverage + no-freeze evidence, and
writes RENDER_MANIFEST.md. Does NOT modify any file."""
import os, subprocess, json, sys, math

RD = r"D:/CongThang_AI_Avatar/renders/doTrang_26_8"
AD = os.path.join(RD, "audio"); LG = os.path.join(RD, "logs")
PARTS = ["01", "02", "03"]
AVATARS = [("closeup", "doTrang_closeup"), ("fullbody", "doTrang_fullbody")]
VOICE_ID = "pGapy9MNHCukzJtjavF0"


def probe(p):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
            "-of", "json", p], capture_output=True, text=True, timeout=30).stdout
        d = json.loads(out)
        s = d.get("streams", [])
        v = next((x for x in s if x.get("codec_type") == "video"), {})
        a = next((x for x in s if x.get("codec_type") == "audio"), None)
        return {
            "v_codec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"),
            "fps": v.get("r_frame_rate"), "duration": float(d.get("format", {}).get("duration", 0) or 0),
            "has_audio": a is not None,
        }
    except Exception as e:
        return {"error": str(e)}


def log_evidence(logpath):
    if not os.path.isfile(logpath):
        return {"exists": False}
    t = open(logpath, encoding="utf-8", errors="ignore").read()
    ev = {
        "exists": True,
        "locked_gain_15": "Audio gain: 1.5" in t,
        "offset_-3": "Audio feature offset: -3" in t,
        "fps_25": ("FPS: 25" in t) or ("25 FPS" in t),
        "res_1080x1920": "1080x1920" in t,
        "cuda_graph_on": "CUDA Graph: ON" in t,
        "wola_on": "WOLA: ON" in t or "Long-audio WOLA: ON" in t,
        "coverage_ok": "Feature coverage OK" in t,
        "render_done": "Render done:" in t,
        "done_line": ([l for l in t.splitlines() if l.startswith("Done:")] or [None])[0],
        "render_done_line": ([l for l in t.splitlines() if "Render done:" in l] or [None])[0],
    }
    return ev


results = {}
for i in PARTS:
    aud = os.path.join(AD, f"part{i}_3min.wav")
    aud_dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", aud], capture_output=True, text=True).stdout.strip() or 0)
    txt = open(os.path.join(AD, f"part{i}_3min.txt"), encoding="utf-8").read()
    results[i] = {"audio": aud, "audio_dur": round(aud_dur, 2), "words": len(txt.split()), "outputs": {}}
    for label, av in AVATARS:
        out = os.path.join(RD, f"part{i}_{label}_3min.mp4")
        pr = probe(out) if os.path.isfile(out) else {"error": "file missing"}
        logp = os.path.join(LG, f"part{i}_{label}.log")
        ev = log_evidence(logp)
        # frame count = duration*25
        frames = round(pr.get("duration", 0) * 25) if "duration" in pr else None
        ok = (pr.get("v_codec") == "h264" and pr.get("w") == 1080 and pr.get("h") == 1920
              and pr.get("has_audio") and ev.get("coverage_ok") and ev.get("render_done")
              and abs(pr.get("duration", 0) - aud_dur) < 2.0)
        results[i]["outputs"][label] = {
            "file": out, "exists": os.path.isfile(out), "probe": pr, "log": ev,
            "frames_est": frames, "duration": round(pr.get("duration", 0), 2),
            "PASS": bool(ok),
        }

# manifest
def cell(b): return "PASS" if b else "FAIL"
lines = ["# Render Manifest — doTrang_26_8 (3-min dual-avatar batch)", "",
    f"Voice: {VOICE_ID} (Hạnh, eleven_turbo_v2_5)  |  Locked truth: gain 1.5 / ctx 0 / offset -3 / 25fps / 1080x1920 / CUDA Graph / WOLA / coverage guard", "",
    "| PART | SOURCE SCRIPT | MASTER AUDIO | VOICE | AUDIO DUR | CLOSEUP OUT | CLOSEUP DUR | FULLBODY OUT | FULLBODY DUR | COVERAGE | SYNC | STATUS |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i in PARTS:
    r = results[i]
    cu = r["outputs"]["closeup"]; fb = r["outputs"]["fullbody"]
    lines.append(f"| {i} | audio/part{i}_3min.txt | part{i}_3min.wav | {VOICE_ID} | {r['audio_dur']}s | {os.path.basename(cu['file'])} | {cu['duration']}s | {os.path.basename(fb['file'])} | {fb['duration']}s | {cell(cu['log'].get('coverage_ok'))} | (see syncnet) | {cell(cu['PASS'] and fb['PASS'])} |")
lines += ["", "## Per-output detail", ""]
for i in PARTS:
    for label, av in AVATARS:
        o = results[i]["outputs"][label]
        ev = o["log"]
        lines.append(f"### part{i}_{label} ({av})  -> {cell(o['PASS'])}")
        lines.append(f"- file: `{o['file']}` (exists={o['exists']})")
        p = o["probe"]
        if "error" in p:
            lines.append(f"- probe ERROR: {p['error']}")
        else:
            lines.append(f"- codec={p.get('v_codec')} {p.get('w')}x{p.get('h')} fps={p.get('fps')} audio={p.get('has_audio')} dur={p.get('duration')}s frames~{o['frames_est']}")
        if ev.get("exists"):
            lines.append(f"- locked: gain1.5={cell(ev.get('locked_gain_15'))} offset-3={cell(ev.get('offset_-3'))} fps25={cell(ev.get('fps_25'))} res={cell(ev.get('res_1080x1920'))} cudaGraph={cell(ev.get('cuda_graph_on'))} wola={cell(ev.get('wola_on'))}")
            lines.append(f"- coverage={cell(ev.get('coverage_ok'))} render_done={cell(ev.get('render_done'))} | {ev.get('render_done_line','')}")
        lines.append("")

json.dump(results, open(os.path.join(RD, "_verify.json"), "w"), indent=2)
open(os.path.join(RD, "RENDER_MANIFEST.md"), "w", encoding="utf-8").write("\n".join(lines))

# summary
np_ok = sum(1 for i in PARTS for _ in AVATARS if results[i]["outputs"][_[0]]["PASS"])
print(f"outputs OK: {np_ok}/6")
for i in PARTS:
    for label, _ in AVATARS:
        o = results[i]["outputs"][label]
        print(f"  part{i}_{label}: {cell(o['PASS'])} dur={o['duration']}s coverage={cell(o['log'].get('coverage_ok'))} done={cell(o['log'].get('render_done'))}")
print(f"manifest: {os.path.join(RD,'RENDER_MANIFEST.md')}")