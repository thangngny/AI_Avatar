# AI Avatar Studio — Controlled Repair Report

**Date:** 2026-08-27
**Branch:** main
**HEAD before:** `3e04bbdb104de0bea8c9dd6355efca36a4680fdc`
**HEAD after:** (see `git log -1` after commit)
**Authoritative audit:** `docs/AI_AVATAR_STUDIO_TRUTH_AUDIT.md`

> Evidence classes used: **PROVEN_REAL** (real workflow executed + artifact
> independently verified), **PROVEN_STATIC** (verified from source, not
> executed), **UNIT_TEST_ONLY**, **BLOCKED_EXTERNAL**, **FAIL**.

## Scope

Repaired ONLY the defects proven by the forensic truth audit. No redesign.
No MuseTalk / lip-sync / render_truth / TTS-voice behavior changes. No
LatentSync integration. No environment migration.

## Defect 1 — Output path collision (CRITICAL) — FIXED

**Before:** `_output_path` used `time.strftime("%Y%m%d_%H%M%S")` + kind +
avatar_id + label — **no job_id**. Two jobs created in the same wall-clock
second resolved to the SAME path. Proven real clobber during the audit's
dual-GPU test (both jobs wrote `20260827_102941_..._test10s.mp4`).

**After:** `studio/render_service._output_path(kind, avatar_id, label, job_id)`
embeds the job's 8-char uuid suffix: filename shape
`{ts}_{kind}_{safe_avatar}_{safe_label}_{uuid8}.mp4`. Uniqueness no longer
depends on the wall clock. An existence guard additionally avoids overwriting
any existing non-trivial file (retry safety). `retry_job` assigns a FRESH
output path (new uuid) so a retry can never silently overwrite a previous
artifact.

**Evidence:**
- UNIT_TEST_ONLY: `tests.test_studio.TestOutputUniqueness` — 50 same-second
  paths all unique; two jobs distinct; safe filenames (no `/`, `..`).
- **PROVEN_REAL (TEST B):** two concurrent `test10s` jobs (script "a", reusing
  the existing master WAV — **no ElevenLabs cost**) ran simultaneously on
  GPU0 + GPU1 and completed with **distinct** outputs:
  - `20260827_105039_..._94f24ee6.mp4` (GPU0, 446 036 B)
  - `20260827_105039_..._3eee0df0.mp4` (GPU1, 445 931 B)
  - DISTINCT_PATHS=True, BOTH_EXIST=True, neither clobbered (different sizes).
  - GPU0 file ffprobe: h264 1080×1920, 25/1 FPS, 16 frames, aac 16 kHz — valid.

**Output collision: FIXED.** **Real dual-GPU unique outputs: PROVEN_REAL.**

## Defect 2 — Create Avatar broken (CRITICAL) — FIXED

**Before:** the controller ran `python avatars/musetalk/genavatar.py ...` from
the repo root. `genavatar.py` does NOT add the repo root to `sys.path` (unlike
`generate_video_from_script.py:35`), and Python puts the script's dir
(`avatars/musetalk/`) on `sys.path[0]` — so `from avatars.musetalk...` raised
`ModuleNotFoundError: No module named 'avatars'`. Preparation never completed
through the controller.

**After:** `studio/avatar_service.PrepJob.start` now invokes
`python -m avatars.musetalk.genavatar --file ... --avatar_id ... --version v15
--parsing_mode jaw --bbox_shift 0` from the repo root, with `PYTHONPATH=<repo
root>` as a belt-and-suspenders guarantee. `-m` puts the repo root (cwd) on
`sys.path[0]` and runs the canonical `__main__` block — **no MuseTalk code
copied**, no second implementation, no shell hack. Interpreter resolution is
centralized in `studio/runtime` (Defect 8).

**Evidence (PROVEN_REAL — TEST C):**
- Source: `C:\CongThang\AI_avatar\test17_8\Close Up.mp4`, trimmed to 6 s as a
  disposable audit source (removed after test).
- `POST /api/avatar/analyze` → `overall=WARN` (MOTION), `can_proceed=true`,
  `face_h_ratio=0.1031`.
- `POST /api/avatar/prepare` (`allow_warning_override=true`, avatar
  `audit_repair_avatar`) → preparation completed (`done=true, ready=true,
  stage=done, timed_out=false`).
- **Artifacts verified on disk:** `full_imgs/` (150 frames), `mask/` (150),
  `coords.pkl` (2416 B), `mask_coords.pkl` (2416 B), `latents.pt` (2 500 934 B),
  `avator_info.json` (`version=v15, parsing_mode=jaw`).
- `_check_ready()` → True. Library entry → `status=READY, ready=true,
  quality=WARN`.
- `python -m avatars.musetalk.genavatar --help` → exit 0 (imports resolve).

**Create Avatar: PROVEN_REAL.** **Create Avatar import bug: FIXED.**

## Defect 3 — Subprocess timeouts (HIGH) — FIXED

**Before:** the renderer and genavatar subprocesses had **no timeout** —
`proc.wait()` with no limit. A hung process pinned a job forever.
`RENDER_GPU_TIMEOUT_SEC` was defined but never used.

**After:** operation-specific, progress-aware timeouts (a slow-but-progressing
long render is NOT killed — only a truly hung process is):

| subprocess | timeout policy |
|---|---|
| validator | fixed 180 s (`subprocess.run(timeout=180)`) — short analysis |
| ElevenLabs TTS | per-request 120 s + 4-retry backoff (unchanged) |
| genavatar (prep) | `STUDIO_PREP_TIMEOUT_SEC` default 1800 s (30 min) hard backstop; `timed_out` flag; `runtime.terminate_tree` kills the child tree |
| renderer | progress-aware watchdog: `STUDIO_RENDER_NO_PROGRESS_SEC` default 300 s (kill only if NO stdout for 5 min) + `STUDIO_RENDER_HARD_TIMEOUT_SEC` default 14 400 s (4 h) backstop; PID tracked; child tree terminated |

On timeout: job status → `timed_out`, stage → `Timed Out`, error visible in
history. Partial output is NOT reported COMPLETE (COMPLETE only after verify).
`timed_out` is a recognized terminal state (retry accepts it). Successful
completed jobs are unaffected (verified — TEST B jobs completed normally).

**Evidence:** PROVEN_STATIC (source: `render_service._run_job` watchdog thread
+ `avatar_service.PrepJob._pump` deadline) + UNIT_TEST_ONLY
(`test_timed_out_is_distinct_state`).

## Defect 4 — Honest avatar library status — FIXED

**Before:** 18 dirs were called "18 prepared avatars"; `30_7_fullbody`
(incomplete) was counted. Status tag said "NEEDS CHECK".

**After:**
- `avatar_service.list_avatars()` returns an explicit `status` field:
  `"READY"` (artifact-complete, v15) or `"INCOMPLETE"` (missing artifacts).
  Incomplete dirs are still LISTED (operator can see + re-prepare) but are NOT
  selectable for rendering. No data deleted.
- `avatar_service.avatar_counts()` → `{total_dirs, ready_avatars,
  incomplete_avatars}`.
- `/api/system/status` returns `avatar_total_dirs`, `ready_avatars`,
  `incomplete_avatars` (replaces the old single `avatar_count`).
- Quick Render dropdown already filtered to READY only (unchanged — correct).
- Library UI tag: `READY` / `INCOMPLETE` (was "NEEDS CHECK").

**Evidence (PROVEN_REAL — TEST D):** `30_7_fullbody` → `ready=false,
status=INCOMPLETE`; `doTrang_closeup` → `ready=true, status=READY`. Counts:
`total_dirs=19, ready_avatars=18, incomplete_avatars=1` (after the disposable
audit avatar was removed: 18 dirs / 17 ready / 1 incomplete — see Known issues).
UNIT_TEST_ONLY: `test_incomplete_avatar_status_field`, `test_avatar_counts`.

**Incomplete avatar handling: PASS.**

## Defect 5 — WARN override full E2E — PROVEN_REAL

**Before:** override was recorded (DB `user_override=true`), but prepare could
not proceed (Defect 2). Partial.

**After (with Defect 2 fixed):** full path proven real:
WARN (MOTION) → warning displayed (`can_proceed=true`) → Use Anyway
(`allow_warning_override=true`) → override persisted (DB row:
`quality=WARN, quality_data.user_override=true`) → prepare SUCCEEDED → new
avatar READY (artifacts + library `status=READY`). See Defect 2 evidence.

**WARN override full E2E: PROVEN_REAL.**

## Defect 6 — ElevenLabs quota truth — ADDRESSED

**Before:** no account-status view; the previous report cited a transient
"9998/10000" snapshot with no live verification in the UI.

**After:** `elevenlabs_client.account_status()` does a LIVE `GET
/v1/user/subscription` (uncached — every call hits the API, so a topped-up /
changed key is reflected immediately). Returns ONLY fields ElevenLabs returns:
`tier, status, character_count, character_limit, remaining (= limit-count),
reset_unix, reset_date_utc`. If the fields are absent, `remaining` is `null` —
**never fabricated**. No quota caching. No key fallback. Exposed read-only at
`GET /api/elevenlabs/quota` and shown in Settings (refreshes on view).

**Current truth (live, this repair):** `tier=payg, character_count=10000,
character_limit=10000, remaining=0, reset=2026-09-06`. TTS for ≥5 chars → 401
quota_exceeded (re-confirmed). The UI now shows this honestly.

**Evidence:** PROVEN_REAL (`/api/elevenlabs/quota` returns the live 0-remaining
status). UNIT_TEST_ONLY: `test_account_status_does_not_fabricate`.

## Defect 7 — Strict 10s acceptance — BLOCKED_EXTERNAL (honest)

**Before:** the smoke video is 0.64 s (16 frames). The previous report's
"PARTIAL" was restated as FAIL in the audit.

**After:** no code claims a 10s guarantee. The repair report does NOT claim
"10s VIDEO TEST PASS". The strict 10s test remains **BLOCKED_EXTERNAL** because
the configured ElevenLabs key has 0 remaining character credits (resets
2026-09-06); a ≥8 s render needs ~40 credits → 401. A fake test was NOT
manufactured. **No `ai-avatar-studio-ui-v1` tag created.**

**Strict 10s UI test: BLOCKED_EXTERNAL.**

## Defect 8 — LatentSync environment coupling — DOCUMENTED (no migration)

**Before:** the torch interpreter was hardcoded in
`avatar_service._torch_python()` with no disclosure that the venv lives inside
the experimental LatentSync repo.

**After:**
- New `studio/runtime.py` is the SINGLE source of truth for the interpreter
  (`runtime.torch_python()`) and repo root (`runtime.repo_root()`).
  `avatar_service` and `render_service` both use it. Overridable via
  `STUDIO_TORCH_PYTHON` (verbatim — honors a bare `python` or a full path).
- `runtime.py` docstring documents the coupling honestly: NO code import of
  LatentSync, but YES filesystem/env-location dependency (the venv is inside
  `C:\CongThang\AI_avatar`).
- **No migration performed** (per spec — only if proven safe). Migration plan
  below.

**LatentSync code import: NO.** **Experimental environment coupling: YES
(documented).** **Environment migration performed: NO.**

**Migration plan (future, not executed now):**
1. Create a dedicated venv at `C:\CongThang_AI_Avatar\venv` using Python 3.10.
2. Install the production deps (`pip install -r requirements-musetalk.txt`
   + flask + requests) from the AI_avatar repo.
3. Set `STUDIO_TORCH_PYTHON=C:\CongThang_AI_Avatar\venv\Scripts\python.exe`
   (no code change needed — the override already exists).
4. Verify Create Avatar + a short render + `system_status.py` against the new
   env, then remove the `latentsync_env` dependency. This must be done in a
   separate, explicitly-approved migration task with full regression.

## Process success rule / job state machine

- COMPLETE is written ONLY after `verify_mod.verify()` passes (renderer) /
  artifacts exist (prep). Never "COMPLETE then verify later".
- Truthful states: `queued, preparing_audio, rendering, encoding, verifying,
  complete, failed, timed_out, cancelled`.
- For every subprocess: return code == 0 AND required output exists AND
  output passes validation. A subprocess starting is not success.

## Regression tests

| Test | Result | Evidence level |
|---|---|---|
| A — output uniqueness (50 same-second paths) | PASS | UNIT_TEST_ONLY + PROVEN_REAL via B |
| B — real dual-GPU short render (distinct outputs) | PASS | PROVEN_REAL |
| C — Create Avatar (analyze→WARN→Use Anyway→prepare→READY) | PASS | PROVEN_REAL |
| D — incomplete avatar (`30_7_fullbody` not READY) | PASS | PROVEN_REAL |
| E — direct CLI regression (`generate_video_from_script.py --help`) | PASS | PROVEN_REAL |
| F — `python system_status.py` (Truth VALID, Ready YES) | PASS | PROVEN_REAL |
| UI regression — unit suite (33 tests) | PASS | UNIT_TEST_ONLY |

## Files changed (legitimate — controller/UI/tests/docs only)

```
studio/runtime.py            (NEW — centralized interpreter + repo root)
studio/render_service.py      (D1: unique output path + retry fresh path;
                                D3: progress-aware renderer timeout + timed_out)
studio/avatar_service.py      (D2: python -m genavatar + PYTHONPATH;
                                D3: prep timeout + timed_out; D4: status/counts;
                                D8: use runtime)
studio/elevenlabs_client.py    (D6: account_status — live, non-fabricating)
studio/app.py                 (D4: system status counts; D6: /api/elevenlabs/quota)
studio/static/app.js           (D4: INCOMPLETE tag; D6: live quota in Settings)
tests/test_studio.py           (D1/D2/D3/D4/D6/D8 regression tests)
docs/AI_AVATAR_STUDIO_TRUTH_AUDIT.md       (repair-status section added)
docs/AI_AVATAR_STUDIO_REPAIR_REPORT.md     (this file)
docs/_audit_elevenlabs_quota.json          (redacted audit evidence; key redacted)
```

## Production files NOT changed

`config/render_truth.json`, `generate_video_from_script.py`, `system_status.py`,
`create_avatar.py`, `avatars/musetalk/genavatar.py`,
`tools/avatar_source_quality/validator.py`, `utils/avatar_validate.py`, and all
MuseTalk/Whisper/mask/CUDA-graph/WOLA/coverage code — **unchanged** (git diff
clean). No MuseTalk, lip-sync, gain/ctx/offset, FPS, resolution, WOLA, CUDA
Graph, coverage, mouth-geometry, or voice-fallback changes.

## Known limitations / remaining issues

1. **Strict 10s test: BLOCKED_EXTERNAL** — ElevenLabs key has 0 credits (reset
   2026-09-06). Re-run the 10s UI test after quota reset/top-up; only then tag
   `ai-avatar-studio-ui-v1`.
2. **LatentSync env coupling: YES (documented, not migrated)** — the torch venv
   still lives inside the experimental repo. Migration plan in §D8.
3. Renderer timeout is progress-aware (no-stdout watchdog); a process that
   emits a line every <5 min but never finishes would run until the 4 h hard
   cap. Acceptable for a local tool.
4. The `audit_repair_avatar` and `audit_short_source.mp4` disposable artifacts
   were removed after proving E2E. The SQLite rows remain (gitignored under
   `data/studio_runtime/`).
5. Auto Split logic is unit-tested only; a real multi-part render was not run
   (no quota for TTS on the parts). The split logic is unchanged and
   sentence-safe.

## Recommended next action

After the ElevenLabs quota resets (2026-09-06) or the operator tops up the
account: run a real UI-driven ≥8 s render (Quick Render → doTrang_closeup →
~30-word Vietnamese script → Voice ID `pGapy9MNHCukzJtjavF0` → TEST 10s), verify
the output is ≥8 s / 1080×1920 / 25 FPS / audio+video, and only then create the
`ai-avatar-studio-ui-v1` tag. Separately, schedule the env-migration task (§D8)
to remove the LatentSync repo coupling.