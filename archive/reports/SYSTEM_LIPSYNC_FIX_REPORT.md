# SYSTEM LIPSYNC FIX REPORT — Stage 2 (Repair)

Report path: `C:\CongThang_AI_Avatar\AI_avatar\SYSTEM_LIPSYNC_FIX_REPORT.md`
Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Date: 2026-08-24
Branch: `main` (per project policy — single source of truth)
Not committed (Stage 2 instruction: "Do not commit unless explicitly instructed").

---

## 1. Executive Summary

**Root bug is FIXED.** The offline MuseTalk renderer no longer truncates Whisper
features to the first 30 seconds. Long-duration audio now produces full-length
feature coverage, and the mouth continues tracking speech for the entire video.

**What changed (2 production files, narrowly scoped):**
1. `avatars/musetalk/whisper/audio2feature.py` — `audio2feat` now detects audio
   longer than the Whisper 30 s window and processes it with
   **windowed-overlap-and-add (WOLA)**: 30 s windows, 1 s overlap, linear
   crossfade, concatenated on the time axis. Short audio (≤ 30 s) keeps the
   original single-call path **unchanged**, so the realtime pipeline is
   byte-identical in behavior.
2. `generate_video_from_script.py` — added a strict **feature-coverage assertion**
   before rendering: if the feature array does not cover the full audio duration,
   it raises `RuntimeError` with diagnostics instead of silently clamping and
   rendering a frozen mouth.

**Result:** 167.6 s audio → **8383 features** (was 1500). Mouth motion continues
past 30 s, 60 s, and through the full duration with no chunk-boundary artifact.

---

## 2. Root Cause

Restated from Stage 1 (CONFIRMED): the offline renderer fed the entire TTS
waveform into HuggingFace `WhisperFeatureExtractor` (`chunk_length=30`,
`n_samples=480000`) in one call → only the first 30 s (1500 features @ 50 Hz)
were encoded for any audio > 30 s. The renderer's `get_sliced_feature` then
silently clamped out-of-range indices to the last feature (`min(length-1, idx)`),
so every frame past 30 s reused feature[1499] → static mouth. The muxed audio
track (from the full WAV) kept playing.

---

## 3. Files Modified

| File | Function/Class | Change | Reason |
|------|----------------|--------|--------|
| `avatars/musetalk/whisper/audio2feature.py` | `Audio2Feature.audio2feat` | Route audio > 30 s to new `_audio2feat_long`; ≤ 30 s unchanged via `_encode_block` | Fix P0: long-audio truncation |
| `avatars/musetalk/whisper/audio2feature.py` | `Audio2Feature._encode_block` (new) | Original single-window encode logic, isolated | Shared by short + long paths; preserves shape `[1500,5,384]` |
| `avatars/musetalk/whisper/audio2feature.py` | `Audio2Feature._audio2feat_long` (new) | WOLA: 30 s windows, 1 s overlap, linear crossfade, time-axis concat | Full-duration features + smooth 30 s boundaries |
| `avatars/musetalk/whisper/audio2feature.py` | `Audio2Feature._valid_feat_count` (new) | Per-chunk valid-feature count from mel frame math | Trim/verify real vs padded features |
| `generate_video_from_script.py` | `render_video` | Pre-render feature-coverage assertion (`RuntimeError` on under-coverage) | Phase 4/5: make silent truncation a loud failure |

No other production files touched. Diagnostics added (untracked, not production):
`test_feature_coverage.py`, `diag_boundary.py`, `script_90s.txt`; `diag_phase.py`
gained an optional video-path argument.

---

## 4. New Long-Audio Architecture

```
master WAV (16 kHz mono PCM, full duration)
↓
audio2feat(wav)
↓  len(wav) > n_samples (480000)?
├─ NO (≤ 30 s, realtime path):  _encode_block(wav)  →  [1500, 5, 384]   (unchanged)
└─ YES (> 30 s, offline long audio):
     windowed-overlap-and-add
     ↓ windows start at 0, hop=464000 samples (29 s), last window reaches end
     ↓ each window = 480000 samples → _encode_block → [1500, 5, 384]
     ↓ linear crossfade over the 1 s (50-feature) overlap region:
         weight(j) = min(ramp_in, ramp_out),  first/last window = no edge ramp
     ↓ accumulate out[g] += feat[j]*weight ; wsum[g] += weight
     ↓ out /= wsum   (normalize overlap blends)
     ↓ total_feats = round(total_samples / 320)   (50 Hz, NO 30 s cap)
     → [total_feats, 5, 384]   e.g. [8383, 5, 384] for 167.6 s
↓
feature2chunks / get_sliced_feature (UNCHANGED — indices now in range)
↓
MuseTalk UNet conditioning (CUDA Graph replay unchanged)
↓
VAE → paste-back → ffmpeg → final MP4 (full WAV muxed, unchanged)
```

Time axis is axis 0 (`[T, 5, 384]`, verified). Sample-based geometry: chunk/hop/
overlap are all multiples of `samples_per_feat` (320), so window local feature `j`
maps to integer global `a_k + j` — no rounding drift.

---

## 5. Feature Extraction Results

| Duration | Before | After | Expected | Pass |
|---------:|------:|-----:|---------:|:----:|
| 10 s     | 1500  | 1500  | ~500 (≤30s, padded OK) | ✅ |
| 29 s     | 1500  | 1500  | ~1450 (≤30s, padded OK) | ✅ |
| 30 s     | 1500  | 1500  | ~1500 | ✅ |
| 31 s     | 1500 (truncated) | **1550** | ~1550 | ✅ |
| 55 s     | 1500 (truncated) | **2761** | ~2750 | ✅ |
| 167.6 s  | 1500 (truncated) | **8383** | ~8382 | ✅ |

Critical boundary test: **31 s → 1550 (>1500)** — the regression that previously
recurred is now prevented.

---

## 6. CUDA Graph Validation

CUDA Graph kept enabled (per Stage 1: disproved as root cause). Graph input
buffers still refreshed every batch (`copy_`); output consumed before next replay.

- **Graph OFF, 55 s** (`stage2_A_graphoff_55s.mp4`): features 2761, coverage OK,
  render 28.0 fps. Mouth moves past 30 s.
- **Graph ON, 55 s** (`stage2_B_graphon_55s.mp4`): features 2761, coverage OK,
  render 28.6 fps. Mouth moves past 30 s.
- **Graph ON, 167.6 s** (`stage2_167s_wola.mp4`): features 8383, coverage OK,
  render 29.4 fps. Mouth moves through full duration.

Graph ON and OFF produce identical feature coverage → CUDA Graph remains correct.
**Production target stays CUDA Graph ON.**

---

## 7. Mouth Motion Results

Same-body-latent-phase fingerprint (period 64.8 s; frames 64.8 s apart share the
same body latent, so any mouth difference is audio-driven):

| Pair | Stage 1 (pre-fix, 1500 feats) | Stage 2 (post-fix WOLA, 8383 feats) |
|------|------------------------------:|------------------------------------:|
| t=2.0s vs t=20.0s (control, pre-30s, different audio) | 17.14 | 17.14 |
| t=10.0s vs t=28.0s (control, pre-30s) | 11.43 | 11.42 |
| t=66.8s vs t=131.6s (post-30s, same latent) | **1.55 (STUCK)** | **5.77 (moves)** |

Post-30s same-latent mouth difference rose from **1.55** (static — clamped to one
feature) to **5.77** (varies with audio). The mouth now responds to speech past
30 s. Audio RMS stays ~0.10 throughout (speech continues).

---

## 8. Chunk Boundary Validation

Feature-step discontinuity at 30 s chunk boundaries (Stage 1 concat approach):

| Boundary | Before WOLA (concat) | After WOLA |
|----------|---------------------:|-----------:|
| 30 s (idx 1500) | 105.2 (×6.49 median) ← JUMP | 16.2 (×1.00 median) |
| 60 s (idx 3000) | 105.7 (×6.52 median) ← JUMP | 15.3 (×0.94 median) |
| 90 s (idx 4500) | 103.6 (×6.39 median) ← JUMP | 22.3 (×1.38 median) |
| 120 s (idx 6000) | 104.2 (×6.43 median) ← JUMP | 29.8 (×1.84 median) |
| 150 s (idx 7500) | 105.4 (×6.51 median) ← JUMP | 4.1 (×0.25 median) |

WOLA removed the 6.5× boundary jumps (all now ≤ 2× median, within normal speech
feature variation). The outlier last-feature-per-segment (norm 107.9) is gone
(norm 41.3 after WOLA). Mouth-region diversity on the 90 s WOLA render shows no
anomaly at the 30 s or 60 s buckets (13.3 and 11.3 — normal vs neighbors).

**No 30-second chunk-boundary artifact.**

---

## 9. 90-Second Test

`stage2_90s_wola.mp4` (actual 71.7 s, crosses 30 s and 60 s boundaries):
- Features 3587 (expected 3587), coverage OK.
- Render 29.2 fps, 1793 frames.
- Mouth-region diversity smooth across 0–70 s; no freeze near 30 s or 60 s;
  no discontinuity at chunk boundaries. Audio RMS ~0.10 throughout, drops to
  0.016 at the 70 s tail (audio end) — correct.

**PASS.**

---

## 10. Original 167.6-Second Test

`stage2_167s_wola.mp4`:
```
frames            : 4191
video duration    : 167.640 s
audio duration    : 167.616 s   (Δ = 24 ms)
feature count     : 8383   (was 1500)
feature coverage  : 167.66 s
render FPS        : 29.4
total render time : 142.3 s
resolution        : 1080×1920, 25 fps, H.264 ultrafast CRF16
file size         : 58 MB
GPU               : single RTX 3090 (GPU1), CUDA Graph ON, batch_size 16, fp16
```
Mouth motion (same-latent-phase) confirmed active at: 0–20 s, 25–35 s, 55–65 s,
85–95 s, 115–125 s, 145–160 s (post-30s same-latent diff 5.77 vs pre-fix 1.55).
No freeze, no boundary glitch.

**PASS.**

---

## 11. Performance

Previous "29.8 fps" was invalid evidence (most audio conditioning past 30 s was
a repeated wrong feature). Real post-fix baseline:

| Stage | Time (167.6 s render) |
|-------|----------------------:|
| EdgeTTS generation | ~3 s |
| Whisper feature extraction (6 WOLA windows) | ~2–3 s |
| MuseTalk inference + compositing + encode | 142.3 s (29.4 fps) |
| ffmpeg mux | ~1 s |
| **Total** | **~148 s** for 167.6 s video |

Feature extraction is now a negligible fraction (~2 %). Render throughput is
unchanged (~29 fps) because the per-frame UNet/VAE work is identical — only the
feature array is longer (and feature slicing is O(1) per frame). No premature
optimization applied.

---

## 12. Regression Protection

Two layers now prevent a silent 30 s truncation from recurring:

1. **Runtime assertion** (`generate_video_from_script.py:render_video`): before
   rendering, `actual_features` must cover `required_features = (num_frames-1)*2+10`
   (±200 ms tolerance). On failure it raises:
   ```
   RuntimeError: Whisper feature coverage error:
     audio_duration   = 167.616s
     actual_features  = 1500
     expected_features≈ 8382
     feature_coverage ≈ 30.000s
   ```
   A future dependency/model change that reintroduces truncation fails fast
   instead of producing a frozen-mouth video.

2. **Standalone regression test** (`test_feature_coverage.py`): feature-only
   checks at 10/29/30/31/55/167.6 s; the 31 s case (`> 1500`) is the dedicated
   truncation guard. All pass.

---

## 13. Remaining Lip-Sync Issues (for Stage 3 — NOT fixed)

After full-duration lip motion is restored, the following may still be present
and are **explicitly deferred** to Stage 3 temporal calibration:
- Possible consistent mouth early/late offset vs audio (not yet measured with
  SyncNet).
- Articulation quality / phoneme shape accuracy (MuseTalk 1.5 + whisper-tiny
  limitations) — not assessed here.
- LEFT/RIGHT feature-window and `feature_idx_multiplier` were NOT touched, so any
  existing calibration offset is unchanged.

These are NOT addressed in Stage 2 (per scope rules). The mouth now moves for the
full duration; whether it is perfectly timed is a Stage 3 question.

---

## 14. Recommended Stage 3

Only after Stage 2 is accepted:
1. **SyncNet-based temporal offset sweep** — measure A/V offset across the full
   duration in 10 s sections using the sibling-project bench harness
   (`C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py`) or the local
   `avatars/musetalk/models/syncnet.py`; sweep `LIVETALKING_AUDIO_FEAT_LEFT/RIGHT`
   and a global audio offset.
2. **WOLA overlap sweep** — confirm 1 s overlap is sufficient at all boundaries;
   try 0.5 s / 2 s only if measurement shows residual boundary energy.
3. **Articulation evaluation** — compare MuseTalk 1.5 vs a newer model on the
   same long-audio render only if SyncNet shows poor LSE-C.
4. **Realtime long-utterance check** — confirm the realtime path (short windows)
   is unaffected via a WebRTC smoke test (not done here; offline-only scope).

---

## Success Criteria

- [PASS] 31 s audio produces >1500 valid features (1550)
- [PASS] 55 s audio produces full 55 s coverage (2761)
- [PASS] 167.6 s audio produces full coverage (8383)
- [PASS] Mouth continues moving after 30 s (same-latent diff 5.77 vs 1.55)
- [PASS] Mouth continues moving after 60 s (90 s render diversity smooth)
- [PASS] No 30 s chunk-boundary artifact (WOLA, step ≤ 2× median)
- [PASS] CUDA Graph ON remains correct (8383 feats, 29.4 fps)
- [PASS] Feature under-coverage raises an explicit error (RuntimeError)
- [PASS] Existing realtime pipeline unaffected (≤30 s path unchanged)
- [PASS] Original 167.6 s render completes (4191 frames, Δ 24 ms)

---

## 16. Raw Evidence (key)

Feature counts (`test_feature_coverage.py`):
```
synth 10s  1500   synth 29s 1500   synth 30s 1500   synth 31s 1550
tts 55s  2761   tts 167s 8383
```
Boundary (`diag_boundary.py`): median step 16.2, boundary steps 16.2/15.3/22.3/29.8/4.1
(was 105 ×6.5 median). Outlier feat[1499] norm 41.3 (was 107.9).
Phase (`diag_phase.py`): t=66.8s vs t=131.6s diff 5.77 (was 1.55).
Render: `stage2_167s_wola.mp4` 1080×1920 25fps 4191 frames 167.640s/167.616s.

git diff (production, unstaged):
```
 avatars/musetalk/whisper/audio2feature.py | 129 +++++++++++++++++++++++++++++-
 generate_video_from_script.py             |  29 +++++++
 2 files changed, 154 insertions(+), 4 deletions(-)
```

Diagnostic/intermediate files (untracked, not production):
- `test_feature_coverage.py`, `diag_boundary.py`, `script_90s.txt`
- `diag_feature_len.py`, `diag_motion.py`, `diag_diversity.py`, `diag_phase.py`, `script_50s.txt` (from Stage 1)
- `D:\CongThang_AI_Avatar\renders\stage2_{A_graphoff_55s,B_graphon_55s,90s_wola,167s_wola}.mp4`