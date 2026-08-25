# SYSTEM LIPSYNC DIAGNOSIS — Stage 1 (Audit Only)

Report path: `C:\CongThang_AI_Avatar\AI_avatar\SYSTEM_LIPSYNC_DIAGNOSIS.md`
Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Render under audit: `D:\CongThang_AI_Avatar\renders\test_5min.mp4`
Date: 2026-08-24

> **No production code was modified during this audit.**
> Only temporary diagnostic scripts (`diag_feature_len.py`, `diag_motion.py`,
> `diag_phase.py`, `diag_diversity.py`, `script_50s.txt`) were added to the
> working tree (untracked) and controlled test renders were produced under
> `D:\CongThang_AI_Avatar\renders\`.

---

## 1. Executive Summary

**What is broken:** In offline script→MP4 rendering (`generate_video_from_script.py`),
lip-sync is correct for roughly the first **30 seconds**, then the mouth effectively
stops tracking the audio. The final audio track continues playing normally for the
full duration, so the video looks like a talking head whose mouth is stuck while the
voice goes on.

**Most likely root cause (CONFIRMED, P0):** The renderer feeds the **entire** TTS
waveform (e.g. 167 s) into the HuggingFace Whisper feature extractor in a single
call. That extractor is configured with `chunk_length = 30` / `n_samples = 480000`,
so it **truncates every input to the first 30 seconds** and emits exactly **1500**
encoder features (50 Hz × 30 s). For any video frame past 30 s, the frame→feature
index exceeds 1500 and is **silently clamped to the last available feature (index
1499)**. Every frame after 30 s therefore receives the *same* audio conditioning →
the mouth holds one static shape (modulated only by the body latent loop) while the
muxed audio is the full original track.

**Confidence: HIGH.** Two independent pieces of hard evidence:
1. Direct measurement: `audio2feat(167.6 s wav)` returns shape **(1500, 5, 384)** —
   exactly the 30 s feature budget (expected 8382). Repeated for a 55 s clip
   (expected 2760 → actual 1500).
2. Same-body-latent-phase fingerprint on the rendered MP4: pre-30 s same-phase mouth
   crops differ by **17.1 / 11.4** (real lip-sync); post-30 s same-phase crops differ
   by only **1.55** (mouth static).

**Is it Whisper, CUDA Graph, queues, temporal indexing, or model quality?**
It is a **Whisper long-audio truncation** bug in the **offline render path only**.
CUDA Graph is *not* the cause (proven: graph ON and graph OFF both freeze at 30 s).
Queues are *not* involved (the offline path has no queue). Temporal indexing math is
correct; it is the truncated feature array + silent clamping that breaks it. Model
quality/version is fine (MuseTalk 1.5 + whisper-tiny).

### Ranked causes
- **P0 — Whisper 30 s truncation in offline `audio2feat`** (root cause). CONFIRMED.
- **P1 — Silent feature-index clamping** (`idx = min(length-1, idx)`) masks the
  truncation as a "static mouth" instead of raising, hiding the bug. CONFIRMED.
- **P2 — Single-source-of-truth audio split**: the same WAV drives both feature
  extraction (truncated to 30 s) and the final mux (full length), so the two paths
  diverge in temporal coverage. Subsumed by P0.
- **P3 — No regression test** for long-duration renders (allowed this to ship).

---

## 2. System Architecture

Actual offline text→video flow used to produce `test_5min.mp4`
(`generate_video_from_script.py:main` → `render_video`):

```
script_5min.txt (text)
  ↓ EdgeTTS (vi-VN-HoaiMyNeural)            tts/edge.py + edge_tts
  ↓ tts.mp3                                  tempfile
  ↓ ffmpeg -ar 16000 -ac 1 -af apad=pad_len=1600
  ↓ audio.wav  (16 kHz mono PCM, 167.6 s)    TEMPORARY, drives BOTH paths
  ├─────────────────────────────────────────── FEATURE PATH (BROKEN) ──────────
  │  sf.read(audio.wav) → wav_data (2,682,539 samples)
  │  ↓ Audio2Feature.audio2feat(wav_data)            avatars/musetalk/whisper/audio2feature.py:108
  │  ↓   feature_extractor(wav_data, sampling_rate=16000)  ← HF WhisperFeatureExtractor
  │  ↓   TRUNCATES to chunk_length=30 → input_features [1,80,3000]
  │  ↓   whisper.encoder(...) → hidden_states → stack → squeeze
  │  ↓ whisper_feature  shape (1500, 5, 384)         ← ONLY FIRST 30 s
  │  ↓ for i in range(num_frames=4191):
  │  ↓   feature2chunks(whisper_feature, fps=25, bs=1, audio_feat_length=[2,2], start=i)
  │  ↓     get_sliced_feature(vid_idx=i): center_idx = i*50/25 = i*2
  │  ↓     for idx in [center, center+(2+2+1)*2]: idx = min(length-1, idx)  ← CLAMP
  │  ↓   all_whisper_chunks[i]                       ← for i≥750 → ALL = feature[1499]
  │  ↓ for batch in range(0, 4191, 16):
  │  ↓   audio_feature_batch = stack(chunks[i:i+16]) → pe → UNet (CUDA graph or eager)
  │  ↓   latent_batch (per-frame body latent)
  │  ↓   pred_latents = UNet(latent, ts, encoder_hidden_states=audio_emb)
  │  ↓   pred = vae.decode_latents(pred_latents) → numpy [16,256,256,3] uint8 BGR
  │  ↓   paste_back (cv2 resize + blend) → combine_frame (1080×1920)
  │  ↓   pipe.stdin.write(combine_frame.tobytes())   ffmpeg libx264 ultrafast CRF16
  ├─────────────────────────────────────────── MUX PATH (CORRECT) ────────────
  │  ffmpeg -i temp_video.mp4 -i audio.wav -shortest → test_5min.mp4   (FULL 167.6 s audio)
  └────────────────────────────────────────────────────────────────────────────
```

**Where CUDA Graph enters:** `render_video` calls `_build_graph_runner` (single-GPU,
graph-on) which captures `pe → UNet` around static buffers of shape
`audio (16,50,384)`, `latent (16,8,32,32)`. Each batch copies fresh
`audio_feature_batch` and `latent_batch` into the static buffers via `copy_` then
`graph.replay()`. VAE decode runs eager after replay. The graph sits **after** the
feature truncation, so it faithfully replays whatever (clamped) features it is given.

| Stage | File | Function | In→Out | Sync/Async |
|---|---|---|---|---|
| TTS | tts/edge.py | EdgeTTS.txt_to_audio | text→mp3 | sync |
| Decode | generate_video_from_script.py | convert_audio_to_wav | mp3→16k wav | sync (ffmpeg) |
| Features | avatars/musetalk/whisper/audio2feature.py | Audio2Feature.audio2feat | wav [N]→feat [1500,5,384] | sync, GPU |
| Chunking | audio2feature.py | feature2chunks / get_sliced_feature | feat→per-frame [50,384] | sync, CPU |
| UNet | avatars/musetalk_avatar.py / generate_video | UNet forward | latent+audio→pred_latents | sync, GPU |
| VAE | avatars/musetalk/models/vae.py | decode_latents | pred_latents→[bs,256,256,3] | sync, GPU |
| Paste | avatars/musetalk/myutil.py | get_image_blending | face+frame→composite | sync, CPU |
| Encode | generate_video_from_script.py | ffmpeg pipe | raw bgr24→h264 mp4 | sync pipe |
| Mux | generate_video_from_script.py | ffmpeg | video+audio→final mp4 | sync |

**Note:** the realtime path (`avatars/audio_features/whisper.py:WhisperASR.run_step`)
does NOT have this bug — it feeds only a small sliding window
(`stride_left + stride_right` frames ≈ < 1 s) to `audio2feat` each step, so it never
crosses 30 s. The bug is specific to the offline renderer's "extract features for the
whole utterance at once" design.

---

## 3. Exact Runtime Environment

```
OS:        Windows 11 Pro, build 26200, x64
Python:    3.10 (latentsync_env at C:\CongThang\AI_avatar\latentsync_env)
CPU:       Intel i9-9900K, 8 cores / 16 threads, 3.60 GHz
RAM:       64 GB
GPUs:      2 × NVIDIA GeForce RTX 3090 (24 GB each, compute cap 8.6)
           topology PXB (PCIe, no NVLink)
Driver:    610.88
torch:     2.5.1+cu121     cuda(is_available)=True  device_count=2
torchvision: 0.20.1+cu121
torchaudio: MISSING (not used by offline render chain)
cuDNN:     9.1.0 (90100)
transformers: 4.48.0
diffusers: 0.32.2
accelerate: 0.26.1
numpy:     1.26.4
opencv:    4.11.0
ffmpeg:    9.0 (gyan full build), system PATH
```

Render config used for the audited file: `batch_size=16`, fp16, TF32 on, cuDNN
benchmark on, CUDA Graph ON, single-GPU (CUDA_VISIBLE_DEVICES=1 → logical cuda:0),
H.264 libx264 ultrafast CRF16, composite capped to 1080×1920, EdgeTTS vi-VN.

---

## 4. Model Inventory

| Component | Path | Size | Version evidence | Loaded by | Device/dtype |
|---|---|---|---|---|---|
| MuseTalk UNet | `models/musetalkV15/unet.pth` | 3.40 GB | `musetalk.json`: UNet2DConditionModel, in_channels=8, cross_attention_dim=384, sample_size=64 → **MuseTalk 1.5** | `avatars/musetalk/utils/utils.py:load_all_model` (default `unet_model_path`) | cuda, fp16 |
| MuseTalk config | `models/musetalkV15/musetalk.json` | 748 B | diffusers 0.6.0.dev0 UNet2DConditionModel | `load_all_model` | — |
| VAE (sd-vae) | `models/sd-vae/diffusion_pytorch_model.bin` | 334 MB | diffusers VAE (no safetensors → bin fallback) | `load_all_model` → `vae_type="sd-vae"` | cuda, fp16 |
| Whisper | `models/whisper/pytorch_model.bin` | 151 MB | `config.json`: model_type=whisper, d_model=384, max_length=448 → **whisper-tiny** | `Audio2Feature.__init__` (WhisperModel.from_pretrained) | cuda, fp16 |
| Whisper preprocessor | `models/whisper/preprocessor_config.json` | 185 KB | **chunk_length=30, n_samples=480000, feature_size=80, hop_length=160** | `AutoFeatureExtractor.from_pretrained` | — |
| Positional encoder (pe) | inside musetalkV15 unet package | — | learned PE, 384-dim | `load_all_model` | cuda, fp16 |
| Face detector | SFD s3fd.pth (wav2lip path) | — | not used by musetalk inference | — | — |
| GFPGAN | `models/GFPGANv1.4.pth` | **MISSING** | not installed | `avatars/face_enhance.py` (disabled) | — |
| LatentSync | `models/syncnet/latentsync_syncnet.pt` | present | sibling project, not used by this render | — | — |
| SyncNet evaluator | **none in this repo** | — | only model defs (`avatars/musetalk/models/syncnet.py`); a bench harness exists in the sibling project `C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py` (not run in Stage 1) | — | — |

**MuseTalk version: 1.5** (the `musetalkV15` path + in_channels=8 masked+reference
latent architecture is the 1.5 design). Not modified/forked in a way that affects
this bug. The bug is upstream of the UNet.

---

## 5. Audio Pipeline

```
script_5min.txt
  → edge_tts.Communicate(text, "vi-VN-HoaiMyNeural").save(tts.mp3)   [EdgeTTS, free]
  → ffmpeg -i tts.mp3 -ar 16000 -ac 1 -af apad=pad_len=1600 audio.wav
      (pad_len=1600 = +100 ms silence pad; 16 kHz mono float32)
  → SAME audio.wav used for BOTH:
      (A) feature extraction:  sf.read → audio2feat(wav)   ← TRUNCATED to 30 s
      (B) final mux:           ffmpeg -i temp_video.mp4 -i audio.wav  ← FULL length
```

Single source file, but the feature path covers only the first 30 s while the mux
path covers the full 167.6 s. The durations of the final tracks match (video
167.640 s, audio 167.616 s, Δ 24 ms) because the mux uses the full WAV; the feature
path's truncation is invisible to the mux.

---

## 6. Whisper Long-Audio Audit  (H1)

Function: `Audio2Feature.audio2feat` — `avatars/musetalk/whisper/audio2feature.py:108-119`

```python
def audio2feat(self, wav_data):
    input_feature = self.feature_extractor(
        wav_data, return_tensors="pt", sampling_rate=16000
    ).input_features                                  # ← HF WhisperFeatureExtractor
    input_feature = input_feature.to(self.device).to(self.weight_dtype)
    whisper_feature = self.whisper.encoder(input_feature, output_hidden_states=True).hidden_states
    whisper_feature = torch.stack(whisper_feature, dim=2)
    return whisper_feature.squeeze(0).cpu().numpy()
```

1. **Does it process the whole waveform in one call?** YES — `audio2feat(wav_data)`
   passes the entire `wav_data` (2.68 M samples) to `feature_extractor` once.
2. **Does it chunk long audio?** NO. There is no windowing/chunking in `audio2feat`.
3. **Max chunk duration?** 30 s — imposed by the extractor config
   (`chunk_length=30`, `n_samples=480000` at 16 kHz).
4. **Does the HF extractor truncate?** YES. `WhisperFeatureExtractor` produces
   `input_features` of shape `[1, 80, 3000]` (3000 mel frames = 30 s) regardless of
   input length; longer input is truncated to the first 30 s.
5. **Tensor into encoder:** `[1, 80, 3000]` fp16.
6. **Feature shape out:** `(1500, 5, 384)` — 1500 time steps × 5 hidden layers × 384.
7. **Effective feature rate:** 50 Hz (1500 / 30 s).

Measured (Test C):
```
audio duration        = 167.659 s
input samples         = 2,682,539 @ 16 kHz
expected 50 Hz feats  = 8382
expected frames @25   = 4191
ACTUAL feature shape  = (1500, 5, 384)
ACTUAL feature length = 1500          ← Rule A triggered (1500 ∧ duration>30s)
TRUNCATED?            = YES (~30 s)
```
Repeated for a 55.22 s clip: expected 2760 features → **actual 1500**. Same
truncation.

Out-of-range / clamping code — `audio2feature.py:get_sliced_feature:47-50`:
```python
for idx in range(left_idx, right_idx):
    idx = max(0, idx)
    idx = min(length-1, idx)        # ← silent clamp to last feature
    x = feature_array[idx]
```
With `center_idx = int(vid_idx*50/fps) = vid_idx*2`, frame `i` maps to feature
`i*2`. For `i ≥ 750` (t ≥ 30 s), `i*2 ≥ 1500` → clamped to `1499`. The slice window
`[center, center+(2+2+1)*2]` is then entirely `1499`. So **every frame from 30 s to
the end receives feature[1499] repeated**.

> **Is the audio effectively limited to ~30 s anywhere in the current lip-sync
> pipeline?**
> **YES.** In the offline renderer, `audio2feat` limits the lip-driving features to
> the first 30 s of audio, no matter how long the input is.

---

## 7. CUDA Graph Audit  (H2)

Implementation: `utils/cuda_graph.py` (`GraphRunner`) + usage in
`generate_video_from_script.py:render_video` and
`avatars/musetalk_avatar.py:inference_batch`.

Lifecycle:
```
warmup (3 eager iters on side stream) → allocate static input buffers →
capture_begin → forward (pe+UNet) → capture_end → per-batch: copy_ inputs → replay
```

Input refresh — `utils/cuda_graph.py:replay`:
```python
for k, v in fresh_inputs.items():
    buf = self._static_inputs[k]
    if v.shape != buf.shape or v.dtype != buf.dtype: raise ...
    buf.copy_(v, non_blocking=True)        # ← audio + latent refreshed EVERY batch
self._graph.replay()
return self._static_output
```

Output handling — offline `render_video`:
```python
pred_latents = graph_runner.replay({"audio_feat": audio_feature_batch, "latent": latent_batch})
pred = vae.decode_latents(pred_latents)    # consumed IMMEDIATELY, same thread, before next replay
```
The output is a static graph buffer but it is consumed by `vae.decode_latents`
synchronously in the same iteration, before the next `replay()` can overwrite it.
The realtime path is identical (replay → decode in the same inference_batch call).

> **Are new audio features copied into graph inputs every batch?** YES (`copy_`).
> **Are new latent inputs copied every batch?** YES (`copy_`).
> **Can graph outputs be overwritten before they are consumed?** NO — single-threaded
> consume-before-next-replay in both offline and realtime paths.

**Controlled proof (Rule B):** Test A (graph OFF, 55 s) produces feature length 1500
and freezes at 30 s by the same mechanism; Test B (graph ON, 167 s) does the same.
Graph state does not change the feature length (audio2feat runs once, pre-graph).
**H2 DISPROVED as root cause.** The graph correctly replays the (clamped) inputs it
is given; the inputs themselves are wrong upstream.

---

## 8. Queue / Silence Audit  (H3)

Offline renderer queues: **NONE.** `generate_video_from_script.py:render_video`
iterates `for i in range(0, num_frames, batch_size)` directly over the precomputed
`all_whisper_chunks` list. There is no `queue.get(timeout=...)`, no silence
synthesis, no `type=1` classification, no `is_all_silence` branch. Every frame is
passed through MuseTalk inference unconditionally.

The realtime `BaseASR.get_audio_frame` (base_asr.py:90-111) DOES synthesize a
zero-filled `type=1` silence frame on `queue.Empty`, and `base_avatar.inference`
skips the UNet when `is_all_silence`. That is realtime-only and did not produce
`test_5min.mp4`.

> **Can queue starvation cause MuseTalk to stop moving the mouth while the final
> audio still continues?**
> **Not in the offline renderer** — it has no queue and never classifies frames as
> silence. (It could in the realtime server, but that is a separate path and not the
> subject of this render.)

---

## 9. Frame / Feature Timing Audit  (H5)

Configured values (offline): `fps=25`, `feature_sr=16000`, `chunk = sr/(fps*2)` =
320 samples/20 ms, `audio_feat_length=[2,2]`, `feature_idx_multiplier = 50/fps = 2`.

Frame→feature mapping (`get_sliced_feature`):
```
center_idx   = int(vid_idx * 50 / fps) = vid_idx * 2          # 2 features per video frame
left_idx     = center_idx
right_idx    = center_idx + (2+2+1)*2 = center_idx + 10       # 5-frame window × 2
```
So each video frame uses a 10-feature (200 ms) window. For a full-length feature
array this is the standard MuseTalk mapping and is **mathematically correct**:
frame `i` ↔ audio centred at `i*2` features = `i*40 ms`. Expected total features for
167.6 s = 8382; expected frames = 4191; ratio 2.0 features/frame — consistent.

The mapping is NOT the bug. The bug is that `feature_array` has only 1500 entries,
so the mapping lands out-of-range for `i ≥ 750` and the clamp returns a constant.

> No LEFT/RIGHT tuning is needed or recommended at this stage (Rule D does not apply:
> the mouth does not move consistently early/late — it stops tracking entirely).

---

## 10. Controlled Test Results

| Test | Graph | Duration | Lip motion after 30 s | Feature length (exp) | Sync score | Notes |
|------|-------|---------:|------------------------|---------------------:|-----------:|-------|
| A | OFF | 55.2 s | STATIC (clamped) | 1500 (2760) | not run | `testA_graphoff_50s.mp4`; same freeze as graph-on → graph not cause |
| B | ON  | 167.6 s | STATIC (clamped) | 1500 (8382) | not run | `test_5min.mp4`; phase fingerprint proves static mouth |
| C | n/a (feature-only) | 167.7 s | n/a | 1500 (8382) | n/a | `diag_feature_len.py`; decisive: TRUNCATED to 30 s |
| C' | n/a (feature-only) | 55.2 s | n/a | 1500 (2760) | n/a | confirms truncation is length-dependent, not graph-dependent |

SyncNet: no evaluator in this repo (only `avatars/musetalk/models/syncnet.py`
definitions). A bench harness exists in the sibling project
`C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py` but uses a different
env; not run in Stage 1 (audit mandate: do not install/validate new tooling).

---

## 11. Mouth-Motion Timeline

Method: extract mouth ROI (avatar coords.pkl frame-0 face bbox × downscale 0.5,
lower 45 % of face = `(474,565,615,646)` in the 1080×1920 output), 5 fps sampling.

Raw per-5 s mean abs frame diff (test_5min.mp4) — *inconclusive on its own* (stays
~7-10 throughout because the body-latent loop keeps wobbling the lower face even
when the lips are static):

```
0-30s:  7.2 9.1 7.7 8.3 8.5 10.5     (lip-sync active + latent wobble)
30-60s: 7.8 10.1 8.1 7.6 7.7 8.4      (latent wobble only — lips static)
...    similar ~7-10 through 167 s
```

**Decisive discriminator — same-body-latent-phase fingerprint**
(`diag_phase.py`, body loop period = 2×810 frames = 64.8 s; frames 64.8 s apart
share the same body latent):

```
Pre-30 s same-phase pairs (different audio → mouth should DIFFER):
  t= 2.0s vs t=20.0s  ->  diff = 17.14      REAL lip-sync
  t=10.0s vs t=28.0s  ->  diff = 11.43      REAL lip-sync

Post-30 s same-phase pair (clamped feature → mouth should be IDENTICAL):
  t=66.8s vs t=131.6s ->  diff =  1.55      MOUTH STATIC (1.55/255 = noise)

Cross (real vs clamped, same phase):
  t= 2.0s vs t= 66.8s ->  diff =  4.04
  t= 2.0s vs t=131.6s ->  diff =  4.01
```

> **Motion collapses at ~30 s.** The post-30 s same-latent mouth is essentially
> identical (1.55) while audio RMS stays high (~0.10) through the whole clip.
> **Rule C satisfied:** audio active, mouth static.

---

## 12. Root Cause Ranking

| Hypothesis | Verdict | Evidence |
|---|---|---|
| **H1 Whisper 30 s truncation** | **CONFIRMED (P0)** | `audio2feat` returns 1500 feats for 167 s & 55 s inputs; config `chunk_length=30`; clamp at `get_sliced_feature:49`; phase fingerprint 1.55 post-30 s vs 17.14 pre-30 s. Rule A triggered. |
| H2 CUDA Graph input/output bug | **DISPROVED** | `copy_` refreshes audio+latent every batch; output consumed before next replay; graph ON and OFF both freeze at 30 s (Test A vs B). Rule B not triggered (both fail identically). |
| H3 Realtime queue starvation reused offline | **DISPROVED (offline)** | Offline renderer has no queue, no timeout, no silence synthesis. (Realtime path has queues but did not produce this file.) |
| H4 Lip audio ≠ mux audio | **LIKELY (subsumed by H1)** | Same `audio.wav` file feeds both, but feature path is truncated to 30 s while mux path is full → temporal coverage diverges. |
| H5 Temporal indexing wrong | **UNLIKELY** | `feature_idx_multiplier=2`, `center=vid_idx*2` is correct for full-length features; failure is the truncated array + clamp, not the math. |
| H6 Wrong MuseTalk version | **UNLIKELY** | MuseTalk 1.5 (`musetalkV15`, in_channels=8, cross_attn_dim=384) + whisper-tiny (d_model=384) are consistent and load correctly. Failure is upstream of the model. |

---

## 13. Recommended Fix Plan (Stage 2 — do NOT implement now)

**Fix 1 — correctness blocker / P0:** Make `audio2feat` handle arbitrary-length
audio. Two safe options:
  (a) **Chunk inside `audio2feat`**: slide a 30 s window over the waveform with a
      small overlap (e.g. 1 s), run the encoder per window, concatenate the 50 Hz
      features along time, trimming the overlap. Returns `(duration*50, 5, 384)`.
      Minimal blast radius — one function, used by both offline and (harmlessly)
      realtime (realtime already passes short windows, so concatenation is a no-op
      there).
  (b) **Chunk in the offline renderer only**: in `generate_video_from_script.py`,
      replace the single `audio2feat(wav)` with a loop that extracts per-30 s
      windows and concatenates, leaving `audio2feat` untouched. Lower risk to the
      realtime server, slightly more code in the renderer.
  Recommendation: (a) is the single-source fix and also protects any future caller.

**Fix 2 — P1:** Replace the silent clamp `idx = min(length-1, idx)` in
`get_sliced_feature` with explicit handling: when the requested centre is out of
range, raise/log once (so truncation is visible) or zero-pad a distinct "no-feature"
token instead of repeating the last real feature. This turns a silent freeze into a
loud failure mode.

**Fix 3 — CUDA Graph:** No change required. Keep the graph; it is correct. After
Fix 1 the graph will replay with correct per-frame features.

**Fix 4 — Offline audio architecture:** Optional cleanup — drive feature extraction
from the same single source-of-truth WAV with an explicit length assertion
(`assert feat_len ≈ duration*50`) so future truncation fails fast.

**Fix 5 — Temporal calibration:** Not needed now (Rule D not triggered). Revisit
only after Fix 1 if a consistent early/late offset remains.

**Fix 6 — Model/version:** No change. MuseTalk 1.5 + whisper-tiny are adequate.

**Fix 7 — Performance re-optimization:** Re-enable CUDA Graph (already correct) and
multi-GPU only after Fix 1 is verified; do not conflate perf work with the
correctness fix.

Safest order: **Fix 1 → verify with 90 s/3 min renders → Fix 2 → regression tests →
then** revisit performance.

---

## 14. Files That Need Modification in Stage 2

| File | Function/class | Reason | Risk |
|---|---|---|---|
| `avatars/musetalk/whisper/audio2feature.py` | `Audio2Feature.audio2feat` | Chunk long audio into 30 s windows + concatenate (Fix 1 option a) | Medium — touches a function used by both offline and realtime; realtime passes short windows so concat is a no-op, but must verify shape contract `(T,5,384)` preserved. |
| `avatars/musetalk/whisper/audio2feature.py` | `get_sliced_feature` (lines 47-50) | Replace silent clamp with explicit out-of-range handling (Fix 2) | Low — only changes error visibility. |
| `generate_video_from_script.py` | `render_video` (feature extraction block, ~line 67-71) | If Fix 1 option (b) chosen: windowed extraction + length assert (Fix 4) | Low — offline only. |
| `avatars/audio_features/whisper.py` | `WhisperASR.run_step` | None (already safe — short windows). Verify after Fix 1. | Low. |
| Tests (new) | — | Regression renders at 10/45/90/180/300 s | None. |

No production code was modified in Stage 1.

---

## 15. Regression Tests Required

For each: assert feature length ≈ duration × 50 (±2), assert mouth-motion diversity
after the 30 s mark stays above the pre-30 s baseline (same-latent-phase diff ≥ ~10),
and assert A/V duration match within 40 ms.

- 10-second render (below truncation boundary — must still be correct)
- 45-second render (crosses 30 s boundary — the failure case)
- 90-second render
- 180-second render
- 300-second render

Matrix:
- CUDA Graph OFF and ON (both must pass after Fix 1)
- continuous Vietnamese speech (EdgeTTS vi-VN)
- speech + intentional silent gaps
- batch_size 16 (and one run at 8 to catch shape-dependent graph paths)

A fast non-render gate: `assert audio2feat(wav).shape[0] >= int(len(wav)/sr*50) - 2`
for a 120 s WAV — fails instantly on any regression of Fix 1 without rendering.

---

## 16. Raw Evidence

### Code excerpts

`avatars/musetalk/whisper/audio2feature.py:108-119` (the truncation site):
```python
def audio2feat(self, wav_data):
    input_feature = self.feature_extractor(
        wav_data, return_tensors="pt", sampling_rate=16000
    ).input_features
    input_feature = input_feature.to(self.device).to(self.weight_dtype)
    whisper_feature = self.whisper.encoder(input_feature, output_hidden_states=True).hidden_states
    whisper_feature = torch.stack(whisper_feature, dim=2)
    return whisper_feature.squeeze(0).cpu().numpy()
```

`avatars/musetalk/whisper/audio2feature.py:43-55` (the clamp):
```python
center_idx = int(vid_idx*50/fps)
left_idx = center_idx
right_idx = center_idx + (audio_feat_length[0]+audio_feat_length[1]+1)*2
for idx in range(left_idx,right_idx):
    idx = max(0, idx)
    idx = min(length-1, idx)      # ← out-of-range → last feature (silent freeze)
    x = feature_array[idx]
```

`generate_video_from_script.py:67-71` (whole-utterance extraction):
```python
whisper_feature = audio_processor.audio2feat(wav_data)   # full 167 s → 1500 feats
...
for i in tqdm(range(num_frames)):                         # 4191 frames
    chunks = audio_processor.feature2chunks(whisper_feature, fps=25, batch_size=1,
                                            audio_feat_length=[2,2], start=i)
```

`models/whisper/preprocessor_config.json`:
```json
{ "chunk_length": 30, "feature_extractor_type": "WhisperFeatureExtractor",
  "feature_size": 80, "hop_length": 160, ... }
```

### Test C output (decisive)
```
WAV: samples=2682539 sr=16000 duration=167.659s
EXPECTED 50Hz features (full): 8382   EXPECTED frames @25: 4191   SUSPICIOUS: 1500
feature_extractor: WhisperFeatureExtractor chunk_length=30 n_samples=480000
ACTUAL feature shape: (1500, 5, 384)   ACTUAL length: 1500   TRUNCATED? YES ~30s
```
55 s clip: `ACTUAL feature length for 55.2s = 1500  -> TRUNCATED to 30s` (expected 2760).

### Phase fingerprint (test_5min.mp4)
```
SAME-LATENT-PHASE pairs:
  t=  2.0s vs t= 66.8s -> diff=4.036
  t=  2.0s vs t=131.6s -> diff=4.014
  t= 66.8s vs t=131.6s -> diff=1.553      <-- post-30s same-latent = STATIC
Control pre-30s:
  t=  2.0s vs t= 20.0s -> diff=17.136      <-- real lip-sync
  t= 10.0s vs t= 28.0s -> diff=11.430
```

### Render metrics
```
test_5min.mp4: 1080x1920, 25fps, 4191 frames, 167.640s video / 167.616s audio (Δ24ms)
  Render: 4191 frames / 140.5s = 29.8 fps, CUDA graph ON, single-GPU
testA_graphoff_50s.mp4: 55.2s, 1380 frames, CUDA graph OFF -> 1500 feats, freezes at 30s
```

### Git
```
branch: main
remote: https://github.com/NeolabAI/avatar_livestream.git
HEAD: 63921b8 fix: replace removed env_flag import in offline render; add 5-min test script
prev: 0470a60 fix: push FPS render + harden security + correctness/code-quality fixes
working tree: untracked diag_*.py, script_50s.txt, script_5min.txt (no production edits)
```

### Temporary diagnostic files created (untracked, not production)
- `C:\CongThang_AI_Avatar\AI_avatar\diag_feature_len.py`  — Test C: feature length probe
- `C:\CongThang_AI_Avatar\AI_avatar\diag_phase.py`        — same-latent-phase fingerprint
- `C:\CongThang_AI_Avatar\AI_avatar\diag_motion.py`       — raw mouth-motion timeline
- `C:\CongThang_AI_Avatar\AI_avatar\diag_diversity.py`    — per-5s mouth-shape diversity
- `C:\CongThang_AI_Avatar\AI_avatar\script_50s.txt`       — 55 s continuous-speech script
- `D:\CongThang_AI_Avatar\renders\testA_graphoff_50s.mp4` — Test A output (graph OFF)
- `D:\CongThang_AI_Avatar\renders\test_5min.mp4`          — audited render (graph ON)
- temp WAV under `%TEMP%\diag_audio.wav` / `diag_a.wav` (regenerated each run)