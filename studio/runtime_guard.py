"""Runtime/deployment hardening for the AI Avatar Studio controller (V1.6.0).

Prevents the proven incident class where the code on disk changed while the
long-running production server kept an OLD route table in memory, so the
browser received NEW frontend JS that called backend routes the running
process did not know — producing silent 404s.

This module is the single place that owns:

  * canonical-interpreter enforcement (which Python may run the Studio);
  * the runtime instance manifest (process identity: PID + creation time +
    command line + interpreter), with stale-PID safety (Windows reuses PIDs);
  * a deterministic STARTUP code fingerprint of restart-sensitive backend
    modules, vs a live DISK fingerprint, to flag CODE_DRIFT / restart_required;
  * the frozen-at-startup API contract version, compared against the value the
    browser sends, to flag a frontend/backend CONTRACT mismatch;
  * a unique boot_id per server start;
  * git head / dirty reporting;
  * the production-truth hash (read-only, never mutated here).

Design rules (per the hardening spec):

  * NO Flask debug auto-reload / watchdog. Drift is DETECTED and REPORTED; a
    restart is performed by a controlled orchestrator, never a hot reloader.
  * NO secrets (API keys, .env, auth headers) are ever written to the manifest,
    logs, or status API.
  * mtime is NOT trusted for drift; SHA256 content fingerprints are.
  * a PID alone is NOT trusted; PID + creation time + command-line identity is.
  * fingerprint scope is a small explicit manifest (bounded file count), with a
    short status cache; we never hash the whole repo on every status request.
"""
from __future__ import annotations

import os
import sys
import json
import time
import uuid
import hashlib
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from . import config

# Expected SHA1 of config/render_truth.json — the production-truth invariant.
# Used ONLY to validate the file has not been altered; the file itself is never
# mutated or re-hashed by this module.
EXPECTED_TRUTH_SHA1 = "a5a0e55f46c29c1722efc5cc3f8fec3d902260f0"


# --------------------------------------------------------------------------- #
# Canonical interpreter                                                       #
# --------------------------------------------------------------------------- #

def _norm(p: str) -> str:
    """Case- and separator-normalized real path for interpreter comparison."""
    try:
        p = os.path.realpath(p or "")
    except Exception:
        pass
    return os.path.normcase(os.path.normpath(p))


def canonical_interpreter() -> str:
    return (config.CANONICAL_INTERPRETER or "").strip()


def canonical_interpreter_exists() -> bool:
    return bool(canonical_interpreter()) and os.path.isfile(canonical_interpreter())


def interpreter_is_canonical(interpreter: Optional[str] = None) -> bool:
    """True iff the given interpreter (default: this process's sys.executable)
    matches the canonical runtime after path normalization."""
    interp = interpreter if interpreter is not None else sys.executable
    return _norm(interp) == _norm(canonical_interpreter())


# --------------------------------------------------------------------------- #
# API contract version (single source of truth: config/api_contract.json)     #
# --------------------------------------------------------------------------- #

def load_contract_version() -> str:
    """Read the contract version from disk (the source of truth)."""
    try:
        with open(config.API_CONTRACT_PATH, "r", encoding="utf-8") as f:
            return str(json.load(f).get("contract_version", "")).strip()
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Restart-sensitive backend manifest + fingerprints                          #
# --------------------------------------------------------------------------- #
# Explicit list of Python modules loaded into the Studio SERVER process whose
# in-memory behavior is frozen at process start. A change to any of these on
# disk requires a controlled restart (Flask does not hot-reload them). This is
# NOT a blind repo hash. Frontend (app.js), docs, reports, renders, and the
# contract JSON are intentionally excluded — frontend drift is caught by the
# contract handshake, not the backend fingerprint.
RESTART_SENSITIVE_FILES: List[str] = [
    "run_studio.py",
    "studio/__init__.py",
    "studio/app.py",
    "studio/config.py",
    "studio/db.py",
    "studio/render_service.py",
    "studio/avatar_service.py",
    "studio/runtime.py",
    "studio/preview_service.py",
    "studio/elevenlabs_client.py",
    "studio/voices.py",
    "studio/gpu_service.py",
    "studio/edge_tts_client.py",
    "studio/script_service.py",
    "studio/share_auth.py",
    "studio/envutil.py",
    "studio/avatar_quality.py",
    "studio/verify.py",
    "studio/runtime_guard.py",
]


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        # Stable sentinel for a missing/unreadable file so a disappearing file
        # is still a deterministic fingerprint change, not an exception.
        return "missing:" + path


def compute_code_fingerprint(rel_paths: Optional[List[str]] = None,
                             root: Optional[str] = None) -> str:
    """Deterministic SHA256 over the ordered (relpath + file_sha256) of the
    restart-sensitive backend files. Stable ordering, independent of platform."""
    root = root or config.ROOT
    paths = rel_paths if rel_paths is not None else RESTART_SENSITIVE_FILES
    h = hashlib.sha256()
    for rel in sorted(paths):
        full = os.path.join(root, rel)
        fh = _file_sha256(full)
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(fh.encode("utf-8"))
        h.update(b"\x01")
    return h.hexdigest()


# Short-lived disk-fingerprint cache so repeated status polls within a couple
# seconds don't re-hash the (bounded) manifest. Correctness over optimization.
_DISK_FP: Dict[str, Any] = {"fp": None, "ts": 0.0}
_DISK_FP_TTL = 2.0


def current_disk_fingerprint(force: bool = False) -> str:
    now = time.time()
    if (not force) and _DISK_FP["fp"] and (now - _DISK_FP["ts"] < _DISK_FP_TTL):
        return _DISK_FP["fp"]
    fp = compute_code_fingerprint()
    _DISK_FP["fp"] = fp
    _DISK_FP["ts"] = now
    return fp


# --------------------------------------------------------------------------- #
# Git + production truth (read-only)                                          #
# --------------------------------------------------------------------------- #

def git_info() -> Dict[str, Any]:
    head = ""
    dirty = False
    try:
        r = subprocess.run(
            ["git", "-C", config.ROOT, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            head = r.stdout.strip()
        r2 = subprocess.run(
            ["git", "-C", config.ROOT, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if r2.returncode == 0:
            dirty = bool(r2.stdout.strip())
    except Exception:
        pass
    return {"git_head": head or "unknown", "git_dirty": bool(dirty)}


def production_truth_hash() -> str:
    """SHA1 of config/render_truth.json (read-only). Matches the operator's
    Expected Production Truth invariant. Never mutated here."""
    try:
        h = hashlib.sha1()
        with open(config.TRUTH_PATH, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def production_truth_valid(expected_hash: str = "") -> bool:
    got = production_truth_hash()
    if not got:
        return False
    expected = expected_hash or EXPECTED_TRUTH_SHA1
    return got.lower() == expected.strip().lower()


# --------------------------------------------------------------------------- #
# Process identity (psutil)                                                   #
# --------------------------------------------------------------------------- #

def _psutil():
    try:
        import psutil  # noqa
        return psutil
    except Exception:
        return None


def process_creation_time(pid: int) -> Optional[float]:
    """Creation time (epoch) for a PID, or None. Used to defeat Windows PID
    reuse: a reused PID will not share the original creation time."""
    ps = _psutil()
    if not ps:
        return None
    try:
        return ps.Process(pid).create_time()
    except Exception:
        return None


def process_cmdline(pid: int) -> Optional[str]:
    ps = _psutil()
    if not ps:
        return None
    try:
        return " ".join(ps.Process(pid).cmdline())
    except Exception:
        return None


def process_exe(pid: int) -> Optional[str]:
    ps = _psutil()
    if not ps:
        return None
    try:
        return ps.Process(pid).exe()
    except Exception:
        return None


def pid_alive(pid: int) -> bool:
    ps = _psutil()
    if not ps:
        return False
    try:
        return ps.Process(pid).is_running()
    except Exception:
        return False


def pid_matches_manifest(manifest: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify a manifest's PID is the SAME process that wrote it:
    alive AND creation time matches AND command line looks like a Studio start.
    Returns (ok, reason)."""
    pid = manifest.get("pid")
    if not isinstance(pid, int):
        return False, "no_pid"
    if not pid_alive(pid):
        return False, "pid_dead"
    ct = manifest.get("process_created_at")
    actual_ct = process_creation_time(pid)
    if actual_ct is None:
        return False, "pid_unreadable"
    if ct is not None and abs(float(ct) - actual_ct) > 1.0:
        return False, "creation_time_mismatch (PID reused)"
    # Command-line identity: must reference run_studio.py.
    cmd = process_cmdline(pid) or ""
    if "run_studio.py" not in cmd:
        return False, "cmdline_not_studio"
    return True, "alive"


# --------------------------------------------------------------------------- #
# Instance manifest                                                           #
# --------------------------------------------------------------------------- #

def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_instance_manifest() -> Optional[Dict[str, Any]]:
    try:
        with open(config.INSTANCE_MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_instance_manifest(data: Dict[str, Any]) -> None:
    _atomic_write_json(config.INSTANCE_MANIFEST_PATH, data)


def clear_instance_manifest() -> None:
    try:
        os.remove(config.INSTANCE_MANIFEST_PATH)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Frozen startup state (set once by run_studio.py at boot)                    #
# --------------------------------------------------------------------------- #
_STARTUP: Dict[str, Any] = {}


def init_at_startup(pid: Optional[int] = None) -> Dict[str, Any]:
    """Called once at server start. Freezes the startup fingerprint + contract
    version + boot_id + process identity, and writes the instance manifest.
    Returns the frozen snapshot."""
    if _STARTUP.get("boot_id"):  # idempotent within a process
        return dict(_STARTUP)
    pid = pid or os.getpid()
    boot_id = uuid.uuid4().hex
    created = process_creation_time(pid)
    started = time.time()
    startup_fp = compute_code_fingerprint()
    contract = load_contract_version()
    gi = git_info()
    truth_hash = production_truth_hash()
    snap = {
        "boot_id": boot_id,
        "pid": pid,
        "process_created_at": created,
        "server_started_at": started,
        "interpreter": sys.executable,
        "entrypoint": "run_studio.py",
        "repository": config.ROOT,
        "port": 8077,
        "startup_code_fingerprint": startup_fp,
        "backend_contract_version": contract,
        "git_head": gi["git_head"],
        "git_dirty": gi["git_dirty"],
        "production_truth_hash": truth_hash,
    }
    _STARTUP.clear()
    _STARTUP.update(snap)
    # Persist the manifest (no secrets).
    try:
        write_instance_manifest(snap)
    except Exception:
        pass
    return dict(snap)


def startup_snapshot() -> Dict[str, Any]:
    return dict(_STARTUP) if _STARTUP else {}


# --------------------------------------------------------------------------- #
# Runtime status snapshot (for /api/system/status)                            #
# --------------------------------------------------------------------------- #
# Sub-second drift transition logging: only log when the fingerprint actually
# changes vs the last reported one.
_LAST_REPORTED_FP: Optional[str] = None


def runtime_status_snapshot(frontend_contract: Optional[str] = None,
                             expected_truth_hash: str = ""
                             ) -> Dict[str, Any]:
    """Assemble process/code/contract diagnostics. Pure data; no secrets."""
    snap = startup_snapshot()
    startup_fp = snap.get("startup_code_fingerprint", "")
    disk_fp = current_disk_fingerprint()
    code_sync = "CURRENT" if (startup_fp and disk_fp == startup_fp) else (
        "STALE" if startup_fp else "UNKNOWN"
    )
    restart_required = (code_sync == "STALE")

    backend_contract = snap.get("backend_contract_version", "")
    fc = (frontend_contract or "").strip()
    contract_compatible = bool(backend_contract and fc and backend_contract == fc)
    # If the frontend didn't send a version we can't judge compatibility; treat
    # as unknown rather than silently compatible.
    contract_known = bool(backend_contract and fc)

    interp_canonical = interpreter_is_canonical(snap.get("interpreter", sys.executable))
    canonical_exists = canonical_interpreter_exists()

    truth_h = production_truth_hash()
    truth_valid = bool(truth_h) and (
        truth_h.lower() == expected_truth_hash.strip().lower() if expected_truth_hash else True
    )

    active = _active_job_count()

    # If code drifted or the contract mismatched, the Studio should not accept
    # NEW mutable work (an already-running immutable render may still finish).
    accepting_new_work = (not restart_required) and contract_compatible and interp_canonical

    out = {
        "process": {
            "pid": snap.get("pid"),
            "boot_id": snap.get("boot_id"),
            "server_started_at": snap.get("server_started_at"),
            "process_created_at": snap.get("process_created_at"),
            "interpreter": snap.get("interpreter", sys.executable),
            "canonical_runtime": interp_canonical,
            "canonical_interpreter": canonical_interpreter(),
            "canonical_interpreter_exists": canonical_exists,
            "entrypoint": snap.get("entrypoint"),
            "port": snap.get("port", 8077),
        },
        "code": {
            "git_head": snap.get("git_head", ""),
            "git_dirty": snap.get("git_dirty", False),
            "startup_fingerprint": startup_fp,
            "disk_fingerprint": disk_fp,
            "sync": code_sync,
            "restart_required": restart_required,
        },
        "contract": {
            "backend_version": backend_contract,
            "frontend_version": fc or None,
            "compatible": contract_compatible,
            "known": contract_known,
        },
        "production_truth": {
            "hash": truth_h,
            "valid": truth_valid,
        },
        "active_jobs": active,
        # Composite health dimensions (spec §15): never one ambiguous READY.
        "runtime_ready": interp_canonical,          # controller interpreter sanity
        "code_sync": code_sync,
        "contract_sync": contract_compatible,
        "restart_required": restart_required,
        "studio_accepting_new_work": accepting_new_work,
    }
    return out


def _active_job_count() -> int:
    """Count non-terminal render jobs from the DB (read-only). Best-effort;
    returns 0 if the DB is unavailable (e.g., during tests with no DB)."""
    try:
        from . import db
        return len(db.list_active_jobs())
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
# Single-instance check (called by run_studio.py BEFORE binding)              #
# --------------------------------------------------------------------------- #

def single_instance_decision(port: int = 8077) -> Dict[str, Any]:
    """Decide whether this process may bind `port`.

    Returns one of:
      {"action": "proceed"}                       -> port free; bind it.
      {"action": "already_running", "manifest": ..} -> a VERIFIED Studio owns it.
      {"action": "unknown_owner", "detail": ..}   -> something else owns it; STOP.
      {"action": "stale_manifest", "manifest": ..} -> manifest points to a dead/
                                                     reused PID; safe to replace.

    Identity of an existing Studio is established from the instance manifest
    (PID + creation time + command line). We do NOT trust the port alone.
    """
    ps = _psutil()
    # Is anything listening on the port?
    owner_pid = None
    if ps:
        try:
            for c in ps.net_connections(kind="tcp"):
                if c.status == psutil_conn_listen() and c.laddr and c.laddr.port == port:
                    owner_pid = c.pid
                    break
        except Exception:
            owner_pid = None
    if not owner_pid:
        return {"action": "proceed"}

    # Manifest-based identity check.
    manifest = read_instance_manifest()
    if manifest and manifest.get("port") == port:
        ok, reason = pid_matches_manifest(manifest)
        if ok:
            return {"action": "already_running", "manifest": manifest}
        # Manifest stale (dead/reused PID) — but the port is still held by
        # owner_pid. Is owner_pid itself a Studio?
        ok2, reason2 = _owner_is_studio(owner_pid)
        if ok2:
            return {"action": "already_running",
                    "manifest": manifest, "live_pid": owner_pid}
        return {"action": "unknown_owner", "detail": {
            "port": port, "owner_pid": owner_pid,
            "reason": "manifest_stale_and_owner_not_studio: " + reason2,
        }}

    # No manifest (or different port): inspect the port owner directly.
    ok3, reason3 = _owner_is_studio(owner_pid)
    if ok3:
        return {"action": "already_running", "manifest": manifest,
                "live_pid": owner_pid}
    return {"action": "unknown_owner", "detail": {
        "port": port, "owner_pid": owner_pid, "reason": reason3,
    }}


def psutil_conn_listen():
    """Return the psutil status string for a listening socket (stable across
    psutil versions)."""
    ps = _psutil()
    return getattr(ps, "CONN_LISTEN", "LISTEN") if ps else "LISTEN"


def _owner_is_studio(pid: int) -> Tuple[bool, str]:
    """A port owner is a Studio iff alive, cmdline references run_studio.py, and
    its interpreter is the canonical venv (or its base interpreter, to tolerate
    the Windows venv-launcher pattern). Identity is NOT assumed from the port."""
    if not pid_alive(pid):
        return False, "owner_pid_dead"
    cmd = process_cmdline(pid) or ""
    if "run_studio.py" not in cmd:
        return False, "cmdline_not_studio"
    exe = process_exe(pid) or ""
    # Accept the canonical venv interpreter OR its base interpreter (the venv
    # launcher spawns the base python.exe on Windows; both are the canonical
    # runtime). Reject a plainly unrelated interpreter.
    if not _interpreter_related_to_canonical(exe):
        return False, "interpreter_not_canonical"
    return True, "studio"


def _interpreter_related_to_canonical(exe: str) -> bool:
    if not exe:
        return False
    if _norm(exe) == _norm(canonical_interpreter()):
        return True
    # The venv's base interpreter (pyvenv.cfg home) is also acceptable.
    try:
        cfg = os.path.join(os.path.dirname(canonical_interpreter()), "..", "pyvenv.cfg")
        cfg = os.path.normpath(cfg)
        if os.path.isfile(cfg):
            home = ""
            with open(cfg, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().lower().startswith("home"):
                        home = line.split("=", 1)[1].strip()
                        break
            if home:
                base = os.path.join(home, "python.exe")
                if _norm(exe) == _norm(base):
                    return True
    except Exception:
        pass
    return False


# --------------------------------------------------------------------------- #
# Drift transition logging helper (called by the status endpoint once per
# newly-changed fingerprint, not per request)                                #
# --------------------------------------------------------------------------- #
def note_drift_if_changed(log_prefix: str = "STUDIO_CODE_DRIFT_DETECTED") -> Optional[str]:
    """Log a drift notice at most once per new disk fingerprint. Returns the
    notice string if a NEW drift was detected this call, else None."""
    global _LAST_REPORTED_FP
    snap = startup_snapshot()
    startup_fp = snap.get("startup_code_fingerprint", "")
    disk_fp = current_disk_fingerprint()
    if startup_fp and disk_fp != startup_fp:
        if _LAST_REPORTED_FP != disk_fp:
            _LAST_REPORTED_FP = disk_fp
            return f"{log_prefix}: startup={startup_fp[:12]} disk={disk_fp[:12]}"
    else:
        _LAST_REPORTED_FP = disk_fp
    return None