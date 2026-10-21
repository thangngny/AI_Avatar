#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — controlled restart orchestrator (V1.6.0).

Performs a SAFE, IDENTITY-VERIFIED restart of the local Studio:

  1.  Inspect the current 8077 owner.
  2.  Verify it IS the Studio (PID + creation time + command line + interpreter).
  3.  Query active jobs.
  4.  If active immutable jobs exist and --force is not set -> DO NOT restart
      (report ACTIVE_JOBS_BLOCK_RESTART).
  5.  Request graceful shutdown (POST /api/studio/shutdown, owner-direct).
  6.  Wait a bounded time for the process to exit.
  7.  If the VERIFIED Studio process remains -> targeted process-tree
      termination (psutil) AFTER identity verification. NEVER kill an unknown
      process.
  8.  Verify port 8077 is released.
  9.  Start the Studio using the canonical interpreter + run_studio.py.
  10. Obtain the NEW PID + creation time (from the new instance manifest).
  11. Verify canonical runtime (sys.executable matches the venv).
  12. Verify HTTP readiness (GET /api/system/status -> 200).
  13. Verify the new process's code fingerprint matches the disk fingerprint
      (CODE_SYNC = CURRENT).
  14. Verify contract versions match.
  15. Run post-start smoke checks (no TTS, no GPU).
  16. Declare STUDIO_RESTART_COMPLETE (or a specific failure mode).

Run detached (spawned by the /api/studio/restart endpoint or manually):

    <canonical-python> tools/restart_studio.py [--force] [--port 8077]

It never exposes a remote kill capability and never constructs shell strings
from untrusted input: all process control uses psutil / validated numeric PIDs.
"""
import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from studio import config, runtime_guard  # noqa

PORT = 8077
HTTP_TIMEOUT = 8
GRACE_SEC = 8
PORT_FREE_WAIT = 20
HTTP_READY_WAIT = 40
LOG_DIR = os.path.join(config.RUNTIME_DIR, "logs")


def _log(msg):
    line = f"[restart {time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "restart.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _port_owner(port):
    """Return the PID listening on `port`, or None."""
    try:
        import psutil
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port:
                return c.pid
    except Exception:
        return None
    return None


def _verify_studio(pid):
    """A port owner is a Studio iff alive + cmdline has run_studio.py +
    interpreter is the canonical venv (or its base). Reuses runtime_guard."""
    return runtime_guard._owner_is_studio(pid)


def _active_jobs():
    try:
        from studio import db
        return db.list_active_jobs()
    except Exception:
        return []


def _http_get(path, port=PORT, timeout=HTTP_TIMEOUT):
    url = f"http://127.0.0.1:{port}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""
    except Exception as e:
        return None, {}, str(e).encode()


def _graceful_shutdown(port):
    """POST /api/studio/shutdown (owner-direct). Best-effort."""
    url = f"http://127.0.0.1:{port}/api/studio/shutdown"
    try:
        req = urllib.request.Request(url, data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.status
    except Exception as e:
        _log(f"graceful shutdown request failed: {e}")
        return None


def _stop_tree(pid):
    """Targeted termination of the VERIFIED Studio process tree (psutil)."""
    try:
        import psutil
        try:
            parent = psutil.Process(pid)
        except Exception:
            return False
        children = parent.children(recursive=True)
        for c in children:
            try:
                c.terminate()
            except Exception:
                pass
        try:
            parent.terminate()
        except Exception:
            pass
        gone, alive = psutil.wait_procs(children + [parent], timeout=GRACE_SEC)
        if alive:
            for p in alive:
                try:
                    p.kill()
                except Exception:
                    pass
            gone2, alive2 = psutil.wait_procs(alive, timeout=5)
            return not alive2
        return True
    except Exception as e:
        _log(f"stop_tree failed: {e}")
        return False


def _wait_port_free(port, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_owner(port) is None:
            return True
        time.sleep(0.5)
    return _port_owner(port) is None


def _wait_http_ready(port, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, _, _ = _http_get("/api/system/status", port=port, timeout=3)
        if st == 200:
            return True
        time.sleep(1.0)
    return False


def _launch_canonical(port):
    """Start the Studio under the canonical interpreter (detached)."""
    py = runtime_guard.canonical_interpreter()
    if not py or not os.path.isfile(py):
        return False, "CANONICAL_RUNTIME_MISSING"
    cmd = [py, os.path.join(ROOT, "run_studio.py"), "--host", "127.0.0.1",
           "--port", str(port), "--no-browser"]
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            import subprocess
            subprocess.Popen(cmd, cwd=ROOT,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import subprocess
            subprocess.Popen(cmd, cwd=ROOT, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return False, f"NEW_SERVER_FAILED_TO_START: {e}"
    return True, "launched"


def smoke(port=PORT):
    """Lightweight post-start smoke (no TTS, no GPU). Returns (ok, details)."""
    checks = {
        "/": None,
        "/static/app.js": None,
        "/api/system/status": None,
        "/api/voices/approved": None,
        "/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample": None,        # Thanh
        "/api/voices/approved/pGapy9MNHCukzJtjavF0/sample": None,         # Hạnh
        "/api/voices/approved/N0Z0aL8qHhzwUHwRBcVo/sample/download": None,
    }
    details = {}
    ok = True
    for path in checks:
        st, hdrs, _ = _http_get(path, port=port, timeout=HTTP_TIMEOUT)
        checks[path] = st
        details[path] = {"status": st, "content_type": (hdrs.get("Content-Type") or hdrs.get("content-type") or "")}
        if path.endswith("/sample") or path.endswith("/sample/download"):
            if st != 200 or "audio" not in (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower():
                ok = False
        else:
            if st != 200:
                ok = False
    return ok, details


def orchestrate(force=False, port=PORT):
    _log("STUDIO_RESTART_BEGIN")
    # 1-2. Inspect + verify current owner.
    owner = _port_owner(port)
    if owner is None:
        _log("PORT_NOT_OCCUPIED — no Studio to restart; launching fresh.")
        ok, msg = _launch_canonical(port)
        if not ok:
            _log(f"NEW_SERVER_FAILED_TO_START: {msg}")
            return 1
    else:
        is_studio, reason = _verify_studio(owner)
        if not is_studio:
            _log(f"PORT_{port}_CONFLICT_UNKNOWN_PROCESS — owner_pid={owner} reason={reason}; "
                 "refusing to kill an unknown process.")
            return 2
        # 3-4. Active jobs.
        active = _active_jobs()
        if active and not force:
            _log(f"RESTART_BLOCKED_ACTIVE_JOB — {len(active)} active job(s). "
                 "Use --force to override (may interrupt rendering).")
            return 3
        # 5. Graceful shutdown.
        _log(f"graceful shutdown of verified Studio PID {owner}")
        _graceful_shutdown(port)
        # 6. Wait.
        deadline = time.time() + GRACE_SEC
        while time.time() < deadline and _port_owner(port) is not None:
            time.sleep(0.5)
        # 7. Targeted termination if still alive.
        if _port_owner(port) is not None:
            still = _port_owner(port)
            is_studio2, _ = _verify_studio(still)
            if is_studio2:
                _log(f"graceful shutdown did not exit; terminating tree PID {still}")
                _stop_tree(still)
            else:
                _log("owner changed mid-restart; aborting kill of unknown process.")
                return 4
        # 8. Port released?
        if not _wait_port_free(port, PORT_FREE_WAIT):
            _log("PORT_NOT_RELEASED")
            return 5
    # 9. Launch canonical.
    ok, msg = _launch_canonical(port)
    if not ok:
        _log(f"NEW_SERVER_FAILED_TO_START: {msg}")
        return 6
    # 12. HTTP readiness.
    if not _wait_http_ready(port, HTTP_READY_WAIT):
        _log("NEW_SERVER_FAILED_TO_START: HTTP not ready")
        return 7
    # 10-11-13-14. Verify new instance via status (send the frontend contract so
    # the backend can judge contract sync — otherwise it sees frontend=None).
    contract_version = runtime_guard.load_contract_version()
    st, hdrs, body = _http_get(
        f"/api/system/status?frontend_contract={urllib.parse.quote(contract_version)}",
        port=port, timeout=HTTP_TIMEOUT)
    if st != 200:
        _log(f"POST_START_SMOKE_FAILED: status={st}")
        return 8
    try:
        status = json.loads(body)
    except Exception:
        _log("POST_START_SMOKE_FAILED: bad status JSON")
        return 8
    proc = status.get("process", {})
    code = status.get("code", {})
    contract = status.get("contract", {})
    if not proc.get("canonical_runtime"):
        _log(f"WRONG_RUNTIME_RUNNING — interpreter={proc.get('interpreter')}")
        return 9
    if code.get("sync") != "CURRENT":
        _log(f"CODE_DRIFT after restart — sync={code.get('sync')}")
        return 10
    if not contract.get("compatible"):
        _log(f"CONTRACT_MISMATCH — backend={contract.get('backend_version')} "
             f"frontend={contract.get('frontend_version')}")
        return 11
    # 15. Smoke.
    sok, sdetails = smoke(port)
    if not sok:
        _log(f"POST_START_SMOKE_FAILED: {json.dumps(sdetails)}")
        return 12
    _log(f"STUDIO_RESTART_COMPLETE new_pid={proc.get('pid')} "
         f"boot_id={proc.get('boot_id')} canonical=True code=CURRENT contract=OK smoke=PASS")
    try:
        from studio import db
        db.log_activity(action="STUDIO_RESTART_COMPLETE", resource_type="studio",
                        resource_id="self",
                        details={"pid": proc.get("pid"), "boot_id": proc.get("boot_id")},
                        result="SUCCESS")
    except Exception:
        pass
    return 0


def main():
    ap = argparse.ArgumentParser(description="Controlled Studio restart orchestrator")
    ap.add_argument("--force", action="store_true", help="restart even if active jobs exist")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    # If invoked via the /api/studio/restart endpoint, give the HTTP response a
    # moment to flush before we stop the current server.
    if os.environ.get("STUDIO_RESTART_DELAY"):
        try:
            time.sleep(float(os.environ["STUDIO_RESTART_DELAY"]))
        except Exception:
            time.sleep(2.0)
    rc = orchestrate(force=args.force, port=args.port)
    sys.exit(rc)


if __name__ == "__main__":
    main()