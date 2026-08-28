"""Post-render verification. Reuses ffprobe (ships with the project's
imageio-ffmpeg / ffmpeg). Verifies the output is a real, playable video with
the locked production shape: 1080x1920, 25 FPS, audio + video streams.

Does NOT fail a successful render merely because a non-critical metric is
slightly off — only hard mismatches (missing stream, wrong dimensions, zero
duration) fail.
"""
import os
import json
import subprocess
from typing import Dict, Any, Optional

from . import config


def _ffprobe(path: str) -> Optional[Dict[str, Any]]:
    # Resolve a ffprobe executable (V1.4.1 R15 fix — the old fallback called
    # imageio_ffmpeg.get_ffprobe_exe which does not exist). Resolution order:
    #   1. ffprobe on PATH
    #   2. FFPROBE_PATH env var
    #   3. ffprobe next to imageio-ffmpeg's bundled ffmpeg
    # If none is available, returns None — verify() then reports an honest
    # failure instead of fabricating success from file size alone.
    candidates = ["ffprobe", "ffprobe.exe"]
    env_p = os.environ.get("FFPROBE_PATH", "").strip()
    if env_p:
        candidates.append(env_p)
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        # imageio-ffmpeg ships ffmpeg; a sibling ffprobe may exist.
        sib = os.path.join(os.path.dirname(ff), "ffprobe.exe")
        if os.path.isfile(sib):
            candidates.append(sib)
    except Exception:
        pass
    for exe in candidates:
        try:
            r = subprocess.run(
                [exe, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", path],
                capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            continue
        if r.returncode == 0 and r.stdout:
            try:
                return json.loads(r.stdout)
            except Exception:
                return None
    return None


def ffprobe_resolved() -> Optional[str]:
    """Return the ffprobe executable path that would be used, or None.
    (V1.4.1 R15 — for preflight/reporting without running a probe.)"""
    candidates = ["ffprobe", "ffprobe.exe"]
    env_p = os.environ.get("FFPROBE_PATH", "").strip()
    if env_p:
        candidates.append(env_p)
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        sib = os.path.join(os.path.dirname(ff), "ffprobe.exe")
        if os.path.isfile(sib):
            candidates.append(sib)
    except Exception:
        pass
    import shutil as _sh
    for exe in candidates:
        if os.path.isfile(exe):
            return exe
        found = _sh.which(exe)
        if found:
            return found
    return None


def _frac_to_float(frac: str) -> float:
    try:
        if "/" in frac:
            a, b = frac.split("/")
            return float(a) / float(b)
        return float(frac)
    except Exception:
        return 0.0


def verify(output_path: str) -> Dict[str, Any]:
    """Verify a render output. Returns {ok, checks: {...}, warnings: [...]}.

    ok=True only if the file exists, is non-zero, has video+audio streams,
    1080x1920, ~25fps, sensible duration. Warnings are reported but don't fail
    unless they are hard problems.
    """
    result = {"ok": False, "checks": {}, "warnings": [], "info": {}}
    if not output_path or not os.path.isfile(output_path):
        result["checks"]["file_exists"] = False
        result["warnings"].append("Output file not found.")
        return result

    size = os.path.getsize(output_path)
    result["checks"]["file_exists"] = True
    result["info"]["size_bytes"] = size
    if size < 1000:
        result["warnings"].append("Output file is suspiciously small.")
        return result

    data = _ffprobe(output_path)
    if not data:
        # V1.4.1 R15: do NOT fabricate a successful verification from file size
        # alone when ffprobe is unavailable. Report an honest failure so the
        # operator installs ffprobe rather than trusting an unverified output.
        result["warnings"].append("ffprobe unavailable — cannot verify render output streams. Install ffprobe on PATH or set FFPROBE_PATH.")
        result["ok"] = False
        return result

    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    result["checks"]["video_stream"] = bool(vstream)
    result["checks"]["audio_stream"] = bool(astream)

    if not vstream:
        result["warnings"].append("No video stream in output.")
        return result
    if not astream:
        result["warnings"].append("No audio stream in output.")
        return result

    w = int(vstream.get("width") or 0)
    h = int(vstream.get("height") or 0)
    fps = _frac_to_float(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0")
    dur = float(data.get("format", {}).get("duration") or 0)
    nb_frames = int(vstream.get("nb_frames") or 0)

    result["info"].update({"width": w, "height": h, "fps": round(fps, 3),
                           "duration_sec": round(dur, 2), "nb_frames": nb_frames})

    # Hard checks (production shape).
    result["checks"]["resolution_1080x1920"] = (w == 1080 and h == 1920)
    if not result["checks"]["resolution_1080x1920"]:
        result["warnings"].append(f"Resolution is {w}x{h}, expected 1080x1920.")

    # ~25fps (tolerance for VFR / rounding).
    result["checks"]["fps_25"] = abs(fps - 25.0) < 1.5
    if not result["checks"]["fps_25"]:
        result["warnings"].append(f"Frame rate is {fps:.2f}, expected ~25.")

    result["checks"]["duration_sensible"] = dur >= 0.3
    if not result["checks"]["duration_sensible"]:
        result["warnings"].append(f"Duration {dur:.2f}s is too short.")

    if nb_frames:
        result["checks"]["frame_count_sensible"] = nb_frames >= 5
        if not result["checks"]["frame_count_sensible"]:
            result["warnings"].append(f"Only {nb_frames} frames.")

    # ok = video + audio + correct resolution + sensible duration. fps/frame
    # count issues are warnings only (VFR can make them drift).
    result["ok"] = (result["checks"]["video_stream"]
                    and result["checks"]["audio_stream"]
                    and result["checks"]["resolution_1080x1920"]
                    and result["checks"]["duration_sensible"])
    return result