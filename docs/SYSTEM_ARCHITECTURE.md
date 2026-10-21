# System Architecture

> One-page map of the AI Avatar system. Read this with `SYSTEM_CONTROL_BOARD.md`
> (operational status) and `config/render_truth.json` (locked render parameters).

## Authoritative repository

```text
C:\CongThang_AI_Avatar\AI_avatar   (git branch: main)
```

`C:\CongThang\AI_avatar` is a **separate, non-authoritative** git repo used only as
the experimental/LatentSync workspace. Production never imports from it.

## The pipeline, end to end

```text
RAW AVATAR SOURCE                 original camera .mp4/.mov or photo
   │                              data/input/avatar_sources/   (lineage: data/avatar_sources.json)
   ▼
create_avatar.py  (avatar prep)    extracts frames, face crop, mask, latents
   │                              avatars/musetalk/genavatar.py does the work
   ▼
PREPARED AVATAR                   data/avatars/<avatar_id>/
   │                                full_imgs/  coords.pkl  latents.pt
   │                                mask/  mask_coords.pkl  avator_info.json  (version v15)
   │                              NOTE: a data/avatars/.uploads/*.mp4 is a RAW source,
   │                              NOT a prepared avatar.
   ▼
Script / Master audio (variable)  data/input/scripts/*.txt  +  *.wav  (job inputs only)
   ▼
generate_video_from_script.py     loads config/render_truth.json (LOCKED truth)
   │                              ↓ MuseTalk v1.5  (avatars/musetalk/*, models/musetalkV15)
   │                              ↓ Whisper audio features (models/whisper)
   │                              ↓ CUDA Graph + long-audio WOLA + feature-coverage guard
   │                              ↓ paste-back composite → 1080x1920 / 25 FPS
   ▼
FINAL VIDEO                       D:\CongThang_AI_Avatar\renders\<job>\  (external)
```

## Where things live (authoritative repo)

| Concern | Location |
|---|---|
| Production renderer | `generate_video_from_script.py` (root) |
| Avatar preparation | `create_avatar.py` (root) |
| System preflight | `system_status.py` (root) |
| Locked render config | `config/render_truth.json` |
| Prepared avatars | `data/avatars/<avatar_id>/` |
| Raw avatar sources | `data/input/avatar_sources/` |
| Raw-source lineage | `data/avatar_sources.json` (data only — never render settings) |
| Input scripts | `data/input/scripts/` |
| MuseTalk code | `avatars/musetalk/` |
| Realtime server code | `app.py`, `server/`, `web/`, `launcher/` (separate from production render) |
| TTS | `tts/` |
| Shared utils | `utils/` (image, device, cuda_graph, avatar_validate, …) |
| Models (gitignored) | `models/` (musetalkV15/, whisper/, syncnet/, GFPGAN) |
| Experiments / diagnostics | `experiments/` (isolated; production never imports these) |
| Archive (reports/legacy) | `archive/` |
| Docs | `docs/` |

## Subsystems (do not mix)

- **Production render** — `generate_video_from_script.py` + `avatars/musetalk/` + `utils/`
  + `config/render_truth.json` + `data/avatars/` + `models/`. The only production path.
- **Avatar preparation** — `create_avatar.py` → `avatars/musetalk/genavatar.py` writes
  `data/avatars/<id>/`.
- **Realtime server** — `app.py`, `server/`, `web/`, `tts/`, `launcher/`, `llm.py`.
  Separate product; untouched by production render.
- **Diagnostics** — `experiments/` (benchmark/sweep/stage5 scripts). Uses the LatentSync
  syncnet weight `models/syncnet/latentsync_syncnet.pt` for lip-sync scoring only;
  never invoked by production.
- **LatentSync** — experimental offline pipeline in the separate repo
  `C:\CongThang\AI_avatar`. Not reachable from `generate_video_from_script.py`.

## Locked production truth (do not change here)

See `config/render_truth.json`: MuseTalk v1.5, gain 1.5, ctx 0, offset -3, 25 FPS,
1080x1920, CUDA Graph ON, WOLA ON, feature-coverage guard ON. Avatar is a variable
input — never hardcoded.