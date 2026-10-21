#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar — lightweight system preflight. Does NOT load any AI models.

Prints the single-source-of-truth system status:
  - current Git branch (must be main for normal production work)
  - render_truth.json validity + locked values
  - prepared avatars under data/avatars/
  - production entrypoint / control board presence
  - Ready: YES / NO  (NO if branch != main OR truth invalid)

Usage:
    python system_status.py
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TRUTH = os.path.join(ROOT, "config", "render_truth.json")
AVATARS = os.path.join(ROOT, "data", "avatars")
BOARD = os.path.join(ROOT, "SYSTEM_CONTROL_BOARD.md")
ENTRY = os.path.join(ROOT, "generate_video_from_script.py")

EXPECTED = {
    "pipeline": "musetalk_v15",
    "audio_gain": 1.5,
    "audio_context_left": 0,
    "audio_feature_offset_frames": -3,
    "fps": 25,
    "resolution_width": 1080,
    "resolution_height": 1920,
    "composite_max_dim": 1920,
    "cuda_graph": True,
    "long_audio_wola": True,
    "feature_coverage_assertion": True,
}


def _git_branch():
    try:
        r = subprocess.run(["git", "branch", "--show-current"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "(unknown)"
    except Exception as e:
        return f"(git error: {e})"


def _load_truth():
    if not os.path.exists(TRUTH):
        return None, "config/render_truth.json NOT FOUND"
    try:
        with open(TRUTH, "r", encoding="utf-8") as f:
            t = json.load(f)
    except Exception as e:
        return None, f"render_truth.json unreadable: {e}"
    problems = []
    for k, v in EXPECTED.items():
        if k not in t:
            problems.append(f"missing key {k}")
        elif t[k] != v:
            problems.append(f"{k}={t[k]!r} expected {v!r}")
    if problems:
        return t, "MISMATCH: " + "; ".join(problems)
    return t, "VALID"


def _avatars():
    if not os.path.isdir(AVATARS):
        return []
    out = []
    for d in sorted(os.listdir(AVATARS)):
        if d.startswith(".") or d.startswith(".uploads"):
            continue
        p = os.path.join(AVATARS, d)
        if not os.path.isdir(p):
            continue
        ready = all(os.path.exists(os.path.join(p, f))
                    for f in ("full_imgs", "coords.pkl", "latents.pt",
                              "mask_coords.pkl", "avator_info.json"))
        out.append((d, "READY" if ready else "NEEDS_CHECK"))
    return out


def main():
    branch = _git_branch()
    truth, truth_status = _load_truth()
    avatars = _avatars()
    board_ok = os.path.exists(BOARD)
    entry_ok = os.path.exists(ENTRY)

    print("AI AVATAR SYSTEM STATUS")
    print("=" * 40)
    print(f"Branch: {branch}")
    print(f"Production Truth: {truth_status}")
    print(f"Pipeline: MuseTalk v1.5")
    print(f"Config: config/render_truth.json")
    if truth:
        print("Locked parameters:")
        print(f"  gain {truth.get('audio_gain')}")
        print(f"  ctx {truth.get('audio_context_left')}")
        print(f"  offset {truth.get('audio_feature_offset_frames')}")
        print(f"  {truth.get('fps')} FPS")
        print(f"  {truth.get('resolution_width')}x{truth.get('resolution_height')}")
        print(f"  CUDA Graph {'ON' if truth.get('cuda_graph') else 'OFF'}")
        print(f"  WOLA {'ON' if truth.get('long_audio_wola') else 'OFF'}")
        print(f"  Feature coverage guard {'ON' if truth.get('feature_coverage_assertion') else 'OFF'}")
    print(f"Prepared avatars ({len(avatars)}):")
    for name, st in avatars:
        print(f"  {name}: {st}")
    print(f"Production entrypoint: {'generate_video_from_script.py' if entry_ok else 'MISSING'}")
    print(f"System Control Board: {'SYSTEM_CONTROL_BOARD.md' if board_ok else 'MISSING'}")
    print("=" * 40)

    ready = (branch in ("main", "nextgen-rtx5090")) and (truth_status == "VALID") and board_ok and entry_ok
    if ready:
        print("Ready: YES")
    else:
        reasons = []
        if branch not in ("main", "nextgen-rtx5090"):
            reasons.append("AUTHORITATIVE_BRANCH_MISMATCH")
        if truth_status != "VALID":
            reasons.append(f"RENDER_TRUTH_{truth_status}")
        if not board_ok:
            reasons.append("CONTROL_BOARD_MISSING")
        if not entry_ok:
            reasons.append("ENTRYPOINT_MISSING")
        print("Ready: NO")
        print("Reason: " + "; ".join(reasons))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())