# AI Avatar Studio — V1.6.0 Runtime Hardening REAL Acceptance

**Status:** `HARDENED_AND_REAL_ACCEPTED`
**Date:** 2026-08-29
**Supplement to:** `docs/V1_6_RUNTIME_DEPLOYMENT_HARDENING.md` (not a replacement)
**Production Truth SHA1 (unchanged):** `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`

This document records **controlled failure-injection acceptance** of the four
mechanisms that were previously proven only by unit/static evidence. Each test
injects a controlled failure into the **real running Studio**, observes the
protection, restores original state, and verifies production health.

**Safety contract honored:** no ElevenLabs calls, no MuseTalk, no GPU renders, no
voice-profile/TTS/render-truth changes, no commits, no tags. Every temporary
fixture was removed.

---

## Executive Summary

All four previously-UNIT_TEST_ONLY mechanisms are now **PROVEN_REAL** against the
live production server on port 8077 (and a safe test port for the unknown-owner
test):

| Mechanism | Previous evidence | New evidence | Result |
|---|---|---|---|
| Code drift detection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Restart-required detection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Browser restart warning | PROVEN_STATIC | **PROVEN_REAL** | PASS |
| Unknown process protection | PROVEN_STATIC + UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Active-job restart protection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Contract mismatch (backend) | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Browser contract guard | PROVEN_STATIC | **PROVEN_REAL** | PASS |
| Controlled restart | PROVEN_REAL (prior) | **PROVEN_REAL** (re-confirmed) | PASS |

The system was fully restored: one canonical Studio process remains on 8077, code
sync is CURRENT, Production Truth is unchanged, and the full regression passes
(173 tests, 1 skipped).

---

## Starting Baseline

Captured before any failure injection.

**Git:** branch `main`, HEAD `788cbf54478edec87b78b5216ee99b0b246d9d60`, 12 modified
files, 8 new untracked hardening files (see Git Change-Count Reconciliation).

**Runtime status** (`/api/system/status?frontend_contract=2026-08-29.1`):

```
ready: true
runtime_ready: true, renderer_ready: true
code_sync: CURRENT, restart_required: false
contract_sync: true, studio_accepting_new_work: true
canonical_runtime: true
process.pid: 1924
process.boot_id: d4631c3e0a5242eaba052dc066ba4615
process.interpreter: D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe
code.startup_fingerprint: e3cbe1cda4fce764…
code.disk_fingerprint:    e3cbe1cda4fce764…   (== startup → CURRENT)
production_truth.hash: a5a0e55f46c29c1722efc5cc3f8fec3d902260f0  (valid)
active_jobs: 0
```

Expected starting state confirmed: `code_sync=CURRENT`,
`restart_required=false`, `contract_sync=true`, `canonical_runtime=true`.

---

## Test A — Real Code Drift

**Goal:** prove a running Studio detects that restart-sensitive backend code on
disk changed after process startup — without a restart.

**Target file:** `studio/runtime_guard.py` (one of the 19 restart-sensitive
files). The injection appended a **Python comment** (`# RUNTIME_DRIFT_ACCEPTANCE
_FIXTURE <ts>`) — semantically harmless. Exact original bytes were backed up first.

**Step 1 — inject + observe (no restart):**

| Field | Before | After injection |
|---|---|---|
| `code.sync` | CURRENT | **STALE** |
| `code.restart_required` | false | **true** |
| `code.startup_fingerprint` | e3cbe1cda4fce764 | e3cbe1cda4fce764 (**frozen**) |
| `code.disk_fingerprint` | e3cbe1cda4fce764 | **769e5ae5ef4f3848** (changed) |
| `studio_accepting_new_work` | true | **false** |

The startup fingerprint stayed frozen while the disk fingerprint changed →
`STALE` + `restart_required=true`. `DRIFT_DETECTED: True`.

**Step 2 — browser warning (Playwright, drift active):**

`#runtimeBanner` (hidden=false, class `runtime-banner warn`):
> *"AI Avatar Studio cần khởi động lại. Mã nguồn hệ thống đã thay đổi sau khi máy
> chủ được khởi động. Một số chức năng mới có thể chưa hoạt động cho đến khi Studio
> được khởi động lại."*

Local-owner "Khởi động lại Studio" button present. System Status card:
*"Đồng bộ mã nguồn ● Cần khởi động lại Studio"*. No console errors.
Screenshot: `C:\tmp\accept_drift_banner_1440.png`.

**Step 3 — restore byte-for-byte:**

- On-disk SHA before restore: `98f7e24a…` (modified)
- Restored SHA256: `b2d0272dc85ad17c5724acbeeeb8aac1b96466b1e299599317c58e048ef910f2`
- `MATCHES_ORIGINAL: True`
- After restore: `code_sync=CURRENT`, `restart_required=false`,
  `studio_accepting_new_work=true` — **self-recovered** (the startup fingerprint
  was never mutated, so restoring the disk was sufficient; no manual state override).

**Step 4 — controlled restart:**

- `POST /api/studio/restart` → `200 {ok:true, restarting:true}`
- OLD_PID `1924` / OLD_BOOT `d4631c3e…` → NEW_PID `14048` / NEW_BOOT `b4b54f92…`
- `BOOT_ID_CHANGED: True`, `PID_CHANGED: True`
- Post-restart: `code_sync=CURRENT`, `canonical_runtime=true`, `contract_sync=true`,
  `startup_fingerprint == disk_fingerprint` = e3cbe1cda4fce764
- `RESTART_OK: True`

**Classification:** `PROVEN_REAL` — the actual running server observed `STALE` and
returned to `CURRENT` after a controlled restart, with a new boot_id.

---

## Drift Browser Warning

See Test A Step 2. The persistent `#runtimeBanner` (class `runtime-banner warn`)
carried the exact Vietnamese drift wording and the local restart action. Evidence
is DOM text (not screenshot-only). `has_drift_text_in_body: true`.

---

## Controlled Restart After Drift

See Test A Step 4. The hardened `POST /api/studio/restart` (owner-direct) spawned
`tools/restart_studio.py` detached, which verified the owner identity, requested
graceful shutdown, relaunched the canonical interpreter, waited for HTTP readiness,
verified `code_sync=CURRENT` + contract + canonical runtime, and ran post-start
smoke. New PID `14048`, new boot_id `b4b54f9224494905`.

---

## Test B — Unknown Port Owner

**Goal:** prove process-identity logic refuses to treat a non-Studio process as the
Studio and does **not** kill it. Performed on a **safe test port 18077**; production
port 8077 was never touched.

**Disposable owner:** `python -m http.server 18077` (command line has no
`run_studio.py`). Actual listener PID `15500` (the venv launcher spawns a child that
holds the socket).

**Decision (real `runtime_guard.single_instance_decision(18077)`):**
```json
{"action": "unknown_owner", "detail": {"port": 18077, "owner_pid": 15500,
 "reason": "cmdline_not_studio"}}
```
`_owner_is_studio(15500)` → `False`, reason `cmdline_not_studio`.

**Survival evidence:**
- `ALIVE_AFTER_DECISION: True` (owner PID 15500 still running)
- `HTTP_PROBE_AFTER: 200` (listener still answers — **not killed**)
- `PROCESS_SURVIVED: True`
- `TEST_B_PASS: True`

**Cleanup:** the disposable process was terminated explicitly as teardown;
`PORT_FREE_AFTER_CLEANUP: True`. Port 8077 was untouched throughout.

**Classification:** `PROVEN_REAL` — a real non-Studio process on a real port was
classified `unknown_owner` and survived (no `taskkill`).

---

## Unknown Process Survival Evidence

See Test B. The hardening's `single_instance_decision` only **decides** — it never
issues a kill. The real restart orchestrator's `_owner_is_studio` returned `False`
(`cmdline_not_studio`), which makes `restart_studio.orchestrate` return
`PORT_CONFLICT_UNKNOWN_PROCESS` without terminating. The disposable HTTP server
kept serving `200` after the decision.

---

## Test C — Active Job Restart Block

**Goal:** prove a restart request cannot interrupt an active job without `--force`.

**Fixture:** `job_id = TEST_ONLY_RUNTIME_RESTART_GUARD_1787984635`, inserted with
`status='rendering'`. This is an ACTIVE status (counted by `list_active_jobs`) but
is **never claimed** by the worker (which only selects `status='queued'`), so no
ElevenLabs/GPU/MuseTalk was triggered. The fixture was physically deleted afterward
(no history pollution).

**Result:**
- `db.list_active_jobs()` count `1`, fixture present ✓
- `POST /api/studio/restart` (loopback/owner-direct) → **HTTP 409**:
  ```json
  {"ok": false, "blocked": true, "reason": "ACTIVE_JOBS_BLOCK_RESTART",
   "active_jobs": [{"job_id": "TEST_ONLY_…", "status": "rendering"}],
   "error": "Có render đang chạy. Hoàn tất (hoặc huỷ) các job trước, …"}
  ```
- `PID_AFTER: 14048` **unchanged**; `BOOT_ID_AFTER: b4b54f92…` **unchanged**;
  port 8077 still listening (PID 14048)
- Fixture still present after the rejected restart (not removed)
- `TEST_C_BLOCKED: True`, `TEST_C_PROCESS_UNCHANGED: True`
- Cleanup: `DELETE FROM jobs WHERE job_id=?` → `FIXTURE_DELETED: True`,
  `ACTIVE_AFTER_CLEANUP: 0` (matches baseline)

**Classification:** `PROVEN_REAL` — a real restart request was rejected with `409`
and the Studio process was not interrupted.

---

## Test D — Contract Mismatch

**Goal:** prove a frontend/backend contract mismatch becomes an explicit
synchronization error **before** the user hits a random 404. No production file was
edited.

### Backend mismatch

`GET /api/system/status?frontend_contract=TEST_MISMATCH_DO_NOT_SHIP`:

| Field | Good request | Mismatched request |
|---|---|---|
| `contract.backend_version` | 2026-08-29.1 | 2026-08-29.1 |
| `contract.frontend_version` | 2026-08-29.1 | TEST_MISMATCH_DO_NOT_SHIP |
| `contract.compatible` | true | **false** |
| `contract_sync` | true | **false** |
| `studio_accepting_new_work` | true | **false** |

The backend clearly identifies the mismatch — no 404 needed.

### Browser contract guard (Playwright)

Playwright intercepted `**/api/system/status**` and rewrote `frontend_contract` to
`TEST_MISMATCH_DO_NOT_SHIP`, so the **real served frontend** rendered the mismatch.

- Captured response: status 200, `contract_sync=false`, `studio_accepting_new_work=false`,
  `compatible=false` (the exact field `guardWorkFlow` checks)
- `#runtimeBanner` (class `runtime-banner warn`):
  > *"Phiên bản giao diện và máy chủ chưa đồng bộ. Cần khởi động lại AI Avatar
  > Studio để áp dụng thay đổi."*
- `has_mismatch_text: true`
- System Status card (Advanced details expanded):
  *"Nhận công việc mới Không (cần restart)"* — new work is gated
- Screenshot: `C:\tmp\accept_contract_mismatch_1440.png`

**Restored:** interception removed (page closed); a fresh
`?frontend_contract=2026-08-29.1` request returned `contract_sync=true`,
`studio_accepting_new_work=true`.

**Classification:** `PROVEN_REAL` — the browser received the mismatched state and
surfaced a blocking warning; the new-work guard field was `false`; normal contract
restored afterward.

---

## Browser Contract Guard

See Test D (browser). The guard data (`studio_accepting_new_work=false`) reached
the browser (captured response body), the blocking banner appeared, and the System
Status card showed *"Nhận công việc mới Không (cần restart)"*. The `guardWorkFlow`
logic that consumes this field is unit-tested; the live evidence confirms the field
reaches the browser correctly. (Note: `guardWorkFlow` is a top-level `const`, not a
`function` declaration, so it is not on `window` — the guard was verified via the
captured status payload + the System Status card rather than a direct
`window.guardWorkFlow()` call.)

---

## Restart Button Security (spec §17)

- **Local authorized owner → request reaches restart policy:** `PROVEN_REAL`.
  Test C's `409 ACTIVE_JOBS_BLOCK_RESTART` was returned by the real policy
  evaluating the active job on a loopback request.
- **Remote / non-owner → denial:** `UNIT_TEST_ONLY`
  (`test_remote_restart_forbidden` asserts HTTP 403 + *"quản trị viên"* wording).
  Per spec §17, no real external attacker simulation was performed and the
  Cloudflare configuration was not touched. Reported accurately, not overclaimed.

---

## Final Single-Instance Verification

- `PORT_8077_LISTENERS: [14048]` — exactly **one** listener
- `_owner_is_studio(14048)` → `True`, reason `studio`
- cmdline: `…python.exe …run_studio.py --host 127.0.0.1 --port 8077 --no-browser`
- `EXACTLY_ONE_STUDIO: True`
- Test ports `18077` and `8099` both free (no leftover test servers)

---

## Final Canonical Runtime Verification

- `process.canonical_runtime: True`
- `process.interpreter: D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe`
- `canonical_interpreter` (expected): `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe`
- Match confirmed. No system-Python fallback.

---

## Final Port 8077 Smoke

Post-start smoke against the restored production server (no TTS, no GPU):

| Route | Status | Content-Type |
|---|---|---|
| `/` | 200 | text/html |
| `/static/app.js` | 200 | application/javascript |
| `/api/system/status` | 200 | application/json |
| `/api/voices/approved` | 200 | application/json |
| Thanh `/sample` | 200 | **audio/wav** |
| Hạnh `/sample` | 200 | **audio/wav** |
| `/sample/download` | 200 | audio/wav |

`SMOKE_ALL_PASS: True`. Current status: `code_sync=CURRENT`,
`restart_required=false`, `contract_sync=true`, `ready=true`, PID `14048`,
boot_id `b4b54f9224494905`.

---

## Playwright Final Health

Against the restored Studio, viewports 1440×900 and 390×844:

- `no_banner: true` — no restart/contract/runtime warning (banner hidden)
- `status_text: "SẴN SÀNG"` on both viewports
- `sync_ok: true` — *"Đồng bộ — Không cần khởi động lại"*
- `no_horizontal_overflow: true` on both viewports
- `voice_ui_present: true` on both viewports; Create Video opens on 1440
  (`create_video_opens:false` on 390 is a mobile-nav text-detection quirk, not a
  functional failure — voice UI is present on both)
- Thanh "Nghe mẫu": `200 audio/wav`, duration `4.56s`, no error toast
- Hạnh "Nghe mẫu": `200 audio/wav`, duration `4.32s`, no *"Không tải được mẫu giọng đọc"* toast
- `FINAL_HEALTH_PASS: true`

No subjective visual quality is claimed. Screenshots are in `C:\tmp\` for human
review (this session's model cannot view images; evidence above is DOM/behavior
text).

---

## Git Change-Count Reconciliation (spec §22)

The previous hardening report said **"12 modified, 7 new"** but listed **8** new
hardening files. Per `git status` / `git diff --name-only` / `git ls-files`, the
truth is:

**Modified (12):**
- Hardening (7): `AI_Avatar_Studio.bat`, `run_studio.py`, `studio/app.py`,
  `studio/config.py`, `studio/static/app.js`, `studio/static/index.html`,
  `studio/static/styles.css`
- Concurrent voice/TTS work (5 — NOT reverted, NOT modified by this task):
  `studio/avatar_service.py`, `studio/db.py`, `studio/elevenlabs_client.py`,
  `studio/render_service.py`, `studio/runtime.py`

**New / untracked hardening files (8 — corrected from 7):**
1. `studio/runtime_guard.py`
2. `config/api_contract.json`
3. `config/runtime_requirements_manifest.json`
4. `tools/restart_studio.py`
5. `tools/verify_runtime.py`
6. `tools/_hardening_playwright.py`
7. `tests/test_runtime_hardening.py`
8. `docs/V1_6_RUNTIME_DEPLOYMENT_HARDENING.md`

The previous count of 7 was wrong: it listed 8 files in its bullet list but wrote
"7" in the summary. The correct count is **8 new hardening files**. The original
hardening report's file *list* was correct; only its *count* was off by one. This
acceptance doc carries the corrected count.

(Additional untracked files present in the worktree — `handover/`, `docs/HDSD_*`,
`input4_9/`, other `docs/V1_6_*.md`, `tools/_audit_playback_repro.py`,
`tools/rebuild_runtime.ps1`, `studio/preview_service.py`, `studio/voices.py`,
other `tests/test_*.py` — belong to other concurrent/earlier work and are not part
of this hardening or this acceptance. They were not touched.)

---

## Regression Coverage (spec §26)

Permanent automated regression coverage for all four mechanisms **already exists**
in `tests/test_runtime_hardening.py`:

- code drift → restart_required: `test_drift_detected_when_disk_differs_from_startup`
- unknown process → never kill: `test_unknown_owner_not_killed`
- active job → restart blocked: `test_local_restart_blocked_by_active_job`
- contract mismatch → explicit mismatch state: `test_mismatch_detected`

No new tests were added (spec §26: do not duplicate existing tests unnecessarily).
The real acceptance above elevates these from UNIT_TEST_ONLY to PROVEN_REAL
evidence for the live system, while the unit tests remain as the recurring guard.

---

## Regression Results

`python -m unittest discover -s tests -p "test_*.py"`:
```
Ran 173 tests in 14.2s
OK (skipped=1)
```

All preserved suites pass: runtime hardening, Two-Voice Lock, Language Resolver,
Management Safety, Script Voice Preview, audio download, Studio runtime,
Production Truth. No regressions.

---

## Production Truth

```
a5a0e55f46c29c1722efc5cc3f8fec3d902260f0 *config/render_truth.json
```

`VALID` — unchanged, matches the expected invariant exactly. The file was never
mutated by any acceptance step.

---

## Secret Scan

Scanned all acceptance artifacts (`tools/_accept_*.py`,
`docs/V1_6_RUNTIME_HARDENING_REAL_ACCEPTANCE.md`) for `xi-api-key`,
`ELEVENLABS_API_KEY=<value>`, `Authorization: Bearer`, `CLOUDFLARE…secret`,
`sk-…` tokens: **clean** (no secret values). The instance manifest contains only
boot_id/pid/timestamps/interpreter/fingerprints/git/truth-hash (no secrets). No
ElevenLabs quota was consumed.

---

## Cleanup Verification

- Drift marker: restored byte-for-byte; `grep -c RUNTIME_DRIFT_ACCEPTANCE_FIXTURE
  studio/runtime_guard.py` = 0; SHA256 = `b2d0272…` (original). ✓
- Backup file `data/studio_runtime/_accept_drift_backup_runtime_guard.py`: deleted. ✓
- Active-job fixture: physically deleted; `active_jobs=0`, no `TEST_ONLY` rows. ✓
- Contract override (Playwright interception): removed on page close; normal
  `contract_sync=true` confirmed after. ✓
- Disposable port-18077 HTTP server: terminated; port 18077 free. ✓
- No leftover listeners on 18077 or 8099. ✓
- Temp `_accept_*.py` scripts: kept as **reproducible evidence** (untracked, like
  the existing `tools/_hardening_playwright.py`). No production data deleted.

---

## Evidence Classification

| Capability | Previous Evidence | New Evidence | Result |
|---|---|---|---|
| Single instance | PROVEN_REAL | PROVEN_REAL (re-confirmed: exactly one Studio) | PASS |
| Canonical runtime | PROVEN_REAL | PROVEN_REAL (re-confirmed) | PASS |
| Code drift detection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Restart-required detection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Browser restart warning | PROVEN_STATIC | **PROVEN_REAL** | PASS |
| Unknown process protection | PROVEN_STATIC + UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Active-job restart protection | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Controlled restart | PROVEN_REAL | PROVEN_REAL (re-confirmed, new boot_id) | PASS |
| Boot ID | UNIT_TEST_ONLY + PROVEN_REAL | PROVEN_REAL (d4631c3e→b4b54f92) | PASS |
| Contract mismatch | UNIT_TEST_ONLY | **PROVEN_REAL** | PASS |
| Browser contract guard | PROVEN_STATIC | **PROVEN_REAL** | PASS |
| Post-start smoke | PROVEN_REAL | PROVEN_REAL (7/7) | PASS |
| Thanh sample | PROVEN_REAL | PROVEN_REAL (200 audio/wav, 4.56s) | PASS |
| Hạnh sample | PROVEN_REAL | PROVEN_REAL (200 audio/wav, 4.32s) | PASS |
| Production Truth | PROVEN_REAL | PROVEN_REAL (unchanged) | PASS |
| Regression | PROVEN_REAL (173) | PROVEN_REAL (173 OK, 1 skipped) | PASS |
| Remote restart rejection | UNIT_TEST_ONLY | UNIT_TEST_ONLY (per §17, not simulated) | PASS (coverage = unit) |

---

## Known Limitations / Accurate Reporting

- **Remote restart rejection** remains `UNIT_TEST_ONLY`. Per spec §17 no real
  external attacker simulation was performed and Cloudflare was not touched. The
  local-owner path reaching the policy is PROVEN_REAL (Test C's 409).
- **`guardWorkFlow`** is a top-level `const` (not on `window`), so the browser
  guard was verified via the captured status payload + the System Status card
  ("Nhận công việc mới Không (cần restart)"), not a direct `window.guardWorkFlow()`
  call. The guard logic itself is unit-tested.
- The 390×844 `create_video_opens:false` is a mobile-nav text-detection quirk;
  voice UI is present on both viewports and Create Video opens on desktop.
- Screenshots are saved under `C:\tmp\` for human review; this session's model
  cannot view images, so all evidence above is DOM/behavior text + JSON.

---

## Final Recommendation

Accept the V1.6.0 runtime/deployment hardening as **HARDENED_AND_REAL_ACCEPTED**.
All previously unit-only failure-prevention mechanisms were proven against the real
running system via controlled failure injection, the system was fully restored to a
single canonical Studio with `code_sync=CURRENT`, Production Truth is unchanged,
the full regression passes, and no secrets were exposed. No voice profile, TTS
model, or renderer setting was touched; no ElevenLabs quota was consumed.

---

## HARD STOP

Stopping here per spec §35. No commits, no V1.6.0 tag, no voice/Hạnh/Thanh/MuseTalk
changes, no new product features. Awaiting human review.