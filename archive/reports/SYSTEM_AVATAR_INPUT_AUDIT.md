# SYSTEM_AVATAR_INPUT_AUDIT.md — MuseTalk input-avatar audit

Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Date: 2026-08-25
Branch: `feature/mouth-articulation-v1` (audit only — no code or source files modified)
Method: pure numeric analysis (face_alignment/FAN 68-landmarks, MuseTalk `coords.pkl`/`mask_coords.pkl`, Laplacian sharpness, frame-diff). **No image was read by a language model.** Contact sheets (5 frames per avatar) were generated for the human reviewer under `D:\CongThang_AI_Avatar\avatar_audit\contact_*.jpg` — the model cannot view them, so occlusion / identity / aesthetic checks are left to the reviewer.

The current problem being diagnosed: lip-sync **timing is correct, but visible mouth articulation still looks too small/subtle**.

---

## Existing avatar inventory

12 prepared avatar folders under `data/avatars/` (one incomplete: `30_7_fullbody` has no mask/coords/latents). The source-video paths recorded in each `avator_info.json` are almost all **missing** (old `D:\AI_avatar*` / `D:\Noble` / `C:\Users\Admin\Videos\30_7\` locations). The prepared `full_imgs` (what MuseTalk actually uses) are intact for all complete folders. Two surviving source videos exist locally (identical 4K/30 fps/30.6 s clips in `data/avatars/.uploads/`).

| Candidate (prepared) | Recorded source path (status) | Prepared res | Frames | Current use |
| --- | --- | --- | --- | --- |
| fullbody_30_7_25fps | `C:\Users\Admin\Videos\30_7\Closeup.mp4` (MISSING) | 2160×3840 | 810 | **ACTIVE** (Stage 5) |
| fullbody_30_7_jaw | Closeup.mp4 (MISSING) | 2160×3840 | 810 | historical (jaw variant of active source) |
| fullbody_30_7_mouth_chin | Closeup.mp4 (MISSING) | 2160×3840 | 810 | historical (mouth_chin variant) |
| fullbody_30_7_stable | Closeup.mp4 (MISSING) | 2160×3840 | 810 | historical (jaw variant) |
| fullbody_30_7 | `…musetalk_3164_7289750.mp4` (MISSING) | 2160×3840 | 459 | historical |
| 30_7_fullbody | `…musetalk_8960_6881921.mp4` (EXISTS in `.uploads`) | 2160×3840 | 459 | historical — **incomplete prep** |
| 30_7close | `…musetalk_5412_…mp4` (MISSING) | 2160×3840 | 486 | historical |
| fulbody_2_8 | `…musetalk_8372_…mp4` (MISSING) | 2160×3840 | 765 | historical (mouth_chin) |
| close_up | `…musetalk_4872_…mp4` (MISSING) | 1080×1920 | 980 | historical — **best candidate** |
| close_up_16_7 | `…musetalk_16920_62453968.mp4` (MISSING) | 1080×1920 | 662 | historical — strong candidate |
| full_body_16_7 | `…musetalk_16920_70558687.mp4` (MISSING) | 1080×1920 | 933 | historical |
| 23_7_avt | `…musetalk_15332_…mp4` (MISSING) | 1080×1920 | 735 | historical (mouth-only parsing) |

Surviving source-video ffprobe (`.uploads/musetalk_8960_6881921.mp4`, = `musetalk_10804_5835750.mp4`, byte-identical): h264, 2160×3840, 30 fps, 918 frames, 30.65 s, 71 MB (~18 Mbps — **low bitrate for 4K → heavy compression / soft**). Project-root `temp*.mp4` files are orphan uploads not referenced by any avatar.

The four `fullbody_30_7_*25fps/jaw/mouth_chin/stable` folders share one source (`Closeup.mp4`) and differ only by `parsing_mode` (jaw vs mouth_chin); their face geometry is identical, only the paste mask differs.

---

## Input-quality comparison

Face size = MuseTalk authoritative `coords.pkl` face height / frame height (median). Frontal = inter-ocular-distance / face-width (≈0.44–0.46 = frontal). Mouth-clear = mean mask alpha over the mouth bbox (1.0 = mouth fully in the replace-zone). Chin-clear = mask alpha at chin. Lower margin = prepared mask margin below face / face_h (all 0.25). Sharpness = Laplacian variance on the face region. Neutral mouth = std of normalized mouth opening across the source (0 = perfectly closed). All avatars are frontal, have the mouth fully covered by the mask, and have a 0.25 lower-face margin; the differentiators are **face size** and **source sharpness**.

| Candidate | Face size (fh/fH) | Frontal (IOR) | Mouth clear | Chin clear | Lower margin | Sharpness (face) | Neutral mouth | Score | Grade |
| --- | ---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: | :---: |
| **close_up** | 0.116 (223 px) | 0.444 | PASS (1.00) | 0.52 (jaw) | 0.25 | **385** | 0.000 | **93** | **A** |
| close_up_16_7 | 0.128 (246 px) | 0.451 | PASS (1.00) | 0.60 (jaw) | 0.25 | 154 | 0.008 | 82 | B |
| 23_7_avt | 0.107 (206 px) | 0.442 | PASS (1.00) | 0.00 (**mouth-only**) | 0.25 | 343 | 0.007 | 80 | B |
| full_body_16_7 | 0.097 (186 px) | 0.447 | PASS (1.00) | 0.52 (jaw) | 0.25 | 280 | 0.009 | 79 | B |
| **fullbody_30_7_25fps (ACTIVE)** | 0.094 (180 px @1080) | 0.464 | PASS (1.00) | 0.69 (jaw) | 0.25 | **28** | 0.009 | **67** | **C** |
| fullbody_30_7_mouth_chin | 0.094 | 0.464 | PASS (0.98) | 0.26 | 0.25 | 28 | 0.009 | 64 | C |
| 30_7close | 0.094 | 0.464 | PASS (1.00) | 0.69 (jaw) | 0.25 | 28 | 0.010 | 65 | C |
| fullbody_30_7 | 0.084 | 0.450 | PASS | ~0.69 (jaw) | 0.25 | 34 | 0.010 | 61 | C |
| fulbody_2_8 | 0.084 | 0.451 | PASS (0.98) | 0.25 | 0.25 | 33 | 0.007 | 56 | C |
| 30_7_fullbody | — | — | — | — | — | — | — | — | (incomplete) |

Scoring rubric (0–100): face size/detail 25, frontal 15, mouth visibility 15, chin/lower-face margin 15, source sharpness 10, low blur 5, stable lighting 5, stable geometry 5, neutral source mouth 5. Critical failures (mouth covered, chin cropped, face extremely small) would disqualify regardless of score — none found here, but `23_7_avt`'s mouth-only parsing (chin_alpha 0.00 → **no jaw replacement**, so the jaw cannot articulate) is treated as a chin-margin limitation that caps it at B.

---

## Current Stage 5 avatar

`D:\CongThang_AI_Avatar\renders\stage5_gain15_3min.mp4` was rendered with `--avatar_id fullbody_30_7_25fps`.

```
source video path      : C:\Users\Admin\Videos\30_7\Closeup.mp4  (MISSING — only the prepared frames survive)
prepared avatar path   : data/avatars/fullbody_30_7_25fps
preparation            : MuseTalk v15, bbox_shift=0, parsing_mode=jaw, extra_margin/lower margin = 0.25×face_h
face size              : 0.094 of frame height (≈180 px in the final 1080 composite — SMALL)
lower-face margin      : 0.25×face_h (≈45 px below face in 1080) — adequate but not generous
head pose              : frontal (IOR 0.464, most frontal of the set), low jitter
mouth-source behavior  : NEUTRAL_MOUTH (closed; vopen std 0.009)
source sharpness       : very low (face-region Laplacian 28; 4K source ≈18 Mbps, heavily compressed)
```

The four `fullbody_30_7_*` variants of this source differ only in parsing mask; the active one (`jaw`) already has the best jaw/chin coverage of the set (chin_alpha 0.69, underlip 0.89), so switching to the `_mouth_chin` or `_stable` variant of the SAME source would **not** fix the small-face/blurry-source problem.

---

## Best existing avatar

```
data/avatars/close_up
```

- 1080×1920, 980 prepared frames, complete v15 prep, parsing_mode=**jaw**.
- **Face 0.116 of frame height (≈223 px @1080) — ~24 % larger than the active avatar's 180 px.** MuseTalk generates a 256×256 face then pastes it into the face bbox; a larger paste target (223 vs 180 px) preserves ~1.24× more lip pixels, and the source is far sharper so the encoded latent carries more lip-edge detail.
- **Sharpest face of all candidates (Laplacian 385 vs the active's 28 — ~14× sharper source)** → cleaner lip edges for MuseTalk to generate against.
- Frontal (IOR 0.444), neutral closed source mouth (vopen std 0.000 — cleanest slate for audio-driven generation), mouth fully in the replace-mask (alpha 1.00), jaw mode (chin_alpha 0.52, underlip 0.80 → jaw can move).
- Stable: real moving video (mean frame-diff 5.94, not a frozen still), low lighting flicker (luma std 1), lowest face-y jitter (cyStd 4).

Caveat the metrics cannot resolve (needs the reviewer on the contact sheet `contact_close_up.jpg`): confirm there is **no microphone / hand / hair occluding the lower face**, and that the identity is the intended presenter. The numeric profile (frontal, neutral closed mouth, mouth fully covered by a jaw mask, sharp, real motion) is exactly the ideal MuseTalk input, but occlusion can only be ruled out visually.

Runner-up: `close_up_16_7` (face 0.128 — the largest face, but softer, sharpness 154). `23_7_avt` is sharp and frontal but uses **mouth-only** parsing (no jaw replacement) so the jaw will not articulate — not recommended.

---

## Critical findings — what is causing the small-looking articulation

- **Face too small: YES (primary).** The active avatar's face is only 9.4 % of frame height (180 px in the final 1080 composite). MuseTalk decodes a 256×256 face and `cv2.resize`-pastes it **down** to 180 px — lip detail is discarded. `close_up` keeps ~223 px (and `close_up_16_7` ~246 px), so more lip detail survives into the composite. This is the most likely contributor to "articulation looks small".
- **Lower-face crop too tight: NOT a differentiator.** All complete avatars use the same 0.25×face_h lower margin. The active one is no tighter than the alternatives. A *larger* `extra_margin` would help jaw visibility, but that requires **re-preparation**, and the active source (`Closeup.mp4`) is missing (see below).
- **Source sharpness / blur: YES (secondary).** The active 4K source is heavily compressed (≈18 Mbps) → face-region sharpness 28, ~14× softer than `close_up` (385). A soft source encodes a soft latent → soft generated mouth, and the 256→180 downscale then hides it ("acceptable" on review, but with little lip-edge energy to begin with). The 1080p candidates are far sharper at a resolution MuseTalk can actually use.
- **Source mouth geometry: NOT a problem.** Active source mouth is neutral/closed (ideal). All candidates are neutral or light-natural-motion.
- **Head angle: NOT a problem.** Active is frontal (IOR 0.464, the most frontal). All candidates frontal.
- **Source speaking: NOT a problem.** All neutral.
- **Avatar preparation: consistent.** v15, bbox_shift 0, 0.25 margin. The active prep is not malformed; it is simply a small-face, soft-source input. The four same-source variants only differ in mask parsing and do not address the root cause.

Net: the small articulation is most plausibly caused by the active avatar being a **full-body, heavily-compressed 4K shot with a small face**, not by timing, pose, mouth geometry, or preparation. A sharper, closer existing avatar should give MuseTalk more lip pixels and lip-edge energy to work with.

---

## Does the project already contain an ideal existing avatar?

**YES** — `data/avatars/close_up`:
- larger face (0.116 vs 0.094), ~14× sharper source (385 vs 28), jaw-mode mask with the mouth fully covered, frontal, neutral closed mouth, real motion, stable lighting/geometry.
- It is **better than the currently used avatar** on the two axes that directly limit visible articulation (face pixels and source sharpness), and equal or better on every other axis except a tiny frontal-pose edge for the active avatar (0.464 vs 0.444 — both frontal) and jaw-coverage edge (active chin_alpha 0.69 vs 0.52 — both adequate).
- It is **not currently used** (the Stage 5 renders use `fullbody_30_7_25fps`).

One caveat only the reviewer can resolve: confirm no lower-face occlusion on `contact_close_up.jpg`.

---

## Re-preparation status

- The **active** source (`Closeup.mp4`) is **MISSING** → `fullbody_30_7_25fps` **cannot be re-prepared** with a larger `extra_margin`. Same for all four `fullbody_30_7_*` variants.
- The **`close_up`** source is also **MISSING** → it cannot be re-prepared either, but its **existing v15 prep is complete and usable as-is** (full_imgs + mask + coords + mask_coords + latents all present). So it can be tested immediately without any re-prep.
- The only avatar whose source still exists is `30_7_fullbody` (`.uploads/musetalk_8960_6881921.mp4`, 4K/30 fps) — but that one is a small-face, very-soft 4K source (sharpness 4) and its prep is **incomplete** (no mask/coords/latents), so it is not a useful candidate.

**Does the avatar need to be re-prepared for MuseTalk?** For the recommended next test (use `close_up`'s existing prep as-is): **NO**. Only if a *larger lower-face `extra_margin`* is later wanted would re-prep be needed — and for `close_up` the source is gone, so that would require a re-record.

---

## Recommendation

**`TEST_EXISTING_BETTER_AVATAR`** — do not render yet; the exact next test is a short controlled A/B on the existing 20 s continuous passage (`script_stage5_continuous.txt`, master WAV `master_continuous.wav`, gain 1.5, ctx0, off-3, 25 fps, CUDA Graph ON):

1. Render `--avatar_id close_up` with the **same** Stage 5 Candidate-C settings.
2. Render (or reuse) `--avatar_id fullbody_30_7_25fps` (active) with the same settings/audio.
3. Compare with the existing harness: SyncNet (av_offset, sync_conf), `stage5_measure.py` mouth range/diversity/identity, `diag_motion.py` freeze check, and **reviewer visual** on the contact sheets + the two rendered clips.

Only if `close_up` also fails to show clearly more articulation, or the reviewer finds an occlusion/identity problem on its contact sheet, fall back to `RECORD_NEW_AVATAR` (a 1080p/4K sharp, frontal, neutral-mouth, head-and-shoulders close-up recorded with a clean lower face and ≥50 Mbps). `REPREPARE_CURRENT_AVATAR` is **not available** — the active source video is missing. `KEEP_CURRENT_AVATAR` is not recommended because the active avatar is a small-face, heavily-compressed 4K shot, which is the most likely root cause of the small-looking articulation.

---

## Files produced by this audit (diagnostics only — not production, not committed)

- `avatar_audit.py`, `avatar_audit2.py`, `avatar_audit3.py` — measurement scripts
- `D:\CongThang_AI_Avatar\avatar_audit\contact_*.jpg` — 12 contact sheets (5 frames each) for human review
- `D:\CongThang_AI_Avatar\avatar_audit\avatar_audit*.json` — raw metric data

No production code or source avatar files were modified.