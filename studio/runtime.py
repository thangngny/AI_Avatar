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
import json
import subprocess
from typing import Any, Dict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)  # C:\CongThang_AI_Avatar\AI_avatar

# Default torch interpreter. Overridable via STUDIO_TORCH_PYTHON for a future
# standalone env. This is the ONLY place the path is hardcoded.
def _resolve_default_torch_python() -> str:
    candidates = [
        r"D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
        r"C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
        os.path.normpath(os.path.join(REPO_ROOT, "..", "runtime", "venv", "Scripts", "python.exe")),
        r"C:\CongThang_AI_Avatar_TikTokLive\runtime\venv\Scripts\python.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[0]


_DEFAULT_TORCH_PYTHON = _resolve_default_torch_python()


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


# --------------------------------------------------------------------------- #
# V1.6.0 — runtime preflight (fail-fast on a wrong/broken interpreter)        #
# --------------------------------------------------------------------------- #
_PREFLIGHT = None
_PREFLIGHT_TS = 0.0

_PROBE_CODE = (
    "import sys,json\n"
    "out={'ok':True,'python_version':sys.version.split()[0],'executable':sys.executable,"
    "'runtime_root':sys.prefix,'base_prefix':sys.base_prefix}\n"
    "try:\n"
    "  import torch\n"
    "  out['torch_version']=torch.__version__; out['torch_file']=torch.__file__\n"
    "  out['torch_cuda']=torch.version.cuda\n"
    "  out['cuda_available']=torch.cuda.is_available()\n"
    "  out['gpu_count']=torch.cuda.device_count()\n"
    "  out['gpus']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]\n"
    "  x=torch.tensor([1.,2.]).cuda(); out['cuda_op_ok']=bool((x*2).sum().item()==6.0); torch.cuda.synchronize()\n"
    "  out['renderer_ready']=out['cuda_available'] and out['cuda_op_ok']\n"
    "except Exception as e:\n"
    "  out['renderer_ready']=False; out['torch_error']=f'{type(e).__name__}: {e}'\n"
    "print(json.dumps(out))\n"
)


def probe_interpreter(python_exe: str, timeout: int = 120) -> Dict[str, Any]:
    """Read-only probe of an interpreter for the renderer stack (torch+CUDA).
    Never raises; returns {ok, ...} with an error string on failure. No secrets,
    no MuseTalk model loading. Used by preflight() and tools/verify_runtime.py."""
    if not python_exe or not os.path.isfile(python_exe):
        return {"ok": False, "executable": python_exe,
                "error": "interpreter not found", "renderer_ready": False}
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([python_exe, "-c", _PROBE_CODE], capture_output=True,
                           text=True, timeout=timeout, env=env)
        try:
            return json.loads(r.stdout)
        except Exception:
            return {"ok": False, "executable": python_exe,
                    "error": (r.stderr or r.stdout)[:300], "renderer_ready": False}
    except Exception as e:
        return {"ok": False, "executable": python_exe,
                "error": f"{type(e).__name__}: {e}", "renderer_ready": False}


def preflight(refresh: bool = False, ttl: float = 60.0) -> Dict[str, Any]:
    """Cached runtime preflight for the renderer interpreter (torch_python()).
    Returns {ok, interpreter, python_version, runtime_root, torch_version,
    torch_cuda, cuda_available, gpu_count, gpus, renderer_ready, torch_error?}.
    The studio reports this at launch + via /api/runtime/status so a wrong/broken
    interpreter is surfaced BEFORE render time (fail-fast), not at render time."""
    import time as _t
    global _PREFLIGHT, _PREFLIGHT_TS
    if (not refresh) and _PREFLIGHT and (_t.time() - _PREFLIGHT_TS < ttl):
        return _PREFLIGHT
    interp = torch_python()
    info = probe_interpreter(interp)
    info["interpreter"] = interp
    info["ok"] = info.get("renderer_ready", False)
    if info.get("torch_error"):
        info["status"] = "NOT_READY"
        info["message"] = "Production renderer runtime mismatch — torch/CUDA unavailable in the configured interpreter."
    elif not info.get("renderer_ready"):
        info["status"] = "NOT_READY"
        info["message"] = "Renderer runtime not ready (CUDA unavailable)."
    else:
        info["status"] = "READY"
    _PREFLIGHT = info
    _PREFLIGHT_TS = _t.time()
    return info


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