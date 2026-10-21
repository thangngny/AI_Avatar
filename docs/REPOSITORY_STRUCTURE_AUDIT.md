# Repository Structure Audit

> Restructure performed 2026-08-26 on `main`. Discovery + safe reorganization only.
> **Production behavior was not changed** (verified by smoke render).
> Authoritative repo: `C:\CongThang_AI_Avatar\AI_avatar` (git, branch `main`).

## Before — main structural problems

1. **Repo root was a dumping ground.** ~40 loose files: input scripts
   (`script_*.txt`), build artifacts (`.spec`, `build_*.ps1/bat`), build logs
   (8+ `.log` files), 16 disposable `temp<uuid>.mp4/.aac` render outputs, a
   **903 MB** `livetalking.log`, two stray raw test videos (`Hearing-1.mp4`,
   `half.mp4`), zero-byte junk (`torchaudio.functional.resample`,
   `utils.app_root.app_root()`), `gen.b64`, and historical reports
   (`SYSTEM_7PART_RENDER_CONFIG_AUDIT.md`, `README_target.txt`).
2. **Raw source vs prepared avatar was conflated.** `data/avatars/.uploads/*.mp4`
   (raw uploaded sources) sat beside `data/avatars/<id>/` (prepared assets) with
   no index or documentation distinguishing them. There was no manifest mapping
   each prepared avatar back to its original source video.
3. **No `docs/` dir.** `quickstart.md` and operational docs were loose in root.
4. **Stale source paths.** 12 of 13 prepared avatars' `avator_info.json`
   `video_path` pointed at now-deleted `D:\Noble`, `D:\AI_avatar`,
   `D:\AI_avatar_ship` paths; only one surviving copy (`30_7_fullbody`) was
   relocated to the C: project copy with no record.

## Production dependency map

`generate_video_from_script.py` (the only production renderer) depends on:

```
config/render_truth.json            (LOCKED truth; loaded via __file__)
avatars/musetalk/utils/utils.py     load_all_model
avatars/musetalk/myutil.py          get_image_blending
avatars/musetalk/whisper/audio2feature.py   Audio2Feature
utils/image.py                     read_imgs, mirror_index
utils/device.py                    initialize_device
utils/cuda_graph.py                GraphRunner
utils/avatar_validate.py           validate_avatar
./data/avatars/{avatar_id}/        prepared avatar (hardcoded relative path)
./models/musetalkV15/ , ./models/whisper/   model weights
models/GFPGANv1.4.pth              (optional face enhance)
```

It imports **only** `avatars.musetalk.*` and `utils.*`. It does **not** import
`experiments/`, `archive/`, or anything LatentSync. Avatar preparation
(`create_avatar.py` → `avatars/musetalk/genavatar.py`), the realtime server
(`app.py`/`server/`/`web/`/`launcher/`), and diagnostics (`experiments/`) are
separate subsystems and were not mixed.

## Duplicate / legacy areas

| Path | Classification |
|---|---|
| `C:\CongThang\AI_avatar` | **Separate git repo**, branch `experiment/latentsync-master-plus`, no tags. This is the **experimental / LatentSync workspace** (matches control board §8). Not authoritative; production never imports from it. Left untouched. |
| `C:\CongThang_AI_Avatar\AI_avatar` | **Authoritative repo** (`main`, 3 stable tags). |
| `D:\CongThang_AI_Avatar\noble_live_25_8\` | External completed 7-part job output. Indexed in `data/avatar_sources.json`-style external references; not moved. |
| `D:\CongThang_AI_Avatar\renders\` | External production output dir (default `--output`). Not in repo (gitignored). |
| Root build scripts (`build_*.ps1/.spec/.bat`, `assemble_deliverable.ps1`, `gen.b64`) | Coupled build/ship unit referencing root layout by `$root`. **Deferred** (see tech debt). |

## Target structure

Production-first, with raw/prepared/output separation. Adapted to actual code
dependencies (prepared avatars left at `data/avatars/<id>` because the renderer
hardcodes that path — moving them would break production; raw-vs-prepared
separation is achieved via `data/input/avatar_sources/` + `data/avatar_sources.json`
+ docs instead):

```
AI_avatar/
├── config/              render_truth.json (locked)
├── data/
│   ├── avatars/<id>/    PREPARED avatars (full_imgs/, coords.pkl, latents.pt, mask/, ...)
│   ├── .uploads/        RAW uploaded sources (NOT prepared avatars)
│   ├── input/
│   │   ├── avatar_sources/   RAW source videos (.mp4/.mov) + photos
│   │   └── scripts/          input scripts (script_*.txt)
│   ├── recordings/
│   └── avatar_sources.json  RAW-source lineage index (data only)
├── models/              musetalkV15/, whisper/, syncnet/, GFPGAN (gitignored)
├── docs/               SYSTEM_ARCHITECTURE.md, quickstart.md, REPOSITORY_STRUCTURE_AUDIT.md
├── archive/reports/    historical SYSTEM_*.md reports + README_target.txt
├── experiments/        isolated diagnostics/sweeps/stage5 (production never imports)
├── diagnostics/        (gitignored local runtime artifacts)
├── tools/, scripts/, launcher/, build/, utils/, avatars/, tts/, web/, server/
├── generate_video_from_script.py   (production renderer)
├── create_avatar.py                (avatar preparation)
├── system_status.py                 (preflight)
├── SYSTEM_CONTROL_BOARD.md, AGENTS.md, PRODUCTION_TRUTH.md, README*.md, LICENSE
```

## Files moved

- `SYSTEM_7PART_RENDER_CONFIG_AUDIT.md` → `archive/reports/` (git mv)
- `README_target.txt` → `archive/reports/` (git mv)
- `SYSTEM_BEST_RAW_AVATAR_SOURCE_AUDIT.md` → `archive/reports/` (mv, prior audit)
- `quickstart.md` → `docs/quickstart.md` (git mv)
- `script_5min.txt`, `script_example.txt` → `data/input/scripts/` (git mv)
- `script_20s/20s_b/50s/90s/artic/artic_short/stage5_3min/stage5_continuous/stage5_long.txt` → `data/input/scripts/` (mv, 9 files)
- `Hearing-1.mp4`, `half.mp4` → `data/input/avatar_sources/` (raw sources, mv)
- 8 stray build logs → `logs/` (mv, gitignored)
- `docs/_migration_manifest.txt` records the full manifest.

## Files archived

Historical reports relocated to `archive/reports/` (see above). No valuable
Stage 1–6 evidence was deleted.

## Files deleted (gitignored disposable only)

- 16 `temp<uuid>.mp4` / `temp<uuid>.aac` disposable render outputs (~260 MB)
- `livetalking.log` (903 MB realtime runtime log, regenerable)
- zero-byte junk: `torchaudio.functional.resample`, `utils.app_root.app_root()`,
  `_pa_stdout.log`, `build_run2.err.log`, `build_run3.err.log`

No tracked source file was deleted. Full deletion list in `docs/_migration_manifest.txt`.

## External paths preserved

- `C:\CongThang\AI_avatar` (LatentSync/experimental repo) — untouched.
- `D:\CongThang_AI_Avatar\noble_live_25_8\` — completed job, not moved (indexed).
- `D:\CongThang_AI_Avatar\renders\` — production output dir, untouched.
- `D:\CongThang_AI_Avatar\avatar_source_audit\` — prior-audit contact sheets.

## Hardcoded paths

Production code uses repo-relative paths (`config/render_truth.json` via
`__file__`, `./data/avatars/{id}`, `./models/...`). These were **intentionally
left unchanged** — they are stable and changing them is high-risk. The only
hardcoded absolute path in the renderer is the `--output` default
(`D:\CongThang_AI_Avatar\renders\output.mp4`), which is an external output
location and was left as-is. No hardcoded paths were "fixed" by moving files;
hardcoded-path cleanup was scoped to read-only classification (see tech debt).

## Regression results

| Check | Result |
|---|---|
| `config/render_truth.json` locked values unchanged | **PASS** (gain 1.5, ctx 0, offset -3, 25 FPS, 1080x1920, CUDA Graph ON, WOLA ON, coverage guard ON) |
| `system_status.py` | **PASS** — Branch: main, Production Truth: VALID, 13 avatars discovered (close_up READY, fullbody_30_7_25fps READY) |
| `validate_avatar(close_up)` | **PASS** (980 frames, v15) |
| `validate_avatar(fullbody_30_7_25fps)` | **PASS** (810 frames, v15) |
| Production import isolation (no experiments/archive/latentsync) | **PASS** |
| LatentSync not reachable from production | **PASS** (renderer imports only musetalk + utils) |
| Short smoke render (close_up, 5.5 s) | **PASS** — 1080x1920 / 25 fps / h264+aac, 5.56 s, locked config confirmed in banner, CUDA graph captured, feature coverage OK |

Smoke render output: `D:\CongThang_AI_Avatar\renders\smoke\smoke_close_up.mp4`

## Remaining technical debt (deferred — needs dedicated regression)

1. **Prepared-avatar path migration** (`data/avatars/<id>` →
   `data/avatars/prepared/<id>`): would require editing 4 production files
   (`generate_video_from_script.py:150`, `utils/avatar_validate.py`,
   `avatars/musetalk_avatar.py:123`, `config.py:47`) + the control board +
   all `avator_info.json` consumers, with full regression. Deferred to avoid
   production disruption; raw/prepared separation is already clear via index + docs.
2. **Build/ship script consolidation**: `build_*.ps1/.spec/.bat`,
   `assemble_deliverable.ps1`, `gen.b64` form a coupled unit referencing root
   layout by `$root`; moving them needs build-flow regression (PyInstaller/pyarmor),
   which this task does not run. Left in root.
3. **Operator launchers** (`run_*.ps1`, `start_dual_gpu.ps1`, `setup_smoketest.ps1`):
   coupled to `launcher/launcher.py` (which resolves `run_target.ps1` by path).
   Left in root to avoid breaking the realtime launcher.
4. **Stale raw-source paths**: 12/13 `avator_info.json` `video_path` values point
   at deleted D: locations. Recorded in `data/avatar_sources.json`; not rewritten
   (they are lineage metadata, not runtime inputs).
5. `30_7_fullbody` shows `NEEDS_CHECK` in `system_status.py` (pre-existing, not
   caused by this restructure).