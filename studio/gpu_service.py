"""GPU detection + job-level scheduling.

The workstation has 2 × RTX 3090 and has demonstrated successful JOB-LEVEL
parallelism (one independent render process per GPU). We never split a single
video across GPUs. This module detects available GPUs via nvidia-smi and
tracks busy/free state so the render scheduler can assign queued jobs
automatically. Normal users never choose a GPU.
"""
import os
import re
import subprocess
import threading
from typing import List, Dict, Any

from . import config

_LOCK = threading.Lock()
_GPUS: List[Dict[str, Any]] = []   # [{id, name, memory_total_mib}]
_BUSY: set = set()                  # gpu ids currently running a job


def _query_gpus() -> List[Dict[str, Any]]:
    """Detect GPUs via nvidia-smi. Returns [] if unavailable (CPU-only / no
    nvidia-smi). Memory is informative only — scheduling is by count, not VRAM."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0 or not r.stdout.strip():
        return []
    gpus = []
    for line in r.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        gpus.append({"id": idx, "name": parts[1],
                     "memory_total_mib": int(parts[2]) if parts[2].isdigit() else 0})
    return gpus


def detect() -> List[Dict[str, Any]]:
    """Populate/cache the GPU list."""
    global _GPUS
    with _LOCK:
        if not _GPUS:
            _GPUS = _query_gpus()
        return list(_GPUS)


def available_count() -> int:
    """Number of usable GPUs (job-level parallelism width)."""
    return max(1, len(detect()))


def status() -> List[Dict[str, Any]]:
    """Per-GPU status with busy/free state for the System Status view."""
    gpus = detect()
    out = []
    with _LOCK:
        busy = set(_BUSY)
    for g in gpus:
        out.append({"id": g["id"], "name": g["name"],
                    "memory_total_mib": g["memory_total_mib"],
                    "state": "BUSY" if g["id"] in busy else "READY"})
    return out


def acquire() -> int:
    """Acquire a free GPU for a job. Returns the gpu id, or None if all busy.
    If no nvidia-smi GPUs are visible, returns 0 (CPU/fallback) so a single job
    can still run sequentially."""
    gpus = detect()
    with _LOCK:
        if not gpus:
            # Fallback single slot.
            if 0 in _BUSY:
                return None
            _BUSY.add(0)
            return 0
        for g in gpus:
            if g["id"] not in _BUSY:
                _BUSY.add(g["id"])
                return g["id"]
        return None


def release(gpu_id: int) -> None:
    with _LOCK:
        _BUSY.discard(gpu_id)