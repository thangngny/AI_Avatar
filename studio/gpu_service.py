"""GPU detection + job-level scheduling for NextGen RTX 5090.

The workstation features an NVIDIA GeForce RTX 5090 with 32 GB GDDR7 VRAM.
Each full-quality 1080p render stream requires ~15.5 GB VRAM.
This module supports 2 concurrent execution slots on 32GB-class GPUs,
allowing 2 videos to render simultaneously while automatically queuing any
subsequent jobs until a slot frees up.
"""
import os
import re
import subprocess
import threading
from typing import List, Dict, Any, Optional

from . import config

_LOCK = threading.Lock()
_GPUS: List[Dict[str, Any]] = []        # [{id, name, memory_total_mib}]
_BUSY_COUNTS: Dict[int, int] = {}       # gpu id -> count of actively running jobs


def _query_gpus() -> List[Dict[str, Any]]:
    """Detect GPUs via nvidia-smi. Returns [] if unavailable (CPU-only / no
    nvidia-smi)."""
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


def max_slots_for_gpu(gpu: Dict[str, Any]) -> int:
    """Determine safe concurrent render slots for this GPU.
    RTX 5090 (32GB GDDR7) can host 2 concurrent streams (~15.5GB each).
    GPUs < 30GB host 1 stream. Overridable via STUDIO_SLOTS_PER_GPU."""
    env_override = os.getenv("STUDIO_SLOTS_PER_GPU", "").strip()
    if env_override.isdigit():
        return max(1, int(env_override))
    mem_mib = gpu.get("memory_total_mib", 0)
    if mem_mib >= 30000:  # 32 GB class (e.g. RTX 5090)
        return 2
    return 1


def available_count() -> int:
    """Number of usable concurrent job slots across all GPUs."""
    gpus = detect()
    if not gpus:
        return 1
    return sum(max_slots_for_gpu(g) for g in gpus)


def status() -> List[Dict[str, Any]]:
    """Per-GPU status with busy/free state for the System Status view."""
    gpus = detect()
    out = []
    with _LOCK:
        counts = dict(_BUSY_COUNTS)
    for g in gpus:
        gid = g["id"]
        slots = max_slots_for_gpu(g)
        active = counts.get(gid, 0)
        state = "READY" if active < slots else "BUSY"
        out.append({
            "id": gid,
            "name": g["name"],
            "memory_total_mib": g["memory_total_mib"],
            "active_jobs": active,
            "max_slots": slots,
            "state": state
        })
    return out


def acquire() -> Optional[int]:
    """Acquire an available GPU slot for a job.
    Returns the gpu id (e.g. 0), or None if all slots on all GPUs are saturated."""
    gpus = detect()
    with _LOCK:
        if not gpus:
            # Fallback single slot for CPU.
            if _BUSY_COUNTS.get(0, 0) >= 1:
                return None
            _BUSY_COUNTS[0] = _BUSY_COUNTS.get(0, 0) + 1
            return 0

        for g in gpus:
            gid = g["id"]
            slots = max_slots_for_gpu(g)
            current_active = _BUSY_COUNTS.get(gid, 0)
            if current_active < slots:
                _BUSY_COUNTS[gid] = current_active + 1
                return gid
        return None


def release(gpu_id: int) -> None:
    """Release an active slot on the specified GPU."""
    with _LOCK:
        if gpu_id in _BUSY_COUNTS:
            _BUSY_COUNTS[gpu_id] = max(0, _BUSY_COUNTS[gpu_id] - 1)
            if _BUSY_COUNTS[gpu_id] == 0:
                del _BUSY_COUNTS[gpu_id]
