# AI AVATAR — SYSTEM CONTROL BOARD

> **READ THIS FIRST.** This is the shared operational board for the entire AI Avatar
> system. Any agent/session must read it before modifying or running this repository.
>
> **If `SYSTEM_CONTROL_BOARD.md` and `config/render_truth.json` disagree,
> `config/render_truth.json` is authoritative for runtime parameters, and this board
> must be corrected immediately.**

## 1. SYSTEM STATUS

| Field                     | Current State                              |
| ------------------------- | ------------------------------------------ |
| Operational status         | PRODUCTION READY                            |
| Authoritative branch       | main                                        |
| Production pipeline         | MuseTalk v1.5                                |
| Production entrypoint       | generate_video_from_script.py                |
| Production config           | config/render_truth.json                     |
| Production truth version   | v1                                           |
| Realtime product           | Separate / untouched                         |
| LatentSync                 | Experimental only / not production           |
| Last update                | 2026-08-25                                   |
| Last verified commit        | 5e295db (main HEAD)                          |

## 2. LOCKED PRODUCTION TRUTH

| Parameter                    | Locked Value | Can Job Override? |
| ---------------------------- | -----------: | ----------------- |
| Pipeline                     | MuseTalk v1.5 | NO                |
| audio_gain                   |          1.5 | NO                |
| audio_context_left           |            0 | NO                |
| audio_feature_offset_frames  |           -3 | NO                |
| FPS                          |           25 | NO                |
| Resolution                   |   1080x1920  | NO                |
| CUDA Graph                   |           ON | NO                |
| Long-audio WOLA              |           ON | NO                |
| Feature coverage guard       |           ON | NO                |
| Batch size (throughput only) |           16 | YES (perf knob, no quality impact) |

The machine-readable authority remains:

```text
config/render_truth.json
```

Do NOT manually maintain conflicting values in this board. If this board and
`render_truth.json` disagree, `render_truth.json` wins for runtime parameters and this
board must be corrected.

## 3. VARIABLE JOB INPUTS

| Input         | Variable? | Example          |
| ------------- | --------- | ---------------- |
| avatar_id     | YES       | close_up         |
| script        | YES       | script.txt       |
| master audio  | YES       | part_1.wav       |
| output path   | YES       | output.mp4       |
| GPU worker    | YES       | GPU0 / GPU1      |

```text
Avatar is data.
Avatar is NOT render configuration.
```

Changing an avatar must NEVER change quality/lip-sync configuration. Changing a script
or audio duration must NEVER change quality/lip-sync configuration.

## 4. CURRENT VALIDATED AVATARS

Prepared avatars live in `data/avatars/<avatar_id>/`. Required on-disk shape:
`full_imgs/`, `coords.pkl`, `latents.pt`, `mask/`, `mask_coords.pkl`, `avator_info.json`
with `version == "v15"`. Validate with `utils.avatar_validate.validate_avatar(id)`.

| avatar_id             | Status | Prepared path                                | Known source                                                   | Notes |
| --------------------- | ------ | -------------------------------------------- | ------------------------------------------------------------- | ----- |
| close_up              | READY  | data/avatars/close_up/                       | D:\Noble\livetalking\data\avatars\.uploads\musetalk_4872_697362812.mp4 | Used in the validated 7-part job; multi-frame video avatar (body motion). |
| fullbody_30_7_25fps   | READY  | data/avatars/fullbody_30_7_25fps/            | C:\Users\Admin\Videos\30_7\Closeup.mp4                         | Multi-frame video avatar; different source file than close_up. |
| mc_hamai_mid          | READY  | data/avatars/mc_hamai_mid/                   | input_25_8/Input/MID/Ver 1/MID_1.png (single photo)            | 1-frame photo avatar -> talking-photo output (body static, mouth moves). |

Other prepared avatars on disk (READY, historical): `23_7_avt, 30_7_fullbody, 30_7close,
close_up_16_7, fulbody_2_8, full_body_16_7, fullbody_30_7, fullbody_30_7_jaw,
fullbody_30_7_mouth_chin, fullbody_30_7_stable`.

No single avatar is the system default truth. Avatar selection is a per-job variable
input. (A future UI may pick a default for convenience only.)

## 5. LAST PRODUCTION VALIDATION

Completed 7-part job, audited (see `SYSTEM_7PART_RENDER_CONFIG_AUDIT.md`):

```text
Output dir: D:\CongThang_AI_Avatar\noble_live_25_8\
7 / 7 outputs complete
~52.5 minutes total video
1080x1920, 25 FPS, MuseTalk v1.5
gain 1.5, ctx 0, offset -3
CUDA Graph ON, WOLA ON, batch 16
no fallback
```

GPU mode:

```text
2 physical GPUs
job-level parallelism
one render process per GPU (NOT single-video multi-GPU inference)
```

## 6. PRODUCTION RUNTIME FLOW

```text
Avatar
   +
Script / Master Audio
   ↓
Job validation  (utils.avatar_validate)
   ↓
config/render_truth.json  (locked quality/lip-sync)
   ↓
generate_video_from_script.py  (loads truth, fail-closed)
   ↓
MuseTalk v1.5
   ↓
CUDA Graph + long-audio WOLA + feature-coverage guard
   ↓
Paste-back composite
   ↓
1080x1920 / 25 FPS
   ↓
Final MP4
```

## 7. FORBIDDEN AUTOMATIC BEHAVIOR

```text
DO NOT automatically switch to LatentSync.
DO NOT automatically change gain.
DO NOT automatically change context.
DO NOT automatically change audio offset.
DO NOT automatically change FPS.
DO NOT automatically change resolution.
DO NOT disable CUDA Graph silently.
DO NOT disable WOLA silently.
DO NOT choose a different avatar as fallback.
DO NOT use old experimental configs as production defaults.
```

If production cannot run: **FAIL CLOSED**. Report the blocker. Do not invent a
fallback. (The renderer already exits non-zero on missing/invalid `render_truth.json`,
missing MuseTalk weights, or an incompatible avatar; it never falls back to a different
avatar, gain 1.0, or LatentSync.)

## 8. EXPERIMENTAL / HISTORICAL AREA

These are NOT current production truth and must never silently affect production
runtime. An agent may inspect them only when explicitly debugging or researching
history:

```text
experiments/            (diagnostic / experimental source scripts)
archive/reports/        (historical SYSTEM_*.md reports + handoff notes)
diagnostics/            (gitignored local runtime/debug artifacts)
LatentSync copy         (C:\CongThang\AI_avatar — experimental/offline, separate repo)
old diagnostic scripts  (moved into experiments/)
historical branches     (feature/mouth-articulation-v1, checkpoint/lipsync-stable-v1)
```

Production runtime (`generate_video_from_script.py` + its imports) does NOT import from
`experiments/` or `archive/`; documentation never influences runtime.

## 9. GIT OPERATING RULE

```text
ALL NORMAL SYSTEM WORK STARTS FROM main.
```

Do not create or switch to another branch unless the user explicitly requests
branch-based experimentation. Historical branches may remain for recovery; they are
reference only.

Before any work:

```text
1. git branch --show-current
2. confirm main
3. read SYSTEM_CONTROL_BOARD.md
4. read config/render_truth.json
```

If not on main: **STOP and return to main before normal production work.** Do not
automatically merge unrelated branch work. Do not rewrite history; do not force-push.

## 10. CHANGE CONTROL

Any future quality change must follow:

```text
CURRENT TRUTH
   ↓ explicit experiment (under --experimental-config, or experiments/)
   ↓ A/B validation
   ↓ human approval
   ↓ regression test (≥2 avatars, identical locked config)
   ↓ update config/render_truth.json
   ↓ update SYSTEM_CONTROL_BOARD.md
   ↓ commit on main
   ↓ new production-truth tag
```

Never modify production truth just because an experiment scored better. Human approval
is required.

## 11. CURRENT NEXT PRODUCT DIRECTION

Build a simple local AI Avatar UI:

```text
Select/add avatar
   → paste/upload script or audio
   → choose output
   → Render
```

All locked quality settings remain hidden behind `config/render_truth.json` and are not
exposed as per-job knobs in normal production. (Do NOT build the UI yet — informational
only.)