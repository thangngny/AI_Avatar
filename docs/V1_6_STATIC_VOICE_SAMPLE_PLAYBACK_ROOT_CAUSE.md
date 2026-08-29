# AI Avatar Studio V1.6.0 — Static Voice Sample Playback Root-Cause Audit

**Date:** 2026-08-29
**Mode:** READ-ONLY audit (REPRODUCE → TRACE → PROVE ROOT CAUSE → DOCUMENT → STOP)
**Auditor:** Claude Code (no production code, routes, DB, audio files, or config modified)

---

# Executive Summary

**ROOT_CAUSE_PROVEN**

The user-visible defect — clicking **▶ Nghe mẫu** for Thanh (and identically for Hạnh) shows the toast
**"Không tải được mẫu giọng đọc"** — is caused by a **stale production server process**, NOT by a code
defect, a missing file, a wrong route, a MIME problem, or a frontend bug.

The Studio actually serving the user on `http://127.0.0.1:8077/` is OS process **PID 8384**
(`C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe`), which loaded `studio/app.py`
into memory at **10:05:40 AM** on 2026-08-29. At that moment `app.py` did **not** contain the
static-sample routes `/api/voices/approved/<voice_id>/sample` and `.../sample/download`. Those routes
are **uncommitted working-tree additions** that were saved to disk only at **11:38:54 AM** — after the
process had already started. A Flask process freezes its Python route table at startup, but it serves
static files (e.g. `app.js`) fresh from disk on every request. The browser therefore loads the
**current** `app.js` (saved 11:45:28 AM), whose `playVoiceSample()` calls the `/sample` route, but the
**stale** backend has no such route registered → it returns Flask's default 404 HTML page → the
browser `Audio` element fires `onerror` (code 4) → `playVoiceSample` shows the toast.

A freshly started server on port 8099 using the **current** disk `app.py` returns **HTTP 200** with
`Content-Type: audio/wav`, `Content-Disposition: inline`, and a body whose SHA256 **exactly matches**
the file on disk — for both voices. The code is correct; only the running process is stale.

**Evidence grade:** PROVEN_REAL (live HTTP on production port 8077 + Playwright browser reproduction +
fresh-server control + git + filesystem + timeline).

---

# Human-Observed Defect

- **Flow:** Create Video → Step 3: Giọng → ElevenLabs → select **Thanh** → language **Vietnamese** → click **▶ Nghe mẫu**
- **Real UI toast (human-provided):** `"Không tải được mẫu giọng đọc"`
- **Status:** STATIC VOICE SAMPLE PLAYBACK = FAIL (confirmed).

---

# Reproduction

Reproduced at three layers, all against the **production** endpoint on `127.0.0.1:8077`:

1. **Direct HTTP (curl / Invoke-WebRequest)** — see § HTTP Evidence.
2. **Playwright browser** (canonical-runtime Chromium, headless) — see § Browser Audio Evidence.
3. **Fresh-server control** on port 8099 (current code) — see § Playback vs Download Comparison.

The browser reproduction drives the real Studio page, replicates the exact `playVoiceSample()` call,
and also locates the real `▶ Nghe mẫu` button in the DOM.

---

# Thanh Evidence

| Field | Value |
|---|---|
| VOICE | Thanh |
| VOICE_ID | `N0Z0aL8qHhzwUHwRBcVo` |
| FRONTEND ACTION | `playVoiceSample('N0Z0aL8qHhzwUHwRBcVo')` → `new Audio('/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample')` |
| REQUEST URL | `http://127.0.0.1:8077/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample` |
| REQUEST METHOD | GET |
| HTTP STATUS (prod 8077) | **404 NOT FOUND** |
| RESPONSE Content-Type (prod) | `text/html; charset=utf-8` (Werkzeug default 404 HTML page) |
| RESPONSE Content-Disposition (prod) | none |
| RESPONSE Content-Length (prod) | 207 bytes (default 404 page) |
| RESPONSE BODY / ERROR (prod) | `<!doctype html>...<title>404 Not Found</title>...` |
| BROWSER CONSOLE ERROR | `Failed to load resource: the server responded with a status of 404 (NOT FOUND)` (×2: fetch + Audio) |
| Audio error event | `onerror fired`, `error.code = 4` (MEDIA_ERR_SRC_NOT_SUPPORTED) |
| BACKEND LOG (prod 8077) | 404 logged for the `/sample` URL (default Werkzeug handler; route not registered) |
| FRESH SERVER (8099, current code) | **200 OK**, `Content-Type: audio/wav`, `Content-Disposition: inline`, 804464 B, SHA256 matches disk |

**Failure class:** **D — Server returns 404**, because the route is **not registered** in the running
(stale) process. (Not class B/C/E/F/G/H/I/J/K.)

---

# Hạnh Evidence

| Field | Value |
|---|---|
| VOICE | Hạnh |
| VOICE_ID | `pGapy9MNHCukzJtjavF0` |
| FRONTEND ACTION | `playVoiceSample('pGapy9MNHCukzJtjavF0')` → `new Audio('/api/voices/approved/pGapy9MNHCukzJtjavF0/sample')` |
| REQUEST URL | `http://127.0.0.1:8077/api/voices/approved/pGapy9MNHCukzJtjavF0/sample` |
| REQUEST METHOD | GET |
| HTTP STATUS (prod 8077) | **404 NOT FOUND** (same default HTML page) |
| RESPONSE Content-Type (prod) | `text/html; charset=utf-8` |
| RESPONSE Content-Length (prod) | 207 bytes |
| FRESH SERVER (8099, current code) | **200 OK**, `audio/wav`, 843856 B, SHA256 matches disk |

Both voices fail **identically** (same root cause: stale route table). Hạnh and Thanh are not different
in failure mode.

---

# Actual Frontend Call Path

File: `studio/static/app.js`

```
944: let _sampleAudio = null;
945: function playVoiceSample(vid) {
946:   if (!vid) return;
947:   if (_sampleAudio && state.playingSampleVid === vid) {     // toggle off
948:     _sampleAudio.pause(); _sampleAudio = null;
950:     state.playingSampleVid = null; renderVoiceCards(); return;
952:   }
954:   if (_sampleAudio) { _sampleAudio.pause(); _sampleAudio = null; }
958:   state.playingSampleVid = vid; renderVoiceCards();
960:   _sampleAudio = new Audio(`/api/voices/approved/${encodeURIComponent(vid)}/sample`);
961:   _sampleAudio.onended  = () => { ...; renderVoiceCards(); };
966:   _sampleAudio.onerror  = () => {
967:     toast("Không tải được mẫu giọng đọc", "bad");          // <-- the user's toast
968:     state.playingSampleVid = null; _sampleAudio = null; renderVoiceCards();
970:   };
972:   _sampleAudio.play().catch(() => {});
973: }
...
993:   <button type="button" class="voice-sample-btn..." onclick="event.preventDefault(); event.stopPropagation(); playVoiceSample('${esc(v.voice_id)}')">
994:     ${isPlaying ? '⏸ Dừng' : '▶ Nghe mẫu'}
```

- Implementation uses **`new Audio(url)`** (HTMLMediaElement), not `fetch+blob`, not `<audio>` tag, not an
  object URL, not a download helper, not the shared script-preview player, not an old API route.
- The URL is a **relative** API route (`/api/voices/approved/<vid>/sample`) — correct for both local and
  remote (Cloudflare) use; no hardcoded `http://127.0.0.1:8077/`.
- `onerror` has **no HTTP status** (the `Audio` element exposes only `error.code`), which is why the
  toast is generic. The browser network layer shows the 404.
- The button is `event.preventDefault(); event.stopPropagation()` guarded, so it does not trigger voice
  select / step navigation / rerender. No SPA state collision observed (see § SPA / UI State Findings).

---

# Actual Backend Route Map

`studio/app.py` (working tree — current code on disk):

| METHOD | ROUTE | PURPOSE | USED BY FRONTEND? | COMMITTED? |
|---|---|---|---|---|
| GET | `/api/voices/approved` | list approved render voices | yes (`loadApprovedVoices`) | yes |
| GET | `/api/voices/approved/<voice_id>/sample` | **static sample PLAYBACK** (inline stream) | **yes — `playVoiceSample`** | **NO (uncommitted)** |
| GET | `/api/voices/approved/<voice_id>/sample/download` | static sample DOWNLOAD (attachment) | **no** (no UI reference in app.js) | **NO (uncommitted)** |
| GET | `/api/audio-preview/<preview_id>/audio` | script preview PLAYBACK (inline stream) | yes (script preview UI) | **NO (uncommitted)** |
| GET | `/api/audio-preview/<preview_id>/download` | script preview DOWNLOAD (attachment) | yes (script preview UI) | **NO (uncommitted)** |
| POST | `/api/audio-preview` | create script voice preview | yes | **NO (uncommitted)** |
| GET | `/api/avatar/sample` | avatar source **video** sample (unrelated to voice) | yes (`loadSample`) | yes |

Key points:
- **Playback route** = `/api/voices/approved/<voice_id>/sample` (inline, `as_attachment` only when `?download=1`).
- **Download route** = `/api/voices/approved/<voice_id>/sample/download` (always attachment).
- They are **different routes** (and should be). The frontend uses the **playback** route only.
- The frontend does **not** call the static-sample download route (it exists for direct-HTTP/download tooling).
- `/api/avatar/sample` is a **different** feature (avatar source video) — do not conflate.
- The **entire V1.6 audio route surface** (static sample + script preview) is **uncommitted** in the working
  tree. `git show HEAD:studio/app.py` contains none of the four `/sample` / `/audio-preview/.../audio` /
  `/audio-preview/.../download` routes.

---

# HTTP Evidence

Production port 8077 (stale process PID 8384):

```
GET /api/voices/approved                                   -> 200  application/json   (route exists in stale code)
GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample        -> 404  text/html; charset=utf-8  (default Werkzeug page, 207 B)
GET /api/voices/approved/pGapy9MNHCukzJtjavF0/sample         -> 404  text/html; charset=utf-8  (default Werkzeug page, 207 B)
GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample/download -> 404  text/html; charset=utf-8  (default Werkzeug page)
GET /api/voices/approved/!!!/sample/download                -> 404  text/html; charset=utf-8  (default Werkzeug page)
```

**Decisive distinction:** if the `/sample/download` route were registered, its handler returns
`jsonify({"ok": False, "error": "..."}), 404` → `application/json`. It returns the default **HTML** 404
page instead → the route is **not registered** in the running process. Same conclusion from the bogus
voice-id `!!!/sample/download` (a registered route would still return JSON 404, not the HTML default page).

Fresh control server on port 8099 (current disk `app.py`, canonical runtime):

```
GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample
  -> 200 OK
     Content-Type: audio/wav
     Content-Disposition: inline; filename=N0Z0aL8qHhzwUHwRBcVo.wav
     Content-Length: 804464
     Accept-Ranges: bytes
     body SHA256 = fd77a7dd44fe32f798ed3883aeabef101e2bd616dec007cf75fafd5dcf9551d1  (== disk)

GET /api/voices/approved/pGapy9MNHCukzJtjavF0/sample
  -> 200 OK  audio/wav  843856 B
     body SHA256 = f1ca2c7fdee81f7ccee41ddb705b7d8f8f0643a7aebf0fc6553dc58c88f51eac  (== disk)

GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample/download
  -> 200 OK  audio/wav  Content-Disposition: attachment; filename=..._sample.wav
```

Method check: frontend uses **GET**; backend route accepts **GET** (default). No GET/POST mismatch.
No `Allow` header issue. No 401/403/500. The failure is purely "route not registered in the running process".

---

# Static Sample File Inventory

Directory: `C:\CongThang_AI_Avatar\AI_avatar\data\studio_runtime\voice_samples\`

| Filename | Size | Modified | SHA256 | ffprobe |
|---|---|---|---|---|
| `N0Z0aL8qHhzwUHwRBcVo.wav` (Thanh) | 804,464 B | 2026-08-29 11:21:47 | `fd77a7dd44fe32f798ed3883aeabef101e2bd616dec007cf75fafd5dcf9551d1` | PCM f32le, 44100 Hz, mono, 4.56 s, valid |
| `pGapy9MNHCukzJtjavF0.wav` (Hạnh) | 843,856 B | 2026-08-29 11:21:42 | `f1ca2c7fdee81f7ccee41ddb705b7d8f8f0643a7aebf0fc6553dc58c88f51eac` | PCM f32le, 44100 Hz, mono, 4.78 s, valid |

- Storage naming is by **voice_id** (`<voice_id>.wav`), resolved in
  `preview_service.get_static_voice_sample()` (`preview_service.py:339`).
- No `Thanh_sample.wav` / `Hanh_sample.wav` naming at storage level → **no Hạnh/Hanh accent/space/hyphen
  mismatch** at the file layer. Those names appear only as `Content-Disposition` `download_name` for the
  download route (via `_safe_voice_label`), not as on-disk filenames.
- Both files are valid, non-zero, non-truncated, correctly labelled `.wav`. Decode validity: OK.
- On-disk SHA256 == fresh-server response SHA256 for both voices. The files are fine.

Backend mapping chain (current code): `voice_id` → `_sanitize_filename` (app.py:737) → regex
`^[A-Za-z0-9_\-]+$` guard (voice IDs satisfy this) → `preview_service.get_static_voice_sample(safe_vid)`
→ `voices.is_approved_render_voice(vid)` (voices.py:42; both IDs in `APPROVED_RENDER_VOICES`) →
`os.path.join(VOICE_SAMPLES_DIR, f"{vid}.wav")` → file exists & >1000 B → return path →
`send_file(..., mimetype="audio/wav", conditional=True)`. No mismatch anywhere.

---

# Playback vs Download Comparison

| | THANH playback `/sample` | THANH download `/sample/download` | HẠNH playback `/sample` | HẠNH download `/sample/download` |
|---|---|---|---|---|
| **Prod 8077 (stale)** status | 404 | 404 | 404 | 404 |
| **Prod 8077** Content-Type | text/html | text/html | text/html | text/html |
| **Prod 8077** bytes | 207 | 207 | 207 | 207 |
| **Prod 8077** SHA256 == disk | n/a (404) | n/a (404) | n/a (404) | n/a (404) |
| **Fresh 8099** status | 200 | 200 | 200 | 200 |
| **Fresh 8099** Content-Type | audio/wav | audio/wav | audio/wav | audio/wav |
| **Fresh 8099** Content-Disposition | inline | attachment | inline | attachment |
| **Fresh 8099** bytes | 804464 | 804464 | 843856 | 843856 |
| **Fresh 8099** SHA256 == disk | YES | YES | YES | YES |

**Conclusion:** On the production process, **both playback and download fail** (404 — route unregistered).
On a fresh current-code process, **both work**. The backend logic is correct; the production process is
stale. This is **not** a "download works but playback fails" case, and **not** a "backend works but
browser fails" case.

---

# Browser Audio Evidence (Playwright, production port 8077)

Drove the real Studio UI with headless Chromium (canonical-runtime Playwright). The page also locates
the real `▶ Nghe mẫu` button: `<button class="voice-sample-btn" onclick="...playVoiceSample('pGapy9MNHCukzJtjavF0')">▶ Nghe mẫu</button>` — present and correctly wired.

Captured:
- **Console errors:** `Failed to load resource: the server responded with a status of 404 (NOT FOUND)` (×2)
- **Network responses:**
  - `R 200 GET .../api/voices/approved  ct=application/json`
  - `R 404 GET .../api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample  ct=text/html; charset=utf-8` (×2: fetch probe + Audio)
- **Replicated `playVoiceSample('N0Z0aL8qHhzwUHwRBcVo')`:**
  - `url` = `/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample`
  - `status` = **404**, `statusText` = `NOT FOUND`
  - `contentType` = `text/html; charset=utf-8`, `bodyLen` = 207
  - `audioError` = **"onerror fired"**, `audioErrCode` = **4** (MEDIA_ERR_SRC_NOT_SUPPORTED)
- Page errors: none.

This is the exact chain that produces the toast: 404 → `Audio.onerror` (code 4) →
`toast("Không tải được mẫu giọng đọc", "bad")` (app.js:967).

---

# SPA / UI State Findings

- The `▶ Nghe mẫu` button is wrapped with `event.preventDefault(); event.stopPropagation()` (app.js:993),
  so clicking it does **not** toggle the voice radio, does **not** navigate steps, does **not** remount the
  card. No SPA-navigation/download collision observed.
- `_sampleAudio` is a single module-level Audio instance; toggling off / switching voices pauses and
  replaces it. No garbage-collection cancellation issue observed at the click level.
- The button markup is present in the DOM even before the voice is fully selected (Playwright resolved
  the element); it is hidden until the voice card is visible, but the handler wiring is correct.
- The defect is **not** a UI-state/SPA collision. It is purely the 404 from the stale backend.

---

# Authorization Findings

- The static-sample route is non-destructive and has **no** owner/host/Management-Safety guard decorator.
  The V1.6 Management Safety work did **not** add an auth guard to `/api/voices/approved/<id>/sample`.
- No 401/403 observed. The 404 is the default Werkzeug "route not found" page, not an authorization
  denial. Authorization is **not** a factor.

---

# Cache / Process Findings

- The controller was **one** canonical-runtime instance, visible as two PIDs (Windows venv launcher + base
  interpreter), both started 2026-08-29 10:05:40 AM:
  - **PID 8384** — `C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe` (the venv's base
    interpreter per `runtime\venv\pyvenv.cfg` `home = ...Python310`) — **owns port 8077**, serving the user.
    Carries the venv site-packages (e.g. `soundfile`, and `torch 2.5.1+cu121` for any in-process needs).
    Stale route table (loaded `app.py` at 10:05:40 AM, before the `/sample` routes existed on disk).
  - **PID 12988** — `D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe` (the venv launcher) — the parent
    of 8384; it does not bind a port itself (normal for a venv launcher). It is **not** a dead/failed
    second server — there was exactly one logical Studio instance.
- The launcher `AI_Avatar_Studio.bat` (modified 2026-08-28 22:41) uses the **canonical runtime**
  (`STUDIO_PY=D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe`). That launcher process (12988) then
  spawns its base interpreter (8384) to run the app — so the canonical runtime **is** the one serving;
  the "system Python path" is simply the venv's base interpreter, not a separate competing environment.
- **Served `app.js` SHA256 matches disk** (`2fbe1fec…`) → the browser is **not** running stale JS; it runs
  the current `app.js` that calls the `/sample` route. The mismatch is **frontend current vs backend stale**.
- File mtimes vs process start:
  - PID 8384 start: **10:05:40 AM**
  - `studio/app.py` mtime: **11:38:54 AM** (contains the `/sample` routes — uncommitted)
  - `studio/static/app.js` mtime: **11:45:28 AM** (contains the `playVoiceSample` call)
  - => the running process predates both the route additions and the frontend that calls them.

---

# Why Previous Automated Report Passed

The prior report (`docs/V1_6_AUDIO_DOWNLOAD_FIX.md`) and the test suite (`tests/test_script_preview.py`,
`tests/test_two_voice_lock.py`) reported success. They are **not wrong about the code** — they are
**testing a different process** than the one the user's browser hits:

1. **In-process testing:** `tests/test_script_preview.py` overrides
   `config.VOICE_SAMPLES_DIR` to a temp dir and exercises the Flask **test client** (`studio.app.app`)
   in-process. The test client loads the **current** `app.py` from the working tree, so the `/sample`
   routes are registered and pass. The test client **never** contacts the live production process
   (PID 8384), so it cannot observe the stale-route 404.
2. **Direct HTTP on a fresh instance:** The prior report's HTTP matrix queried
   `/api/voices/approved/<id>/sample/download` and got 200 — but that was run against a freshly started
   server with current code (or the test client), not against the stale PID 8384.
3. **Download, not playback:** The prior report verified the **download** endpoint
   (`/sample/download`) via direct HTTP. It did **not** exercise the browser **`▶ Nghe mẫu` click** nor
   the `Audio()` playback path. (Note: the prior report's recorded byte sizes — 288,044 B for both
   voices — differ from the current on-disk files — 804,464 / 843,856 B — confirming the static samples
   were regenerated between that report and now; this does not affect the root cause.)
4. **Process-state blindness:** No existing test asserts "the process bound to 8077 actually has route X
   registered" or "the served frontend's called routes exist in the running backend's route table."

So: the tests prove the **code** is correct (confirmed independently by the fresh 8099 server returning
200), but they do **not** test the **deployed/running process state**, which is where the defect lives.

---

# Primary Root Cause

```
PROVEN ROOT CAUSE:

The production Studio serving the user (PID 8384, system Python 3.10.11, bound to 127.0.0.1:8077)
loaded studio/app.py into memory at 10:05:40 AM on 2026-08-29 — BEFORE the static-sample routes
were added to the working tree (app.py saved 11:38:54 AM; routes are UNCOMMITTED, absent from
HEAD commit 788cbf5).

  app.js:960  playVoiceSample(vid) -> new Audio('/api/voices/approved/<vid>/sample')
  browser sends  GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample
  PID 8384 (stale route table) has NO such route registered
  -> Flask returns default 404 HTML page (text/html, 207 B)
  -> browser Audio element fires onerror (error.code = 4, MEDIA_ERR_SRC_NOT_SUPPORTED)
  -> app.js:967  _sampleAudio.onerror -> toast("Không tải được mẫu giọng đọc", "bad")
```

Failure class: **D (server returns 404)** — because the route is **unregistered in the running process**
(stale in-memory code), while the static files, the route logic, the MIME type, the frontend, and the
browser are all correct.

---

# Contributing Causes

1. **Stale process not restarted after a code change:** The single canonical-runtime controller
   instance — a Windows venv launcher (PID 12988, `D:\...\runtime\venv\Scripts\python.exe`) plus its
   base interpreter (PID 8384, `C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe`;
   `pyvenv.cfg` home = that base) — was started at 10:05:40 AM with the then-current `app.py`
   (which lacked the `/sample` routes). The V1.6 route additions were saved later (11:38:54 AM) but the
   running process was never restarted, so its in-memory route table stayed stale. **Note:** the two
   PIDs are the venv launcher + interpreter of **one** logical canonical-runtime instance (normal
   Windows venv behavior), **not** competing servers — port 8077 had exactly one owner. (An earlier
   draft of this report misread the pair as a "system-Python vs canonical" port collision; that is
   incorrect — 8384 was the canonical venv's interpreter carrying the venv site-packages.)
2. **Uncommitted feature routes:** The entire V1.6 audio route surface (`/sample`, `/sample/download`,
   `/api/audio-preview/<id>/audio`, `/api/audio-preview/<id>/download`) is uncommitted in the working
   tree. Any process started from committed code (or before the working-tree edits) lacks them,
   increasing stale-process risk.
3. **Static-file vs route desync:** Flask serves `app.js` fresh from disk (always current) but freezes
   Python routes at process start, so the browser can load a frontend that calls routes the running
   backend does not yet have.
4. **No process-state guard:** Nothing fails loud when a stale process is serving a newer frontend.
   The generic toast ("Không tải được mẫu giọng đọc") hides the underlying 404.

---

# Minimal Fix Surface

> **DO NOT implement now.** This section only describes what SHOULD change next; nothing was changed
> by this audit.

1. **Restart the production Studio against the current working-tree code, with only the canonical
   runtime binding to 8077.** Kill the stale system-Python PID 8384 first (or reboot), then relaunch via
   `AI_Avatar_Studio.bat` (which already targets the canonical runtime). After a clean restart with
   current `app.py`, `/api/voices/approved/<id>/sample` returns 200 and `▶ Nghe mẫu` works for both
   voices. **This single action resolves the user-visible defect with zero code change.**
2. **Process hygiene (launcher):** make `run_studio.py` / the `.bat` detect and refuse a second bind to
   8077 (or kill the existing listener) so the canonical runtime is guaranteed to serve. Ensure exactly
   one Studio process.
3. **Commit the V1.6 audio routes** so a fresh start from the repository always has them, reducing
   future stale-process drift.
4. **Optional robustness (frontend):** on `/sample` non-200, surface a clearer message (e.g. "Cần khởi
   động lại Studio") instead of the generic toast, and/or health-check the route on app load.

---

# Risk of Proposed Fix

- **Restart / kill PID 8384:** may interrupt any in-flight render job running on that process. Coordinate
  with the operator before restarting. A restart does **not** touch MuseTalk v1.5, `audio_gain=1.5`,
  `audio_context_left=0`, `audio_feature_offset_frames=-3`, FPS=25, 1080×1920, CUDA Graph, WOLA, Feature
  Coverage Guard, the Hạnh/Thanh production profiles, the language resolver, the canonical runtime, Torch,
  or CUDA dependencies. No production lock is affected.
- **Committing routes:** normal SCM action; low risk, but only once the broader V1.6 changes are ready.
- **No code change is required to fix playback** — only a process restart against current code.

---

# Production Truth Verification

- `config/render_truth.json` SHA1 = **`a5a0e55f46c29c1722efc5cc3f8fec3d902260f0`** = expected. **VERIFIED, unchanged.**
- The audit created no render, no GPU work, no MuseTalk run, no ElevenLabs call, no DB mutation.
- No renderer change was required or made.

---

# Files Modified

**No production code, routes, DB, audio files, or config modified.**

Artifacts created by this audit (diagnostic output only, non-production):
- `docs/V1_6_STATIC_VOICE_SAMPLE_PLAYBACK_ROOT_CAUSE.md` (this report)
- `tools/_audit_playback_repro.py` (read-only Playwright reproduction script; safe to delete)

A temporary fresh test server was started on **port 8099** (canonical runtime, current code) for the
control experiment and was **stopped** afterward.

---

# Post-Audit Fix Applied & Verified (2026-08-29, after user authorization)

After the audit, the user authorized the targeted fix (a process restart — no code change). Applied:

1. Stopped the stale controller instance (PID 8384 interpreter + PID 12988 launcher).
2. Relaunched `AI_Avatar_Studio.bat` (canonical runtime). New instance: venv launcher PID 13164 →
   base interpreter PID 15992, started 12:18 PM (after `app.py` saved 11:38:54 AM → current code loaded).
3. Verified on production port 8077 (current code now in memory):

| Check | Result |
|---|---|
| `GET /` (UI) | 200 |
| `GET /static/app.js` | 200 |
| `GET /api/voices/approved` | 200 application/json |
| `GET /api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample` (Thanh playback) | **200 audio/wav, inline, 804464 B, SHA256 fd77a7dd… == disk** |
| `GET /api/voices/approved/pGapy9MNHCukzJtjavF0/sample` (Hạnh playback) | **200 audio/wav, 843856 B, SHA256 f1ca2c7f… == disk** |
| `GET /api/voices/approved/<id>/sample/download` (download) | 200 audio/wav, attachment |

The defect is resolved: `▶ Nghe mẫu` now plays the static sample for both voices. Rendering remains
unaffected (controller shells out to the canonical-runtime renderer via `_torch_python()`, torch
2.5.1+cu121/CUDA available). Production Truth SHA1 unchanged.

**Residual hygiene recommendation (not yet applied):** to prevent this recurrence, restart the Studio
after any `studio/app.py` change, and commit the V1.6 audio routes so a fresh start from the repo
always has them.

---

# Final Recommendation

**READY_FOR_TARGETED_FIX**

The root cause is fully proven: a stale production server process (PID 8384) is serving a current
frontend but lacks the uncommitted `/api/voices/approved/<id>/sample` route, producing 404 → Audio
`onerror` → toast. The code on disk is correct (proven by a fresh server returning 200 with byte-exact
audio). The targeted fix is a clean restart of the canonical runtime against current code (plus process
hygiene and committing the routes). No production code, audio files, DB, routes, or config were changed
during this audit.