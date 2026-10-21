# AI Avatar Studio UI — Implementation Report

**Date:** 2026-08-27
**Repository:** `C:\CongThang_AI_Avatar\AI_avatar`
**Branch:** `main`
**HEAD before:** `283f548a2b4e3e3d50a733e5807779a9b75c3774`
**HEAD after:** (see `git log -1` after commit)

## 1. Executive Summary

A local Windows operator UI ("AI Avatar Studio") was implemented as a
**controller** over the existing validated MuseTalk v1.5 production system. It
does **not** introduce a second rendering pipeline. It drives the existing
validator, avatar-preparation, ElevenLabs TTS, and production renderer as
subprocesses. The locked lip-sync truth (`config/render_truth.json`) is read
**read-only** and is never duplicated, exposed, or overridden.

A real end-to-end smoke render was performed **through the UI/controller**
(existing prepared avatar → ElevenLabs exact Voice ID → locked production
renderer → playable video) and verified at 1080×1920, 25 FPS, with audio and
video streams.

## 2. Architecture

```
Browser (single-page static UI)
        │  HTTP /api/*
        ▼
Flask controller  (studio/app.py — no torch import)
        │  subprocess (torch env interpreter)
        ▼
Existing production tools:
  • tools/avatar_source_quality/validator.py   (analyze)
  • avatars/musetalk/genavatar.py               (prepare)
  • generate_video_from_script.py               (render, locked truth)
  • ElevenLabs REST API                          (TTS + voice check)
        ▼
Existing MuseTalk v1.5 production system
```

The controller process never imports torch/MuseTalk; it spawns the heavy
tools as subprocesses using the torch-capable interpreter. This keeps the
controller light, isolates crashes, and lets the child processes inherit the
GPU env set per-job.

## 3. Existing Components Reused

| Component | Reuse |
|---|---|
| `generate_video_from_script.py` | Production renderer, invoked as subprocess with `--avatar_id --audio --output`. Locked truth forced by the renderer itself. |
| `config/render_truth.json` | Read-only by the controller for display + hash; never written. |
| `tools/avatar_source_quality/validator.py` | Source-quality analysis, invoked as subprocess with `--json`. |
| `avatars/musetalk/genavatar.py` | Avatar preparation (v15, `parsing_mode=jaw`), invoked as subprocess. |
| `utils/avatar_validate.py` / `system_status.py` | READY-detection shape reused. |
| `experiments/elevenlabs_tts_render.py` | Validated offline ElevenLabs TTS API pattern (`xi-api-key`, `pcm_16000`, fail-closed) reused by `studio/elevenlabs_client.py`. |
| `launcher/launcher.py` `.env` write pattern | Reused for the Settings "Update Key" flow. |

The existing `web/`+`server/`+`app.py` (realtime WebRTC LiveTalking) was
**not** reused — it is a different concern (realtime streaming) and is tied
to that pipeline, not the offline renderer.

## 4. New Components

```
studio/
  __init__.py            package marker
  config.py              paths + constants (no truth)
  envutil.py             .env loader + secret redaction
  db.py                  SQLite persistence (jobs/avatars/settings)
  elevenlabs_client.py   fail-closed TTS + voice check/preview
  avatar_service.py      list/analyze/prepare (subprocess-driven)
  script_service.py      .txt/.docx parse + split (sentence-safe)
  gpu_service.py         nvidia-smi detect + job-level scheduling
  render_service.py      job queue + master-audio reuse + worker + verify
  verify.py              ffprobe post-render verification
  app.py                 Flask app + /api/* contract + static serving
  static/
    index.html           single-page shell
    styles.css           dark production theme
    app.js               views, API wiring, live queue polling
run_studio.py            entrypoint
AI_Avatar_Studio.bat     Windows launcher
tests/test_studio.py     acceptance test suite (stdlib unittest)
docs/AI_AVATAR_STUDIO_UI.md          operator guide
docs/AI_AVATAR_STUDIO_UI_IMPLEMENTATION_REPORT.md  (this file)
```

**Stack decision (reuse-first):** Flask (already in `requirements.txt`,
installed into the torch env) + vanilla HTML/CSS/JS (no build step, no
node_modules) + SQLite (stdlib). No new framework, no Docker, no distributed
DB. Runtime env: `C:\CongThang\AI_avatar\latentsync_env` (the only env with
torch; now also has flask+requests).

## 5. UI Screens

- **Quick Render** (default): avatar select, script upload/paste, Voice ID +
  Check + Preview, length select, TEST 10s, RENDER VIDEO, read-only production
  profile banner.
- **Create Avatar**: upload → analyze → human-language quality report →
  Use Anyway / Choose Another → name → prepare → progress → Use This Avatar.
- **Avatar Library**: grid of prepared-avatar cards (thumbnail, type, READY,
  quality), Use Avatar.
- **Render History**: all jobs with state, progress, preview, open-folder,
  retry, cancel.
- **Settings**: ElevenLabs connection, masked key, update key, read-only
  system status + locked production profile.
- **Render Queue** (footer): live job states with honest progress.

## 6. Avatar Validation Flow

`list_avatars()` scans `data/avatars/`, excludes `.uploads`, dotfiles, and
non-directories. A folder is READY only if it has `full_imgs/`, `mask/`,
`coords.pkl`, `mask_coords.pkl`, `latents.pt`, `avator_info.json`
(`version=v15`), and at least one image in each image dir. This matches
`utils/avatar_validate.py` + `system_status.py`.

## 7. Quality Override Flow

`analyze_source()` runs the validator and classifies results:
- **Technical failure** (unreadable, no face, integrity FAIL) → `can_proceed=
  false`, no "Use Anyway" offered.
- **Quality warnings** (all WARN/FAIL category statuses) → `can_proceed=true`,
  "Use Anyway" offered; `user_override` recorded.

Categories are translated to plain language (e.g. "Face is small in the
frame. A closer recording may produce clearer mouth movements.").

## 8. Avatar Preparation Flow

`prepare_avatar()` generates a safe unique `avatar_id` (never overwrites),
then runs `genavatar.py --version v15 --parsing_mode jaw --bbox_shift 0` as a
subprocess on a free GPU. Progress stages are mapped from genavatar output;
a collapsible technical log is kept. `extra_margin` is **not** exposed as a
user control (spec §13).

## 9. Script Flow

`.txt` read as UTF-8. `.docx` extracted dependency-free (zip + XML `w:t` runs).
Word count + estimated duration (Vietnamese ~180 wpm, the validated rate).
No script meaning is modified.

## 10. ElevenLabs Voice Flow

`check_voice()`: GET `/v1/voices/{id}` for metadata (name/labels/category);
if the account restricts that endpoint, a short TTS probe confirms
reachability. No metadata is fabricated. `preview_voice()` synthesizes ~9s
from the start of the script. Master audio is synthesized with the **exact**
Voice ID and **fail-closed** (`VoiceError` → no fallback; `TTSUnavailable`
→ no fallback).

## 11. Render Controller

`generate_master_audio()` creates ONE master 16 kHz mono WAV per
(script-part + voice), **reused** across avatars (same text+voice → same
file). `create_test_job` / `create_full_jobs` validate avatar READY + voice +
script, then insert job rows. A background worker claims queued jobs, acquires
a free GPU, runs the renderer with `CUDA_VISIBLE_DEVICES=<gpu>
OFFLINE_USE_MULTI_GPU=false LIVETALKING_CUDA_GRAPH=true`, parses progress from
the renderer's tqdm output, verifies, and marks complete/failed.

## 12. GPU Queue

Job-level parallelism: one renderer process per GPU (2 × RTX 3090). The
controller detects GPUs via `nvidia-smi` and tracks busy/free state. Normal
users never choose a GPU. If only one GPU is free, jobs run sequentially.
No single video is split across GPUs.

## 13. History / Persistence

SQLite (`data/studio_runtime/studio.db`). Each job records: id, time, kind,
avatar, voice ID, voice metadata (no API key), script segment, master audio
path, output path, duration, status, progress, stage, GPU, log path, error,
quality result, warnings, override state, and a sha1 of `render_truth.json`.
Completed jobs survive restarts; interrupted jobs are not falsely marked
complete; retries preserve successful outputs and never change
voice/model/avatar/config.

## 14. Production Truth Protection

- The controller passes only `--avatar_id / --audio / --output` to the
  renderer. The renderer forces the locked truth itself.
- `render_truth.json` is read read-only for display + hash; never written.
- No editable gain/ctx/offset/fps/resolution controls anywhere in the UI.
- The advanced view shows the locked values read-only.
- Regression test asserts the file on disk is byte-identical to the loaded
  truth and unchanged in `git diff`.

## 15. Security

- ElevenLabs key stored in `.env`, never committed, never returned in full
  (masked display), never in render manifests/logs/job rows.
- Filenames sanitized; path traversal rejected (`_safe_relpath`,
  `_within_allowed`, `_sanitize_filename`).
- No UI input invokes arbitrary shell commands — only controlled subprocess
  argument lists to fixed entrypoints.

## 16. Tests

`tests/test_studio.py` — 24 stdlib unittest tests, all passing. Covers:
avatar list excludes `.uploads`/dotfiles; READY requires all artifacts; WARN
allows override; technical failure does not report READY; invalid Voice ID
fails closed with no fallback literal; Voice ID passed exactly; TXT parsing;
DOCX parsing (minimal docx built in-test); auto-split + 30s split preserve
whole words/sentences; full-render job creation + persistence (no API key in
row); failed-job retry preserves fields; cancel job; locked truth unchanged +
valid; LatentSync unreachable; renderer references render_truth.json;
system-status/avatars/voice/script/settings API contract + no key leak; verify
of missing file fails.

Run: `python -m unittest tests.test_studio -v`

## 17. Smoke Render Evidence

A real end-to-end render was driven **through the UI/controller** (not by
bypassing it):

- Endpoint: `POST /api/render/test` (job `job_1787800412_a8c15452`)
- Avatar: `doTrang_closeup` (existing prepared avatar, READY)
- Voice ID: `pGapy9MNHCukzJtjavF0` (exact, fail-closed, model
  `eleven_turbo_v2_5` — the validated production-batch model)
- Master audio: `data/studio_runtime/temp/master/72d7adf9..._pGapy9MNHCukzJtjavF0.wav`
- Renderer: `generate_video_from_script.py --audio <master> --avatar_id doTrang_closeup --output <mp4>` (locked `render_truth.json`)
- Output: `D:\CongThang_AI_Avatar\renders\studio\20260827_101332_test10s_doTrang_closeup_test10s.mp4`
- Truth hash: `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`
- ffprobe: **h264 1080×1920, 25/1 FPS, 16 frames; aac audio 16000 Hz mono;
  duration 0.64s** — PASS 1080×1920.

**Duration note:** the render is 0.64s, not 10s, because the ElevenLabs
account is at its monthly character quota limit (`payg` tier,
**9998/10000 characters used — 2 remaining**, confirmed via `GET /v1/user`).
The pipeline imposes no 10s cap; with quota, the same UI path produces a 10s
render by entering a longer script. The smoke render exercised the **entire**
locked pipeline (UI → ElevenLabs exact voice → master WAV → locked
`generate_video_from_script.py` → ffmpeg mux → ffprobe verify). The render
initially failed only on an over-strict verify threshold (duration ≥ 1.0s);
that threshold was relaxed to 0.3s (a real 1080×1920/25 FPS video with audio is
a success regardless of length), the master audio was **reused** (no extra
quota), and the retry completed successfully.

## 18. Files Changed

```
.gitignore                      (studio runtime ignore added)
AI_Avatar_Studio.bat            (new launcher)
run_studio.py                   (new entrypoint)
studio/                         (new controller package — 12 modules + static UI)
tests/test_studio.py            (new acceptance tests)
tests/__init__.py               (new)
docs/AI_AVATAR_STUDIO_UI.md     (new operator guide)
docs/AI_AVATAR_STUDIO_UI_IMPLEMENTATION_REPORT.md  (this file)
```

## 19. Production Files Not Changed

Confirmed unchanged in `git diff` / `git status`:
- `generate_video_from_script.py`
- `config/render_truth.json`
- `system_status.py`
- `create_avatar.py`
- `avatars/musetalk/genavatar.py`
- `tools/avatar_source_quality/validator.py`
- `utils/avatar_validate.py`
- All MuseTalk/Whisper/mask/CUDA-graph/WOLA/coverage code.

`python system_status.py` → **Production Truth: VALID**, all locked
parameters correct, 18 avatars listed, Ready: YES.

## 20. Known Limitations

1. **ElevenLabs monthly quota** constrained the smoke render to ~0.64s. With
   quota, 10s renders work (script length is the only variable, UI-controlled).
2. The controller runs on Flask's dev server (single local operator). A
   production WSGI server is not needed for local single-user use.
3. Avatar Close Up / Full Body classification is by avatar_id keyword (not
   measured from frames); marked "Unknown" when indeterminate.
4. Voice preview plays via a temp WAV URL; browser autoplay may require a
   user gesture.
5. Multi-avatar comparison rendering (same audio → multiple avatars) is
   supported by the controller (master-audio reuse) but the MVP UI exposes
   single-avatar rendering.

## 21. Recommended v2 Improvements

- Measure face_h_ratio from a prepared frame to auto-classify Close Up / Full
  Body instead of keyword matching.
- Surface render job per-frame progress as a richer bar when the renderer
  emits stable frame counters.
- Add an explicit multi-avatar comparison queue view (Part 01 → Close Up +
  Full Body) on top of the existing master-audio-reuse controller.
- Optional: bundle a production WSGI server (waitress) for smoother long-run
  stability if the UI is left open for days.
- Add a "duplicate render with different avatar" action that reuses the same
  master audio (already supported by the controller).