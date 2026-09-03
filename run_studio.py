#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — entrypoint.

Launches the Flask controller that drives the existing MuseTalk v1.5
production renderer. The controller never imports torch; it spawns the
production entrypoints (validator / genavatar / generate_video_from_script)
as subprocesses using the torch-capable interpreter.

Run:
    python run_studio.py            # http://127.0.0.1:8077
    python run_studio.py --port 8077 --no-browser
"""
import os
import sys
import webbrowser
import argparse

# Make the repo root importable whether run from repo root or elsewhere.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from studio import config, db, render_service  # noqa: E402
from studio import runtime_guard  # noqa: E402


def _startup_hardening(port: int) -> bool:
    """V1.6.0 runtime/deployment hardening, run BEFORE the server binds.

    1. Canonical-interpreter enforcement (missing -> STOP; wrong -> warn +
       status reports not-ready, but we still serve for diagnostics).
    2. Single-instance guarantee: only one authoritative Studio may own the
       port. A verified running Studio -> exit 0 ("already running"); an
       UNKNOWN port owner -> exit 1 (never kill unrelated software).
    3. Freeze + persist the runtime instance manifest (boot_id, fingerprint,
       contract version, process identity).

    Returns:
      "proceed"          -> this process may bind;
      "already_running" -> exit 0 (a verified Studio owns the port);
      <other>            -> exit 1 (refused: unknown owner / missing runtime).
    """
    # 1) Canonical runtime.
    if not runtime_guard.canonical_interpreter_exists():
        print("=" * 56)
        print("CANONICAL_RUNTIME_MISSING")
        print("  Expected interpreter: %s" % runtime_guard.canonical_interpreter())
        print("  The Studio must run under its canonical torch-capable runtime.")
        print("  Refusing to start (no silent fallback to system Python).")
        print("=" * 56)
        return "canonical_missing"
    if not runtime_guard.interpreter_is_canonical():
        # Wrong interpreter: do NOT silently claim READY. We still serve so the
        # operator can read /api/system/status (canonical_runtime=false), but
        # flag it loudly.
        print("=" * 56)
        print("RUNTIME_MISMATCH")
        print("  Running interpreter: %s" % sys.executable)
        print("  Canonical interpreter: %s" % runtime_guard.canonical_interpreter())
        print("  Studio will NOT report READY until restarted under the canonical runtime.")
        print("=" * 56)

    # 2) Single-instance.
    decision = runtime_guard.single_instance_decision(port)
    action = decision.get("action")
    if action == "already_running":
        m = decision.get("manifest") or {}
        live = decision.get("live_pid") or m.get("pid")
        import time as _t
        started = m.get("server_started_at")
        started_s = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(started)) if started else "?"
        print("Studio already running")
        print("  PID:    %s" % live)
        print("  Port:   %s" % port)
        print("  Runtime: %s" % (m.get("interpreter") or "?"))
        print("  Started: %s" % started_s)
        print("  No duplicate server spawned. Open http://127.0.0.1:%s/" % port)
        return "already_running"
    if action == "unknown_owner":
        print("=" * 56)
        print("PORT_%s_CONFLICT_UNKNOWN_PROCESS" % port)
        print("  Port %s is held by a process that is NOT the AI Avatar Studio." % port)
        print("  Refusing to kill an unknown process. Detail:")
        d = decision.get("detail", {})
        print("    owner_pid: %s" % d.get("owner_pid"))
        print("    reason:    %s" % d.get("reason"))
        print("  Resolve the conflict manually, then relaunch.")
        print("=" * 56)
        return "unknown_owner"
    if action == "stale_manifest":
        # Manifest pointed at a dead/reused PID; safe to replace.
        runtime_guard.clear_instance_manifest()
    # action == "proceed": fall through.

    # 3) Freeze + persist instance manifest (boot_id, fingerprints, identity).
    snap = runtime_guard.init_at_startup()
    print("STUDIO_BOOT boot_id=%s pid=%s interpreter=%s" % (
        snap.get("boot_id"), snap.get("pid"), snap.get("interpreter")))
    if snap.get("git_dirty"):
        print("  git: dirty (uncommitted) — allowed for development; "
              "restart after backend code changes.")
    return "proceed"


def main():
    ap = argparse.ArgumentParser(description="AI Avatar Studio local UI/controller")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    args = ap.parse_args()

    config.ensure_runtime_dirs()
    db.init_db()
    render_service.start()

    # V1.6.0 hardening: canonical runtime + single-instance + manifest, BEFORE bind.
    action = _startup_hardening(args.port)
    if action == "already_running":
        sys.exit(0)
    if action != "proceed":
        sys.exit(1)

    from studio.app import app
    url = f"http://{args.host}:{args.port}/"
    print("=" * 56)
    print("AI AVATAR STUDIO")
    print("=" * 56)
    print(f"  URL:   {url}")
    print(f"  Repo:  {HERE}")
    print(f"  Truth: {config.TRUTH_PATH} (read-only)")
    print(f"  Renders: {config.RENDERS_DIR}")
    print("  Production renderer: generate_video_from_script.py")
    print("  LatentSync: NOT integrated (experimental only)")
    print("=" * 56)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    # use_reloader=False: reloading would re-spawn nothing heavy, but it also
    # restarts the worker thread; keep it off for a stable local tool. Drift is
    # detected and reported by runtime_guard, never hot-reloaded.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False,
            threaded=True)


if __name__ == "__main__":
    main()