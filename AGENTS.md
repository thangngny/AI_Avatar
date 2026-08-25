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
6. Do not use experimental pipelines (`experiments/`, `archive/`, the LatentSync copy)
   unless explicitly requested. Production runtime is MuseTalk v1.5 only.
7. If not on `main`, STOP and return to `main` before normal production work.
8. Preflight (optional, no models loaded): `python system_status.py`.

Do not duplicate the control board here. `SYSTEM_CONTROL_BOARD.md` is authoritative;
this file only points to it.