# AGENTS.md

## MANDATORY STARTUP

Before modifying or running this repository:

1. Confirm the Git branch is **main** (`git branch --show-current`).
2. Read **SYSTEM_CONTROL_BOARD.md** (the shared system board).
3. Read **config/render_truth.json** (the only runtime quality/lip-sync truth).
4. Treat **render_truth.json** as the single source of truth for locked render
   parameters. Do not reintroduce quality defaults elsewhere.
5. `avatar_id`, `script`, `master audio`, and `output path` are **variable job inputs
   only** — never part of the locked truth.
6. **Never confuse a RAW avatar source with a PREPARED avatar.**
   - RAW source = the original camera `.mp4`/`.mov`/photo *before* MuseTalk
     preprocessing → `data/input/avatar_sources/` (and lineage index
     `data/avatar_sources.json`).
   - PREPARED avatar = `data/avatars/<avatar_id>/` (`full_imgs/`, `coords.pkl`,
     `latents.pt`, `mask/`, `mask_coords.pkl`, `avator_info.json`) — the generated
     asset the renderer actually consumes.
   - A `data/avatars/.uploads/*.mp4` is a RAW source, not a prepared avatar.
7. Do not use experimental pipelines (`experiments/`, `archive/`, the LatentSync copy)
   unless explicitly requested. Production runtime is MuseTalk v1.5 only.
8. If not on `main`, STOP and return to `main` before normal production work.
9. Preflight (optional, no models loaded): `python system_status.py`.

Do not duplicate the control board here. `SYSTEM_CONTROL_BOARD.md` is authoritative;
this file only points to it.