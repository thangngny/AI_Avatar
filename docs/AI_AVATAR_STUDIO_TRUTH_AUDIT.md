# AI Avatar Studio — Forensic Truth Audit

**Date:** 2026-08-27
**Auditor:** read-only forensic pass (no production changes)
**Audited commit:** `3e04bbdb104de0bea8c9dd6355efca36a4680fdc` (main)
**Audited report:** `docs/AI_AVATAR_STUDIO_UI_IMPLEMENTATION_REPORT.md`

> Evidence levels used: **PROVEN_REAL** (executed + verified from artifacts),
> **PROVEN_STATIC** (verified from source/config, not executed),
> **UNIT_TEST_ONLY**, **CLAIMED_UNVERIFIED**, **FAIL**, **UNKNOWN**.
> A unit test is not a real PASS. A queued job is not a completed render.

## 0. HEADLINE FINDINGS

- The **controller→renderer pipeline is genuinely proven end-to-end**: real
  UI-driven renders completed through the locked production renderer (1080×1920,
  25 FPS, audio+video), including a real **two-GPU concurrent** run (GPU0 + GPU1).
- **Two real bugs were found** that the previous report overstated as PASS:
  1. **Create Avatar is broken** (`genavatar.py` `ModuleNotFoundError: No module
     named 'avatars'` — sys.path bug in the controller's subprocess invocation).
     The previous "Prepared avatar creation: PASS" was never actually exercised.
  2. **Concurrent-job output collision** (`_output_path` uses per-second timestamp
     + avatar + label, no job_id/uuid → two jobs in the same second clobber each
     other's MP4). Both jobs report COMPLETE pointing at one file → silent data
     loss in the very multi-GPU scenario the previous report claimed PASS.
- The **10-second smoke render did NOT happen**. The smoke video is 0.64 s
  (16 frames). The ElevenLabs account genuinely lacks quota for a 10s render
  (0 credits; ≥5-char TTS → 401). The operator's belief that quota exists is
  **not supported by the API** for the key the UI uses.

## 1. CLAIM-BY-CLAIM TABLE

| # | CLAIM | PREV STATUS | ACTUAL EVIDENCE | EVIDENCE LEVEL | TRUE STATUS | NOTES |
|---|---|---|---|---|---|---|
| 1 | QUICK RENDER | PASS | Avatar select + script parse + voice check + render-test/full endpoints all work; real renders completed (smoke + 2 multi-GPU jobs) | PROVEN_REAL | PASS (flow) / FAIL (10s target) | 10s target not met (quota) |
| 2 | CREATE AVATAR | PASS | `genavatar.py` subprocess exited code 1: `ModuleNotFoundError: No module named 'avatars'` (reproduced) | PROVEN_REAL | **FAIL** | sys.path bug; never completed through controller |
| 3 | AVATAR LIBRARY | PASS (18) | Filesystem: 18 non-dot dirs, **17 artifact-complete READY**, `30_7_fullbody` incomplete (NEEDS_CHECK) | PROVEN_REAL | PARTIAL | Library lists 18 with honest ready flags; "18 prepared" overcounts by 1 |
| 4 | RENDER HISTORY | PASS | SQLite has 3 jobs: 2 honest failures (quota 401, no output), 1 complete (output exists 445 KB) | PROVEN_REAL | PASS | Failed/interrupted jobs represented honestly; collision can make 2 rows point to 1 file |
| 5 | Avatar validator | CONNECTED | `validator.py` subprocess ran on a real source → WARN with MOTION+LIGHTING warnings | PROVEN_REAL | PASS | Reused existing validator; human-language translation works |
| 6 | WARN override | PASS | Override recorded in DB: `user_override=true`, quality=WARN, warnings persisted | PROVEN_REAL | PARTIAL | Override **recorded** = PASS; override→**proceed** = FAIL (genavatar bug) |
| 7 | Prepared avatar creation | PASS | Preparation failed (claim 2). No artifacts created. | PROVEN_REAL | **FAIL** | Was CLAIMED_UNVERIFIED; now proven FAIL |
| 8 | ElevenLabs Voice ID | PASS | Exact voice_id passed verbatim to TTS/verify; used in all real renders | PROVEN_REAL | PASS | — |
| 9 | Voice fail-closed | PASS | Invalid voice → 404/401 error, no fallback; source has no default-voice literal | PROVEN_REAL | PASS | — |
| 10 | Voice preview | PASS | Worked in prior session (quota available); now 401 (quota). Feature is real. | PROVEN_REAL (prior) | PASS (with quota) | Currently blocked by quota, not code |
| 11 | 10s video test | PARTIAL (0.64s) | ffprobe: 16 frames @ 25 FPS, dur 0.64 s, 1080×1920, aac 16 kHz | PROVEN_REAL | **FAIL** (strict 10s) | Quota genuinely blocks (0 credits for ≥5-char TTS) |
| 12 | Full render controller | PASS | CAN_CREATE/QUEUE/START/COMPLETE/VERIFY all proven by real completed renders | PROVEN_REAL | PASS (with collision bug) | Output collision under concurrency (claim 2-bug) |
| 13 | Auto Split | PASS | Split logic unit-tested, sentence-safe; **no real multi-part render executed** | UNIT_TEST_ONLY | PARTIAL | Logic PROVEN_STATIC; no real multi-part render evidence |
| 14 | Render Queue | PASS | Live states observed; 2 jobs shown rendering concurrently | PROVEN_REAL | PASS | — |
| 15 | Multi-GPU scheduler | PASS | Two jobs ran **concurrently** on GPU0 + GPU1, both completed | PROVEN_REAL | PASS (with collision caveat) | Real E2E proven; but outputs collided (bug) |
| 16 | Production truth protection | PASS | render_truth.json unchanged in git; runtime log banner: gain 1.5 / ctx 0 / offset -3 / 25fps / 1080×1920 / CUDA Graph ON / WOLA ON / coverage ON | PROVEN_REAL | PASS | No editable controls in UI |
| 17 | LatentSync isolation | PASS | `latentsync` not importable; renderer imports production code via cwd; no LatentSync code invoked | PROVEN_REAL | PARTIAL | Code isolated, BUT studio's torch env lives inside the experimental repo (env-location coupling) |
| 18 | CLI regression | PASS | `generate_video_from_script.py` ran successfully as subprocess (smoke + 2 jobs); `system_status.py` VALID | PROVEN_REAL | PASS | CLI still works independently |
| 19 | system_status | PASS | Ran: Branch main, Production Truth VALID, Ready YES, 18 dirs listed | PROVEN_REAL | PASS | — |

## 2. ELEVENLABS QUOTA — CRITICAL

**Key source:** `.env` `ELEVENLABS_API_KEY` (the only key the UI uses), len 51, prefix `sk_`.

**Endpoints queried (live, this audit):**
- `GET /v1/user` → 200
- `GET /v1/user/subscription` → 200
- `POST /v1/text-to-speech/{voice_id}` (probes, 1-char and 191-char)

**Raw relevant fields (redacted JSON saved: `docs/_audit_elevenlabs_quota.json`):**
```
tier:                                  payg
status:                                active
character_count:                       10000
character_limit:                       10000
max_character_limit_extension:         0
can_extend_character_limit:            false
next_character_count_reset_unix:        1788705828  ->  2026-09-06 14:43:48 UTC
billing_period / character_refresh_period: monthly_period
voice_limit:                           3
current_overage:                        0 USD
```

**Definitive TTS probe (this audit, exact key, voice `pGapy9MNHCukzJtjavF0`, model `eleven_turbo_v2_5`):**
| text chars | HTTP | result |
|---|---|---|
| 1 ("a") | 200 | 19320–20806 bytes audio (~1 s) |
| 5 | 401 | `quota_exceeded` "0 credits remaining" |
| 10 / 20 / 30 / 50 | 401 | `quota_exceeded` "0 credits remaining" |
| 191 (~10 s script) | 401 | "0 credits remaining, **40 credits required**" |

**Calculated remaining quota:** `character_limit - character_count = 10000 - 10000 = 0`.
The binding limit is the monthly character credit pool (the same counter the 401
calls "credits"). A 10 s (~191 char) script needs ~40 credits → blocked. Only
sub-minimal (1-char) requests slip through. Reset: **2026-09-06**.

**Reconciliation with the operator's belief that "the account still has quota":**
The API for the key the UI uses returns **0 remaining** for any meaningful TTS.
The dashboard the operator may be viewing is either a different account, a
prepaid balance that does not apply to this key, or the `voice_limit`/`tier`
fields (which are not character quota). Per the authoritative TTS endpoint, real
TTS is blocked.

**ELEVENLABS_QUOTA_CLAIM: TRUE** (the substance — a 10s render is quota-blocked —
is correct). The previous report's "9998/10000, 2 remaining" was an accurate
real-time snapshot at smoke time; the final 1-char render consumed the last
credits, so it is now 10000/10000, 0 remaining. The previous report did **not**
misread the field. The operator's contrary belief is not supported by the API
for this key.

**ACTUAL_QUOTA:** `payg`, monthly character quota 10000/10000 used, **0 remaining**,
reset 2026-09-06. No character-limit extension allowed. TTS for ≥5 chars → 401.

## 3. SMOKE VIDEO

`D:\CongThang_AI_Avatar\renders\studio\20260827_101332_test10s_doTrang_closeup_test10s.mp4`
- exists, 445 902 bytes
- ffprobe: video h264 **1080×1920**, **25/1 FPS**, **16 frames**, dur **0.640 s**
- audio aac, 16 000 Hz mono, dur 0.640 s

16 frames @ 25 FPS = 0.64 s. **This is NOT a 10-second render.**

**STRICT_10_SECOND_UI_SMOKE: FAIL** (real, but 0.64 s, not ≥8 s).

## 4. CAN A 10s RENDER BE RUN NOW?

No. A 191-char (~10 s) script → 401 "0 credits remaining, 40 required." The
account lacks quota. Per audit rule §4, a fake test was **not** run.
**Strict real 10s UI render: NOT_RUN** (honestly — quota does not exist).

A real **short** render (~1 s, 1-char script) WAS run through the full controller
pipeline and verified (claims 1, 12, 15). The pipeline itself is proven; only
the 10s duration is quota-blocked.

## 5. EXACT VOICE METADATA (`pGapy9MNHCukzJtjavF0`)

Live `GET /v1/voices/{id}` → 200. API-returned raw fields:
```
voice_id:  pGapy9MNHCukzJtjavF0
name:      "TVC Ái Hạnh"               <- API_RETURNED
category:  "professional"              <- API_RETURNED
description: "TVC Ái Hạnh - Young woman from Hanoi. Used for advertising, commercials, and entertainment."  <- API_RETURNED
labels:    {use_case:"advertisement", descriptive:"crisp", gender:"female", language:"vi", accent:"northern", age:"young"}  <- API_RETURNED
```
Reconciliation of names used in prior reports/spec:
- "TVC Ái Hạnh" — **API_RETURNED** (correct; the UI shows this).
- "Hạnh" — **INFERRED/HUMAN_DESCRIPTION** (a truncation of the real name).
- "Smooth, Clear and Feminine" — **NOT in the API**. This came from the original
  spec prompt (§21), not from any API response. The API returns `descriptive:"crisp"`,
  not "smooth"/"clear". The UI does **not** fabricate this — it shows real labels.

**Voice exact-ID real verification: PASS** (exact ID used in all real renders + GET
returns real metadata; no fabrication in the UI).

## 6. CREATE AVATAR REAL E2E

- Source: `C:\CongThang\AI_avatar\test17_8\Close Up.mp4` (known WARN source),
  copied into the allowed raw-sources dir as `audit_warn_source.mp4` (removed after audit).
- Analyze (`POST /api/avatar/analyze`): real `validator.py` subprocess →
  `overall=WARN`, `face_h_ratio=0.1034`, warnings MOTION+LIGHTING, `can_proceed=true`,
  `technical_failure=false`. ✅ (evidence: `docs/_audit_analyze.json`)
- Prepare (`POST /api/avatar/prepare`, `allow_warning_override=true`,
  avatar_id `audit_test_avatar`): `genavatar.py` subprocess **exited code 1**:
  ```
  ModuleNotFoundError: No module named 'avatars'
    from avatars.musetalk.utils.preprocessing import get_landmark_and_bbox, read_imgs
  ```
- No artifacts created; no `data/avatars/audit_test_avatar/` dir.

**Root cause:** `generate_video_from_script.py:35` does
`sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` (adds repo root),
so it works as a subprocess. `avatars/musetalk/genavatar.py` does **not** do this,
and when launched as `python avatars/musetalk/genavatar.py` from the repo root,
Python puts the *script's* dir (`avatars/musetalk/`) on `sys.path[0]`, not the repo
root → `avatars` package unimportable. The controller does not set `PYTHONPATH`
to the repo root for the prep subprocess. (Confirmed: from a neutral cwd with
`PYTHONPATH=repo_root`, `avatars` is importable; without it, it is not.)

**CREATE_AVATAR_REAL_E2E: FAIL** (real bug; previous "PASS" was never executed).

## 7. AVATAR LIBRARY COUNT

- Filesystem non-dot dirs under `data/avatars/`: **18** (`.uploads` excluded ✅).
- Artifact-complete (READY, v15): **17**. Incomplete: `30_7_fullbody` (NEEDS_CHECK).
- The API lists all 18 with honest per-avatar ready flags (17 READY, 1 NEEDS_CHECK).

**PREVIOUS_COUNT_18: PARTIAL** — 18 dirs exist, but only 17 are actually prepared.
The library UI is honest (it shows the NEEDS_CHECK flag); the previous report's
"18 prepared avatars" phrasing overcounts.

## 8. WARN OVERRIDE REAL E2E

- Quality WARNING produced (MOTION, LIGHTING), `can_proceed=true`, not technical.
- UI exposes "Use Anyway & Prepare" when `can_proceed && !technical_failure`
  (verified in source: `app.js showPrepare()`).
- Override **recorded in DB** (proven): `avatars` row for `audit_test_avatar` has
  `quality_data = {"quality_result":{"face_h_ratio":0.1034},
  "quality_warnings":[MOTION,LIGHTING], "user_override":true}`, `quality=WARN`.
- Prepare operation **could not proceed** (genavatar bug, §6).

**WARN_OVERRIDE_REAL_E2E: PARTIAL** — override recorded = PASS; override→proceed = FAIL.

## 9. FULL RENDER CONTROLLER

Independent sub-capabilities (proven by real completed renders — smoke + 2 multi-GPU jobs):
- CAN_CREATE_JOB: PASS (real job rows inserted)
- CAN_QUEUE_JOB: PASS (worker claimed queued jobs)
- CAN_START_RENDER: PASS (renderer subprocess launched)
- CAN_COMPLETE_RENDER: PASS (renderer exited 0, MP4 written)
- CAN_VERIFY_OUTPUT: PASS (ffprobe verify ran, 1080×1920/25fps/audio confirmed)

**FULL_RENDER_CONTROLLER_REAL_E2E: PASS** (with the output-collision caveat, §15).

## 10. RENDER HISTORY

SQLite `data/studio_runtime/studio.db`, 3 rows:
| job_id | kind | avatar | voice | status | dur | output exists |
|---|---|---|---|---|---|---|
| job_...ba727e99 | test10s | doTrang_closeup | pGapy9... | failed | — | False |
| job_...e79296dd | test10s | doTrang_closeup | pGapy9... | failed | — | False |
| job_...a8c15452 | test10s | doTrang_closeup | pGapy9... | complete | 0.557 s | True (445 KB) |

- `truth_hash` recorded on all rows (`a5a0e55f...`), matches `render_truth.json` sha1.
- `master_audio_path` present only on the complete job; exists on disk.
- Failed jobs honestly show `status=failed`, no output, no master audio (not faked).
- No `user_override` on render jobs (correct — override is for avatar prep).

**RENDER_HISTORY_REAL: PASS.** (Caveat: the 2 multi-GPU jobs both wrote rows
pointing to the **same** output path due to the collision bug — history can
mislead under concurrency.)

## 11. MULTI-GPU REAL E2E

- `nvidia-smi`: 2 × RTX 3090 (GPU0, GPU1), both free at test time.
- Scheduler: `gpu_service.acquire()` returns free GPU ids; `_run_job` runs in a
  thread per job; `CUDA_VISIBLE_DEVICES=<gpu>` + `OFFLINE_USE_MULTI_GPU=false`
  per subprocess (one process per GPU).
- **Real concurrent test:** two `test10s` jobs (script "a", reusing the existing
  master WAV — **no ElevenLabs cost**) queued simultaneously.
- Observed live: `4846ca: preparing_audio gpu=0 Rendering Lip-sync 5% |
  7708fc: preparing_audio gpu=1 Rendering Lip-sync 5%` — **both rendering
  simultaneously on GPU0 and GPU1**.
- Both completed: `4846ca complete gpu=0`, `7708fc complete gpu=1`.

**MULTI_GPU_REAL_E2E: PASS** (two real concurrent jobs on GPU0+GPU1, both
completed). **Caveat (bug):** both jobs wrote to the same output file
(`20260827_102941_test10s_doTrang_closeup_test10s.mp4`) because `_output_path`
uses `time.strftime("%Y%m%d_%H%M%S")` + kind + avatar + label with **no job_id**,
so two jobs created in the same second collide. The second job's `ffmpeg -y`
overwrote the first's mux; both history rows point to one file. This is silent
data loss in the exact concurrency scenario the feature is for.

## 12. PYTHON ENV / LATENTSYNC COUPLING

- `latentsync_env` IS a real venv (`pyvenv.cfg`: home=Python310,
  include-system-site-packages=false). Its `sys.path` = its own site-packages
  + base Python310 DLLs/lib. It does **not** include `C:\CongThang\AI_avatar`
  (the experimental repo root).
- `import latentsync` → **NOT FOUND** (not installed in the env).
- From a **neutral cwd** (`C:\Windows\Temp`): `find_spec('avatars')` = None,
  `find_spec('utils')` = None, `find_spec('latentsync')` = None → the env does
  **not** contain production code; production code is loaded from the AI_avatar
  repo via cwd (`generate_video_from_script.py:35` adds the repo root).
- `.pth` files in the env: only `coloredlogs`, `distutils-precedence`, `protobuf`
  (standard) — **no** coupling `.pth` to either repo.
- `C:\CongThang\AI_avatar` is a **separate git repo** (top-level = itself,
  HEAD `5a64413` "Add MASTER lipsync config + objective benchmark harness").
  `latentsync_env/` is a subfolder *inside* that experimental repo.
- The studio's configured interpreter is hardcoded to
  `C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe`
  (`studio/avatar_service._torch_python()`).

**LATENTSYNC_CODE_IMPORT: NO** (production never imports LatentSync; renderer
imports production code via cwd).
**EXPERIMENTAL_REPO_ENV_DEPENDENCY: YES** (the studio's torch interpreter is a
venv located *inside* the experimental LatentSync repo; moving/deleting that
repo would break the studio's hardcoded python path).
**FULL_ISOLATION_CLAIM: PARTIAL** — code-level isolation is real (no LatentSync
code is invoked), but there is a filesystem/env-location dependency on the
experimental repo. The previous "LatentSync unreachable from UI" is true at the
code level but does not disclose this env coupling.

## 13. PRODUCTION TRUTH — REVERIFY

`config/render_truth.json` (git HEAD, unchanged):
```json
{"pipeline":"musetalk_v15","audio_gain":1.5,"audio_context_left":0,
 "audio_feature_offset_frames":-3,"fps":25,"resolution_width":1080,
 "resolution_height":1920,"composite_max_dim":1920,"cuda_graph":true,
 "long_audio_wola":true,"feature_coverage_assertion":true}
```
Real runtime banner (from smoke job log `job_...a8c15452.log`):
```
AI AVATAR — PRODUCTION TRUTH
LOCKED QUALITY CONFIG:
  Audio gain: 1.5 / Audio context left: 0 / Audio feature offset: -3
  FPS: 25 / Resolution: 1080x1920 (composite_max_dim 1920)
  CUDA Graph: ON / Long-audio WOLA: ON / Feature coverage guard: ON
...
Rendering 16 frames in batches of 16 (multi_gpu=False, cuda_graph=True)
```
UI source: no editable gain/ctx/offset/fps/resolution controls; truth shown
read-only; controller passes only `--avatar_id/--audio/--output`.

**PRODUCTION_TRUTH: PASS** (PROVEN_REAL at runtime + source + git).

## 14. MOCKS / FAKE SUCCESS

Source scan (`studio/`, `tests/`): the only `fake`/`simulate` hits are
**unit-test fixtures** (`fake_result`, `fake` test dir in `tests/test_studio.py`)
and HTML `placeholder=` attributes (UI input hints). No production code returns
`success=True` without a real subprocess/artifact check:
- COMPLETE is set **only after** `verify_mod.verify()` passes (render_service
  `status="verifying"` → `verify()` → `status="complete"`; fail → `failed`).
- READY requires on-disk artifacts (`_check_ready`).
- Voice check requires a real API response (GET 200 with name OR a TTS probe 200).
- GPU state comes from `nvidia-smi` (not hardcoded).

**FAKE/MOCK_SUCCESS_PATHS_FOUND: NO** (no production endpoint fakes success).

## 15. PROCESS ERROR HANDLING

| subprocess | return code checked | stderr captured | timeout | output existence checked |
|---|---|---|---|---|
| validator | ✅ (`proc.returncode` + JSON file) | ✅ (capture_output) | ✅ 180 s | ✅ (JSON parsed) |
| genavatar (prep) | ✅ (`proc.wait()` + rc) | ✅ (stdout=stderr pipe to log) | ❌ **no timeout** | ✅ (`_check_ready`) |
| renderer | ✅ (`rc != 0` → failed) | ✅ (stdout=stderr to log) | ❌ **no timeout** | ✅ (verify) |
| ElevenLabs TTS | ✅ (status code) | ✅ (body parsed) | ✅ 120 s | ✅ (len check) |
| ffprobe (verify) | ✅ | ✅ | ✅ 60 s | ✅ |

**Gaps:** the renderer and genavatar subprocesses have **no timeout** — a hung
process leaves the job in RENDERING forever (the worker thread blocks on
`proc.wait()`). `RENDER_GPU_TIMEOUT_SEC` is defined (1800) but never passed to
`Popen`. Partial output: if the renderer exits 0 but writes a tiny/empty file,
`verify` catches it (size < 1000 → fail). A subprocess invocation alone is not
treated as success (verify gates COMPLETE).

## 16. FILES CHANGED BY THIS AUDIT (read-only intent)

- Created: `docs/AI_AVATAR_STUDIO_TRUTH_AUDIT.md` (this file),
  `docs/_audit_elevenlabs_quota.json`, `docs/_audit_analyze.json`,
  `docs/_audit_prepare_start.json`, `docs/_audit_multigpu_ids.json`
  (small JSON evidence; redacted).
- Created then removed (temp, cleaned up): a 52 MB source copy for analysis,
  `audit_server.log`, an empty failed master WAV.
- DB: one `audit_test_avatar` row persisted (evidence of the override record +
  failed prep); no avatar dir was created. No production avatar touched.
- **Production files changed: NO.** **render_truth.json changed: NO.**
  (git working tree clean vs HEAD except pre-existing untracked `input/`.)

## 17. OVERSTATED PREVIOUS PASS CLAIMS

1. **Prepared avatar creation (PASS → FAIL):** never executed; real run fails
   with `ModuleNotFoundError: No module named 'avatars'` (genavatar sys.path bug).
2. **10s video test (PARTIAL → FAIL):** the smoke video is 0.64 s (16 frames),
   not 10 s. The previous report itself acknowledged this; restating as FAIL.
3. **AVATAR LIBRARY "18 prepared" (PASS → PARTIAL):** 18 dirs, only 17 are
   artifact-complete; `30_7_fullbody` is incomplete.
4. **WARN override (PASS → PARTIAL):** override is recorded, but "prepare can
   proceed" is false (genavatar bug).
5. **Multi-GPU (PASS → PASS-with-bug):** real concurrency proven, but the output
   path collision means concurrent jobs clobber each other's MP4 (silent data
   loss) — undisclosed in the previous report.
6. **LatentSync isolation (PASS → PARTIAL):** code isolation is real, but the
   studio's torch env lives inside the experimental repo (env-location coupling
   not disclosed).
7. **Auto Split (PASS → PARTIAL):** split logic is unit-tested only; no real
   multi-part render was ever executed.
8. **Voice preview (PASS → PASS-with-quota-caveat):** real feature, worked in the
   prior session, but currently 401 (quota) — not a code defect.

## 18. ACTUALLY PROVEN CAPABILITIES

1. Controller→production-renderer end-to-end pipeline (real completed renders,
   1080×1920 25 FPS audio+video, locked truth applied at runtime).
2. ElevenLabs exact-Voice-ID TTS + fail-closed (no fallback) + master-audio reuse.
3. Avatar source quality analysis (real validator, human-language warnings).
4. WARN override recording (DB persistence of `user_override`/warnings/quality).
5. Render job lifecycle + SQLite history (honest failed/complete states).
6. Multi-GPU job-level concurrency (two jobs, GPU0+GPU1, concurrent, both done).
7. Production-truth protection (unchanged, read-only, runtime-verified).
8. CLI renderer still works independently; `system_status.py` VALID.

## 19. CLAIMS REQUIRING CORRECTION

1. **Fix `genavatar` subprocess invocation** — set `PYTHONPATH=<repo root>` (or
   run `python -m avatars.musetalk.genavatar`) so `avatars.*` imports resolve.
   Until fixed, Create Avatar is non-functional through the UI.
2. **Fix `_output_path` collision** — include the `job_id` (or a uuid) in the
   output filename so concurrent/same-second jobs never share a path.
3. **Add a timeout to the renderer and genavatar subprocesses** (use
   `RENDER_GPU_TIMEOUT_SEC`/a prep timeout) so a hung process cannot pin a job
   forever.
4. **Disclose the env-location coupling** — the studio's torch interpreter lives
   inside the experimental LatentSync repo; either relocate the venv or document
   the dependency (do not claim full isolation).
5. **Re-state "10s smoke" as FAIL** until a real ≥8 s UI render completes (needs
   ElevenLabs quota, reset 2026-09-06, or a topped-up account).
6. **Re-state avatar count** as "17 ready / 18 dirs" (not "18 prepared").

## 20. EVIDENCE ARTIFACTS

- `docs/_audit_elevenlabs_quota.json` — redacted `/v1/user` + `/v1/user/subscription`
- `docs/_audit_analyze.json` — real validator output on the WARN source
- `docs/_audit_prepare_start.json` — prepare invocation (failed)
- `docs/_audit_multigpu_ids.json` — the two concurrent job ids
- `data/studio_runtime/studio.db` — jobs table + `audit_test_avatar` override row
- `data/studio_runtime/logs/job_1787800412_a8c15452.log` — locked-truth runtime banner
- `data/studio_runtime/logs/prep_audit_test_avatar.log` — genavatar failure traceback
- `D:\CongThang_AI_Avatar\renders\studio\20260827_101332_..._test10s.mp4` — 0.64 s smoke video

## 21. LIMITATIONS

- 10s render could not be run (ElevenLabs quota = 0); a 1-char (~1 s) render was
  used to prove the pipeline + multi-GPU. The 10s target remains unmet honestly.
- The dual-GPU test reused an existing 1-char master WAV (no ElevenLabs cost);
  outputs collided (documented as a bug, §15).
- No long 3-minute render was attempted (per audit rules).
- LatentSync env was **not** migrated (per audit rules) — the coupling is
  documented, not resolved.

---

**END OF READ-ONLY FORENSIC AUDIT. No production changes, no render_truth.json
changes, no architecture changes. Awaiting human review before any repair.**

## REPAIR STATUS (added after the controlled repair — see
## docs/AI_AVATAR_STUDIO_REPAIR_REPORT.md)

| Finding | Repair status | Evidence level |
|---|---|---|
| Defect 1 — output collision | FIXED | PROVEN_REAL (TEST B: 2 concurrent jobs, distinct non-clobbered MP4s) |
| Defect 2 — Create Avatar broken | FIXED | PROVEN_REAL (audit_repair_avatar: all artifacts, READY) |
| Defect 3 — no subprocess timeouts | FIXED | PROVEN_STATIC + unit test (progress-aware watchdog; TIMED_OUT state) |
| Defect 4 — avatar library count | FIXED | PROVEN_REAL (TEST D: 30_7_fullbody INCOMPLETE; counts split) |
| Defect 5 — WARN override E2E | FIXED | PROVEN_REAL (WARN→Use Anyway→override persisted→prepare→READY) |
| Defect 6 — quota truth | ADDRESSED | PROVEN_REAL (live /api/elevenlabs/quota, uncached, non-fabricating) |
| Defect 7 — strict 10s | NOT FIXED (external) | BLOCKED_EXTERNAL (quota 0; reset 2026-09-06). No tag. |
| Defect 8 — env coupling | DOCUMENTED | PROVEN_STATIC (centralized in studio.runtime; migration plan; no migration) |

Production files, render_truth.json, MuseTalk, and TTS voice behavior are
unchanged. `python system_status.py` remains Production Truth: VALID / Ready: YES.