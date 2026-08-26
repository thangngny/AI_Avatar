# Lip-Sync Source Optimization Report

> Phase: source-quality + avatar-preparation optimization for the remaining
> small/narrow mouth-articulation limitation. Production truth NOT changed.
> Authoritative repo `C:\CongThang_AI_Avatar\AI_avatar`, branch `main`.

## 1. Executive Summary

The remaining small/narrow mouth articulation is **primarily a RAW_MUSETALK
(model-level) limitation**, not a compositing problem and not fixable by avatar-
preparation geometry alone. Across every avatar tested — including the production
`close_up` baseline and three new geometry variants — the raw 256×256 model output
has an essentially fixed vertical-mouth range of ~0.078 (normalized by face width).
Avatar-preparation geometry (`extra_margin`) can modestly increase the *composite*
jaw-motion visibility (+17% vertical range, +18% width range in a controlled
same-landmark comparison) without hurting timing or lip closure, but this is a
composite-level gain, not a model-level fix, and it does **not** beat the existing
production `close_up` (which already benefits from mmpose landmarks + its original
raw, both now unavailable).

**Outcome: NO PROMOTION.** A new master recording with a larger face (face_h /
frame_height ≥ 0.16 vs close_up's 0.116) and a neutral mouth is required for a
material, model-level improvement.

## 2. Current Production Baseline

- Renderer: `generate_video_from_script.py`; truth: `config/render_truth.json`
  (MuseTalk v1.5, gain 1.5, ctx 0, offset -3, 25 FPS, 1080×1920, CUDA Graph ON,
  WOLA ON, coverage guard ON) — **unchanged**.
- Production avatar: `close_up` (980 frames, v15). Face crop 168×222, mask 332×332,
  face_h/frame_height = 0.116, parsing_mode = `jaw` (PROVEN from avator_info),
  extra_margin = 10 / cheek = 90 (INFERRED — genavatar defaults; not stored in
  avator_info.json).
- close_up original raw (`D:\Noble\…\musetalk_4872_697362812.mp4`) is **MISSING**.

## 3. Remaining Lip-Sync Limitation

Human review reports mouth movements look too small/narrow and several syllables
look visually similar. The known fixes (long-audio WOLA, temporal offset -3, ctx 0,
gain 1.5) are validated and unchanged. The residual limitation is mouth aperture /
shape diversity, previously attributed to RAW_MUSETALK. This experiment confirms:
raw 256 vertical mouth range ≈ 0.078 across all candidates (close_up 0.0757,
variants 0.078–0.079) — i.e. the model output mouth is narrow and essentially
independent of avatar geometry. Geometry changes the composite (how much jaw motion
is *visible* after paste-back), not the raw model mouth.

## 4. Raw Source Inventory

Classified (RAW_SOURCE vs PREPARED_DERIVED vs GENERATED_OUTPUT). Source-quality
gate (`tools/avatar_source_quality/validator.py`, OpenCV-only, offline):

| Candidate | Class | Overall | face_h_ratio | sharp | mouth_state | Notes |
|---|---|---|---|---|---|---|
| `close_up` recon (from full_imgs) | RAW_SOURCE (derived) | PASS | 0.104 | 282 | neutral | close_up's own source frames; best quality but circular for new avatars |
| `test17_8\Close Up.mp4` | RAW_SOURCE | WARN | 0.103 | 235 | neutral* | best surviving raw; *gate proxy says neutral but source IS talking (known) |
| `recordings\test_take_1.mp4` | RAW_SOURCE | WARN | 0.105 | 147 | neutral | 254 s, softer face |
| `record_av.mp4` | RAW_SOURCE | WARN | 0.093 | 90 | neutral | small face, soft |
| `.uploads\musetalk_8960_*.mp4` (4K) | RAW_SOURCE | **FAIL** | 0.074 | 25.6 | neutral | 4K but full-body → tiny + blurry face |
| `Hearing-1.mp4` (4K) | RAW_SOURCE | **FAIL** | 0.087 | 16.5 | neutral | 4K but soft, 8 s |
| `half.mp4` | RAW_SOURCE | **FAIL** | 0.187 | 212 | neutral | high motion/shake, landscape |

*The gate's OpenCV-only talking_proxy under-detects talking (limitation noted in
§23); the test17_8 source is known to be talking from prior audit, hence only a
fallback, not an ideal master.

## 5. Source Ranking

1. `close_up` recon (PASS, but derived — not a new raw)
2. `test17_8\Close Up.mp4` (WARN — best *surviving original* raw, but talking)
3. `recordings\test_take_1.mp4` (WARN — soft)
4. `record_av.mp4` (WARN — small/soft)
5–7. 4K `.uploads`, `Hearing-1`, `half.mp4` (FAIL)

## 6. Best Surviving Raw Source

```
C:\CongThang\AI_avatar\test17_8\Close Up.mp4   (1080x1920, 60fps, 29.4s)
```
WARN (motion + lighting); usable fallback only because the subject is talking
(non-neutral base mouth). Second-best `recordings\test_take_1.mp4` is softer.

## 7. Prepared Avatar Audit

`avator_info.json` stores only `avatar_id, video_path, bbox_shift, version,
parsing_mode` — it does **not** store `extra_margin` / `cheek_width` (those are
prep-time params baked into `coords.pkl`/`mask/`). Geometry measured from
`coords.pkl`/`mask_coords.pkl` (format `[x1,y1,x2,y2]`):

| Avatar | face crop | mask crop | face_h/frameH | em (prep) | parsing |
|---|---|---|---|---|---|
| close_up (prod) | 168×222 | 332×332 | 0.116 | 10 (INF) | jaw (PROVEN) |
| V0 cu_recon_em10_jaw | 165×226 | 338×338 | 0.118 | 10 | jaw |
| V1 cu_recon_em20_jaw | 165×236 | 354×354 | 0.123 | 20 | jaw |
| V2 cu_recon_em10_mouthchin | 165×226 | 338×338 | 0.118 | 10 | mouth_chin |
| fullbody_30_7_25fps | 282×360 | 540×540 | 0.188 | ? | jaw |

PROVEN = read from metadata/artifacts; INF = inferred (genavatar default, not stored).

## 8. Source → Avatar Lineage

```
close_up  ←  D:\Noble\…\musetalk_4872_697362812.mp4  (MISSING)
cu_recon_em10_jaw        ←  close_up full_imgs reconstructed video  (em10, jaw)   [control]
cu_recon_em20_jaw       ←  close_up full_imgs reconstructed video  (em20, jaw)   [extra_margin]
cu_recon_em10_mouthchin ←  close_up full_imgs reconstructed video  (em10, mouth_chin) [parsing]
```
All three `cu_recon_*` are NEW ids; `close_up` was never overwritten.
`data/avatar_sources.json` updated (data-only, backward compatible) with the 3
experimental variants flagged `experimental: true`.

## 9. Source Quality Gate

CREATED: `tools/avatar_source_quality/validator.py` — `--video <path> [--json]`.
Reports PASS/WARN/FAIL for VIDEO_INTEGRITY, FACE_SIZE, FACE_SHARPNESS, FRONTALNESS,
MOUTH_VISIBILITY, CHIN_VISIBILITY, SOURCE_MOUTH_STATE, MOTION, LIGHTING. OpenCV +
NumPy only (offline, no OCR/internet, never mutates). NOT wired into production.
JSON outputs for the audited sources are under
`D:\CongThang_AI_Avatar\renders\source_opt\gate\`.

## 10. Geometry Experiment

Canonical v1.5 prep is `python -m avatars.musetalk.genavatar` (NOT the legacy
`create_avatar.py`, which only writes full_imgs+coords, no latents/mask/avator_info).
Three bounded variants prepared (extra_margin 10→20; parsing jaw vs mouth_chin;
cheek 90 fixed; bbox_shift 0). Preparation used fallback-bbox mode (mmpose landmark
model not available in this env) — a confound noted in §23.

## 11. Locked A/B Configuration

Same for all 4 renders: audio `test_ab.wav` (17.9 s, vi-VN-HoaiMyNeural edge-tts,
phonetically diverse), gain 1.5, ctx 0, offset -3, 25 FPS, 1080×1920, CUDA Graph
ON, WOLA ON, coverage guard ON. Only avatar source/preparation varied. Feature
coverage OK (1500 features for 449 frames) on every render.

## 12. Objective Metrics

SyncNet (LatentSync syncnet, `experiments/ab_syncnet.py` → `syncnet_score.py`) and
mouth geometry (FAN 68 landmarks, `experiments/raw_vs_composite_measure.py`):

| Avatar | comp_vopen_range | comp_width_range | ratio_vopen | diversity R/C | closure_min | SyncNet conf | AV off |
|---|---|---|---|---|---|---|---|
| **close_up (prod)** | **0.1316** | 0.0600 | 1.370 | 16/21 | 0.0000 | 0.5511 | +1 |
| V0 recon em10_jaw | 0.0977 | 0.0734 | 1.394 | 18/16 | 0.0000 | 0.5896 | 0 |
| V1 em20_jaw | 0.1145 | 0.0866 | 1.463 | 18/18 | 0.0000 | 0.5542 | +1 |
| V2 em10_mouthchin | 0.0873 | 0.0646 | 1.414 | 18/18 | 0.0000 | 0.4720 | 0 |

Controlled geometry delta (V1 vs V0 — both reconstructed, both fallback-bbox, only
geometry differs): comp_vopen_range **+17%**, comp_width_range **+18%**, diversity
16→18, closure preserved, sync within noise (0.5542 vs 0.5896). So extra_margin=20
genuinely increases composite jaw-motion visibility.

vs production close_up: V1 is mixed (-12.9% vertical range, +44.2% width range).
No variant clearly beats close_up; V2 (mouth_chin) is worse on both range and sync.

## 13. RAW_MUSETALK Findings

Raw 256 vertical mouth range is ~0.078 for ALL candidates (close_up 0.0757; V0
0.0789; V1 0.0786; V2 0.0777) — essentially fixed. composite/raw ratio ~1.37–1.46
(composite opens *more* than raw, so compositing is not compressing). **The
narrowness is at the model output (RAW_MUSETALK), independent of avatar geometry.**
Geometry changes composite visibility, not the raw model mouth.

## 14. Composite Findings

extra_margin=20 enlarges the mask crop (332→354) and the face-crop height (222→236),
giving ~16 px more chin/jaw room → more visible jaw motion in the composite (+17%
vertical, +18% width range). Closure remains PASS (min inner-lip opening 0.0). No
sync regression (AV offset +1, same as baseline).

## 15. Best Candidate

Within the controlled reconstruction, **V1 (em20_jaw)** is the best geometry
candidate (+17%/+18% composite range, closure preserved, no sync regression). But
it does **not** clearly beat the production `close_up` (which retains higher
vertical range from mmpose landmarks + original mask), and its gain is composite-
level, not model-level.

## 16. Whether New Recording Is Required

**YES.** No surviving raw source and no geometry variant materially beats
`close_up`. The model-level narrowness (raw 256 range ≈ 0.078) is fixed by lip
pixel density in the 256 input, which depends on SOURCE face size. close_up's
face_h/frame_height is only 0.116; a master with face ≥ 0.16 gives more lip detail
per 256 pixel → the only path to a material RAW-level improvement. Spec:
`docs/MASTER_AVATAR_SOURCE_SPEC.md`.

## 17. Recommended Next Action

1. Do NOT promote any variant to production. Keep `close_up` as the production
   avatar (locked config unchanged).
2. Record a new master per `docs/MASTER_AVATAR_SOURCE_SPEC.md` (vertical, large
   face ≥0.16, neutral mouth, full chin/jaw, fixed camera, stable light).
3. Validate the new raw with `tools/avatar_source_quality/validator.py` (must PASS).
4. Prepare it with `python -m avatars.musetalk.genavatar --parsing_mode jaw
   --extra_margin 10` into a NEW id; A/B vs `close_up` under locked truth; promote
   only with human approval and a CLEAR objective + perceptual win.
5. (Optional, if a new master is delayed) the +17% composite-range geometry
   finding suggests a future controlled test of extra_margin=20 on a NEWLY recorded
   master (with mmpose landmarks if available) — but only after a clean recording.

## 18. New Recording Required

YES — see §16 and `docs/MASTER_AVATAR_SOURCE_SPEC.md`.

## 19. Files Changed (committed)

- `tools/avatar_source_quality/validator.py` (new — source-quality gate)
- `experiments/raw_vs_composite_measure.py` (new — RAW vs composite + mouth metrics)
- `experiments/ab_syncnet.py` (new — SyncNet A/B scorer)
- `docs/MASTER_AVATAR_SOURCE_SPEC.md` (new — master recording spec)
- `docs/LIPSYNC_SOURCE_OPTIMIZATION_REPORT.md` (this file)
- `data/avatar_sources.json` (updated — added 3 experimental cu_recon_* lineage
  entries; data-only, gitignored)

## 20. Production Files NOT Changed

- `config/render_truth.json` — unchanged (verified: all locked values identical)
- `generate_video_from_script.py` — unchanged
- `data/avatars/close_up/` — NOT overwritten (read-only; used only for rendering)
- `avatars/musetalk/genavatar.py` — unchanged
- No production import from `experiments/` or `archive/` (verified)
- LatentSync not integrated; production still MuseTalk v1.5 only

## 21. Commands Run

```
python system_status.py                                  # PASS (main/VALID/YES)
python -m avatars.musetalk.genavatar --file <recon>.mp4 --avatar_id cu_recon_em10_jaw   --extra_margin 10 --parsing_mode jaw
python -m avatars.musetalk.genavatar --file <recon>.mp4 --avatar_id cu_recon_em20_jaw   --extra_margin 20 --parsing_mode jaw
python -m avatars.musetalk.genavatar --file <recon>.mp4 --avatar_id cu_recon_em10_mouthchin --extra_margin 10 --parsing_mode mouth_chin
python generate_video_from_script.py --avatar_id <id> --audio test_ab.wav --output <id>.mp4   (×4, locked truth)
python experiments/ab_syncnet.py --videos <label=path>... --out_json syncnet.json
python experiments/raw_vs_composite_measure.py --avatar_id <id> --wav test_ab.wav --out_json <id>.json   (×4)
python tools/avatar_source_quality/validator.py --video <path> --json <out>   (×sources)
```

## 22. Render Paths

- A/B composites: `D:\CongThang_AI_Avatar\renders\source_opt\ab\<avatar>.mp4`
- Human review package: `D:\CongThang_AI_Avatar\renders\source_opt\review\`
  (`A_baseline_close_up.mp4`, `B_candidate_em20_jaw.mp4`,
   `C_candidate_mouthchin.mp4`, `D_recon_control_em10_jaw.mp4`,
   `side_by_side_ABC.mp4`)
- Metrics JSON: `D:\CongThang_AI_Avatar\renders\source_opt\metrics\`
  (`syncnet.json`, `rvc_<avatar>.json`)
- Gate JSON: `D:\CongThang_AI_Avatar\renders\source_opt\gate\`
- New prepared avatars (gitignored): `data\avatars\cu_recon_em10_jaw`,
  `cu_recon_em20_jaw`, `cu_recon_em10_mouthchin`

## 23. Unknowns / Limitations

- **mmpose landmark model unavailable** in this env → all 3 variants used fallback
  bbox mode. close_up was likely prepared WITH mmpose (better mask/landmarks), so
  the reconstruction (V0) is not a faithful control (V0 vertical range -25.8% vs
  close_up). The clean geometry signal is V1-vs-V0 (both fallback), not V1-vs-close_up.
- **Reconstruction artifacts**: re-encoding close_up's full_imgs to video then
  re-extracting introduces minor frame differences (genavatar reported abrupt
  transitions). All variants share this, so V1-vs-V0 still isolates geometry.
- **OpenCV-only talking_proxy** in the gate under-detects talking (test17_8 scored
  neutral but is known-talking). A landmark-based mouth-aperture metric (FAN, used
  in §12) is the reliable mouth-state measure; the gate is a first-pass screen.
- **No artifact detection**: extra_margin=20 might introduce chin/neck artifacts not
  caught by metrics — requires human review of `B_candidate_em20_jaw.mp4` before
  any future use.
- **Short test clip** (17.9 s) — sufficient for articulation/sync metrics; longer
  validation skipped because no candidate clearly beat close_up.
- extra_margin was tested at 10 vs 20 only (bounded per spec); higher values were
  NOT pursued (risk of stretched jaw / neck deformation per spec warnings).