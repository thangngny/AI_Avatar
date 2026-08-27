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


def main():
    ap = argparse.ArgumentParser(description="AI Avatar Studio local UI/controller")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    args = ap.parse_args()

    config.ensure_runtime_dirs()
    db.init_db()
    render_service.start()

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
    # restarts the worker thread; keep it off for a stable local tool.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False,
            threaded=True)


if __name__ == "__main__":
    main()