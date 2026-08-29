# AI Avatar Studio

A local, operator-focused studio for preparing Vietnamese-speaking AI avatar videos.
You prepare an avatar, write a script, pick a voice, preview the reading, and render
the final video with the existing MuseTalk v1.5 production renderer.

> **Note:** This project is a derivative of the
> [NeolabAI/avatar_livestream](https://github.com/NeolabAI/avatar_livestream) /
> [lipku/LiveTalking](https://github.com/lipku/LiveTalking) realtime digital-human
> work (Apache-2.0). The realtime/streaming layer is upstream; **AI Avatar Studio**
> is the local Studio UI, avatar-preparation, Vietnamese voice, and render-job
> workflow built on top of that foundation. See **Attribution** below.

## What it does

- **Studio UI** — a local web app (`AI_Avatar_Studio.bat`) at `http://127.0.0.1:8077`
  for the operator workflow: Avatar → Script → Voice → Test → Render.
- **Avatar preparation** — guided avatar source input, mouth-motion quality test, and
  per-avatar asset preparation for the production renderer.
- **Vietnamese TTS** — ElevenLabs integration tuned for Vietnamese (`eleven_v3`), with
  Edge TTS as a local fallback. Voice profiles are matched to generation settings.
- **Script voice preview** — preview the chosen voice reading the script (including a
  two-voice lock and a language resolver) before committing to a full render.
- **Production rendering** — drives the existing `generate_video_from_script.py`
  MuseTalk v1.5 renderer; master-audio / conditioning-audio reuse; production-truth
  validation.
- **Job management** — render queue, history, and management-safety controls.
- **Runtime / deployment hardening** — single-instance guard, canonical-runtime
  enforcement, code-drift detection, frontend/backend API-contract handshake, boot-id,
  and a controlled, identity-verified restart orchestrator.

## Architecture (high level)

```
AI_Avatar_Studio.bat
  └─ run_studio.py            (Flask controller; never imports torch)
      ├─ studio/app.py         (routes + system status + restart endpoints)
      ├─ studio/runtime_guard.py  (hardening: fingerprint, contract, single-instance)
      ├─ studio/render_service.py (queue worker)
      ├─ studio/elevenlabs_client.py / voices.py / preview_service.py
      └─ generate_video_from_script.py   (production MuseTalk v1.5 renderer, subprocess)
```

The controller spawns the production renderer as a subprocess using a torch-capable
interpreter; the controller itself does not load torch.

## Requirements

- **OS:** Windows 11 (developed/tested on this machine). Linux/macOS should work for
  the controller but the launcher is Windows-oriented.
- **Python:** 3.10.x for the controller. The renderer needs a torch-capable environment.
- **Canonical runtime:** a dedicated venv with the torch/CUDA stack pinned for the
  renderer (see `config/runtime_requirements_manifest.json` for the pinned versions
  and `docs/RUNTIME_ENVIRONMENT.md`). The launcher refuses to fall back to system
  Python if the canonical interpreter is missing.
- **GPU:** NVIDIA (e.g. RTX 3090) for rendering. The controller runs without a GPU.
- **ElevenLabs API key** for Vietnamese TTS (set in a local `.env` — never committed).
  Edge TTS is available as a local fallback that needs no key.

> Model weights, prepared avatar assets, and the runtime database are **not** included
> in this Git repository (see **Production notes**).

## Quick start

```bat
:: From the repository root, on Windows:
AI_Avatar_Studio.bat
```

This launches the Studio under the canonical interpreter and opens
`http://127.0.0.1:8077/`. The launcher enforces a single instance and the canonical
runtime; if a verified Studio is already running it reuses it (no duplicate server).

Operator workflow in the UI: **Avatar → Script → Voice ID → TEST 10s → RENDER**.

## Production notes

- **Not in Git:** large model weights (MuseTalk/wav2lip/whisper), prepared avatar
  latents/masks/coords, the runtime SQLite database, generated audio previews, render
  outputs, and `.env` are all intentionally gitignored and kept local. A fresh clone
  cannot render until models and avatar assets are supplied.
- **Production truth:** `config/render_truth.json` locks the production rendering
  configuration (resolution, FPS, audio settings, MuseTalk settings). Do not change it
  without an explicit, reviewed release decision.

## Security

- `.env` (containing the ElevenLabs API key) is **local-only and gitignored**. Never
  commit it. A `.env.example` template is included.
- The controlled-restart / shutdown endpoints are **owner-direct only** (localhost).
  Remote collaborators reached through a share tunnel never receive OS
  process-control privileges.
- No API keys, auth headers, or credentials are written to the runtime instance
  manifest, logs, or status API.

## Runtime hardening (V1.6)

The Studio detects when backend code on disk has changed while the server keeps
running (a stale route table caused a silent 404 in a prior incident). It surfaces a
"restart required" warning and a frontend/backend contract-mismatch banner, refuses to
accept new work until restarted, and offers a controlled, identity-verified restart.
See `docs/V1_6_RUNTIME_DEPLOYMENT_HARDENING.md` and
`docs/V1_6_RUNTIME_HARDENING_REAL_ACCEPTANCE.md`.

## Attribution

This repository builds on the realtime digital-human work from:

- **Upstream:** [lipku/LiveTalking](https://github.com/lipku/LiveTalking) (Apache-2.0)
- **Intermediate:** [NeolabAI/avatar_livestream](https://github.com/NeolabAI/avatar_livestream)

The `upstream` git remote points to `NeolabAI/avatar_livestream`. The LICENSE
(Apache-2.0) and upstream notice files are preserved. AI Avatar Studio is the local
workflow/UI/voice/render-management layer added on top.

## License

Apache License 2.0 (see `LICENSE`), inherited from the upstream LiveTalking project.
Third-party components retain their own licenses — see included component license
files where present.