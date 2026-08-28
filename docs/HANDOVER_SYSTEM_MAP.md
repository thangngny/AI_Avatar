# AI Avatar Studio — System Map

Plain-language architecture. Key file + function per stage.

## Main production flow (make a video)

```
Browser (studio/static: index.html, app.js, styles.css)
   │  HTTP/JSON to 127.0.0.1:8077
   ▼
Flask Studio  (studio/app.py — routes)
   │  reads/writes state
   ▼
SQLite  (studio/db.py — jobs, avatars, settings; WAL; API key NEVER here)
   │
   ├──► Avatar Library  (studio/avatar_service.py — reads data/avatars/ on disk)
   │
   ├──► TTS  (studio/render_service.generate_master_audio)
   │        ├─ ElevenLabs  (studio/elevenlabs_client.py — exact voice_id, FAIL-CLOSED, no fallback)
   │        └─ Edge TTS    (studio/edge_tts_client.py — free test, no quota, no ElevenLabs fallback)
   │        → canonical 16 kHz mono WAV  (data/studio_runtime/temp/master/*.wav, cached by content hash)
   │
   ├──► GPU scheduler  (studio/gpu_service.py — nvidia-smi detect; acquire/release; one job per GPU)
   │
   ▼
MuseTalk renderer  (generate_video_from_script.py — subprocess, torch env)
   - locked truth from config/render_truth.json (read-only, hash recorded per job)
   - env: CUDA_VISIBLE_DEVICES=<gpu> + OFFLINE_USE_MULTI_GPU=false  (per-job single-GPU isolation)
   - imports avatars.musetalk.* (models/, utils/, whisper/) from this repo
   ▼
FFmpeg (mux audio+video)  →  MP4
   ▼
Post-render verify  (studio/verify.py — ffprobe: video+audio streams, 1080×1920, ~25fps, duration)
   ▼
D:\CongThang_AI_Avatar\renders\studio\<timestamp>_<kind>_<avatar>_<label>_<uuid>.mp4
```

The render worker is a **daemon thread inside the Studio process** (studio/render_service._worker_loop / _run_job), NOT tied to any browser session. Closing the browser does NOT kill a running render.

## Create-Avatar flow

```
raw source video (data/input/avatar_sources/ or chunked upload → studio/app.py /api/uploads/*)
   ▼
validator  (tools/avatar_source_quality/validator.py — cv2 face/blur/lighting/mouth; torch env)
   ▼  (studio/avatar_service.analyze_source → human-language categories)
UI quality result + manual mouth-state confirmation (studio/static/app.js)
   ▼
prepare  (avatars/musetalk/genavatar.py — subprocess; ~20-30 min/GPU)
   ▼
prepared Avatar  (data/avatars/<id>/ : full_imgs/ + coords.pkl + latents.pt + mask.png)
   ▼
Avatar Library  (ready=1 in db; usable for renders)
```

## Remote collaboration flow

```
collaborator browser
   ▼  https://<random>.trycloudflare.com
Cloudflare Quick Tunnel  (cloudflared process — separate from Studio)
   ▼  proxy to 127.0.0.1:8077
Studio (Flask)  ← share_auth.py (link-only access, no auth code by default since V1.2.2)
```
The tunnel is a separate process. If cloudflared dies or the host sleeps, remote access stops but the local Studio + any running render continue.

## Single points of control
- **Runtime interpreter resolution**: `studio/runtime.py` (the ONLY place the torch-python path is hardcoded; overridable via `STUDIO_TORCH_PYTHON` env).
- **Paths/config**: `studio/config.py` (ROOT-relative except RENDERS_DIR = D: drive).
- **Production truth**: `config/render_truth.json` (read-only; `system_status.py` validates it).