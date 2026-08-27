"""Avatar service: list prepared avatars, analyze raw sources, prepare new
avatars — all by driving EXISTING production entrypoints as subprocesses.

Never imports torch / MuseTalk. Never overwrites an existing avatar. Reuses:
  * tools/avatar_source_quality/validator.py  (analyze)
  * avatars/musetalk/genavatar.py             (prepare, v15, parsing_mode jaw)
  * utils/avatar_validate.py shape            (READY detection)
"""
import os
import json
import shutil
import subprocess
import threading
import time
from typing import Dict, Any, List, Optional

from . import config
from . import db
from . import runtime


def _time_monotonic() -> float:
    return time.monotonic()


def _terminate_tree(proc: subprocess.Popen) -> None:
    """Terminate a subprocess and its child tree cleanly. Best-effort."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            import signal
            proc.terminate()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

# Required on-disk artifacts for a prepared avatar to be READY (matches
# utils/avatar_validate.py + system_status.py).
REQUIRED_ARTIFACTS = ("full_imgs", "coords.pkl", "latents.pt",
                     "mask_coords.pkl", "avator_info.json")
REQUIRED_DIR_ARTIFACTS = ("full_imgs", "mask")


def _torch_python() -> str:
    """The torch-capable interpreter. Resolved centrally via studio.runtime
    (single source of truth; overridable via STUDIO_TORCH_PYTHON)."""
    return runtime.torch_python()


def _is_excluded(name: str) -> bool:
    """Skip .uploads, .gitkeep, raw source files, logs, incomplete folders."""
    if name.startswith("."):
        return True
    if name.lower() in ("logs", "readme", ".gitkeep"):
        return True
    return False


def _avatar_type(avatar_id: str, info: Optional[dict]) -> str:
    """Best-effort Close Up / Full Body classification from the avatar_id
    keyword (determinable for the existing prepared avatars)."""
    aid = avatar_id.lower()
    if any(k in aid for k in ("closeup", "close_up", "cu_", "cu2", "close-up")):
        return "Close Up"
    if any(k in aid for k in ("fullbody", "full_body", "fullbody_", "fb_", "full-body")):
        return "Full Body"
    return "Unknown"


def _check_ready(avatar_dir: str) -> bool:
    for d in REQUIRED_DIR_ARTIFACTS:
        if not os.path.isdir(os.path.join(avatar_dir, d)):
            return False
    for f in REQUIRED_ARTIFACTS:
        p = os.path.join(avatar_dir, f)
        if not os.path.exists(p):
            return False
    # full_imgs and mask must contain at least one image
    if not _first_img(os.path.join(avatar_dir, "full_imgs")):
        return False
    if not _first_img(os.path.join(avatar_dir, "mask")):
        return False
    # avator_info.json must declare v15
    try:
        with open(os.path.join(avatar_dir, "avator_info.json"), "r", encoding="utf-8") as fh:
            info = json.load(fh)
        if str(info.get("version", "")).lower() != "v15":
            return False
    except Exception:
        return False
    return True


def _first_img(directory: str) -> Optional[str]:
    if not os.path.isdir(directory):
        return None
    for f in sorted(os.listdir(directory)):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(directory, f)
    return None


def _read_info(avatar_dir: str) -> Optional[dict]:
    try:
        with open(os.path.join(avatar_dir, "avator_info.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _creation_time(avatar_dir: str) -> Optional[float]:
    p = os.path.join(avatar_dir, "avator_info.json")
    if not os.path.exists(p):
        p = avatar_dir
    try:
        return os.path.getmtime(p)
    except Exception:
        return None


def list_avatars() -> List[Dict[str, Any]]:
    """List avatar directories under data/avatars/. Excludes .uploads and
    dotfiles (raw sources / logs). Each item carries an artifact-validated
    status: "READY" (artifact-complete, v15) or "INCOMPLETE" (missing required
    artifacts). Incomplete dirs are listed (so the operator can see them and
    re-prepare) but are NOT selectable for rendering (the UI gates on
    status=="READY"). No data is deleted."""
    out = []
    if not os.path.isdir(config.AVATARS_ROOT):
        return out
    for name in sorted(os.listdir(config.AVATARS_ROOT)):
        if _is_excluded(name):
            continue
        d = os.path.join(config.AVATARS_ROOT, name)
        if not os.path.isdir(d):
            continue
        info = _read_info(d)
        ready = _check_ready(d)
        thumb = _first_img(os.path.join(d, "full_imgs"))
        item = {
            "avatar_id": name,
            "name": name,
            "avatar_type": _avatar_type(name, info),
            "ready": ready,
            "status": "READY" if ready else "INCOMPLETE",
            "thumbnail": f"/api/avatars/{name}/thumbnail",
            "quality": None,
            "source_video": (info or {}).get("video_path"),
            "created_at": _creation_time(d),
            "parsing_mode": (info or {}).get("parsing_mode"),
            "version": (info or {}).get("version"),
            "frame_count": len([x for x in os.listdir(os.path.join(d, "full_imgs"))
                                if x.lower().endswith((".png", ".jpg", ".jpeg"))])
            if os.path.isdir(os.path.join(d, "full_imgs")) else 0,
        }
        # merge cached quality from db if present
        row = db.get_avatar(name)
        if row:
            item["quality"] = row.get("quality")
        # build a compact, honest quality summary for the library card
        from . import avatar_quality as aq
        qd = None
        if row and row.get("quality_data"):
            try:
                qd = json.loads(row["quality_data"])
            except Exception:
                qd = None
        qsum = aq.quality_summary_for_list(qd)
        item["quality_status"] = qsum["quality_status"]
        item["quality_strengths"] = qsum["strengths"]
        item["quality_warnings"] = qsum["warnings"]
        item["quality_source"] = qsum["quality_source"]
        item["face_h_ratio"] = qsum["face_h_ratio"]
        item["production_confidence"] = qsum["production_confidence"]
        item["render_count"] = qsum["render_count"]
        item["prepared_status"] = qsum["prepared_status"]
        item["prepared_strengths"] = qsum["prepared_strengths"]
        item["prepared_warnings"] = qsum["prepared_warnings"]
        out.append(item)
    return out


def avatar_counts() -> Dict[str, int]:
    """TOTAL_DIRS / READY_AVATARS / INCOMPLETE_AVATARS for the system status
    view. Only non-excluded dirs are counted."""
    av = list_avatars()
    ready = sum(1 for a in av if a["ready"])
    return {
        "total_dirs": len(av),
        "ready_avatars": ready,
        "incomplete_avatars": len(av) - ready,
    }


def avatar_thumbnail_path(avatar_id: str) -> Optional[str]:
    """Resolve the thumbnail image path for an avatar (first full_img)."""
    d = os.path.join(config.AVATARS_ROOT, avatar_id)
    if _is_excluded(avatar_id) or not os.path.isdir(d):
        return None
    return _first_img(os.path.join(d, "full_imgs"))


# --------------------------------------------------------------------------- #
# Source quality analysis                                                     #
# --------------------------------------------------------------------------- #
# Human-language translation per spec section 36/12. Maps validator category
# -> {PASS/WARN/FAIL: human message}. Falls back to the validator's own note.
_HUMAN = {
    "FACE_SIZE": {
        "WARN": "Khuôn mặt hơi nhỏ trong khung hình. Nên quay gần hơn để vùng môi có nhiều chi tiết hơn.",
        "FAIL": "Khuôn mặt khá nhỏ / xa camera. Chất lượng khẩu hình sẽ thấp; nên dùng nguồn quay gần hơn nếu có thể.",
    },
    "FACE_SHARPNESS": {
        "WARN": "Khuôn mặt hơi mờ. Nguồn sắc nét hơn giúp chi tiết môi tốt hơn.",
        "FAIL": "Khuôn mặt rất mờ. Khẩu hình sẽ kém.",
    },
    "FRONTALNESS": {
        "WARN": "Mặt hơi lệch. Nhìn thẳng vào camera cho kết quả tốt nhất.",
        "FAIL": "Mặt lệch nhiều, không đủ chính diện cho lipsync ổn định.",
    },
    "MOUTH_VISIBILITY": {
        "WARN": "Miệng hơi ra khỏi khung. Giữ toàn bộ miệng nhìn thấy.",
        "FAIL": "Miệng không nhìn thấy rõ trong khung.",
    },
    "CHIN_VISIBILITY": {
        "WARN": "Cằm/hàm hơi sát mép. Bao gồm cả cằm và đường hàm trong khung.",
        "FAIL": "Cằm/hàm bị cắt. Mask cần đường hàm đầy đủ.",
    },
    "SOURCE_MOUTH_STATE": {
        "WARN": "Nhân vật đang nói trong video nguồn. Nên dùng nguồn miệng nghỉ, trung tính.",
        "FAIL": "Nguồn có nói nhiều / biểu cảm mạnh. Nên dùng nguồn miệng nghỉ, trung tính.",
    },
    "MOTION": {
        "WARN": "Có chuyển động camera/nhân vật. Nguồn cố định tốt hơn.",
        "FAIL": "Chuyển động/rung nhiều. Nên dùng nguồn cố định, ổn định.",
    },
    "LIGHTING": {
        "WARN": "Ánh sáng thay đổi trong video. Ánh sáng ổn định, đều tốt hơn.",
        "FAIL": "Ánh sáng không ổn định. Nên dùng ánh sáng đều, ổn định.",
    },
}


def _translate_category(cat: str, status: str, note: str, value: Any) -> Dict[str, Any]:
    msg = _HUMAN.get(cat, {}).get(status)
    if not msg:
        if status == "PASS":
            msg = "Good"
        else:
            msg = note or status
    return {"category": cat, "status": status, "message": msg,
            "note": note, "value": value}


# Categories whose failure means the source CANNOT be technically processed.
_TECHNICAL_CATEGORIES = set()  # all are quality categories; integrity handled separately


def analyze_source(video_path: str) -> Dict[str, Any]:
    """Run the validator as a subprocess and translate results to human
    language. Returns:
      { technical_failure: bool, can_proceed: bool, overall, warnings: [...],
        categories: [...], raw: <validator json> }

    QUALITY problems -> warnings (can_proceed=True, override allowed).
    TECHNICAL problems (unreadable/corrupted/no face) -> technical_failure=True,
    can_proceed=False (no override).
    """
    if not video_path or not os.path.isfile(video_path):
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL", "error": "File not found or unreadable.",
                "warnings": [], "categories": []}

    config.ensure_runtime_dirs()
    out_json = os.path.join(config.TEMP_DIR, f"analyze_{os.getpid()}_{threading.get_ident()}.json")
    try:
        os.unlink(out_json)
    except OSError:
        pass

    cmd = [_torch_python(), config.VALIDATOR, "--video", video_path, "--json", out_json]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                              cwd=config.ROOT)
    except subprocess.TimeoutExpired:
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL", "error": "Analysis timed out.",
                "warnings": [], "categories": []}
    except FileNotFoundError:
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL",
                "error": f"Python runtime not found: {_torch_python()}",
                "warnings": [], "categories": []}

    # The validator writes JSON to out_json (preferred). Exit code is 0/1/2/3.
    raw = None
    if os.path.exists(out_json):
        try:
            with open(out_json, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = None
    if raw is None:
        # Fallback: parse stdout if the validator printed a FAIL with no JSON.
        err = proc.stderr.strip() or proc.stdout.strip() or "Analysis failed."
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL", "error": err, "warnings": [], "categories": []}

    # Technical failure: validator couldn't open / no face / integrity FAIL.
    if raw.get("error") and raw.get("overall") == "FAIL" and "categories" not in raw:
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL", "error": raw["error"],
                "warnings": [], "categories": [], "raw": raw}

    integrity = raw.get("integrity", {})
    cats = raw.get("categories", {})
    if not cats:
        # No face detected -> technical failure (can't prepare a lip-sync avatar).
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL", "error": "No face detected in the source video.",
                "warnings": [], "categories": [], "raw": raw}

    # Integrity FAIL (corrupted/empty) is technical.
    if integrity.get("status") == "FAIL":
        return {"technical_failure": True, "can_proceed": False,
                "overall": "FAIL",
                "error": "Video integrity problem: unreadable or empty stream.",
                "warnings": [], "categories": [], "raw": raw}

    # All category WARN/FAIL are QUALITY warnings (override allowed).
    warnings = []
    categories = []
    for cat in ("FACE_SIZE", "FACE_SHARPNESS", "FRONTALNESS", "MOUTH_VISIBILITY",
                 "CHIN_VISIBILITY", "SOURCE_MOUTH_STATE", "MOTION", "LIGHTING"):
        c = cats.get(cat)
        if not c:
            continue
        status = c.get("status", "PASS")
        translated = _translate_category(cat, status, c.get("note", ""),
                                         c.get("value"))
        categories.append(translated)
        if status in ("WARN", "FAIL"):
            warnings.append({"category": cat, "status": status,
                             "message": translated["message"]})

    overall = raw.get("overall", "PASS")
    # can_proceed: quality warnings don't block (user can override).
    return {"technical_failure": False, "can_proceed": True, "overall": overall,
            "warnings": warnings, "categories": categories,
            "face_h_ratio": raw.get("face_h_ratio"),
            "source_video": os.path.abspath(video_path),
            "integrity": integrity, "raw": raw}


# --------------------------------------------------------------------------- #
# Avatar preparation                                                          #
# --------------------------------------------------------------------------- #
# Progress stages mapped from genavatar.py output line prefixes. The UI shows
# these as friendly stage labels; a collapsible technical log is also written.
_STAGE_MAP = [
    (r"frame", "Extracting video frames..."),
    (r"landmark|bbox|face", "Detecting face..."),
    (r"mask|parsing", "Creating masks..."),
    (r"latent|vae|encode", "Building lip-sync data..."),
    (r"save|coord|final", "Finalizing avatar..."),
]


def _match_stage(line: str) -> Optional[str]:
    low = line.lower()
    for pat, label in _STAGE_MAP:
        if any(k in low for k in pat.split("|")):
            return label
    return None


class PrepJob:
    """Tracks one avatar-preparation subprocess for progress polling."""
    def __init__(self, video_path: str, avatar_id: str):
        self.video_path = video_path
        self.avatar_id = avatar_id
        self.proc = None
        self.log_path = None
        self.stage = "Starting..."
        self.error = None
        self.done = False
        self.timed_out = False
        self.pid = None
        self._stdout = []
        self._lock = threading.Lock()

    def start(self):
        config.ensure_runtime_dirs()
        self.log_path = os.path.join(config.LOG_DIR, f"prep_{self.avatar_id}.log")
        # Run genavatar as a MODULE from the repo root so `avatars.*` /
        # `utils.*` resolve (the script itself does not add the repo root to
        # sys.path, unlike generate_video_from_script.py). `python -m
        # avatars.musetalk.genavatar` puts the repo root (cwd) on sys.path[0]
        # and runs the canonical __main__ block. PYTHONPATH is also set as a
        # belt-and-suspenders guarantee. No MuseTalk code is copied.
        cmd = [_torch_python(), "-m", "avatars.musetalk.genavatar",
               "--file", self.video_path,
               "--avatar_id", self.avatar_id,
               "--version", "v15",
               "--parsing_mode", "jaw",
               "--bbox_shift", "0"]
        env = os.environ.copy()
        env["PYTHONPATH"] = runtime.repo_root() + os.pathsep + env.get("PYTHONPATH", "")
        # Use a free GPU if the scheduler exposes one; default GPU 0 (single).
        gid = env.get("STUDIO_PREP_GPU_ID", "0")
        env["CUDA_VISIBLE_DEVICES"] = gid
        env["LIVETALKING_GPU_ID"] = "0"
        env["OFFLINE_USE_MULTI_GPU"] = "false"
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True,
                                         cwd=runtime.repo_root(), env=env,
                                         encoding="utf-8", errors="replace")
            self.pid = self.proc.pid
        except Exception as e:
            self.error = f"Failed to start preparation: {e}"
            self.done = True
            return
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        # Generous bounded timeout for avatar preparation (loads MuseTalk +
        # face parsing + VAE latents for every frame). Default 30 min; override
        # via STUDIO_PREP_TIMEOUT_SEC. A slow but progressing job is NOT killed
        # merely for being slow — the timeout is a hard backstop against hangs.
        timeout = float(os.environ.get("STUDIO_PREP_TIMEOUT_SEC", "1800"))
        deadline = _time_monotonic() + timeout
        try:
            with open(self.log_path, "w", encoding="utf-8") as logf:
                for line in self.proc.stdout:
                    logf.write(line)
                    logf.flush()
                    with self._lock:
                        self._stdout.append(line)
                    stage = _match_stage(line)
                    if stage:
                        self.stage = stage
                    if _time_monotonic() > deadline:
                        self.timed_out = True
                        _terminate_tree(self.proc)
                        break
        except Exception as e:
            with self._lock:
                self.error = f"Log pump error: {e}"
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _terminate_tree(self.proc)
        rc = self.proc.returncode
        if self.timed_out:
            self.error = "Preparation timed out (hung process terminated)."
        elif rc != 0:
            self.error = self.error or f"Preparation process exited with code {rc}."
        self.done = True


_PREP_JOBS: Dict[str, PrepJob] = {}


def prepare_avatar(video_path: str, avatar_name: str,
                    allow_warning_override: bool) -> Dict[str, Any]:
    """Kick off avatar preparation. Returns immediately with the new avatar_id
    and job handle info. Never overwrites an existing avatar."""
    if not video_path or not os.path.isfile(video_path):
        return {"ok": False, "error": "Source video not found."}
    aid = config.unique_avatar_id(avatar_name)
    if os.path.exists(os.path.join(config.AVATARS_ROOT, aid)):
        # Should never happen (unique_avatar_id guarantees), but guard anyway.
        return {"ok": False, "error": f"Avatar '{aid}' already exists. Choose another name."}

    # Record quality/override state for this avatar for future debugging.
    job = PrepJob(video_path, aid)
    _PREP_JOBS[aid] = job
    job.start()
    return {"ok": True, "avatar_id": aid, "override": bool(allow_warning_override),
            "log_path": job.log_path}


def get_prep_status(avatar_id: str) -> Dict[str, Any]:
    job = _PREP_JOBS.get(avatar_id)
    if not job:
        # Not an in-flight prep job. Reflect on-disk READY state.
        d = os.path.join(config.AVATARS_ROOT, avatar_id)
        if os.path.isdir(d):
            return {"done": True, "ready": _check_ready(d),
                    "stage": "done", "exists": True}
        return {"done": False, "ready": False, "stage": "unknown",
                "exists": False, "error": "No such preparation job."}
    return {"done": job.done, "ready": job.done and _check_ready(
                os.path.join(config.AVATARS_ROOT, avatar_id)),
            "stage": job.stage if not job.done else (
                "timed_out" if job.timed_out else ("done" if not job.error else "failed")),
            "error": job.error, "log_path": job.log_path,
            "timed_out": job.timed_out, "pid": job.pid}


def get_prep_log_tail(avatar_id: str, n: int = 30) -> str:
    job = _PREP_JOBS.get(avatar_id)
    if not job:
        return ""
    with job._lock:
        return "".join(job._stdout[-n:])