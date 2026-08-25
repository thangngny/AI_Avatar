# SYSTEM LIPSYNC STAGE 3 REPORT — Temporal Calibration

Report path: `C:\CongThang_AI_Avatar\AI_avatar\SYSTEM_LIPSYNC_STAGE3_REPORT.md`
Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Date: 2026-08-24
Branch: `main`. Not committed (per instruction).

Evaluator: SyncNet scorer at `C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py`
(ByteDance StableSyncNet, `models/syncnet/latentsync_syncnet.pt`, face_crop preprocess,
25 FPS, 16-frame windows). Metrics: `sync_confidence`=S(0) (higher better),
`lse_c`=S(0)-mean(S(±10)) (higher better), `lse_d_min`=1-max S(d) (lower better),
`av_offset_frames`=argmax_d S(d) (0 = aligned; **+ = mouth leads audio**).

---

## 1. Executive Summary

- **Baseline measured lag: +2 frames (+80 ms) — the mouth LEADS the audio** by ~80 ms
  (consistent with the offline renderer's future-biased 200 ms feature window
  `[center, center+10]`).
- **Best offset: −3 frames (−120 ms)**, applied as a clean configurable
  `--audio-feature-offset-frames` parameter that shifts only the audio-conditioning
  feature window in time (shape unchanged, final audio track untouched).
- **Sync improved strongly and consistently:** whole-video `lse_c` 0.043 → 0.252
  (~6×), `sync_confidence` 0.203 → 0.418, and `av_offset` +2 → **0** (aligned) on
  the 55 s, 90 s, and 167.6 s renders, in every measured segment.
- **Confidence: HIGH.** The −3 offset won on two independent 20 s speech sections
  (A: lse_c 0.302; B: 0.230) and held across 55 s / 90 s / 167.6 s.
- **No drift:** `av_offset` is CONSTANT (0 after fix, +2 before) from 5 s to 155 s —
  a single global offset is the correct fix (not a rate mismatch).
- **Remaining issue: ARTICULATION / visual mouth quality, not timing.** Timing is
  now correct (av_offset 0); the residual `lse_c ≈ 0.25` is a mouth-shape fidelity
  limit of MuseTalk 1.5 + whisper-tiny, deferred to Stage 4.

---

## 2. Current Timing Architecture

Offline path (`generate_video_from_script.py:render_video` → `Audio2Feature.feature2chunks` → `get_sliced_feature`):

```
video frame i  (25 FPS, 1 frame = 40 ms)
↓
vid_idx = i + start                       (start = i + offset, see below)
↓
center_feature_index = int(vid_idx * 50 / 25) = vid_idx * 2     (50 Hz features, 20 ms/feature)
↓
left_idx  = center_idx                    (NOTE: offline uses NO left context — window is future-biased)
right_idx = center_idx + (L+R+1)*2 = center_idx + 10            (audio_feat_length=[2,2] -> 10 features = 200 ms)
↓
window = feature_array[center .. center+10]   (10 features, 200 ms look-ahead)
   out-of-range indices clamp to [0, length-1]  (natural start/end padding)
↓
reshape -> [50, 384] MuseTalk audio conditioning (shape CONSTANT regardless of offset)
↓
UNet(latent[i], audio_window) -> mouth[i]
```

Constants: fps=25, feature rate=50 Hz, `feature_idx_multiplier=50/fps=2`,
`audio_feat_length=[2,2]`, window=10 features=200 ms. 1 video frame = 2 feature
steps = 40 ms. The 200 ms future-biased window is the source of the baseline +2
frame (~80 ms) mouth lead.

---

## 3. Offset Definition

Parameter: `--audio-feature-offset-frames N` (integer video frames, default **0**).

Effect: `vid_idx = i + N` → `center = (i + N) * 2` features. Window SHAPE
(10 features, [2,2]) is unchanged; only the center shifts in time.

- **+1 frame (+40 ms):** use audio features 40 ms LATER → mouth anticipates / leads MORE.
- **−1 frame (−40 ms):** use audio features 40 ms EARLIER → mouth lags MORE / leads less.
- **0:** unchanged Stage 2 behavior (byte-identical; `start = i + 0 = i`).

The offset does NOT touch: the final audio track, the WAV, ffmpeg mux, video
duration, FPS, Whisper feature generation, WOLA, or realtime. Negative offsets
near the start (i < |N|) just clamp to feature 0 (natural start padding) — no error.

---

## 4. Baseline Measurements (offset 0, 55 s, face_crop)

Whole video: `sync_confidence=0.2034, lse_c=0.0430, lse_d=0.6095, av_offset=+2`.

| segment | conf | lse_c | lse_d | av_off |
|---------|-----:|------:|------:|-------:|
| 0–10  | 0.2294 | 0.0928 | 0.6475 | +2 |
| 10–20 | 0.1912 | 0.0137 | 0.6692 | +2 |
| 20–30 | 0.1977 | 0.0293 | 0.6493 | +2 |
| 30–40 | 0.2101 | 0.0412 | 0.5477 | +2 |
| 40–50 | 0.2083 | 0.0704 | 0.7143 | +2 |

Baseline lag is a **constant +2 frames** across all segments (no drift), ~80 ms
mouth lead. `lse_c ≈ 0.04–0.09` (near chance) → poor sync.

---

## 5. Offset Sweep (20 s section A, offsets −5…+5)

| Offset frames | Offset ms | sync_conf | lse_c | av_off | Notes |
|-------------:|----------:|----------:|------:|-------:|-------|
| −5 | −200 | 0.3149 | 0.1916 | −1 | over-corrected (mouth now lags) |
| −4 | −160 | 0.4334 | 0.3012 |  0 | strong, aligned |
| **−3** | **−120** | **0.4363** | **0.3024** | **0** | **best** |
| −2 |  −80 | 0.3347 | 0.2134 | +1 | |
| −1 |  −40 | 0.2435 | 0.1154 | +1 | |
|  0 |    0 | 0.2074 | 0.0582 | +2 | baseline |
| +1 |  +40 | 0.1910 | 0.0200 | +2 | worse |
| +2 |  +80 | 0.1682 | −0.0127 | +3 | worse |
| +3 | +120 | 0.1551 | −0.0186 | +3 | worse |
| +4 | +160 | 0.1612 | −0.0071 | +4 | worse |
| +5 | +200 | 0.1772 | 0.0123 | +4 | worse |

Clear unimodal peak at −3/−4. `av_offset` shifts monotonically +2→0→−1 as offset
goes 0→−3→−5, confirming the mechanism is linear and correctly signed (~1 offset
frame ≈ 1 av_offset frame).

---

## 6. Best Candidate

**−3 frames (−120 ms).** Won on section A (lse_c 0.3024, av_off 0; −4 tied at
0.3012). Chosen over −4 because it was marginally higher on A and confirmed #1 on
the independent section B (below). The improvement over baseline is large and
robust (lse_c ×5.2, av_offset 0 vs +2).

---

## 7. Multi-Segment Validation (independent 20 s section B, top-3)

| Offset | ms | sync_conf | lse_c | av_off |
|-------:|---:|----------:|------:|-------:|
| −4 | −160 | 0.3647 | 0.2076 | 0 |
| **−3** | **−120** | **0.3844** | **0.2297** | **0** |
| −2 |  −80 | 0.2929 | 0.1523 | +1 |
|  0 |    0 | 0.1653 | 0.0359 | +2 |

−3 wins again on the independent section (lse_c 0.230, av_off 0). −4 is a close,
consistent second. The ranking is stable across two different Vietnamese speech
sections.

---

## 8. 55-Second Validation (offset 0 vs −3)

| metric | offset 0 (baseline) | offset −3 (optimized) |
|--------|--------------------:|----------------------:|
| whole sync_confidence | 0.2034 | **0.4180** |
| whole lse_c | 0.0430 | **0.2517** |
| whole av_offset | +2 | **0** |
| 0–10 av_off | +2 | 0 |
| 10–20 av_off | +2 | 0 |
| 20–30 av_off | +2 | 0 |
| 30–40 av_off | +2 | 0 |
| 40–50 av_off | +2 | 0 |
| render fps | 28.6 | 28.7 |
| video/audio duration | 55.22 / 55.22 s | 55.22 / 55.22 s (unchanged) |

`av_offset` is 0 in **every** segment after the fix; the +2 lead is removed
everywhere. Duration unchanged (offset never touches the mux). **PASS.**

---

## 9. 90-Second Validation (30 s / 60 s WOLA boundaries)

| segment | offset 0 av_off | offset −3 av_off | offset −3 lse_c |
|---------|----------------:|-----------------:|----------------:|
| WHOLE | +2 | **0** | 0.2094 |
| 0–20 | +2 | 0 | 0.1737 |
| 20–40 (spans 30 s boundary) | +2 | **0** | 0.1524 |
| 40–60 (spans toward 60 s) | +2 | **0** | 0.1877 |
| 60–71 (after 60 s boundary) | +2 | **0** | 0.2040 |

No timing discontinuity at the 30 s or 60 s WOLA boundaries — `av_offset` stays
0 across them. **PASS.**

---

## 10. 167.6-Second Validation (early/mid/late, drift)

| segment | offset 0 av_off | offset −3 av_off | offset −3 lse_c |
|---------|----------------:|-----------------:|----------------:|
| WHOLE | +2 | **0** | 0.2489 |
| 5–15 | +2 | 0 | 0.1927 |
| 25–35 | — | 0 | 0.2954 |
| 55–65 | +2 | 0 | 0.1257 |
| 85–95 | — | 0 | 0.2553 |
| 115–125 | +2 | 0 | 0.1484 |
| 145–155 | +2 | 0 | 0.2582 |

Whole: `sync_confidence=0.4162, lse_c=0.2489, av_offset=0`, 4191 frames,
167.66 s, 29.4 fps. Mouth motion is aligned (av_off 0) from 5 s to 155 s.
**PASS.**

---

## 11. Drift Analysis

**CONSTANT OFFSET — no temporal drift.**

- Baseline (offset 0): `av_offset = +2` at 5–15 s, 55–65 s, 115–125 s, 145–155 s
  (constant +2 across the full 167.6 s).
- Optimized (offset −3): `av_offset = 0` at 5–15, 25–35, 55–65, 85–95, 115–125,
  145–155 (constant 0 across the full 167.6 s).

The lag does NOT grow with duration → the audio/video/feature rates are correctly
matched; a single global offset is the correct and sufficient fix. If drift
existed (e.g. 0 at 10 s, −3 at 150 s) a global offset would be wrong — that is NOT
observed.

---

## 12. WOLA Boundary Analysis

Stage 2's 30 s windowed-overlap-and-add does **not** introduce a temporal
alignment artifact at boundaries:
- 90 s render, segment 20–40 (contains the 30 s boundary) and 40–71 (contains the
  60 s boundary): `av_offset = 0` both sides, lse_c smooth (0.152 / 0.188 / 0.204).
- 167.6 s: `av_offset = 0` in segments straddling 30 s (25–35), 60 s (55–65),
  90 s (85–95), 120 s (115–125), 150 s (145–155).

**WOLA is left untouched** (per rule: no rewrite without evidence of degradation;
none found).

---

## 13. Articulation Assessment

After timing is corrected (av_offset 0), categorize remaining issues:
- **TIMING: resolved.** `av_offset` 0 across all durations/segments.
- **ARTICULATION: the remaining gap.** `lse_c ≈ 0.20–0.30` (whole 0.25) is
  moderate — there is real sync but the mouth shape does not perfectly match every
  phoneme. This is a MuseTalk 1.5 + whisper-tiny fidelity limit, NOT a timing
  problem. Observed by visual inspection: vowels open/close broadly correctly;
  fine consonant distinctions (m/b/p closures, rounded o/ô/u vs wide i/ê) are
  approximate.
- **VISUAL QUALITY: separate.** 1080p composite is clean; optional GFPGAN (still
  not installed) would sharpen the pasted face. Not a timing issue.

Dominant remaining issue: **ARTICULATION** (model fidelity), not timing.

---

## 14. Files Modified

| File | Function | Change | Reason |
|------|----------|--------|--------|
| `generate_video_from_script.py` | `render_video` | Added `audio_feature_offset_frames` param; `start=i+offset` in feature chunking; offset log line | Stage 3 configurable temporal offset |
| `generate_video_from_script.py` | `main` / argparse | Added `--audio-feature-offset-frames` CLI (default 0) | Expose the offset; default 0 preserves Stage 2 |

`avatars/musetalk/whisper/audio2feature.py` is **unchanged in Stage 3** (its diff
is the Stage 2 WOLA fix). Realtime path (`avatars/audio_features/whisper.py`,
`base_asr.py`) is **untouched** — the offset is offline-only. No model/weight,
WOLA, FPS, audio-mux, or CUDA-graph changes.

Diagnostic/eval files added (untracked, not production): `sweep_musetalk_audio_offset.py`,
`score_segments.py`, `script_20s.txt`, `script_20s_b.txt`.

---

## 15. Performance Impact

| metric | offset 0 | offset −3 |
|--------|---------:|----------:|
| 55 s render fps | 28.6 | 28.7 |
| 90 s render fps | 29.2 | 29.2 |
| 167.6 s render fps | 29.4 | 29.4 |
| feature extraction | unchanged | unchanged |

**Negligible.** The offset is one integer add to a feature index per frame; no
extra GPU work. Render FPS is identical within noise. CUDA Graph remains enabled
and correct on all renders.

---

## 16. Regression Results

- 10 s render (offset −3): coverage OK, render completes, no freeze. **PASS**
- 31 s feature coverage: **1550 features** (>1500, no truncation) — Stage 2 WOLA
  intact. **PASS**
- 55 s (offset −3): av_off 0 all segments, no freeze, duration unchanged. **PASS**
- 90 s (offset −3): av_off 0 across 30/60 s boundaries. **PASS**
- 167.6 s (offset −3): av_off 0 from 5 s to 155 s. **PASS**
- offset = 0 reproduces Stage 2 exactly (`start = i + 0`). **PASS**
- CUDA Graph ON: all Stage 3 renders used the graph, correct. **PASS**
- Realtime: untouched (offset is offline-only). **PASS**

---

## 17. Recommended Stage 4

Only after Stage 3 is accepted:
1. **LEFT/RIGHT context optimization** — now that the center is temporally
   correct, sweep `LIVETALKING_AUDIO_FEAT_LEFT/RIGHT` (and the offline
   `audio_feat_length=[2,2]` which currently uses NO left context) to improve
   articulation. The offline path's future-only window `[center, center+10]` is
   asymmetric vs realtime's `[center-4, center+6]`; aligning them may raise lse_c.
2. **MuseTalk 1.5 verification / model upgrade** — evaluate a newer MuseTalk or
   whisper encoder for better phoneme fidelity (the remaining lse_c ceiling).
3. **GFPGAN face enhancement** — install `models/GFPGANv1.4.pth` for sharper
   mouth/face (visual quality, not timing).
4. **LatentSync comparison** — benchmark the same audio/avatar with LatentSync as
   an articulation reference.

Do NOT implement Stage 4 now.

---

## Success Criteria

- [PASS] Baseline lip-sync quantitatively measured (av_offset +2, lse_c 0.043)
- [PASS] Offset sweep covers −5..+5
- [PASS] Best candidate validated on 2 independent speech regions (A & B)
- [PASS] Best candidate validated on 55 s (av_off 0 all segments)
- [PASS] Best candidate validated on 90 s (no 30/60 s boundary artifact)
- [PASS] Long-video lip motion correct (167.6 s av_off 0, 5–155 s)
- [PASS] No 30/60 s WOLA timing discontinuity
- [PASS] Temporal drift measured — CONSTANT offset, no drift
- [PASS] CUDA Graph remains correct (ON, all renders)
- [PASS] Realtime unaffected (offset is offline-only)
- [PASS] Final audio track timing untouched (duration identical, mux unchanged)
- [PASS] Offset implemented explicitly (`--audio-feature-offset-frames`), not via LEFT/RIGHT

The baseline offset 0 was NOT optimal (av_offset +2). A non-zero offset (−3) is
justified by strong, consistent, segment-level evidence — not forced.