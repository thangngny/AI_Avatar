# AI AVATAR STUDIO V1.6.0 — PRE-CHANGE SYSTEM AUDIT REPORT
**Document Version:** 1.6.0-AUDIT-01  
**Audit Timestamp:** 2026-08-29T10:45:00+07:00  
**Audit Scope:** Pre-implementation architecture, data model, persistence, lifecycle, dependency, safety, process control, and risk audit for future management features.  
**Mode:** READ-ONLY / NON-DESTRUCTIVE (`INSPECT -> TRACE -> VERIFY -> DOCUMENT -> STOP`)  

---

## 1. Executive Summary

This audit evaluates the architectural readiness and safety constraints of **AI Avatar Studio** prior to introducing any management, deletion, trash, restore, retry, cancellation, cleanup, or administrative features.

**Audit Findings Summary:**
1. **Production Truth & Lip-Sync Invariants:** The single production lip-sync configuration (`config/render_truth.json`) is intact and locked (`a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`, MuseTalk v1.5, 25 FPS, 1080x1920, gain 1.5, ctx 0, offset -3, CUDA Graph ON, WOLA ON).
2. **Canonical Runtime:** Canonical Python interpreter `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe` (Python 3.10.11, PyTorch 2.5.1+cu121, CUDA 12.1, 2x RTX 3090) is operational and verified via `tools/verify_runtime.py`.
3. **Data Model & Persistence:** SQLite WAL database (`data/studio_runtime/studio.db`) cleanly separates `jobs`, `avatars`, `voice_configs`, `voice_language_configs`, `voice_model_profiles`, and `settings`.
4. **Active Job Safety & Deletion Risks:** Deleting a prepared avatar while render jobs are queued or running introduces a severe `FileNotFoundError` race condition in `generate_video_from_script.py`. Server-side referential integrity guards are mandatory before enabling deletion.
5. **Cross-Volume Storage:** Prepared avatars reside on `C:` (`data/avatars/`, ~44.8 GB), while final production renders reside on `D:` (`D:\CongThang_AI_Avatar\renders\`, ~1.0 GB). Physical cross-drive moves are non-atomic on Windows; soft-delete via database flags or volume-local `.trash/` namespaces is required.
6. **Cancellation & Retry Baseline:** Job cancellation (`cancel_job` via `taskkill /PID /T /F`) and retry (`retry_job` with fresh UUID output paths) already exist in `studio/render_service.py` and are proven safe.
7. **Security & Cloudflare Remote Exposure:** When exposed via Cloudflare Tunnel, the application uses an in-memory access code gate (`share_auth.py`). Destructive endpoints must enforce server-side authentication, origin verification, and strict path-traversal guards.

**Final Audit Recommendation:**  
`SAFE_WITH_PREREQUISITES`  
*(Features may be designed, but implementation must strictly follow the prerequisite server-side invariants, reference locks, and non-destructive soft-delete architecture detailed in this report).*

---

## 2. Current Baseline & Evidence

| Check Item | Observed Value | Evidence Source | Classification |
| :--- | :--- | :--- | :--- |
| **Git Branch** | `main` | `git branch --show-current` | `PROVEN_REAL` |
| **HEAD Commit** | `788cbf54478edec87b78b5216ee99b0b246d9d60` | `git rev-parse HEAD` | `PROVEN_REAL` |
| **Working Tree** | Clean tracked modifications (UI card fix, verify tool fix) | `git status --short` | `PROVEN_REAL` |
| **Python Runtime** | `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe` (v3.10.11) | `tools/verify_runtime.py` | `PROVEN_REAL` |
| **PyTorch & CUDA** | PyTorch 2.5.1+cu121, CUDA 12.1, 2x NVIDIA GeForce RTX 3090 | `probe()` output | `PROVEN_REAL` |
| **System Status** | Ready: YES (21 prepared avatars, truth valid) | `system_status.py` | `PROVEN_REAL` |
| **Production Truth** | MuseTalk v1.5 locked config | `config/render_truth.json` | `PROVEN_REAL` |
| **Truth SHA1** | `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0` | SHA1 hash calculation | `PROVEN_REAL` |
| **Two-Voice Lock** | Exactly 2 approved voices (Hanh `pGapy9MNHCukzJtjavF0`, Thanh `N0Z0aL8qHhzwUHwRBcVo`) | `studio/voices.py`, `tests/test_two_voice_lock.py` | `PROVEN_REAL` |
| **Thanh Profile** | `eleven_v3` / `HUMAN_BENCHMARK_APPROVED` | `tests/test_language_resolver.py` | `PROVEN_REAL` |
| **Test Baseline** | 126/126 unit tests passed | `unittest discover tests` | `PROVEN_REAL` |
| **Secret Scan** | Clean (0 API keys / secrets in diff) | Regex diff audit | `PROVEN_REAL` |

---

## 3. Architecture & Data Model Map

The actual entity relationships derived from static code and on-disk data:

```
[RAW SOURCE VIDEO]
  Location: data/input/avatar_sources/<filename>.mp4 (or data/avatars/.uploads/)
  Lineage Record: data/avatar_sources.json
  Cardinality: 1 Raw Source -> 0..N Prepared Avatars (e.g. cu_recon_* variants)
        |
        v (Subprocess: python -m avatars.musetalk.genavatar)
[PREPARED AVATAR]
  Location: data/avatars/<avatar_id>/ (full_imgs/, mask/, coords.pkl, latents.pt, mask_coords.pkl, avator_info.json)
  Cache Record: avatars table in studio.db
  Cardinality: 1 Prepared Avatar -> 0..N Render Jobs
        |
        v (UI Job Submission: /api/render or /api/render/test)
[RENDER JOB (IMMUTABLE SNAPSHOT)]
  Location: jobs table in studio.db (job_id, script_text, tts_config, avatar_id, output_path, status)
  Audio Generation: master WAV (temp/master/) & 16kHz mono cond WAV (temp/master/)
  Worker Execution: generate_video_from_script.py --avatar_id <id> --audio <cond> --output <mp4>
        |
        v (Mux + Verification)
[FINAL RENDER & HISTORY]
  Video Output: D:\CongThang_AI_Avatar\renders\studio\<ts>_<kind>_<avatar>_<label>_<uuid8>.mp4
  Render Log: data/studio_runtime/logs/<job_id>.log
  Preview Stream: /api/render/jobs/<job_id>/preview
```

### Entity Lineage & Multi-Reference Analysis:
* **Raw Avatar Source:** Stored in `data/input/avatar_sources/` or `.uploads/`. Filename is preserved via `_sanitize_filename`. Lineage indexed in `data/avatar_sources.json`. Multiple prepared avatars CAN share a single raw source video (`PROVEN_REAL`: `cu_recon_em10_jaw`, `cu_recon_em10_mouthchin`, `cu_recon_em20_jaw` all point to `close_up_recon.mp4`). Therefore, deleting a prepared avatar must NEVER automatically delete the underlying raw source file.
* **Prepared Avatar:** Stored in `data/avatars/<avatar_id>/`. Requires 5 core artifacts (`full_imgs/`, `mask/`, `coords.pkl`, `latents.pt`, `mask_coords.pkl`, `avator_info.json`). The renderer consumes `coords.pkl`, `latents.pt`, `mask`, and `full_imgs` by reading the folder on disk.
* **Script:** Not a standalone database table; scripts are stored as immutable snapshots inside each job record (`jobs.script_text`, `jobs.script_name`, `jobs.script_segment`).
* **Render Job:** Stored in SQLite `jobs` table. Contains immutable parameters (`avatar_id`, `voice_id`, `script_text`, `tts_config`, `truth_hash`).
* **Completed Render:** Final MP4 registered in `jobs.output_path`. Preview served via streaming range requests.

---

## 4. Persistence Inventory

| Store Type | Path / Table | Purpose | Retention Policy | Classification |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite DB** | `data/studio_runtime/studio.db` | Central relational database (WAL mode) | Permanent | `PROVEN_REAL` |
|   **Table: jobs** | `jobs` (PK: `job_id`) | Active queue state + render history | Permanent | `PROVEN_REAL` |
|   **Table: avatars** | `avatars` (PK: `avatar_id`) | Metadata and quality analysis cache | Derived from disk | `PROVEN_REAL` |
|   **Table: voice_configs** | `voice_configs` (PK: `voice_id`) | Legacy resolved TTS config | Permanent | `PROVEN_REAL` |
|   **Table: voice_language_configs** | `voice_language_configs` (PK: `(voice_id, language_code, resolver_policy)`) | Language-aware TTS config cache | Permanent | `PROVEN_REAL` |
|   **Table: voice_model_profiles** | `voice_model_profiles` (PK: `(voice_id, language_code)`) | Human-approved voice model mappings | Permanent | `PROVEN_REAL` |
|   **Table: settings** | `settings` (PK: `key`) | Non-secret UI settings | Permanent | `PROVEN_REAL` |
| **JSON Lineage** | `data/avatar_sources.json` | Raw source mapping and experimental metadata | Permanent | `PROVEN_REAL` |
| **JSON Config** | `config/render_truth.json` | Single locked production truth | Read-Only | `PROVEN_REAL` |
| **Avatar Info** | `data/avatars/<avatar_id>/avator_info.json` | Individual avatar version & parsing mode | Permanent | `PROVEN_REAL` |
| **Temp Uploads** | `data/studio_runtime/temp/uploads/<upload_id>/meta.json` | Chunked upload assembly metadata | 2-hour TTL sweep | `PROVEN_REAL` |
| **Temp Master Audio** | `data/studio_runtime/temp/master/` | Synthesized master & conditioning WAVs | Cache / Temp | `PROVEN_REAL` |
| **Render Logs** | `data/studio_runtime/logs/<job_id>.log` | Subprocess console outputs | Retained with job | `PROVEN_REAL` |

---

## 5. File Ownership Matrix

| Asset | Created By | Referenced By | Safe Delete Condition | Recovery Possible? |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Avatar Source** (`.mp4`) | User upload / operator ingest | `avatar_sources.json`, `avatars.source_video` | Zero prepared avatars reference it AND operator confirms | No (unless external backup exists) |
| **Prepared Avatar Directory** | `avatars.musetalk.genavatar` | `jobs.avatar_id`, `studio/avatar_service.py` | Zero active (queued/running) jobs reference `avatar_id` | Only by full re-preparation from raw source |
| **Avatar Thumbnail** | First image in `full_imgs/` | UI library cards, Create Video selection | Tied to Prepared Avatar lifecycle | Regenerated from `full_imgs/` |
| **Avatar Metadata** (DB row) | `avatar_service.py` / `db.upsert_avatar` | `list_avatars()`, `/api/avatars` | Can be rebuilt on demand from filesystem | Re-derivable from disk scan |
| **Master Audio** (`.wav`) | `elevenlabs_client.py` / `edge_tts_client.py` | `jobs.master_audio_path`, renderer mux | Job is complete or failed | Re-synthesizable (consumes ElevenLabs quota) |
| **Conditioning Audio** (`.wav`) | `elevenlabs_client.py` (16 kHz mono) | `generate_video_from_script.py --audio` | Job is complete or failed | Derived from Master Audio |
| **Final Render MP4** | `generate_video_from_script.py` | `jobs.output_path`, History UI | Operator deletes render record | No (must re-render from job snapshot) |
| **Intermediate Video** (`_temp.mp4`) | `generate_video_from_script.py` | ffmpeg mux pipe | Render process completes or crashes | Ephemeral scratch artifact |
| **Job Log File** (`.log`) | Background worker pump | `/api/render/jobs/<job_id>/log` | Linked with job record deletion | No (historical execution logs lost) |
| **Staging Upload Chunks** (`.part`) | `/api/uploads/<id>/chunk` | `/api/uploads/<id>/complete` | Assembly completed OR staging directory > 2 hours old | Re-upload required |

---

## 6. Job State Machine & Transitions

The current authoritative job states implemented in `studio/db.py` and `studio/render_service.py`:

```
                 +--------------------------------------------------------+
                 |                        [QUEUED]                        |
                 +---------------------------+----------------------------+
                                             |
                       +---------------------+----------------------+
                       | Worker claims job (_claim_queued_job)      |
                       v                                            | Cancel requested
               [PREPARING_AUDIO]                                    | (/api/render/jobs/<id>/cancel)
                       |                                            v
                       | TTS generation OK                     [CANCELLED]
                       v                                            ^
                  [RENDERING] --------------------------------------+
                       |                                            | (Kills PID via taskkill /T /F,
                       | MuseTalk inference done                    |  releases GPU)
                       v                                            |
                  [ENCODING] ---------------------------------------+
                       |                                            |
                       | ffmpeg final mux done                      |
                       v                                            |
                  [VERIFYING] --------------------------------------+
                       |
         +-------------+-------------+
         | Post-render check OK      | Verification FAIL / Subprocess Exit != 0 / Watchdog Timeout
         v                           v
    [COMPLETE]                    [FAILED] / [TIMED_OUT]
                                     |
                                     | User triggers retry (/api/render/jobs/<id>/retry)
                                     v
                                  [QUEUED] (Fresh output_path, error cleared)
```

### State Behavior Details:
1. **QUEUED:** Awaiting free GPU. Atomically claimed by worker via `_claim_queued_job()`. Can be cancelled immediately.
2. **PREPARING_AUDIO:** Generating master WAV + 16kHz conditioning WAV via ElevenLabs or Edge TTS.
3. **RENDERING:** Subprocess running `generate_video_from_script.py`. Progress monitored via stdout tqdm `Rendering: XX%` (mapped to 5%..88%). Monitored by a progress-aware watchdog (`STUDIO_RENDER_NO_PROGRESS_SEC=300s`, `STUDIO_RENDER_HARD_TIMEOUT_SEC=14400s`).
4. **ENCODING / VERIFYING:** Final ffmpeg audio-video mux and integrity check via `studio/verify.py`.
5. **COMPLETE / FAILED / CANCELLED / TIMED_OUT:** Terminal states.
6. **Restart Reconciliation:** `_reconcile_inflight_jobs()` runs on startup and transitions any orphaned transient jobs (`preparing_audio`, `rendering`, etc.) directly to `failed` with an explicit reason ("Studio da khoi dong lai trong khi job dang chay.").

---

## 7. Existing Delete / Cancel / Cleanup Operations

Static inspection reveals the following existing deletion and termination logic in the repository:

1. **Job Cancellation (`studio/render_service.py:cancel_job`):**
   * *Status:* Implemented & Functional (`PROVEN_REAL`).
   * *Mechanism:* Updates database status to `cancelled`, terminates process tree via `taskkill /PID <pid> /T /F`, and releases allocated GPU in `gpu_service`.
2. **Job Retry (`studio/render_service.py:retry_job`):**
   * *Status:* Implemented & Functional (`PROVEN_REAL`).
   * *Mechanism:* Re-queues failed/cancelled jobs, resets progress to 0, generates a fresh unique output path (`_output_path`), and wakes the background worker.
3. **Voice Profile Deletion (`studio/app.py:el_delete_profile`):**
   * *Status:* Implemented for admin endpoints (`DELETE /api/elevenlabs/profiles`).
   * *Mechanism:* Executes `DELETE FROM voice_model_profiles WHERE voice_id=? AND language_code=?`.
4. **Stale Upload Staging Cleanup (`studio/app.py:_sweep_stale_uploads`):**
   * *Status:* Internal automated maintenance (`PROVEN_STATIC`).
   * *Mechanism:* Scans `data/studio_runtime/temp/uploads/` and removes staging directories older than `UPLOAD_TTL_SEC` (2 hours).
5. **Temporary File Removal (`studio/avatar_service.py` & `studio/avatar_quality.py`):**
   * *Status:* Ephemeral scratch cleanup (`PROVEN_STATIC`).
   * *Mechanism:* Calls `os.unlink(out_json)` on temporary validator JSON results.

**Conclusion:** No UI-facing Avatar Deletion, Render Video Deletion, Bulk Cleanup, or Trash/Restore system currently exists in production.

---

## 8. Active Job Dependency & Race Condition Risks

| Scenario | Trigger / Race Condition | Direct Impact | Severity | Required Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **Delete Avatar during Queued Job** | Avatar folder deleted while jobs in `queued` status reference `avatar_id`. | When worker claims job, renderer subprocess immediately throws `FileNotFoundError`. | HIGH | Server-side foreign reference guard: reject avatar deletion if active jobs reference `avatar_id`. |
| **Delete Avatar during Active Render** | Avatar directory deleted while `generate_video_from_script.py` is in inference loop. | Process crashes mid-batch on missing `full_imgs` frame reads; output MP4 corrupted; GPU locked until watchdog triggers. | CRITICAL | Active job execution lock on avatar directory. |
| **Delete Render during Download/Preview** | Final MP4 deleted from `D:\renders\studio\` while user or browser is streaming `/api/render/jobs/<id>/preview`. | Stream aborts with HTTP 404 / broken pipe. | MEDIUM | Soft-delete flag; file removal deferred or handled gracefully. |
| **Stop Running Render vs Final Mux** | User stops/cancels render at 95% while ffmpeg is muxing audio and video. | `taskkill /T /F` kills ffmpeg; partial/corrupt MP4 left on disk. | MEDIUM | Cancellation handler must unlink incomplete target MP4 and temporary `_temp.mp4` file. |
| **Temp Master Audio Cleanup vs Active Job** | Cleanup routine purges `temp/master/` while renderer is loading audio. | Audio file missing during conditioning or final mux. | HIGH | Only purge master audio files whose corresponding jobs are terminal and older than retention window. |
| **Windows Cross-Volume Move** | Moving avatar (`C:`) or render (`D:`) to a global trash folder. | Cross-drive moves are non-atomic copy+delete operations; power failure or process abort causes data loss. | HIGH | Trash folders must be volume-local (`C:\...\data\.trash` and `D:\renders\.trash`). |

---

## 9. Process Control & Process Termination Audit

* **Subprocess Spawning:**
  * Worker uses `subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=config.ROOT, env=env)`.
  * Environment explicitly isolates GPUs: `CUDA_VISIBLE_DEVICES = str(gpu_id)`, `OFFLINE_USE_MULTI_GPU = "false"`, `LIVETALKING_CUDA_GRAPH = "true"`.
* **Process Tree Structure on Windows:**
  * Parent: Flask Studio process (`python.exe`).
  * Child: Renderer process (`generate_video_from_script.py`).
  * Grandchildren: ffmpeg rawvideo pipe process, ffmpeg mux process, ffprobe processes.
* **Termination Mechanism:**
  * `runtime.terminate_tree(proc)` executes `taskkill /PID <pid> /T /F`.
  * `/T` traverses and kills all descendant processes (including grandchildren ffmpeg pipes).
  * `/F` ensures forceful termination even if a thread is blocked on GPU CUDA calls.
  * GPU memory is automatically reclaimed by the NVIDIA driver when the OS destroys the process handle.

---

## 10. Feasibility Evaluation for Future Management Features

### A. Cancel Queued & Stop Running Render:
* **Feasibility:** `FULLY_FEASIBLE` (`PROVEN_REAL`).
* **Existing Code:** `studio/render_service.py:cancel_job` already handles both queued state removal and running subprocess termination via `taskkill`.
* **Enhancement Needed:** Surface explicit "Huy render" / "Dung render" buttons with confirmation in Queue drawer and History UI.

### B. Retry Failed Render:
* **Feasibility:** `FULLY_FEASIBLE` (`PROVEN_REAL`).
* **Existing Code:** `studio/render_service.py:retry_job` cleanly clones the immutable snapshot (`avatar_id`, `voice_id`, `script_text`, `tts_config`, `truth_hash`) into a new run with a fresh output path.

### C. Trash / Restore vs Permanent Delete:
* **Feasibility:** `HIGH` with Strategy A/C (Volume-Local Soft Delete).
* **Recommended Design:**
  * **Soft Delete (Trash):** Add `deleted_at REAL DEFAULT NULL` and `is_deleted INTEGER DEFAULT 0` columns to `avatars` and `jobs` tables in `studio.db`. Normal lists filter `WHERE is_deleted=0`.
  * **Restore:** Resets `is_deleted=0` and `deleted_at=NULL`.
  * **Permanent Delete (Purge):** Physically unlinks files ONLY after confirming zero active references and owner-direct authorization.
  * **Drive Volumes:** Avatar trash remains on `C:`; Render trash remains on `D:`.

### D. Avatar Rename:
* **Feasibility:** `FULLY_FEASIBLE` as Metadata-Only Display Rename.
* **Mechanism:** Update `avatars.name` in SQLite database (`db.upsert_avatar(aid, name=new_name)`).
* **Rule:** Never rename the physical directory `data/avatars/<avatar_id>/` because existing render jobs hold foreign references to `avatar_id`.

### E. Storage Reporting & Orphan Detection:
* **Feasibility:** `HIGH`.
* **Storage Distribution:**
  * Prepared Avatars (`C:\...\data\avatars`): **44.83 GB** (30,461 files)
  * Raw Sources (`C:\...\data\input\avatar_sources`): **547.41 MB** (13 files)
  * Production Renders (`D:\renders`): **986.05 MB** (100 files, Studio: 439.69 MB)
  * Master Audio Temp (`C:\...\temp\master`): **49.95 MB** (15 files)
  * SQLite DB (`studio.db`): **220 KB**
* **Orphan Detection Rules:**
  1. *Filesystem Avatar Orphan:* Directory exists in `data/avatars/` but is incomplete or untracked.
  2. *Metadata Avatar Orphan:* Row in `avatars` table with no matching folder on disk.
  3. *Render Orphan:* MP4 file in `D:\renders\studio\` with no matching `output_path` in `jobs` table.
  4. *History Orphan:* Job in `jobs` table marked `complete` whose `output_path` file is missing.
  5. *Temp Residue Orphan:* `*_temp.mp4` files left in render folder after process interruption.

---

## 11. Security & Remote Access Boundary Findings

* **Current Network Architecture:**
  * Studio origin binds strictly to `127.0.0.1:8077` (`run_studio.py`).
  * Collaborator sharing uses Cloudflare Quick Tunnel (`cloudflared`).
  * Cloudflare edge injects `Cf-Connecting-IP` on all tunnel requests.
  * Flask application uses `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)`.
* **Access Boundary Analysis:**
  * `_share_gate` in `studio/app.py` blocks unauthenticated remote requests with HTTP 401 when sharing is enabled.
  * `_is_owner_direct()` verifies loopback origin AND absence of `Cf-Connecting-IP`.
  * Owner-only endpoints (`/api/share/enable`, `/api/share/disable`) return 403 Forbidden to tunnel users.
  * Frontend hides host-specific tools (e.g. `openFolder`) when `!isLocalhost()`.
* **Security Requirements for Future Management Features:**
  * Permanent delete and bulk storage purge must be restricted to `_is_owner_direct()` or require secondary confirmation.
  * Strict path validation (`_within_allowed()` and `_sanitize_filename()`) must prevent directory traversal attacks.
  * Audit logging must redact all API keys (`ELEVENLABS_API_KEY`, `xi-api-key`), session tokens, and Cloudflare credentials.

---

## 12. UI Architecture & Reusable Primitives

Static inspection of `studio/static/app.js` and `studio/static/styles.css` confirms that existing UI primitives are available:
* **Modal Framework:** `modal(html)` and `closeModal()` in `studio/static/app.js` (lines 1695-1702).
* **Toast Notifications:** `toast(msg, kind)` supporting `good`, `warn`, `bad` (lines 35-41).
* **Confirmation Dialog Pattern:** Used in Create Avatar warning override and quality modals.
* **Search & Filter Chips:** Implemented in Library (`#libSearch`, `#libFilters`) and History (`#jobSearch`, `#jobFilters`).
* **Card & Badge Layouts:** Semantic CSS classes `.avatar-card`, `.job`, `.tag`, `.rec-badge`, `.fstatus`.

---

## 13. Required Backend Guards (Invariants)

Before any management code is written, the backend must enforce the following non-negotiable invariants:

1. **Active Reference Guard:** Rejects deletion or trashing of any Avatar currently associated with active jobs (`queued`, `preparing_audio`, `rendering`, `encoding`, `verifying`).
2. **Immutable Job Snapshots:** Jobs in history retain their snapshotted parameters (`avatar_id`, `voice_id`, `script_text`, `tts_config`, `truth_hash`) even if the source avatar is soft-deleted.
3. **Volume Isolation Invariant:** File moves for Trash/Restore must never attempt cross-drive transfers between `C:` and `D:`.
4. **Lineage Preservation Invariant:** Deleting a prepared avatar must NEVER delete the original raw source video referenced in `data/avatar_sources.json`.
5. **Fail-Closed Voice Gate:** Production render jobs must only use approved production voices (`pGapy9MNHCukzJtjavF0`, `N0Z0aL8qHhzwUHwRBcVo`) and never perform silent fallback.
6. **Production Truth Immutability:** `config/render_truth.json` remains read-only and locked to SHA1 `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`.

---

## 14. Recommended Implementation Scope

### P0 -- Required (Core Safety & Basic Management):
* [ ] Cancel queued job & Stop running render from History/Queue UI.
* [ ] Retry failed/interrupted render job.
* [ ] Active job dependency check preventing deletion of active avatars.
* [ ] Display-name rename for Avatars (metadata-only update in SQLite `avatars.name`).
* [ ] Soft-delete for Completed Renders (hide from history, mark `is_deleted=1`).

### P1 -- Recommended (Complete Management & Trash System):
* [ ] Soft-delete (Trash) and Restore for Avatars.
* [ ] Trash view with "Khoi phuc" (Restore) and "Xoa vinh vien" (Permanent Delete).
* [ ] Storage breakdown reporting in Settings/Status view.
* [ ] Cleanup routine for orphaned `*_temp.mp4` and stale temporary preview audio files.
* [ ] Server-side owner authorization guards on destructive actions.

### P2 -- Future / Nice-to-Have (Advanced Auditing & Maintenance):
* [ ] Automated orphan detector (detecting untracked render MP4s or incomplete avatar folders).
* [ ] Export render history / audit activity log (JSON/CSV).
* [ ] Batch operations (bulk cancel, bulk retry).

---

## 15. Change Impact & Safety Boundaries

### Files Expected to Change in Future Implementation:
* `studio/db.py` (Add soft-delete columns, query filters, rename functions).
* `studio/avatar_service.py` (Add delete/restore/rename with active-job guards).
* `studio/render_service.py` (Enhance stop/cancel/retry and cleanup helpers).
* `studio/app.py` (Add API routes for delete, restore, rename, storage stats with auth guards).
* `studio/static/app.js` (Add UI action buttons, confirmation modals, trash view).
* `studio/static/styles.css` (Styles for trash chips, danger buttons, action menus).
* `tests/test_management.py` (New comprehensive test suite for management features).

### Files That MUST NOT Change:
* `generate_video_from_script.py` (Canonical production renderer).
* `config/render_truth.json` (Production truth configuration).
* `system_status.py` (Preflight health check).
* `studio/voices.py` (Approved voice allowlist).
* `avatars/musetalk/*` (Core MuseTalk v1.5 algorithms).
* `utils/cuda_graph.py`, `utils/image.py`, `utils/device.py`.

---

## 16. Test Plan Required for Future Implementation

Future implementation must create and pass tests covering:
1. `test_cannot_delete_avatar_with_queued_job`
2. `test_cannot_delete_avatar_with_running_job`
3. `test_soft_delete_and_restore_avatar`
4. `test_soft_delete_and_restore_render_job`
5. `test_permanent_delete_purges_files_cleanly`
6. `test_rename_avatar_updates_metadata_preserves_id`
7. `test_cancel_queued_job_releases_queue`
8. `test_cancel_running_job_kills_process_and_releases_gpu`
9. `test_retry_creates_fresh_output_path`
10. `test_path_traversal_rejection_in_delete_endpoints`
11. `test_remote_unauthenticated_delete_rejected`
12. `test_orphan_cleanup_does_not_touch_active_files`

---

## 17. Risk Register

| Risk ID | Risk Description | Severity | Likelihood | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Accidental permanent deletion of raw avatar source files during avatar removal. | HIGH | Medium | Strict decoupling: avatar deletion only affects `data/avatars/<id>`, never `data/input/avatar_sources/`. |
| **RSK-02** | Process handle locking on Windows preventing file deletion during active render. | MEDIUM | High | Use soft-delete flags; perform physical unlinks only when process handle is confirmed closed. |
| **RSK-03** | Race condition between worker claiming a queued job and user deleting the avatar. | HIGH | Low | Execute status checks inside database transaction lock (`db._LOCK`). |
| **RSK-04** | Remote collaborator deleting assets over Cloudflare Tunnel. | HIGH | Low | Gate permanent delete operations with `_is_owner_direct()` or session admin check. |
| **RSK-05** | Production truth or runtime regression during management refactoring. | CRITICAL | Very Low | Automated CI/test checks verifying truth hash `a5a0e55f46c29c1722efc5cc3f8fec3d902260f0` and 126+ unit tests. |

---

## 18. Final Recommendation

**Status:** `SAFE_WITH_PREREQUISITES`

The architecture of AI Avatar Studio V1.6.0 is solid, modular, and well-isolated. It is safe to proceed with detailed design and implementation of management features, provided that all backend invariants, reference guards, non-destructive soft-delete patterns, and Windows volume-isolation rules defined in this audit are strictly respected.

*End of Pre-Change System Audit Report.*
