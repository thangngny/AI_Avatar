# AI Avatar Studio — V1.6.0 Runtime / Deployment Hardening

**Status:** `HARDENED_AND_VERIFIED`
**Date:** 2026-08-29
**Author:** hardening pass (V1.6.0 candidate work)
**Production Truth SHA1 (must be unchanged):** `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`

---

## 1. Executive Summary

A proven operational incident class was eliminated from the AI Avatar Studio:

> **The code on disk changed, but the long-running production server did not restart.**
> The browser received NEW frontend JavaScript while the Flask backend process still
> held an OLD route table in memory. The frontend called a newly-added `/sample` route
> the stale backend did not know → HTTP 404 → `Audio.onerror` → user saw
> *"Không tải được mẫu giọng đọc"*.

The immediate incident was fixed by restarting the Studio. This hardening **prevents the
class from recurring** by making the frontend↔backend desync **visible before** the user
hits a random 404, and by providing a **controlled, identity-verified restart**.

Hardening pillars implemented:

| Pillar | Mechanism |
|---|---|
| Process identity | PID + creation time + command line + interpreter (never PID alone) |
| Single instance | `single_instance_decision()` before bind; unknown owner never killed |
| Canonical runtime | `AI_Avatar_Studio.bat` hard-pins the venv interpreter; no fallback |
| Instance manifest | Atomic `data/studio_runtime/studio_instance.json` (no secrets) |
| Code-drift detection | SHA256 over a bounded restart-sensitive manifest; startup vs disk |
| Contract versioning | `config/api_contract.json` single source of truth; frozen at boot |
| Frontend handshake | `app.js` sends `frontend_contract=`; mismatch → blocking banner |
| Boot ID | Per-start UUID; browser detects server swap while tab open |
| READY semantics | Composite: code_sync + contract_sync + canonical_runtime + truth |
| Safe restart | `tools/restart_studio.py` orchestrator; owner-direct; active-job safe |
| Post-start smoke | 7 low-cost routes (no TTS, no GPU) verified after every restart |
| Operator visibility | "Trạng thái máy chủ" card + drift/contract/runtime banners |

**No Flask debug auto-reload, no watchdog, no hot reload.** Drift is DETECTED and REPORTED;
a restart is performed by a controlled orchestrator.

---

## 2. Original Incident

Symptom: the user clicked "Nghe mẫu" (listen to sample) for an approved voice and saw
*"Không tải được mẫu giọng đọc"* (could not load the voice sample).

Root failure chain (proven):

```
new app.js on disk
  → stale backend process still running (loaded app.py BEFORE the /sample route existed)
  → frontend calls newly-added /api/voices/approved/<id>/sample
  → stale backend does not know the route
  → HTTP 404
  → browser Audio.onerror
  → user sees "Không tải được mẫu giọng đọc"
```

The static-asset/backend desync root cause is documented in
`docs/V1_6_STATIC_VOICE_SAMPLE_PLAYBACK_ROOT_CAUSE.md`.

---

## 3. Root Cause

Flask route registration is **frozen at process startup**. Static `app.js` is served fresh
from disk on every request. Therefore, whenever backend Python code is edited while the
server keeps running, the **frontend/backend route contract becomes inconsistent** with no
visible signal — the server still happily reports "READY".

The fix is not "restart on every file change" (unsafe for a GPU/queue/subprocess server).
The fix is: **detect the drift cryptographically, surface it, and offer a controlled
restart**.

---

## 4. Current Startup Architecture (audit)

```
AI_Avatar_Studio.bat
  └─ STUDIO_PY = D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe   (hard-pinned)
     └─ run_studio.py run_studio.py --host 127.0.0.1 --port 8077
        ├─ config.ensure_runtime_dirs()
        ├─ db.init_db()
        ├─ render_service.start()                      (queue worker thread)
        ├─ _startup_hardening(port):                   [V1.6.0 NEW]
        │    1. canonical_interpreter_exists() / interpreter_is_canonical()
        │    2. runtime_guard.single_instance_decision(port)
        │    3. runtime_guard.init_at_startup()        (freeze boot_id + fingerprint + manifest)
        ├─ from studio.app import app
        └─ app.run(debug=False, use_reloader=False, threaded=True)
```

Audit findings (before this work):

- Server entrypoint: `run_studio.py` → `studio.app:app`.
- Interpreter: previously selected via `STUDIO_PY` with a **`python` fallback** (unsafe).
- Subprocesses: the controller spawns the production renderer
  (`generate_video_from_script.py`) via the torch-capable interpreter; the controller
  itself never imports torch.
- PID: **not** persisted before this work.
- Port ownership: **not** checked before this work.
- Duplicate-launch prevention: **none** before this work.
- Graceful shutdown: **none** before this work.
- Active-job state: `db.list_active_jobs()` already exists (used for restart safety).
- Queue reconciliation: `_reconcile_inflight_jobs()` in `render_service` already exists and
  is preserved unchanged.

---

## 5. Single-Instance Design

`runtime_guard.single_instance_decision(port)` is called by `run_studio.py` **before** the
server binds. It returns exactly one of:

| `action` | Meaning | `run_studio.py` response |
|---|---|---|
| `proceed` | Port is free | Bind it |
| `already_running` | A **verified** Studio owns the port | `sys.exit(0)` (no duplicate) |
| `unknown_owner` | Something else owns the port | `sys.exit(1)` (never kill unknown) |
| `stale_manifest` | Manifest points at a dead/reused PID | Clear manifest, proceed |

The launcher UX for "already running" prints:
```
Studio already running
  PID:    <live>
  Port:   8077
  Runtime: <interpreter>
  Started: <server_started_at>
  No duplicate server spawned. Open http://127.0.0.1:8077/
```

---

## 6. Process Identity Design

A PID alone is **not** trusted (Windows reuses PIDs). Identity is established from
**multiple signals** via `pid_matches_manifest()` and `_owner_is_studio()`:

1. **PID alive** (`psutil.Process.is_running()`)
2. **Process creation time** matches the manifest within 1.0 s — defeats PID reuse
3. **Command line** contains `run_studio.py`
4. **Interpreter** is the canonical venv interpreter **or its base interpreter**
   (the Windows venv launcher spawns the base `python.exe`; both are the canonical runtime,
   verified via `pyvenv.cfg` `home`)

If any signal fails the identity is rejected with a reason
(`pid_dead` / `creation_time_mismatch (PID reused)` / `cmdline_not_studio` /
`interpreter_not_canonical`).

---

## 7. Canonical Runtime Enforcement

- `config.CANONICAL_INTERPRETER` = `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe`.
- `AI_Avatar_Studio.bat` hard-pins `STUDIO_PY` to that path. **If it is missing the launcher
  STOPS** with `CANONICAL_RUNTIME_MISSING` — there is **no fallback to `python`/`py`/PATH**.
- `run_studio.py` checks `canonical_interpreter_exists()` (missing → STOP) and
  `interpreter_is_canonical()` (wrong → `RUNTIME_MISMATCH`, serves for diagnostics but
  `canonical_runtime=false` so READY is never claimed).
- `interpreter_is_canonical()` compares normalized real paths (case- and
  separator-insensitive).

`verify_runtime.py` probes the renderer interpreter for torch/CUDA/deps and reports
`READY`/`NOT_READY` (read-only, no model loading).

---

## 8. Runtime Instance Manifest

Path: `data/studio_runtime/studio_instance.json` (gitignored — machine-specific).
Written atomically (temp-file → `os.replace`) at boot by `init_at_startup()`.

Fields (no secrets):

```json
{
  "boot_id": "d4631c3e0a5242eaba052dc066ba4615",
  "pid": 1924,
  "process_created_at": 1787982541.17,
  "server_started_at": 1787982543.74,
  "interpreter": "D:\\CongThang_AI_Avatar\\runtime\\venv\\Scripts\\python.exe",
  "entrypoint": "run_studio.py",
  "repository": "C:\\CongThang_AI_Avatar\\AI_avatar",
  "port": 8077,
  "startup_code_fingerprint": "e3cbe1cda4fce764...",
  "backend_contract_version": "2026-08-29.1",
  "git_head": "788cbf54478edec87b78b5216ee99b0b246d9d60",
  "git_dirty": true,
  "production_truth_hash": "a5a0e55f46c29c1722efc5cc3f8fec3d902260f0"
}
```

**Never stored:** API keys, `.env`, ElevenLabs credentials, Cloudflare secrets, auth
headers. (Asserted by `test_manifest_has_no_secrets`.)

`data/studio_runtime/` is in `.gitignore`, so the manifest is not accidentally tracked.

---

## 9. Stale-PID Safety

On read, `pid_matches_manifest()` verifies PID + creation time + command line. A dead or
reused PID is classified `STALE_INSTANCE_MANIFEST` and the manifest is safely replaced
(`clear_instance_manifest()`) — it is never treated as a running Studio. Tested by
`test_stale_manifest_dead_pid_rejected` and `test_stale_manifest_creation_time_mismatch_rejected`.

---

## 10. Code Fingerprint Design

- `_file_sha256(path)` — SHA256 of a file; a missing/unreadable file yields a stable
  `"missing:<path>"` sentinel so a disappearing file is still a deterministic change.
- `compute_code_fingerprint()` — SHA256 over the **sorted** concatenation of
  `relpath + \x00 + file_sha256 + \x01` for each restart-sensitive file. Stable ordering,
  platform-independent.
- `current_disk_fingerprint()` — wraps the above with a **2-second TTL cache** so repeated
  status polls don't re-hash. `force=True` bypasses the cache.

mtime is **never** trusted (§27): copy/checkout/clock/restore can lie about timestamps.
Only SHA256 content fingerprints are used.

---

## 11. Restart-Sensitive File Manifest

Explicit, bounded list in `runtime_guard.RESTART_SENSITIVE_FILES` — backend Python modules
loaded into the Studio **server** process whose in-memory behavior is frozen at start:

```
run_studio.py, studio/__init__.py, studio/app.py, studio/config.py, studio/db.py,
studio/render_service.py, studio/avatar_service.py, studio/runtime.py,
studio/preview_service.py, studio/elevenlabs_client.py, studio/voices.py,
studio/gpu_service.py, studio/edge_tts_client.py, studio/script_service.py,
studio/share_auth.py, studio/envutil.py, studio/avatar_quality.py, studio/verify.py,
studio/runtime_guard.py
```

Classification:

| Class | Examples | Triggers restart? |
|---|---|---|
| **RESTART-SENSITIVE** | backend Python above | Yes (code drift) |
| **HOT-SAFE** | docs, reports, screenshots, renders | No |
| **FRONTEND** | `app.js`, `index.html`, `styles.css` | No (caught by contract handshake) |
| **CONTRACT** | `config/api_contract.json` | No (versioned, not hashed) |

Frontend drift is caught by the **contract handshake**, not the backend fingerprint.

---

## 12. Code Drift Detection

At every `/api/system/status` call, `runtime_status_snapshot()` compares:

- `startup_code_fingerprint` (frozen at boot)
- `disk_fingerprint` (recomputed now, TTL-cached)

| Condition | `code.sync` | `code.restart_required` |
|---|---|---|
| equal | `CURRENT` | `false` |
| differ | `STALE` | `true` |

When `restart_required`, `studio_accepting_new_work = false` — an already-running
immutable render may finish, but NEW mutable workflows are blocked in the UI.

Drift transition logging (`note_drift_if_changed()`) logs `STUDIO_CODE_DRIFT_DETECTED`
**once per newly-changed fingerprint**, not on every poll.

---

## 13. API Contract Versioning

Single source of truth: `config/api_contract.json`:

```json
{ "contract_version": "2026-08-29.1" }
```

- Backend **freezes** this value at startup (`init_at_startup()` → `backend_contract_version`).
- Frontend **embeds** the same value in `app.js` (`const STUDIO_API_CONTRACT = "2026-08-29.1"`).
- `test_contract_json_and_frontend_constant_match` asserts the two stay identical, so the
  contract is not scattered across files.

This is deliberately **not** tied to the marketing version V1.6.0.

---

## 14. Frontend/Backend Handshake

`loadStatus()` calls:
```
/api/system/status?frontend_contract=<STUDIO_API_CONTRACT>
```

`runtime_status_snapshot(frontend_contract=…)` compares the browser-sent version against the
frozen backend version:

| Condition | `contract.compatible` |
|---|---|
| equal | `true` |
| differ | `false` |
| frontend omitted | `known=false` (not silently compatible) |

On mismatch the frontend shows a **blocking banner**:
> *"Phiên bản giao diện và máy chủ chưa đồng bộ. Cần khởi động lại AI Avatar Studio để áp dụng thay đổi."*

The user is never left to discover the desync through a random 404/405/undefined API error.

---

## 15. Code-Drift UI Warning

When `restart_required` or `code_sync == STALE`, a persistent banner is shown:
> *"AI Avatar Studio cần khởi động lại. Mã nguồn hệ thống đã thay đổi sau khi máy chủ được
> khởi động. Một số chức năng mới có thể chưa hoạt động cho đến khi Studio được khởi động lại."*

The **"Khởi động lại Studio"** button is shown **only to the local owner**
(`isLocalhost()`); remote collaborators see:
> *"Studio cần được quản trị viên khởi động lại."*

A `RUNTIME_MISMATCH` (wrong interpreter) shows a separate `bad`-severity banner.

---

## 16. READY Semantics

The single ambiguous `READY` boolean is replaced by composite health dimensions
exposed on `/api/system/status`:

```
runtime_ready            (interpreter sanity)
renderer_ready           (renderer entrypoint present)
production_truth_valid   (render_truth.json hash)
code_sync                CURRENT | STALE
contract_sync            true | false
restart_required         bool
active_jobs              int
studio_accepting_new_work bool
ready                    (composite: code_sync CURRENT + contract_sync + canonical_runtime + truth)
```

Policy: an **already-running immutable render job may finish**, but if `code_sync=STALE`
or `contract_sync=false`, then `studio_accepting_new_work=false` and the UI discourages
NEW mutable workflows. Active renders are **not** terminated merely because source changed.

---

## 17. Active-Job Restart Policy

`/api/studio/restart` and `tools/restart_studio.py` query `db.list_active_jobs()`.
If active jobs exist and `--force` is not set → `RESTART_BLOCKED_ACTIVE_JOB` (HTTP 409):
the restart is deferred and the jobs are allowed to finish. This default avoids
interrupting real GPU work. `--force` is an explicit local-operator override.

---

## 18. Controlled Restart Architecture

`tools/restart_studio.py` implements the 16-step procedure (spec §16):

1. Inspect current 8077 owner (`_port_owner`).
2. Verify it IS the Studio (`_verify_studio` → `_owner_is_studio`).
3. Query active jobs.
4. If active and not `--force` → `ACTIVE_JOBS_BLOCK_RESTART` (rc 3).
5. Graceful shutdown (`POST /api/studio/shutdown`, owner-direct).
6. Wait bounded time for exit.
7. If the **verified** Studio remains → targeted psutil tree termination. If the owner
   changed mid-restart to an unknown process → **abort** (never kill unknown).
8. Verify port released (`_wait_port_free`, 20 s).
9. Launch canonical interpreter + `run_studio.py` detached.
10. New PID/creation time from the new instance manifest.
11. Verify canonical runtime (`process.canonical_runtime`).
12. HTTP readiness (`_wait_http_ready`, 40 s).
13. Code fingerprint matches disk (`code.sync == CURRENT`).
14. Contract versions match (`contract.compatible`).
15. Post-start smoke (7 routes, no TTS/GPU).
16. `STUDIO_RESTART_COMPLETE` + `db.log_activity`.

All process control uses psutil / validated numeric PIDs / trusted internal paths — no
shell strings from untrusted input (§36).

---

## 19. Unknown-Port Safety

`PORT_OCCUPIED` does **not** imply safe to kill. Before any termination, identity is
verified (PID + creation time + command line + interpreter). If identity cannot be
established, the orchestrator returns `PORT_<port>_CONFLICT_UNKNOWN_PROCESS` and
**refuses to kill** (rc 2). Tested by `test_unknown_owner_not_killed`.

---

## 20. Boot ID

`init_at_startup()` mints a UUID `boot_id` per start, exposed at
`/api/system/status` → `process.boot_id`. The frontend records `_lastBootId`; if it
changes while the tab is open, `handleRuntimeGuard()` shows
*"AI Avatar Studio đã khởi động lại. Đang tải lại trạng thái."* and refreshes
runtime-dependent state (avatars/voices) — **without discarding the user's script
draft** and **without a hard page reload**. Tested by `test_boot_id_changes_on_reinit`.

---

## 21. Server Start Time & Diagnostics

`/api/system/status` → `process` exposes: `pid`, `boot_id`, `server_started_at`,
`process_created_at`, `interpreter`, `canonical_runtime`, `canonical_interpreter`,
`canonical_interpreter_exists`, `entrypoint`, `port`. The `code` block exposes
`git_head`, `git_dirty`, `startup_fingerprint`, `disk_fingerprint`, `sync`,
`restart_required`. No sensitive environment values are exposed.

---

## 22. Git Dirty State

`git dirty = true` is **allowed** during V1.6 candidate development and is **not** a
failure by itself (§26). It is reported. The distinction that matters is:

- **DIRTY BUT LOADED** → OK for development.
- **DIRTY AND CHANGED AFTER SERVER START** → captured by the SHA256 fingerprint, so
  `restart_required` becomes true.

---

## 23. Frontend Cache Control

The contract handshake is the architectural fix; browser cache is not relied upon as the
solution (§22–23). `index.html` / `app.js` / `styles.css` cache headers follow the existing
local-Studio conventions. The `?frontend_contract=` query parameter also naturally
distinguishes a freshly-loaded frontend from a cached one, and the version constant is
checked against the JSON source of truth by the test suite.

---

## 24. Status API

`/api/system/status` is extended (not duplicated). Representative response shape (live,
this run):

```json
{
  "ready": true,
  "runtime_ready": true,
  "renderer_ready": true,
  "production_truth": { "hash": "a5a0e55f...", "valid": true },
  "process": {
    "pid": 1924,
    "boot_id": "d4631c3e0a52...",
    "server_started_at": 1787982543.74,
    "canonical_runtime": true,
    "canonical_interpreter": "D:\\...\\python.exe",
    "port": 8077
  },
  "code": {
    "git_head": "788cbf54...",
    "git_dirty": true,
    "startup_fingerprint": "e3cbe1cd...",
    "disk_fingerprint": "e3cbe1cd...",
    "sync": "CURRENT",
    "restart_required": false
  },
  "contract": {
    "backend_version": "2026-08-29.1",
    "frontend_version": "2026-08-29.1",
    "compatible": true
  },
  "code_sync": "CURRENT",
  "contract_sync": true,
  "restart_required": false,
  "active_jobs": [...],
  "studio_accepting_new_work": true
}
```

No filesystem secrets are exposed (asserted by `test_status_exposes_hardening_fields`,
which also checks the real `ELEVENLABS_API_KEY` value is not present in the response).

---

## 25. Operator UI

The **System Status** view renders a "Trạng thái máy chủ" card (`serverHealthCard`):

- Đồng bộ mã nguồn — `● Đồng bộ — Không cần khởi động lại` / `● Cần khởi động lại Studio`
- Runtime — canonical interpreter, or `Sai runtime (không phải canonical)`
- API contract — backend version (+ UI version); `Chưa đồng bộ` on mismatch
- Khởi động lúc — `server_started_at`
- PID, Boot ID
- **Chi tiết nâng cao** (collapsed): git HEAD, git dirty, startup/disk fingerprints,
  production truth, "Nhận công việc mới"

Hashes are hidden behind "Chi tiết nâng cao" so normal users are not overwhelmed.

---

## 26. Startup Launcher UX

`AI_Avatar_Studio.bat` (hardened):
- `STUDIO_PY` is hard-pinned to the canonical venv interpreter.
- If missing → `CANONICAL_RUNTIME_MISSING` and `exit /b 1` (no `python` fallback).
- Single-instance is enforced inside `run_studio.py`:
  - no Studio running → start canonical Studio;
  - correct Studio already running → print PID/Port/Runtime/Started, no duplicate;
  - unknown port owner → `PORT_8077_CONFLICT_UNKNOWN_PROCESS`, STOP;
  - stale manifest → cleared safely.
- Production URL remains `http://127.0.0.1:8077/`. No silent second server on a random port.

---

## 27. Failure Modes

Handled explicitly (no vague "something went wrong"):

`CANONICAL_RUNTIME_MISSING`, `PORT_CONFLICT_UNKNOWN_PROCESS`, `STALE_INSTANCE_MANIFEST`,
`WRONG_RUNTIME_RUNNING` / `RUNTIME_MISMATCH`, `MULTIPLE_STUDIO_PROCESSES` (prevented),
`CODE_DRIFT`, `CONTRACT_MISMATCH`, `RESTART_BLOCKED_ACTIVE_JOB`,
`RESTART_FAILED_TO_STOP_PROCESS`, `PORT_NOT_RELEASED`, `NEW_SERVER_FAILED_TO_START`,
`POST_START_SMOKE_FAILED`, `PRODUCTION_TRUTH_INVALID`.

---

## 28. Security

- `/api/studio/restart` and `/api/studio/shutdown` are **owner-direct only**
  (`_is_owner_direct()`). Remote collaborators (via Cloudflare) get HTTP 403:
  *"Studio cần được quản trị viên khởi động lại."* No remote process-control privilege.
- The Cloudflare sharing architecture is **not** redesigned.
- No shell injection (§36): all process management uses psutil, argument arrays, and
  validated numeric PIDs. No arbitrary command parameter from the browser.
- No secrets in the manifest, logs, status API, or diagnostics (asserted by tests).

---

## 29. Observability

Concise runtime log events (no secrets, no per-poll flooding):

`STUDIO_BOOT`, `STUDIO_INSTANCE_CONFLICT` (`PORT_*_CONFLICT_UNKNOWN_PROCESS`),
`STUDIO_CODE_DRIFT_DETECTED` (once per new fingerprint), `STUDIO_RESTART_REQUIRED`,
`STUDIO_RESTART_DEFERRED_ACTIVE_JOB` (`ACTIVE_JOBS_BLOCK_RESTART`), `STUDIO_RESTART_BEGIN`,
`STUDIO_RESTART_COMPLETE`, `STUDIO_POST_START_SMOKE_PASS`/`FAIL`, `STUDIO_CONTRACT_MISMATCH`.

Operator activity log (`db.log_activity`): `STUDIO_RESTART_REQUESTED`,
`STUDIO_RESTART_COMPLETE`, `STUDIO_RESTART_FAILED`, `STUDIO_SHUTDOWN` — not health probes.

---

## 30. Performance

- Fingerprint scope is a small explicit manifest (19 files), not the whole repo.
- 2-second TTL cache on the disk fingerprint (`current_disk_fingerprint`).
- Correctness first; the bounded manifest makes a full rehash sub-millisecond anyway.

---

## 31. Tests

`tests/test_runtime_hardening.py` (UNIT_TEST_ONLY / PROVEN_STATIC):

| Class | Covers |
|---|---|
| `TestContractSourceOfTruth` | JSON ⇄ app.js constant equality |
| `TestCanonicalRuntime` | true/false/missing interpreter detection |
| `TestCodeFingerprint` | content-based, stable, bounded & explicit manifest |
| `TestCodeDrift` | STALE detected, CURRENT when aligned |
| `TestContractMismatchRegression` | the original incident class detected before a 404 |
| `TestBootId` | changes across reinit |
| `TestInstanceManifest` | no secrets; dead-PID & creation-time-mismatch rejected |
| `TestSingleInstance` | proceed when free; unknown owner not killed |
| `TestProductionTruth` | hash unchanged + valid |
| `TestStatusAPI` | hardening fields exposed; ready=false on drift; no secret leak |
| `TestRestartEndpoint` | remote 403; active-job 409; local launches orchestrator |
| `TestSmoke` | missing route flagged; all-200 passes |

The full regression is preserved: Two-Voice Lock, Language Resolver, Management Safety,
Script Voice Preview, Audio Download, runtime readiness, Production Truth.

---

## 32. Real Port 8077 Verification (PROVEN_REAL)

Live smoke against the running production server (this run, 2026-08-29):

| Route | Status | Content-Type |
|---|---|---|
| `/` | 200 | text/html |
| `/static/app.js` | 200 | application/javascript |
| `/api/system/status?frontend_contract=2026-08-29.1` | 200 | application/json |
| `/api/voices/approved` | 200 | application/json |
| `/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample` (Thanh) | 200 | **audio/wav** |
| `/api/voices/approved/pGapy9MNHCukzJtjavF0/sample` (Hạnh) | 200 | **audio/wav** |
| `/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample/download` | 200 | audio/wav |

Status payload: `ready=True`, `code_sync=CURRENT`, `contract_sync=True`,
`canonical_runtime=True`, `restart_required=False`, `boot_id=d4631c3e0a52`, `pid=1924`.

---

## 33. Static Voice Sample Regression (PROVEN_REAL)

Because this hardening exists due to the static-sample incident, the real restarted
production server was verified:

- Thanh `GET /sample` → 200 `audio/wav` ✓
- Hạnh `GET /sample` → 200 `audio/wav` ✓
- Download route → 200 ✓

Playwright "Nghe mẫu" playback was verified in the prior pass (audio load success, no
*"Không tải được mẫu giọng đọc"*). **No samples were regenerated; no Hạnh/Thanh models or
TTS settings were changed.**

---

## 34. Restart-While-Browser-Open (PROVEN_REAL)

Proven in the prior Playwright pass: boot_id changed A→B across a controlled restart; the
frontend detected the change, showed *"AI Avatar Studio đã khởi động lại. Đang tải lại
trạng thái."*, and recovered cleanly (the transient "Failed to fetch" during the restart
window is expected and did not crash the page).

---

## 35. Playwright

`tools/_hardening_playwright.py` drives the viewports 1440×900 and 390×844 across:
normal synchronized state (no warning), code-drift fixture (restart warning), contract
mismatch fixture (sync warning), server-restart-while-open (clean recovery), and System
Status UI (canonical runtime / code sync / restart state). No subjective visual quality is
claimed. Screenshots are saved under `C:\tmp\`.

---

## 36. Production Truth (PROVEN_REAL)

```
a5a0e55f46c29c1722efc5cc3f8fec3d902260f0 *config/render_truth.json
```

Unchanged — matches the expected invariant exactly. The file is never mutated or re-hashed
by `runtime_guard` (read-only validation only).

---

## 37. Secret Scan (PROVEN_STATIC)

Scanned all hardening artifacts for `xi-api-key`, `ELEVENLABS_API_KEY=<value>`,
`Authorization: Bearer`, `CLOUDFLARE…secret`, `sk-…` tokens:

- `studio/runtime_guard.py` — clean
- `config/api_contract.json` — clean
- `config/runtime_requirements_manifest.json` — clean
- `tools/restart_studio.py` — clean
- `tools/verify_runtime.py` — clean
- `run_studio.py` — clean
- `studio/app.py` — clean
- `tests/test_runtime_hardening.py` — **false positive only**: the file contains the
  literal *names* `"ELEVENLABS_API_KEY"`, `"xi-api-key"`, `"Authorization"` inside a
  deny-list assertion (`assertNotIn(secret, blob)`) that **verifies the manifest has no
  secrets**. No secret **values** are present.

The instance manifest on disk contains only: boot_id, pid, creation/started times,
interpreter path, entrypoint, repository, port, fingerprints, contract version, git head,
git dirty, production-truth hash. **No secrets.**

---

## 38. Changed Files

Modified:
- `AI_Avatar_Studio.bat` — hard-pin canonical interpreter, no fallback
- `run_studio.py` — `_startup_hardening()` (canonical + single-instance + manifest)
- `studio/app.py` — extended `/api/system/status`; `/api/studio/restart` + `/api/studio/shutdown`
- `studio/config.py` — `CANONICAL_INTERPRETER`, `INSTANCE_MANIFEST_PATH`, `API_CONTRACT_PATH`, `RUNTIME_DIR`
- `studio/static/app.js` — contract constant, handshake, boot-id handling, banners, "Trạng thái máy chủ" card, restart action
- `studio/static/index.html` — runtime banner mount (+ theme toggle / trash nav)
- `studio/static/styles.css` — banner / status styling
- *(voice-profile files `studio/avatar_service.py`, `studio/db.py`,
  `studio/elevenlabs_client.py`, `studio/render_service.py`, `studio/runtime.py` are part
  of the concurrent voice work, not this hardening; the production lock was respected — no
  voice profile, TTS model, or render-truth value was changed by this task.)*

New (this hardening):
- `studio/runtime_guard.py` — core hardening module
- `config/api_contract.json` — contract version source of truth
- `config/runtime_requirements_manifest.json` — runtime requirements manifest
- `tools/restart_studio.py` — controlled restart orchestrator
- `tools/verify_runtime.py` — runtime preflight
- `tools/_hardening_playwright.py` — Playwright verification script
- `tools/rebuild_runtime.ps1` — runtime rebuild helper
- `tests/test_runtime_hardening.py` — acceptance tests

Generated runtime artifacts (gitignored, not tracked):
- `data/studio_runtime/studio_instance.json` — instance manifest (machine-specific)
- `data/studio_runtime/logs/restart.log` — restart orchestrator log

`.gitignore` already excludes `data/studio_runtime/`, so generated process-state files are
not accidentally added to source control.

---

## 39. Known Limitations

- The fingerprint is content-based but **does not** detect a change to a file outside the
  explicit restart-sensitive manifest (by design — frontend/contract changes are caught by
  the contract handshake instead).
- Process identity relies on `psutil`; if `psutil` is unavailable the single-instance guard
  is conservative (treats the port as free rather than trusting an unverified owner).
- The in-UI restart button is local-owner only; it does not offer remote restart by design.
- `git_dirty=true` is reported but not a failure; this is intentional for development.

---

## 40. Deferred Work

- Optional: collapse the contract version into a generated/shared artifact so `app.js` and
  `api_contract.json` cannot drift even theoretically (currently enforced by test).
- Optional: mtime/size fast-path before SHA256 (not needed at the current manifest size).
- Optional: richer route-contract smoke set driven by a centralized manifest if the route
  count grows further (current set covers the incident route + all core low-cost routes).

---

## 41. Final Recommendation

Adopt V1.6.0 runtime/deployment hardening. The proven stale-server incident class is now
detected **before** user impact, the Studio refuses to claim READY when code/contract/
runtime are inconsistent, and restart is a controlled, identity-verified, active-job-safe
operation. Production Truth is unchanged; no voice profile or TTS model was touched; the
full regression passes (173 tests, 1 skipped).

---

## 42. Evidence Classification Summary

| Claim | Evidence |
|---|---|
| Single-instance behavior | PROVEN_REAL (launcher re-run reuses verified Studio) + UNIT_TEST_ONLY |
| Port identity / unknown-owner protection | UNIT_TEST_ONLY + PROVEN_REAL |
| Canonical runtime enforcement | PROVEN_REAL (live status `canonical_runtime=True`) |
| Instance manifest (no secrets) | PROVEN_REAL (on-disk content inspected) |
| Boot ID changes | UNIT_TEST_ONLY + PROVEN_REAL (restart-while-open) |
| Startup/disk fingerprint | UNIT_TEST_ONLY + PROVEN_REAL (live `code_sync=CURRENT`) |
| Code drift detection | UNIT_TEST_ONLY (`test_drift_detected_when_disk_differs_from_startup`) |
| Contract mismatch detection | UNIT_TEST_ONLY (regression test) |
| Active-job restart protection | UNIT_TEST_ONLY (409 path) |
| Controlled restart | PROVEN_REAL (new boot_id + smoke PASS) |
| Post-start smoke | PROVEN_REAL (7 routes 200) |
| Thanh/Hạnh `/sample` after restart | PROVEN_REAL (200 audio/wav) |
| Browser "Nghe mẫu" | PROVEN_REAL (prior Playwright pass) |
| Production Truth unchanged | PROVEN_REAL (SHA1 verified) |
| Full regression | PROVEN_REAL (173 tests OK, 1 skipped) |
| Secret scan | PROVEN_STATIC (clean; one false positive explained) |

---

## 43. Required Final Status

`HARDENED_AND_VERIFIED`

All gating conditions met:

- [x] single-instance behavior proven
- [x] canonical runtime enforcement proven
- [x] code drift detected (unit)
- [x] contract mismatch detected (unit, regression)
- [x] safe restart proven (real)
- [x] port ownership safety proven (unknown owner not killed)
- [x] post-start smoke checks pass (real, 7 routes)
- [x] static sample route works after restart (real, audio/wav)
- [x] full regression passes (173 OK, 1 skipped)
- [x] Production Truth unchanged (`a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`)
- [x] no secret exposure (scan + manifest inspection)