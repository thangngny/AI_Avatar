# 7-Part Render Configuration Audit (Forensic, Read-Only)

Audit date: 2026-08-25
Scope: determine EXACTLY what configuration produced the 7 completed MP4s in
`D:\CongThang_AI_Avatar\noble_live_25_8\`. No files or production settings were
modified during this audit. No rerender / no config change / no TTS regen / no
file moves or deletes were performed.

## STEP 1 — Repository state

```
git branch --show-current : feature/mouth-articulation-v1
git log -5 --oneline:
  5e295db fix production renderer: resample --audio to 16kHz + even composite dims
  8e695fa consolidate avatar renderer to single production truth
  0d0f03a stabilize long-audio MuseTalk lip-sync pipeline
  63921b8 fix: replace removed env_flag import in offline render; add 5-min test script
  0470a60 fix: push FPS render + harden security + correctness/code-quality fixes
git describe --tags --always : ai-avatar-production-truth-v1-1-g5e295db
8e695fa is ancestor of HEAD : YES
```

- Current HEAD: `5e295db` (on top of the production-truth commit `8e695fa`).
- The production-truth code (`8e695fa`) plus two correctness fixes (`5e295db`) were
  committed BEFORE the render started (15:55). The render therefore ran on code that
  contains the locked-truth loader + the resample/even-dim fixes. Tag
  `ai-avatar-production-truth-v1` is intact; HEAD is 1 commit past it.
- Working-tree status was not modified by this audit.

## STEP 2 — Canonical render truth (current)

`config\render_truth.json` (read, not modified):
```json
{
  "pipeline": "musetalk_v15",
  "audio_gain": 1.5,
  "audio_context_left": 0,
  "audio_feature_offset_frames": -3,
  "fps": 25,
  "resolution_width": 1080,
  "resolution_height": 1920,
  "composite_max_dim": 1920,
  "cuda_graph": true,
  "long_audio_wola": true,
  "feature_coverage_assertion": true
}
```

`generate_video_from_script.py` (HEAD `5e295db`) loads this file via `load_render_truth()`
(fail-closed), forces the locked values into `eff` when `--experimental-config` is NOT
passed, and pushes `LIVETALKING_CUDA_GRAPH` + `LIVETALKING_COMPOSITE_MAX_DIM` from the
truth. The banner is printed from `eff` (the actual values used by `render_video`).

IMPORTANT separation maintained in this report: CURRENT config == CONFIG ACTUALLY USED
because the wrapper passed no quality overrides and no `--experimental-config`
(see Step 4). Both are verified independently below from the runtime logs.

## STEP 3 — Per-log runtime evidence

All 7 logs live in `D:\CongThang_AI_Avatar\noble_live_25_8\logs\`:
`mo_dau_gpu0.log, phan_1_gpu1.log, phan_2_gpu1.log, phan_3_gpu0.log, phan_4_gpu0.log,
phan_5_1_gpu1.log, phan_5_2_gpu0.log`.

Each log opens with an identical banner (printed from `eff`, i.e. the values actually
used):

```
AI AVATAR — PRODUCTION TRUTH
Pipeline: MuseTalk v1.5
LOCKED QUALITY CONFIG:
  Audio gain: 1.5
  Audio context left: 0
  Audio feature offset: -3
  FPS: 25
  Resolution: 1080x1920 (composite_max_dim 1920)
  CUDA Graph: ON
  Long-audio WOLA: ON
  Feature coverage guard: ON
VARIABLE JOB INPUT:
  Avatar: close_up
  Audio: D:\CongThang_AI_Avatar\renders\audio\<part>.wav
  Output: D:\CongThang_AI_Avatar\noble_live_25_8\<NN>_<part>.mp4
Config source: C:\CongThang_AI_Avatar\AI_avatar\config\render_truth.json
```

Additional runtime lines present in every log:
- `Normalizing master audio to 16kHz mono...`  (the resample fix, commit 5e295db)
- `load unet model from C:\...\models\musetalkV15\unet.pth`
- `Loading avatar: close_up`
- `[Whisper Long Audio] window 0: 0.000-30.000s -> local 1500 feats, global [0, 1500)`
- `[Whisper Long Audio] total: duration=... windows=... overlap=1.00s features=... coverage=... uncovered=0`
- `Feature coverage OK: <N> features (~<s>s) for <frames> frames (required ~<req>)`
- `Audio feature offset: -3 frames (-120 ms)  [center=(i+off)*2]`
- `Audio conditioning gain: 1.500 (expression intensity; 1.0 = stable)`
- `offline_musetalk_unet: captured on cuda:0 (inputs={'audio_feat': (16, 50, 384), 'latent': (16, 8, 32, 32)} ...)`
- `Rendering <frames> frames in batches of 16 (multi_gpu=False, cuda_graph=True)...`
- `Render done: <frames> frames in <s>s = <fps> fps`
- `Done: D:\CongThang_AI_Avatar\noble_live_25_8\<NN>_<part>.mp4`

Values NOT explicitly logged at runtime (only in the banner, which is itself runtime
output from `eff`): `audio_context_left=0` (render_video only prints the context window
line when ctx != 0; ctx=0 is the no-op/no-print case). Classified
CONFIRMED_FROM_RUNTIME_LOG via the banner (printed from the actual `eff`).

## STEP 4 — Exact launch command / wrapper

Recovered from `input_25_8\render_pipeline.py` (the batch launcher; 2 worker threads,
one per GPU). Per-part subprocess command (lines 88-90):

```python
cmd = [PY, "-u", ".../generate_video_from_script.py",
       "--avatar_id", AVATAR,      # "close_up"
       "--audio", ap(part),         # master WAV
       "--output", outp,           # noble_live_25_8/<NN>_<part>.mp4
       "--batch_size", str(BATCH)] # 16
env: CUDA_VISIBLE_DEVICES=<gpu>, LIVETALKING_GPU_ID=0
```

- `generate_video_from_script.py` WAS used directly (as the per-part subprocess).
- A wrapper (`render_pipeline.py`) WAS used — for 2-GPU job scheduling only.
- The wrapper passed ONLY `--avatar_id / --audio / --output / --batch_size`.
- It did NOT pass `--audio-gain`, `--audio-context-left`, `--audio-feature-offset-frames`,
  `--fps`, or `--experimental-config`. → No production-truth override was possible.
- No `.bat`/`.ps1` launcher was used; the wrapper is a Python script.

## STEP 5 — Pipeline identity (high confidence)

Pipeline used = **MuseTalk v1.5**. Evidence (per log):
- Entrypoint: `generate_video_from_script.py` (MuseTalk offline renderer).
- Imports/log signatures: `load unet model from ...\models\musetalkV15\unet.pth`.
- `offline_musetalk_unet: captured on cuda:0` (the MuseTalk UNet CUDA-graph label).
- Banner: `Pipeline: MuseTalk v1.5`.
- No occurrence of `avatar_export`, `latentsync`, `export_avatar`, `scripts.inference`,
  `LatentSync`, or `guidance_scale`/`deepcache` in any log.
- Render speed ~22 fps at 1080x1920 (paste-back) is consistent with MuseTalk and
  inconsistent with LatentSync diffusion (~0.4-0.8 fps for 512x512 inpainting).

Conclusion: MuseTalk v1.5, NOT LatentSync. High confidence.

## STEP 6 — Avatar identity

- `avatar_id` passed to renderer: `close_up` (banner `Avatar: close_up` + `Loading avatar: close_up`).
- Prepared avatar directory: `C:\CongThang_AI_Avatar\AI_avatar\data\avatars\close_up\`
  (980 frames, coords.pkl, latents.pt, mask/, mask_coords.pkl, avator_info.json).
- `avator_info.json`:
  `{"avatar_id":"close_up","video_path":"D:\\Noble\\livetalking\\data\\avatars\\.uploads\\musetalk_4872_697362812.mp4","bbox_shift":0,"version":"v15","parsing_mode":"jaw"}`
- Original source identity/path: `D:\Noble\livetalking\data\avatars\.uploads\musetalk_4872_697362812.mp4`.
- `close_up` and `fullbody_30_7_25fps` reference DIFFERENT source files:
  - close_up → `D:\Noble\livetalking\data\avatars\.uploads\musetalk_4872_697362812.mp4`
  - fullbody_30_7_25fps → `C:\Users\Admin\Videos\30_7\Closeup.mp4`
  Whether the two source videos depict the same person cannot be determined from
  metadata alone (would require viewing the videos); the source FILES are distinct.
- No alias/symlink/config mapping involved: `--avatar_id close_up` maps directly to
  `data/avatars/close_up/` via `load_avatar_data`.

DISCREPANCY FLAG: an earlier completion message stated the face was "from the old 30_7
video". That is IMPRECISE. The exact prepared avatar used (`close_up`) was prepared from
`musetalk_4872_697362812.mp4`, NOT `C:\Users\Admin\Videos\30_7\Closeup.mp4` (the latter is
the source of `fullbody_30_7_25fps`). The exact face in all 7 outputs comes from
`close_up`, source `musetalk_4872_697362812.mp4`.

## STEP 7 — Audio configuration

Per-part master WAV (in `noble_live_25_8\audio\`, ffprobe):
| part | duration | sample_rate | channels | codec |
|---|---|---|---|---|
| 01_mo_dau.wav | 502.056s | 48000 | 1 | pcm_s16le |
| 02_phan_1.wav | 479.856s | 48000 | 1 | pcm_s16le |
| 03_phan_2.wav | 523.152s | 48000 | 1 | pcm_s16le |
| 04_phan_3.wav | 335.760s | 48000 | 1 | pcm_s16le |
| 05_phan_4.wav | 322.200s | 48000 | 1 | pcm_s16le |
| 06_phan_5_1.wav | 514.152s | 48000 | 1 | pcm_s16le |
| 07_phan_5_2.wav | 448.728s | 48000 | 1 | pcm_s16le |

- TTS: EdgeTTS (not recoverable from the PCM WAV itself — no metadata — but confirmed by
  the generation script `input_25_8\gen_tts.py` which uses `edge_tts.Communicate(...)`,
  `VOICE = "vi-VN-HoaiMyNeural"`, and the TTS job log `.../b397ae0j6.output` lines
  `[TTS] <part>` / `<part> -> dur=... skipped=0` / `TTS ALL DONE`).
- Voice: `vi-VN-HoaiMyNeural`.
- One master WAV per part: YES (7 WAVs, one per part).
- The on-disk master WAVs are 48 kHz mono. The renderer (`--audio` path, commit 5e295db)
  normalized each to 16 kHz mono via `convert_audio_to_wav` into a temp dir
  (`Normalizing master audio to 16kHz mono...` in every log) and used THAT 16 kHz temp
  for both Whisper feature extraction and the final mux. So the exact same (16 kHz
  normalized) audio was used for features and for the muxed AAC track. Content/duration
  is identical to the 48 kHz master; only the on-disk master's sample rate differs from
  what entered the pipeline.

## STEP 8 — Video metadata (ffprobe, all 7)

| file | res | fps | frames | dur | vcodec | pix | acodec | adur | vdur | A/V diff | bitrate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01_mo_dau.mp4 | 1080x1920 | 25/1 | 12552 | 502.080s | h264 | yuv420p | aac | 502.080s | 502.080s | 0.000s | ~4.20 Mbps |
| 02_phan_1.mp4 | 1080x1920 | 25/1 | 11997 | 479.880s | h264 | yuv420p | aac | 479.872s | 479.880s | 0.008s | ~4.20 Mbps |
| 03_phan_2.mp4 | 1080x1920 | 25/1 | 13079 | 523.160s | h264 | yuv420p | aac | 523.136s | 523.160s | 0.024s | ~4.20 Mbps |
| 04_phan_3.mp4 | 1080x1920 | 25/1 | 8394 | 335.760s | h264 | yuv420p | aac | 335.744s | 335.760s | 0.016s | ~4.21 Mbps |
| 05_phan_4.mp4 | 1080x1920 | 25/1 | 8055 | 322.200s | h264 | yuv420p | aac | 322.176s | 322.200s | 0.024s | ~4.21 Mbps |
| 06_phan_5_1.mp4 | 1080x1920 | 25/1 | 12854 | 514.160s | h264 | yuv420p | aac | 514.112s | 514.160s | 0.048s | ~4.21 Mbps |
| 07_phan_5_2.mp4 | 1080x1920 | 25/1 | 11219 | 448.760s | h264 | yuv420p | aac | 448.704s | 448.760s | 0.056s | ~4.21 Mbps |

Confirmed: all 7 are 1080x1920, 25 FPS, h264/yuv420p, AAC. A/V duration differences are
≤56 ms (mux rounding / -shortest), negligible. No file relied on the prior textual
summary; all values are from ffprobe.

## STEP 9 — Lip-sync timing configuration (actual values used)

| parameter | expected | actual | evidence classification |
|---|---|---|---|
| audio_gain | 1.5 | 1.5 | CONFIRMED_FROM_RUNTIME_LOG (banner + `Audio conditioning gain: 1.500`) |
| audio_context_left | 0 | 0 | CONFIRMED_FROM_RUNTIME_LOG (banner from `eff`; render_video no-prints ctx at 0; no override passed) |
| audio_feature_offset_frames | -3 | -3 | CONFIRMED_FROM_RUNTIME_LOG (banner + `Audio feature offset: -3 frames (-120 ms)`) |

All three match. No `--audio-gain / --audio-context-left / --audio-feature-offset-frames`
and no `--experimental-config` were passed by the wrapper → the entrypoint forced the
locked values; no `[LOCKED] ... ignored` warning appears (consistent: nothing was
overridden).

## STEP 10 — Long-audio WOLA (per part)

All 7 parts are >30 s, so the chunked WOLA path is exercised. From each log
`[Whisper Long Audio] total:`:

| part | audio dur | features | coverage | uncovered | windows | overlap | WOLA |
|---|---|---|---|---|---|---|---|
| 01_mo_dau | 502.089s | 25104 | 502.080s | 0 | 18 | 1.00s | PASS |
| 02_phan_1 | 479.889s | 23994 | 479.880s | 0 | 17 | 1.00s | PASS |
| 03_phan_2 | 523.185s | 26159 | 523.180s | 0 | 19 | 1.00s | PASS |
| 04_phan_3 | 335.793s | 16790 | 335.800s | 0 | 12 | 1.00s | PASS |
| 05_phan_4 | 322.233s | 16112 | 322.240s | 0 | 12 | 1.00s | PASS |
| 06_phan_5_1 | 514.185s | 25709 | 514.180s | 0 | 18 | 1.00s | PASS |
| 07_phan_5_2 | 448.761s | 22438 | 448.760s | 0 | 16 | 1.00s | PASS |

- 30-second windows: confirmed (`window 0: 0.000-30.000s`).
- 1-second overlap: confirmed (`overlap=1.00s`).
- Full feature coverage: confirmed (`uncovered=0` for every part; `Feature coverage OK`
  printed for every part).
- Evidence is per-part (not aggregate): each log has its own `[Whisper Long Audio] total`
  line. WOLA ON: PASS for all 7.

## STEP 11 — CUDA Graph

Status: **CONFIRMED ON** for all 7. Per-log evidence:
- `offline_musetalk_unet: captured on cuda:0 (inputs={'audio_feat': (16, 50, 384),
  'latent': (16, 8, 32, 32)} output=(16, 4, 32, 32))` — graph capture succeeded.
- `Rendering <frames> frames in batches of 16 (multi_gpu=False, cuda_graph=True)...`
- Banner `CUDA Graph: ON`.
No `cuda graph failed`, no fallback to eager, no `LIVETALKING_CUDA_GRAPH=false`.

## STEP 12 — GPU execution

- Physical GPUs used: 2 (GPU 0 and GPU 1).
- GPU IDs per part (from log filenames + wrapper `CUDA_VISIBLE_DEVICES`):
  - GPU 0: mo_dau, phan_3, phan_4, phan_5_2  (4 parts)
  - GPU 1: phan_1, phan_2, phan_5_1        (3 parts)
- Each individual render used ONE GPU: every log shows
  `multi_gpu=False, cuda_graph=True` and `captured on cuda:0` (within that process's
  `CUDA_VISIBLE_DEVICES` scope, the bound GPU is visible as cuda:0).
- Two separate render jobs ran CONCURRENTLY (one per GPU) — this is JOB-LEVEL
  PARALLELISM via the `render_pipeline.py` 2-worker scheduler.
- It is NOT multi-GPU inference for a single video (no DataParallel; `multi_gpu=False`).
- batch_size: 16 (every log: `in batches of 16`).

Architecture: **job-level parallelism** (2 processes × 1 GPU each), not single-job
multi-GPU inference.

## STEP 13 — Render speed (from logs)

`Render done: <frames> frames in <s>s = <fps> fps` (render-loop only; wall-clock per
part from the wrapper START/DONE times is larger because it includes model load +
WOLA + mux):

| part | video dur | render-loop s | render fps | wall-clock (min) | x realtime (wall) |
|---|---|---|---|---|---|
| 01_mo_dau | 502.08s | 564.2s | 22.2 | 10.3 | 0.81× |
| 02_phan_1 | 479.88s | 530.5s | 22.6 | 9.7 | 0.82× |
| 03_phan_2 | 523.16s | 585.1s | 22.4 | 10.8 | 0.81× |
| 04_phan_3 | 335.76s | 371.6s | 22.6 | 6.9 | 0.81× |
| 05_phan_4 | 322.20s | 369.9s | 21.8 | 6.8 | 0.79× |
| 06_phan_5_1 | 514.16s | 582.1s | 22.1 | 10.6 | 0.81× |
| 07_phan_5_2 | 448.76s | 510.1s | 22.0 | 9.2 | 0.81× |

- Total output duration: 3126.0s = 52.1 min.
- Total wall-clock elapsed: first START 15:55:13 → last DONE 16:28 ≈ 33 min.
- Aggregate throughput: 52.1 / 33 ≈ 1.58× realtime (across 2 GPUs).
- Reconciles with the reported 15:55 → 16:28 (~33 min). GPU0 was the longer pole
  (4 parts, ~33 min); GPU1 did 3 parts in ~31 min.

## STEP 14 — Hidden fallback scan

Searched every log for: `fallback, disabled, failed, error, warning, cuda graph fail,
out of range, OOM, except, gain fallback, avatar fallback, WOLA fallback, model
fallback, device fallback`.

Findings:
- No gain/offset/ctx/avatar/model/WOLA/CUDA-Graph fallback occurred.
- No `[LOCKED] ... ignored` override warning (no override was attempted).
- The only warning-like lines are benign and unrelated to config:
  - `Defaulting to unsafe serialization. Pass allow_elements=False...` — a
    `torch.load` weights_only FutureWarning (loading the VAE checkpoint that lacks a
    safetensors file). Does not change any quality parameter.
  - One `UserWarning: LIVETALKING_GPU_ID=1 out of visible range [0,0]; falling back to
    cuda:0` appears in earlier test runs; in these 7 production logs the wrapper set
    `LIVETALKING_GPU_ID=0`, so the device is `cuda:0` (the single visible GPU) — this is
    the intended device binding, not a quality fallback.
- Code-level silent-substitution check: the only place `gain` could silently revert is
  `if audio_conditioning_gain != 1.0: sel = sel * gain` — gain=1.5 ≠ 1.0 so the multiply
  WAS applied (confirmed by `Audio conditioning gain: 1.500` print). No path substitutes
  gain 1.0.

Any fallback detected: NO (none that affects quality/config).

## STEP 15 — Per-file configuration matrix

| Video | Pipeline | Avatar | Gain | Ctx | Offset | FPS | Resolution | CUDA Graph | WOLA | GPU | Batch |
|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|
| 01_mo_dau.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (18w, 0 unc) | 0 | 16 |
| 02_phan_1.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (17w, 0 unc) | 1 | 16 |
| 03_phan_2.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (19w, 0 unc) | 1 | 16 |
| 04_phan_3.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (12w, 0 unc) | 0 | 16 |
| 05_phan_4.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (12w, 0 unc) | 0 | 16 |
| 06_phan_5_1.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (18w, 0 unc) | 1 | 16 |
| 07_phan_5_2.mp4 | MuseTalk v1.5 | close_up | 1.5 | 0 | -3 | 25 | 1080x1920 | ON | ON (16w, 0 unc) | 0 | 16 |

Quality settings are IDENTICAL across all 7. Only VARIABLE inputs differ: avatar is the
same (close_up) by design; GPU and WOLA-window count differ by audio length (expected).

## STEP 16 — Actual render vs production truth

| Parameter | Production truth | Actual job | Match |
|---|---|---|---|
| Pipeline | MuseTalk v1.5 | MuseTalk v1.5 (musetalkV15/unet.pth, offline_musetalk_unet) | PASS |
| Gain | 1.5 | 1.5 (banner + `Audio conditioning gain: 1.500`) | PASS |
| Context | 0 | 0 (banner from eff; no override) | PASS |
| Offset | -3 | -3 (banner + `Audio feature offset: -3 frames`) | PASS |
| FPS | 25 | 25 (ffprobe 25/1) | PASS |
| Resolution | 1080x1920 | 1080x1920 (ffprobe all 7) | PASS |
| CUDA Graph | ON | ON (captured on cuda:0; cuda_graph=True) | PASS |
| WOLA | ON | ON (per-part WOLA, overlap 1.00s, uncovered=0) | PASS |

VARIABLE inputs (report exact values):
- Avatar: `close_up` (prepared from `musetalk_4872_697362812.mp4`; NOT the 30_7 file).
- Audio: 7 master WAVs, one per part, `noble_live_25_8\audio\01_…07_*.wav`
  (48 kHz mono pcm_s16le on disk; normalized to 16 kHz inside the renderer).

## STEP 17 — Final question

Were the 7 completed videos rendered using the current locked production truth?

**YES.**

All 8 locked parameters match, verified from runtime logs (not merely from
`render_truth.json`): pipeline MuseTalk v1.5, gain 1.5, ctx 0, offset -3, 25 FPS,
1080x1920, CUDA Graph ON, WOLA ON. No override was passed by the wrapper; no fallback
occurred. The 7 videos used an identical locked quality configuration (only avatar/audio/
output/GPU varied, as intended).

Two notes (not config deviations):
1. The earlier "face from 30_7 video" statement was imprecise — the actual avatar
   `close_up` was prepared from `musetalk_4872_697362812.mp4`.
2. On-disk master WAVs are 48 kHz; the renderer normalized to 16 kHz before Whisper/mux
   (committed fix 5e295db). This is the intended, fixed behavior, not a deviation from the
   truth (the truth does not lock TTS/audio sample rate — TTS is a variable input).

## STEP 18 — No changes made

Audit-only. No rerender, no config change, no avatar change, no TTS regen, no file
moves/deletes, no commit, no new tag. The only file written is this report
(`SYSTEM_7PART_RENDER_CONFIG_AUDIT.md`), as required by the task.