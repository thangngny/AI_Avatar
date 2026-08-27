"""Centralized runtime resolution for the AI Avatar Studio controller.

The controller spawns the existing production tools (validator, genavatar,
generate_video_from_script) as subprocesses using a torch-capable interpreter.
This module is the SINGLE place that resolves:
  * which Python interpreter to use for heavy subprocesses
  * the authoritative repository root (import context for those tools)

ENVIRONMENT COUPLING (documented honestly — see
docs/AI_AVATAR_STUDIO_TRUTH_AUDIT.md §12):
  The current torch interpreter lives at
  C:\\CongThang\\AI_avatar\\latentsync_env — a venv located INSIDE the separate
  experimental LatentSync repository. There is NO code-level coupling (the
  production renderer / genavatar never import LatentSync; production code is
  loaded from this repo via the repo root import context). But there IS a
  filesystem/env-location dependency: if the experimental repo were moved or
  deleted, the studio's configured interpreter would vanish.

  This is NOT migrated in the repair phase. A future standalone environment
  (e.g. C:\\CongThang_AI_Avatar\\venv) is the recommended migration target; see
  docs/AI_AVATAR_STUDIO_REPAIR_REPORT.md for the migration plan. To re-point
  the studio at a different interpreter without code changes, set the env var
  STUDIO_TORCH_PYTHON to the full path of the python executable.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)  # C:\CongThang_AI_Avatar\AI_avatar

# Default torch interpreter. Overridable via STUDIO_TORCH_PYTHON for a future
# standalone env. This is the ONLY place the path is hardcoded.
_DEFAULT_TORCH_PYTHON = r"C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"


def torch_python() -> str:
    """Resolve the torch-capable interpreter for subprocesses.

    Priority:
      1. STUDIO_TORCH_PYTHON env var (explicit operator override / future
         standalone env). Used verbatim — a bare name like 'python' is honored
         (resolved via PATH by the subprocess layer); a full path is used as-is.
      2. The default latentsync_env interpreter (if it exists on disk).
      3. 'python' (last resort; lets an already-activated env on PATH work).
    """
    explicit = os.environ.get("STUDIO_TORCH_PYTHON", "").strip()
    if explicit:
        return explicit
    if os.path.exists(_DEFAULT_TORCH_PYTHON):
        return _DEFAULT_TORCH_PYTHON
    return "python"


def repo_root() -> str:
    """The authoritative repository root used as the cwd / PYTHONPATH for all
    production subprocesses (so `avatars.*` / `utils.*` resolve)."""
    return REPO_ROOT


def terminate_tree(proc) -> None:
    """Terminate a subprocess and its child tree cleanly. Best-effort; used by
    the timeout watchdogs so a hung child cannot pin a job forever."""
    import os, subprocess as _sp
    try:
        pid = proc.pid
    except Exception:
        pid = None
    try:
        if os.name == "nt" and pid:
            _sp.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, timeout=15)
        else:
            proc.terminate()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass