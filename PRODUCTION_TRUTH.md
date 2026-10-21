# ONE PRODUCTION TRUTH

The AI Avatar offline renderer has exactly **one** locked render-quality / lip-sync
configuration. Any valid prepared avatar + master audio flows through the SAME validated
MuseTalk pipeline. The **avatar is a variable input**; the quality config is **not**.

```
                 ANY VALID PREPARED AVATAR
                        │
                        ▼
               VARIABLE avatar_id
                        │
                        ▼
        ┌─────────────────────────────┐
        │   ONE PRODUCTION TRUTH      │
        │  MuseTalk v1.5              │
        │  gain 1.5                   │
        │  ctx 0                      │
        │  offset -3                  │
        │  25 FPS                     │
        │  1080x1920                   │
        │  CUDA Graph ON               │
        │  WOLA ON                     │
        └─────────────────────────────┘
                        │
                        ▼
                   FINAL VIDEO
```

There must NOT be `avatar A → config A, avatar B → config B`. Instead
`avatar A, B, C → SAME LOCKED CONFIG`.

## Locked render truth

| parameter | locked value | set by |
|---|---|---|
| pipeline | MuseTalk v1.5 (`musetalk_v15` / `version=v15`) | `config/render_truth.json` |
| audio_gain | 1.5 | `config/render_truth.json` |
| audio_context_left | 0 | `config/render_truth.json` |
| audio_feature_offset_frames | -3 | `config/render_truth.json` |
| fps | 25 | `config/render_truth.json` |
| resolution | 1080x1920 (composite_max_dim 1920) | `config/render_truth.json` |
| CUDA Graph | ON | `config/render_truth.json` → `LIVETALKING_CUDA_GRAPH` |
| long-audio WOLA | ON | `avatars/musetalk/whisper/audio2feature.py` (chunked WOLA) |
| feature coverage guard | ON | assertion in `generate_video_from_script.py:render_video` |

**Canonical config file:** `config/render_truth.json` — contains ONLY locked render
parameters. It does NOT contain `avatar_id`, `script`, `audio`, or `output` (those are
job inputs).

## Allowed VARIABLE inputs (per job)

- `avatar_id` — any valid prepared avatar under `data/avatars/<id>/`.
- `script` (text for EdgeTTS) **or** `audio` (master WAV) — the lip-sync renderer consumes
  a master audio file; TTS is just one way to produce it (Phase 14 / TTS separation).
- `output` path.

## NOT allowed to vary in production

`model` · `gain` · `context` · `offset` · `FPS` · `resolution` · `CUDA Graph` · `WOLA`.

The production entrypoint **forces** these from `config/render_truth.json`. Passing
`--audio-gain`, `--audio-context-left`, `--audio-feature-offset-frames`, or `--fps` on the
normal production command line is **ignored** with a `[LOCKED] ... ignored` warning. They
are honored ONLY under `--experimental-config`, which flags the run as
`EXPERIMENTAL CONFIG — NOT PRODUCTION TRUTH`.

**Changing the avatar does NOT mean changing the render configuration.**

## One production entrypoint

```
generate_video_from_script.py
```

Usage:

```bash
# master audio (recommended — TTS is separated from the render truth)
python generate_video_from_script.py \
  --avatar-id <avatar_id> --audio <master.wav> --output <out.mp4>

# or EdgeTTS convenience (TTS provider/voice is NOT part of the render truth)
python generate_video_from_script.py \
  --avatar-id <avatar_id> --script <script.txt> --output <out.mp4>
```

Both jobs automatically use gain 1.5 / ctx 0 / offset -3 / 25 FPS / 1080x1920 /
CUDA Graph ON / WOLA ON without passing those values manually.

Every production render prints a banner stating the locked config, the variable job
inputs, and the config source. The renderer **fails closed** (exit 1, no silent fallback)
when:
- `config/render_truth.json` is missing or invalid;
- MuseTalk v1.5 weights (`models/musetalkV15/`, `models/whisper/`) are missing;
- the selected avatar is missing or not v15-compatible (see Avatar validation below).

It never falls back to another avatar, to gain 1.0, to a different FPS, or to LatentSync.

## Avatar compatibility validation

Before render, `utils/avatar_validate.validate_avatar(avatar_id)` checks that the avatar
under `data/avatars/<id>/` is compatible with the MuseTalk v1.5 production pipeline:
`full_imgs/` (≥1 frame), `mask/` (≥1 frame, same count), `coords.pkl`, `mask_coords.pkl`,
`latents.pt`, `avator_info.json` with `version == "v15"`, and consistent frame counts.

This **only** checks compatibility — it never changes the render truth. If an avatar is
incompatible, preprocess it with `avatars/musetalk/genavatar.py` (`--version v15`); do
NOT modify the production pipeline to accommodate one avatar.

## LatentSync — experimental, not production

LatentSync is a separate, higher-latency diffusion inpainting pipeline. It lives in a
separate working copy (`C:\CongThang\AI_avatar`, branch `experiment/latentsync-master-plus`)
and is used only for offline research/experiments. The production entrypoint
(`generate_video_from_script.py`) and its imports never reference `avatar_export`,
`latentsync`, or `export_avatar` — the production path is MuseTalk-only and must never
silently route to LatentSync.

## Interpreter

The production renderer runs under the shared torch env
`C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe` (which also serves the
LatentSync experimental copy). The separation is about **code paths / entrypoints**, not
the interpreter:

```bash
cd C:\CongThang_AI_Avatar\AI_avatar
set CUDA_VISIBLE_DEVICES=1
C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe generate_video_from_script.py \
  --avatar-id <id> --audio <master.wav> --output <out.mp4>
```

## Repository layout after consolidation

| path | role | tracked |
|---|---|---|
| `generate_video_from_script.py` | **THE production entrypoint** | yes |
| `config/render_truth.json` | locked render truth (ONLY render params) | yes |
| `utils/avatar_validate.py` | avatar compatibility validator | yes |
| `create_avatar.py` | avatar prep helper | yes |
| `avatars/`, `utils/`, `tts/`, `models/`, `data/`, `server/`, `streamout/`, `web/` | production libs / assets | yes |
| `app.py`, `config.py`, `registry.py`, `llm.py` | realtime server (separate validated product) | yes |
| `experiments/` | diagnostic / experimental SOURCE scripts (Stage3/4/5, sweeps, diags, audits) | yes |
| `archive/reports/` | historical SYSTEM_*.md reports + handoff notes | yes |
| `diagnostics/` | ignored local runtime/debug ARTIFACTS (images, dumps) | no (gitignored) |

Files kept at the repo root that are **ops/build, not production render** (so they are not
mistaken for quality config): `run_*.ps1`, `build_*.spec` / `build_*.bat` / `build_*.ps1`,
`assemble_deliverable.ps1`, `setup_smoketest.ps1`, `start_dual_gpu.ps1`, `play_script.py`
(realtime `/human` client), `Dockerfile`, `README*.md`, `quickstart.md`, `LICENSE`.

## Realtime server (out of scope)

`app.py` + `config.py` + `utils/tuning.py` + `avatars/musetalk_avatar.py` drive the realtime
WebRTC server, a separate validated product with its own env knobs. The locked truth in
`config/render_truth.json` scopes to the **offline** production renderer only and does not
modify the realtime server.