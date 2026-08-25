# SYSTEM LIPSYNC STAGE 4 REPORT — Audio Context Window Validation

Report path: `C:\CongThang_AI_Avatar\AI_avatar\SYSTEM_LIPSYNC_STAGE4_REPORT.md`
Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Date: 2026-08-24
Branch: `main`. Not committed (per instruction).

Stage 4 adds an `audio_context_left` parameter to `render_video` (and a
`--audio-context-left` CLI flag) that shifts the 10-feature MuseTalk conditioning
window earlier without changing its length (total stays 10 → `[50,384]` unchanged,
`pe`/UNet/CUDA-Graph shapes invariant). `left=0` reproduces the offline future-only
window `[center, center+10)`; `left=4` reproduces the realtime-style `[-4,+6)`;
`left=5` is symmetric `[-5,+5)`. The Stage 3 temporal offset
(`audio_feature_offset_frames=-3`, av_offset 0) is held fixed while the context is
varied, to isolate the articulation effect.

This report documents the **real-render A/B/C validation** that decides whether the
new context setting improves actual mouth articulation without breaking Stage 3
timing.

Evaluator: SyncNet scorer `C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py`
(ByteDance StableSyncNet, `models/syncnet/latentsync/latentsync_syncnet.pt`,
face_crop preprocess, 25 FPS, 16-frame windows, stride 2, batch 32, GPU1).
Metrics: `sync_confidence`=S(0) (higher better), `lse_c`=S(0)-mean(S(±10)) (higher
better), `lse_d_min`=1-max S(d) (lower better), `av_offset_frames`=argmax_d S(d)
(0 = aligned; + = mouth leads audio).

Mouth-quality proxies: `diag_diversity.py` (per-5 s mouth-shape temporal std —
higher = more lip movement / shape variety) and `diag_motion.py` (per-5 s mean
abs frame diff in the mouth ROI). Both use the avatar `coords.pkl` mouth ROI.

---

# Real Render A/B Validation

## Controlled inputs (identical across A/B/C)

- Avatar: `fullbody_30_7_25fps` (same as Stage 2/3).
- Script: `script_artic.txt` — purpose-built Vietnamese articulation sample
  ("Ba, bá, bà. Mẹ, má, mù. Bi, bô, bù. Phở, pha, phố. Mi, mo, mu. … Xin chào
  quý khách, hôm nay tôi xin giới thiệu một sản phẩm mới…"). Covers bilabials
  (m/b/p), open vowels (a/ă/â), rounded vowels (o/ô/u), wide/front vowels
  (i/e/ê), plus a natural sentence.
- TTS: EdgeTTS `vi-VN-HoaiMyNeural` (Stage 4 does NOT touch ElevenLabs).
- **Audio is byte-identical across A/B/C**: one master WAV (`master_artic.wav`,
  22.12 s, 16 kHz) is rendered for all three. Verified by AAC stream MD5 =
  `18503c4a201e344f71db97fd3b1856c4` for all three MP4s.
- 25 FPS, batch 16, CUDA Graph ON, single GPU (GPU1), MuseTalk v1.5 + whisper-tiny,
  1080p composite, libx264 ultrafast CRF16. No GFPGAN. No model/Whisper/WOLA/codec
  changes vs Stage 3.

A and B were rendered by the existing `sweep_musetalk_context.py` harness (one
master WAV per run); C was rendered by a one-off driver calling the production
`render_video` with the same master WAV. All three are promoted to
`D:\CongThang_AI_Avatar\renders\stage4_*.mp4`.

## SyncNet + articulation results (22.12 s articulation clip)

| Version | Context Left | Offset | Sync Confidence | LSE-C | AV Offset | Visual Articulation (mouth diversity / motion) |
| ------- | -----------: | -----: | --------------: | ----: | --------: | ---------------------------------------------- |
| A       |            0 |     -3 |          0.5140 | 0.2613|         0 | div 11.4/17.6/12.1/13.5/9.5  mot 7.3/8.9/8.5/8.2/7.2 |
| B       |            4 |     -3 |          0.4192 | 0.1619|        -1 | div 11.4/17.6/12.1/13.6/9.6  mot 7.3/8.7/8.4/8.4/7.5 |
| C       |            5 |     -3 |          0.3765 | 0.1222|        -1 | div 11.4/17.6/12.0/13.6/9.6  (motion within noise of A/B) |

(diversity/motion values are per-5 s buckets 0/5/10/15/20 s; audio RMS identical
across A/B/C by construction.)

### Findings

1. **SyncNet degrades monotonically with left context:** A 0.514 > B 0.419 > C
   0.377. `lse_c` likewise: 0.261 > 0.162 > 0.122.
2. **Timing shifts negative (mouth lags) as left context grows:** A av_off=0,
   B=-1, C=-1. Mechanism: the -3 offset was calibrated for the future-only
   window's effective center; adding left context moves the effective center
   earlier, so the same -3 offset over-corrects (mouth now reacts to
   already-passed audio). This is the NOTE in the Stage 4 code comment
   (`left+1 → center earlier by ~20 ms → offset must increase ~0.5 frame`).
3. **Mouth articulation is unchanged across contexts.** `diag_diversity` mouth-
   shape diversity is identical within noise (A vs B vs C differ <0.1 on values
   of 9–17, i.e. <1 %). `diag_motion` mouth motion is identical within noise
   (A vs B differ ~2 %; C equivalent). No "static mouth while audio active" or
   "mouth frozen" flags in any version. The 10-feature window *content* differs
   by context, but MuseTalk 1.5 + whisper-tiny produces the same mouth-motion
   envelope regardless of which 200 ms slice conditions it.
4. **Step 8 offset recalibration was NOT performed.** Step 8 applies only "if
   Version B improves articulation but timing shifts." B does **not** improve
   articulation (diversity/motion identical to A), so the precondition is false.
   No ctx4 offset sweep was run.

## Bilabial closure

```
A: baseline (ctx0) — bilabials m/b/p served by the future-only window; sync_conf 0.514, av_off 0.
B: ctx4 — no measurable closure improvement (diversity identical); sync_conf drops to 0.419, av_off -1.
winner: A
```

## Vowel differentiation

```
A: mouth-shape diversity 11.4/17.6/12.1/13.5/9.5 across the articulation script.
B: 11.4/17.6/12.1/13.6/9.6 — within noise of A; no added o/ô/u vs i/e/ê distinction.
winner: A (tie on diversity, but A wins on sync/timing)
```

## Overall naturalness

```
A: correct timing (av_off 0), highest sync confidence, motion continuous.
B: same motion magnitude but mistimed (av_off -1) and lower sync confidence.
winner: A
```

## Selected production configuration

```
audio_context_left = 0
audio_feature_offset_frames = -3
```

Rationale: context-left 0 (the existing offline future-only window) is the
unanimous winner — highest SyncNet, correct timing (av_offset 0), and identical
articulation to the alternatives. The realtime-style symmetric window does not
transfer to the offline path because the Stage 3 offset was calibrated against
the future-only window's effective center; switching contexts double-corrects the
timing without buying any articulation gain. The Stage 4 parameter is retained in
the code (default 0) as a configurable knob, but the production default stays 0.

## Confidence

```
HIGH
```

Three contexts tested on a purpose-built articulation script with byte-identical
audio, scored by SyncNet and two independent mouth-ROI diagnostics; the ranking
(A > B > C) is monotonic and consistent across sync, timing, and articulation
measures. The winner reproduces Stage 3 exactly and re-validates clean on 55 s
and 90 s.

---

# Long Validation (winning config: ctx0 / off-3, new refactored slice path)

The Stage 4 edit replaced `audio_processor.feature2chunks` with an inline slice
(`center=(i+off)*2`, `start_f=center-left`, window `[start_f, start_f+10)`). For
`left=0` this is mathematically identical to Stage 3's `get_sliced_feature`
(`left_idx=center`, `right_idx=center+10`). The long renders below confirm the
refactor introduces **no regression** vs Stage 3.

## 55-second validation (`script_50s.txt`, 55.22 s, 1380 frames, WOLA 2 windows)

| segment | conf | lse_c | lse_d | av_off |
|---------|-----:|------:|------:|-------:|
| WHOLE | 0.4176 | 0.2505 | 0.5824 | 0 |
| 0–10  | 0.3652 | 0.2249 | 0.6348 | 0 |
| 10–20 | 0.3345 | 0.1793 | 0.6655 | 0 |
| 20–30 | 0.3882 | 0.2048 | 0.6118 | 0 |
| 30–40 | 0.4629 | 0.3020 | 0.5371 | 0 |
| 40–50 | 0.3280 | 0.1803 | 0.6720 | 0 |

- `av_offset` = 0 in **every** segment. Matches Stage 3 55 s (whole 0.418/0.252/0).
- Mouth motion (diag_motion) stays 7.0–10.7 across 0–50 s (30 s: 8.66, 35 s: 10.42,
  40 s: 8.98, 50 s: 8.48) — **no freeze past 30 s**. No WOLA boundary artifact.
- Feature coverage 2761 features (~55.22 s, uncovered 0) — Stage 2 WOLA intact.
- CUDA Graph ON, 28.3 fps. **PASS.**

## 90-second validation (`script_90s.txt`, 71.73 s, 1793 frames, WOLA 3 windows)

| segment | conf | lse_c | lse_d | av_off |
|---------|-----:|------:|------:|-------:|
| WHOLE | 0.3837 | 0.2131 | 0.6162 | 0 |
| 0–20  | 0.3370 | 0.1756 | 0.6630 | 0 |
| 20–40 (spans 30 s) | 0.3206 | 0.1530 | 0.6794 | 0 |
| 25–35 (straddles 30 s) | 0.4270 | 0.2880 | 0.5730 | 0 |
| 40–60 (spans toward 60 s) | 0.3664 | 0.1886 | 0.6336 | 0 |
| 55–65 (straddles 60 s) | 0.2986 | 0.0969 | 0.7014 | 0 |
| 60–71 (after 60 s) | 0.3362 | 0.2033 | 0.6638 | 0 |

- `av_offset` = 0 across the 30 s and 60 s WOLA boundaries — no timing jump.
- Matches Stage 3 90 s (whole lse_c 0.209, av_off 0 across all segments).
- Feature coverage 3587 features (~71.74 s, uncovered 0) — no long-audio regression.
- CUDA Graph ON, 28.8 fps. **PASS.**

## 167.6-second validation

NOT RUN. 55 s and 90 s/71 s are clean and match Stage 3 timing exactly; ctx0 is
mathematically identical to the Stage 3 slice path (verified by dry-run probe and
by the 55 s / 90 s reproductions). No suspicious timing, no WOLA behavior change,
no late-context index difference. Per Step 13, the full 167.6 s render is deferred
unless a final-production confirmation is later desired (Stage 3 already validated
167.6 s with this same configuration).

---

# Files

- Modified (Stage 3+4, unstaged): `generate_video_from_script.py` (added
  `audio_context_left` param + `--audio-context-left` CLI + inline context-aware
  slice), `avatars/musetalk/whisper/audio2feature.py` (Stage 2 WOLA, unchanged
  in Stage 4).
- New renders: `D:\CongThang_AI_Avatar\renders\stage4_ctx0_offset-3.mp4` (A),
  `stage4_ctx4_offset-3.mp4` (B), `stage4_ctx5_offset-3.mp4` (C),
  `stage4_55s_ctx0_off-3.mp4`, `stage4_90s_ctx0_off-3.mp4`, plus SyncNet JSONs.
- Diagnostics reused (unmodified): `diag_motion.py`, `diag_diversity.py`,
  `score_segments.py`, `sweep_musetalk_context.py`.
- ElevenLabs: NOT touched (Stage 4 tests MuseTalk lip-sync only; TTS source fixed).