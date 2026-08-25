# CURRENT_STABLE_BUILD.md — AI Avatar Lip-Sync Stable Checkpoint

This documents the current known-good, frozen state of the AI Avatar offline
MuseTalk lip-sync pipeline. It is the fallback to return to if any future
development (50 FPS interpolation, ElevenLabs, GFPGAN, LatentSync, new avatars,
multi-GPU, etc.) introduces a regression.

**Do not develop new features from this tag in place.** Create a new branch off
this tag for future work so this checkpoint stays clean.

---

## Identity

- **Stable tag:** `ai-avatar-lipsync-v1-stable` (annotated, local only)
- **Commit SHA:** `7cd59cebf2fbabffb058712c696f22d5990a3e5c`
- **Branch:** `checkpoint/lipsync-stable-v1`
- **Date:** 2026-08-24
- **Base:** `main` (NeolabAI/avatar_livestream), ahead of origin by 2 commits.
  Not pushed to any remote.

### Recovery

Return to this known-good state at any time with:

```bash
git checkout ai-avatar-lipsync-v1-stable
```

This tag is the known-good fallback. If a future branch breaks lip-sync, checkout
this tag to restore the validated system.

---

## Production configuration

| Setting | Value |
| --- | --- |
| Resolution | 1080x1920 (composite long-side capped at 1920) |
| FPS | 25 |
| Model | MuseTalk v1.5 (`models/musetalkV15/unet.pth`) |
| Audio features | Whisper tiny (`models/whisper`), ~50 Hz |
| `audio_context_left` | **0** (future-only 10-feature window `[center, center+10)`) |
| `audio_feature_offset_frames` | **-3** (-120 ms; center = (i-3)*2) |
| CUDA Graph | **ON** (single-GPU, fixed shape `[16,50,384]` audio / `[16,8,32,32]` latent) |
| Long-audio method | WOLA windowed extraction, 30 s windows, 1.00 s overlap |
| Multi-GPU (offline) | DataParallel only when 2+ GPUs visible and `OFFLINE_USE_MULTI_GPU!=false` |
| Face enhance | OFF (GFPGAN not installed) |
| Encoding | ffmpeg libx264 ultrafast CRF16, rawvideo pipe |
| TTS | EdgeTTS `vi-VN-HoaiMyNeural` (ElevenLabs NOT integrated) |

Realtime pipeline: **untouched** by this checkpoint (changes are offline-only;
`avatars/musetalk/whisper/audio2feature.py` preserves the ≤30 s single-call path
the realtime pipeline uses).

---

## Validation results (final regression, 2026-08-24)

| Check | Result |
| --- | --- |
| 10 s render (ctx0 / off-3) | PASS — av_offset 0, sync_conf 0.492, lse_c 0.329, CUDA Graph ON |
| 31 s feature coverage | PASS — 1550 features, no 30 s truncation |
| 55 s feature coverage | PASS — 2761 features (uncovered 0) |
| 167.6 s feature coverage | PASS — 8383 features (uncovered 0) |
| 55 s render (ctx0 / off-3) | PASS — av_offset 0 in every segment 0-50 s; no freeze past 30 s |
| 90 s render (ctx0 / off-3) | PASS — av_offset 0 across 30 s & 60 s WOLA boundaries |
| Mouth freeze after 30 s | NONE |
| Feature truncation | NONE |
| Timing drift | NONE (constant av_offset 0) |
| WOLA boundary failure | NONE |
| CUDA Graph | PASS (captured, replayed on all renders) |
| Realtime regression | PASS (realtime path not modified) |

## Stage 4 articulation A/B/C (script_artic.txt, byte-identical audio)

| Context Left | Offset | Sync Confidence | LSE-C | AV Offset | Verdict |
| --: | --: | --: | --: | --: | --- |
| 0 | -3 | 0.51400 | 0.26132 | 0 | **BEST (production)** |
| 4 | -3 | 0.41922 | 0.16190 | -1 | worse |
| 5 | -3 | 0.37653 | 0.12224 | -1 | worse |

Symmetric/realtime-style context degrades sync and shifts timing without
improving articulation (mouth-shape diversity and motion identical within noise
across ctx0/4/5). Production stays `audio_context_left = 0`.

---

## Committed files in this checkpoint

Production code:
- `avatars/musetalk/whisper/audio2feature.py` — Stage 2 WOLA long-audio fix
- `generate_video_from_script.py` — Stage 3 temporal offset + Stage 4 audio-context
  parameter, inline context-aware feature slice

Engineering reports (committed):
- `SYSTEM_LIPSYNC_DIAGNOSIS.md`
- `SYSTEM_LIPSYNC_FIX_REPORT.md`
- `SYSTEM_LIPSYNC_STAGE3_REPORT.md`
- `SYSTEM_LIPSYNC_STAGE4_REPORT.md`

## Intentionally left untracked (regression/diagnostic tooling, not production)

`diag_*.py`, `score_segments.py`, `sweep_musetalk_audio_offset.py`,
`sweep_musetalk_context.py`, `test_feature_coverage.py`, `script_*.txt`.
Rendered MP4s, master WAVs, sweep outputs, and SyncNet JSONs live on `D:\` and
are never committed.

---

## How to render from this checkpoint

```bash
cd C:\CongThang_AI_Avatar\AI_avatar
set CUDA_VISIBLE_DEVICES=1
python generate_video_from_script.py \
  --script script_50s.txt --avatar_id fullbody_30_7_25fps \
  --output D:\CongThang_AI_Avatar\renders\out.mp4 \
  --audio-context-left 0 --audio-feature-offset-frames -3
```

(Defaults already are ctx0 / off-0; pass `--audio-feature-offset-frames -3`
explicitly for the validated production timing.)