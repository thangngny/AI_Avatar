#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avatar compatibility validation for the MuseTalk v1.5 production pipeline.

This ONLY checks that a prepared avatar is compatible with the locked production
pipeline. It must NOT change the render truth and must NOT bend the pipeline to
accommodate an unusual avatar — if an avatar is incompatible, the operator has to
(pre)process it via avatars/musetalk/genavatar.py instead.

Required on-disk shape of data/avatars/<avatar_id>/ (matches what
generate_video_from_script.load_avatar_data reads):
    full_imgs/<NNNN>.png ...      (body frames, >=1)
    mask/<NNNN>.png ...            (mouth masks, >=1, same count as full_imgs)
    coords.pkl                     (per-frame face bbox coords)
    mask_coords.pkl                (per-frame mask paste coords)
    latents.pt                     (precomputed VAE latents)
    avator_info.json               ({"version": "v15", ...})

Usage from the production entrypoint:
    from utils.avatar_validate import validate_avatar
    validate_avatar(avatar_id)   # raises SystemExit on any incompatibility
"""
import os
import json
import glob
import pickle


def _img_count(d):
    imgs = sorted(glob.glob(os.path.join(d, "*.[jpJP][pnPN]*[gG]")))
    return imgs


def validate_avatar(avatar_id, avatars_root=None):
    """Validate that `avatar_id` is a MuseTalk v1.5-compatible prepared avatar.

    Fail-closed: prints a precise message and raises SystemExit(1) on the first
    problem. Returns True only if everything checks out.
    """
    root = avatars_root or os.path.join(".", "data", "avatars")
    p = os.path.join(root, avatar_id)

    def _fail(msg):
        raise SystemExit(f"[avatar_validate] AVATAR INCOMPATIBLE ({avatar_id}): {msg}\n"
                        "  Preprocess the avatar with avatars/musetalk/genavatar.py "
                        "(version v15) so it matches the production pipeline. "
                        "Do NOT modify the production pipeline to fit this avatar.")

    if not os.path.isdir(p):
        _fail(f"avatar directory not found: {p}")
    if not os.path.isdir(os.path.join(p, "full_imgs")):
        _fail("missing full_imgs/ directory")
    if not os.path.isdir(os.path.join(p, "mask")):
        _fail("missing mask/ directory")

    full_imgs = _img_count(os.path.join(p, "full_imgs"))
    masks = _img_count(os.path.join(p, "mask"))
    if not full_imgs:
        _fail("full_imgs/ contains no frames")
    if not masks:
        _fail("mask/ contains no masks")

    for fn in ("coords.pkl", "mask_coords.pkl", "latents.pt", "avator_info.json"):
        if not os.path.exists(os.path.join(p, fn)):
            _fail(f"missing required artifact: {fn}")

    # avator_info.json must declare MuseTalk v1.5 (== "v15").
    try:
        with open(os.path.join(p, "avator_info.json"), "r", encoding="utf-8") as f:
            info = json.load(f)
    except Exception as e:
        _fail(f"avator_info.json is unreadable: {e}")
    if str(info.get("version", "")).lower() != "v15":
        _fail(f"avator_info.json version={info.get('version')!r}, required 'v15' "
              "(MuseTalk v1.5 production pipeline).")

    # Count consistency: full_imgs / mask / coords must agree. coords.pkl is a list
    # of per-frame bboxes; its length must equal the frame count.
    try:
        with open(os.path.join(p, "coords.pkl"), "rb") as f:
            coords = pickle.load(f)
    except Exception as e:
        _fail(f"coords.pkl unreadable: {e}")
    n_full = len(full_imgs)
    n_mask = len(masks)
    n_coords = len(coords) if hasattr(coords, "__len__") else None
    if n_coords is None:
        _fail("coords.pkl is not a length-known sequence")
    if n_full != n_mask:
        _fail(f"frame/mask count mismatch: full_imgs={n_full} mask={n_mask}")
    if n_full != n_coords:
        _fail(f"frame/coords count mismatch: full_imgs={n_full} coords={n_coords}")
    if n_full == 0:
        _fail("frame count is 0")

    print(f"[avatar_validate] {avatar_id} OK: {n_full} frames, version=v15, "
          f"all required artifacts present.")
    return True


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Validate a prepared avatar against the MuseTalk v1.5 production pipeline.")
    ap.add_argument("--avatar_id", required=True)
    ap.add_argument("--avatars_root", default=os.path.join(".", "data", "avatars"))
    a = ap.parse_args()
    validate_avatar(a.avatar_id, a.avatars_root)