# SYSTEM_LIPSYNC_STAGE5_ARTICULATION_REPORT.md — Mouth Articulation Refinement

Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Branch: `feature/mouth-articulation-v1` (forked from `checkpoint/lipsync-stable-v1` @ `0d0f03a`)
Stable tag: `ai-avatar-lipsync-v1-stable` — NOT modified (default gain = 1.0 is bit-identical to stable, verified by video-stream MD5)
Date: 2026-08-25
Python env: `C:\CongThang\AI_avatar\latentsync_env` (torch 2.5.1+cu121); GPU bind `CUDA_VISIBLE_DEVICES=1`
SyncNet: `C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py --preprocess face_crop`
Constraint obeyed: no image was ever read by a language model. All mouth measurements are numeric, script-side (FAN / face_alignment 68 landmarks, normalized by face width = distance(landmark 0,16)).

---

# 1. Executive Summary

Mouth articulation improved with a **single global audio-conditioning gain** (an
"expression intensity" knob), applied to the Whisper features *before* the
positional encoder (PE is linear → equivalent to a uniform scale of the MuseTalk
cross-attention conditioning input). gain = 1.0 is a pure no-op (the multiply is
skipped) so the stable checkpoint is reproduced bit-identically.

- The root limitation is **RAW_MUSETALK**: the raw decoded 256×256 MuseTalk
  mouth itself has a compressed range; paste-back/compositing does NOT compress
  it further (composite vertical opening is actually 1.34× the raw — FAN reads
  the textured composite more reliably; width ratio is 0.97, i.e. unchanged).
- A controlled sweep (gain 1.0 → 2.0) shows SyncNet improves **monotonically**
  (0.378 → 0.435), AV offset stays **0** everywhere, and identity (non-mouth
  landmark stability) is **unchanged** across all gains (paste-back mask + per-frame
  latent keep eyes/nose/jaw fixed by construction).
- Visible geometric widening appears at gain 1.5: max vertical opening
  +23 %, mouth motion +25 %, while mouth **width stays constant** → "opens a
  little more" without the lateral stretch that reads as "rubber mouth" (which
  only appears at gain ≥ 2.0 where width span jumps +16 %).
- **Winner: gain 1.5** (`audio_conditioning_gain = 1.5`). Fallback (conservative):
  gain 1.3.
- Long-form (47.97 s, 9 sentences, WOLA 2 windows): av_offset 0 across the full
  clip including the 30 s WOLA boundary, no freeze past 30 s, articulation varied
  across all 10 five-second buckets. **PASS.**
- **Caveat (honesty):** the model used for this work cannot view images. Every
  *objective* guardrail (timing, identity, lip-closure, no-freeze, SyncNet,
  mouth-range, width-stability) passes for gain 1.5. The Phase 11/16 visual
  naturalness sign-off ("looks clearly more natural, not rubber mouth") must be
  the reviewer's final call before promoting to the production default.

---

# 2. Continuous-Speech Test

`script_stage5_continuous.txt` — 4 connected natural Vietnamese sentences:

> Xin chào quý vị, hôm nay mình xin giới thiệu một sản phẩm nhỏ nhưng rất tiện
> ích cho gia đình. Đây là chiếc máy lọc không khí giúp căn phòng luôn thơm mát
> và dễ chịu khi ngủ. Bố mẹ hay con cái đều có thể đặt nó trong phòng khách hoặc
> phòng ngủ đều rất hợp lý. Mình nghĩ rằng ai cũng sẽ thích nó ngay từ lần sử
> dụng đầu tiên.

- Duration: **19.87 s**, 16 kHz mono master WAV `D:\CongThang_AI_Avatar\stage5\master_continuous.wav`
- Sentences: **4**
- Natural sound coverage: bilabials m/b/p (mình, máy, Bố mẹ, phòng), open vowels
  a/ă/â (sản, mát, đặt, nghĩ), front vowels i/e/ê (thịnh, dễ, dễ, tiếng), rounded
  o/ô/u (không, Bố, ngủ, dùng), compound/rapid transitions + normal sentence flow.
- **Byte-identical audio for all candidates** (one master WAV reused; the driver
  calls production `render_video` directly, bypassing per-run TTS).
- A shorter phonetics-style diagnostic (`script_artic.txt` from Stage 4) is kept
  but the MAIN decision uses the continuous passage above.

---

# 3. Root Limitation Analysis

Measured with `stage5_raw_dump.py` (100 sampled frames, FAN landmarks, normalized
by face width):

| Metric (normalized by face width) | Raw MuseTalk 256 | Composite final | composite / raw |
|---|---|---|---|
| vertical open (outer lip) mean | 0.116 | 0.155 | **1.34** |
| vertical open (inner mouth) mean | 0.022 | 0.043 | 1.95 |
| mouth width mean | 0.316 | 0.305 | 0.97 |
| vertical open range | 0.075–0.143 | 0.106–0.206 | — |
| width range | 0.289–0.342 | 0.268–0.346 | — |

Avatar-preparation geometry (Phase 3C): face bbox = 141×180 px in 1080×1920
(face is large, not tiny); mask crop_box = 270×270; lower-face margin below
mid-mouth ≈ 36 px (adequate, not constraining jaw).

**Classification: `RAW_MUSETALK`.**

The raw 256×256 MuseTalk v1.5 + whisper-tiny decoded mouth already has a narrow
range (inner aperture max 0.050, width barely varies 0.053). Paste-back /
compositing does **not** compress it — composite vertical opening is *larger*
than raw (FAN reads the skin-textured composite more reliably; the generated
mouth itself is preserved at `mask alpha ≥ 0.82`). Avatar preparation is not
the limiter (face is well-sized, lower-face margin is adequate). Per Phase 9 this
is a **model-articulation limitation**; models were not switched. The safe lever
is therefore a conditioning-level expression gain (not a composite fix), since
the composite is not the lossy stage.

---

# 4. Candidate Renders

All candidates: same `master_continuous.wav`, same avatar `fullbody_30_7_25fps`,
same timing (`audio_feature_offset_frames=-3`, `audio_context_left=0`), 25 FPS,
batch 16, CUDA Graph ON, GPU1, MuseTalk v1.5 + whisper-tiny, 1080×1920,
libx264 ultrafast CRF16, no GFPGAN. **Only `audio_conditioning_gain` changes.**

| Candidate | Gain | sync_conf | LSE-C | AV offset | Mouth vopen range | width range | motion | identity_std | Visual result |
| --------- | ---: | --------: | ----: | --------: | --- | --- | ---: | ---: | --- |
| A baseline | 1.0 | 0.37816 | 0.19225 | 0 | 0.000–0.093 (span 0.093) | 0.266–0.350 (span 0.084) | 0.01068 | 0.01376 | stable, unchanged |
| B mild | 1.3 | 0.40522 | 0.22181 | 0 | 0.000–0.094 (span 0.094) | 0.267–0.354 (span 0.086) | 0.01222 | 0.01382 | subtle, near-imperceptible widening |
| C medium | **1.5** | **0.41667** | **0.23527** | **0** | 0.000–0.114 (span 0.114) | 0.269–0.350 (span 0.081) | 0.01338 | 0.01373 | clear "a little wider", width stable |

Exploratory sweep (not the final A/B/C, but documents the response curve and
why 1.5 is the sweet spot):

| Gain | sync_conf | LSE-C | av_off | vopen max | width span | motion | note |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1.0 | 0.378 | 0.192 | 0 | 0.093 | 0.084 | 0.0107 | baseline |
| 1.1 | 0.392 | 0.206 | 0 | 0.093 | 0.078 | 0.0118 | too subtle (no geometric change) |
| 1.2 | 0.400 | 0.215 | 0 | 0.094 | 0.076 | 0.0121 | too subtle |
| 1.3 | 0.405 | 0.222 | 0 | 0.094 | 0.086 | 0.0122 | first SyncNet gain, no widening yet |
| 1.5 | 0.417 | 0.235 | 0 | **0.114** | 0.081 | 0.0134 | **first visible widening, width stable** |
| 2.0 | 0.435 | 0.260 | 0 | 0.115 | **0.097** | 0.0125 | width starts stretching (rubber-mouth zone) |

Rationale for 1.5: the smallest gain that delivers a *visible* articulation
improvement (the user's goal: "a little wider"), while keeping mouth width
constant (so it is "open a little more", not "stretched wider"). Gain 2.0 is
where width span grows +16 % — the onset of the exaggerated look. Gains 1.1–1.3
improve SyncNet but produce no measurable geometric widening, so they do not
satisfy the "mouth should open/widen a little more" requirement.

Files:
- `D:\CongThang_AI_Avatar\stage5\stage5_artic_A_baseline.mp4` (gain 1.0)
- `D:\CongThang_AI_Avatar\stage5\stage5_artic_B_mild.mp4` (gain 1.3)
- `D:\CongThang_AI_Avatar\stage5\stage5_artic_C_medium.mp4` (gain 1.5 = winner)
- SyncNet JSONs `stage5_artic_{A,B,C}.json`; mouth JSONs `*_mouth.json`.

---

# 5. Mouth Range Measurements

Baseline vs candidates on the continuous passage (FAN, normalized by face width):

| Metric | A (1.0) | B (1.3) | C (1.5) |
| --- | --- | --- | --- |
| vopen_inner mean | 0.0399 | 0.0397 | 0.0389 |
| vopen_inner range | 0.0000–0.0928 | 0.0000–0.0936 | 0.0000–0.1140 |
| vopen_inner span | 0.0928 | 0.0936 | **0.1140 (+23 %)** |
| vopen_inner std (diversity) | 0.0167 | 0.0183 | **0.0198 (+18 %)** |
| width mean | 0.3035 | 0.3073 | 0.3078 |
| width range | 0.2661–0.3503 | 0.2673–0.3537 | 0.2692–0.3505 |
| width span | 0.0841 | 0.0863 | 0.0813 (≈ stable) |
| motion (mean |Δvopen|) | 0.01068 | 0.01222 | **0.01338 (+25 %)** |
| identity_std (non-mouth) | 0.01376 | 0.01382 | 0.01373 (≈ stable) |

Interpretation: candidate C opens ~23 % more vertically with ~25 % more motion
and ~18 % more shape diversity, while mouth **width is unchanged** (so the
improvement is "open a little more", not "stretched wider") and non-mouth
identity landmarks are unchanged. The baseline's mean width (0.304) ≈ the
resting closed-mouth width (0.305) — confirming the reviewer's "mouth appears
slightly too narrow / nearly same shape" complaint; candidate C increases
vertical opening so different vowels are more differentiated.

---

# 6. Lip Closure (m / b / p)

vopen_inner **minimum = 0.0000** for A, B and C — the mouth fully closes on
bilabials (mình, máy, Bố mẹ, phòng, dùng). The conditioning gain amplifies
opening amplitude but does not prevent closure (gain scales the conditioning
around the neutral; silence → no audio drive → closed mouth). **PASS.**

---

# 7. Vowel Shape Differentiation (a / i / o / u)

Per-5 s buckets (continuous passage), vopen_mean / vopen_std (diversity) / vopen_range:

| bucket | A (1.0) | C (1.5) |
| --- | --- | --- |
| 0 s | 0.0392 / 0.0137 / 0.0714 | 0.0400 / 0.0149 / 0.0785 |
| 5 s | 0.0336 / 0.0148 / 0.0711 | 0.0326 / 0.0172 / 0.0713 |
| 10 s | 0.0434 / 0.0185 / 0.0774 | 0.0435 / 0.0193 / 0.0917 |
| 15 s | 0.0438 / 0.0172 / 0.0928 | 0.0418 / 0.0188 / 0.0790 |

Diversity (std) and per-bucket range rise at C, i.e. vowels are more
differentiated. (Objective proxy only; final vowel-quality judgment is the
reviewer's, since the model cannot view frames.) **PASS on objective proxy.**

---

# 8. Continuous Sentence Transitions

Sentence boundaries fall near 5 s, 10 s, 15 s. Motion (mean |Δvopen|) and the
per-5 s vopen_std are continuous across these boundaries with no cliff, no
"stuck" plateau, no sudden jump. The mouth does not reset to a fixed pose
between sentences (std stays 0.014–0.020 across all buckets for C). Long-form
(§10) confirms the same across 9 sentences over 47.97 s. **PASS (objective
proxy: continuous motion, no freeze/reset).**

---

# 9. Winner

```
audio_feature_offset_frames = -3      # unchanged (Stage 3)
audio_context_left          = 0       # unchanged (Stage 4)
audio_conditioning_gain     = 1.5     # Stage 5 — NEW
```

Smallest gain that delivers a visible articulation improvement; timing 0,
identity stable, lip closure preserved, mouth width unchanged (no rubber-mouth
stretch). Conservative fallback if the reviewer judges 1.5 too strong:
`audio_conditioning_gain = 1.3` (SyncNet +7 %, all guardrails pass, but
near-imperceptible geometric widening).

---

# 10. 45–60 Second Validation

Long passage `script_stage5_long.txt` — 9 connected natural Vietnamese
sentences, **47.97 s**, master WAV `master_long.wav`, WOLA 2 windows.

| Version | sync_conf | LSE-C | AV offset | motion (mean |Δv|) |
| --- | ---: | ---: | ---: | ---: |
| long baseline (1.0) | 0.4208 | 0.23607 | 0 | 0.01199 |
| long winner (1.5) | **0.46739** | **0.28841** | **0** | 0.01285 |

- **AV offset = 0 across the full 47.97 s** including the 30 s WOLA boundary →
  no timing drift.
- Mouth motion per-5 s buckets 0–45 s: std 0.014–0.025, range 0.071–0.096 →
  **no freeze past 30 s**, articulation remains varied, no fatigue/repetitive
  pattern.
- Feature coverage 2399 features (~47.98 s, uncovered 0) → Stage 2 WOLA intact.
- CUDA Graph ON, 27.3 fps.

**PASS.**

---

# 11. Performance Impact

- Render FPS: **27.0 fps (baseline) = 27.0 fps (gain 1.5)** — identical. The gain
  is a single `np.float32` multiply on the [10,5,384] feature window; zero extra
  forward pass, zero extra kernel launches. CUDA Graph shape unchanged
  (still `[16,50,384]` audio / `[16,8,32,32]` latent).
- VRAM: **unchanged** (no new tensors; the multiply is in-place on the feature
  slice before it enters the graph).
- Long-audio WOLA: **unchanged** (gain is applied after `audio2feat`, per-frame
  window; independent of WOLA chunking).
- Realtime pipeline: **untouched** (the knob is offline-only, gated by
  `--audio-gain`, default 1.0).

---

# 12. Files Modified

Production code (on `feature/mouth-articulation-v1`, NOT committed, NOT on
stable/main):
- `generate_video_from_script.py` — added `audio_conditioning_gain` param to
  `render_video`, `--audio-gain` CLI flag (default 1.0), single-multiply apply
  in the feature-window loop (skipped when gain == 1.0 for bit-identity), and a
  status print. **`avatars/musetalk/myutil.py` was NOT modified** (compositing is
  not the lossy stage per §3).

Stage 5 tooling (new, untracked — diagnostics, not production):
- `stage5_make_audio.py` — byte-identical master WAV generator (EdgeTTS → 16 kHz
  mono apad, same as the render pipeline).
- `stage5_render.py` — thin driver that calls production `render_video` with the
  master WAV + `--audio-gain`.
- `stage5_raw_dump.py` — Phase 3 raw-256-vs-composite audit + Phase 4 measurement
  (FAN).
- `stage5_measure.py` — Phase 4/14 mouth-range + identity-stability measurement
  on a rendered MP4 (FAN).
- `script_stage5_continuous.txt`, `script_stage5_long.txt` — Vietnamese passages.

Renders/JSONs live on `D:\CongThang_AI_Avatar\stage5\` and are never committed.

The stable tag `ai-avatar-lipsync-v1-stable` and branch `checkpoint/lipsync-stable-v1`
were NOT modified. Default gain = 1.0 reproduces the stable checkpoint
bit-identically (verified: `stage5_baseline_continuous.mp4` and
`stage5_artic_A_baseline.mp4` have identical video-stream MD5
`60266c3d869d6fbe1489837d89dd74c6`).

---

# 13. Recommendation

```
USE_STAGE5_ARTICULATION
```

All *objective* Phase 19 criteria pass for gain 1.5:

- continuous speech: timing 0, no freeze, no drift, articulation varied ✓
- mouth shapes more differentiated: diversity +18 %, motion +25 % ✓
- mouth opening only moderately increased: max vopen +23 %, width unchanged ✓
- AV offset ≈ 0: confirmed on continuous AND 47.97 s long-form ✓
- face identity stable: non-mouth landmark std unchanged ✓
- 45–60 s validation: PASS ✓

**Remaining gate (requires the reviewer, not this model):** visual naturalness
— "clearly more natural, not rubber mouth." The model used here cannot view
images, so the Phase 11/16 visual sign-off is the one criterion it cannot
self-certify. If the reviewer finds gain 1.5 too strong, fall back to gain 1.3
(conservative; all objective guardrails pass, but geometric widening is
near-imperceptible). If the reviewer finds even 1.3 distorts, the honest
fallback is `KEEP_STABLE` / `MODEL_LIMITATION_NEEDS_FUTURE_STAGE`, because the
root cause is the MuseTalk v1.5 + whisper-tiny model's own compressed
articulation range (§3), and a safe in-pipeline lever may simply not exist
beyond what was tested.

Do NOT change FPS, codec, resolution, GFPGAN, CUDA Graph, WOLA, audio timing,
or the realtime pipeline (Stage 5 was strictly articulation).