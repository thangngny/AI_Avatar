"""Central path/config constants for the AI Avatar Studio controller.

All paths resolve from the project root (the AI_avatar repo dir). The
controller writes ONLY to safe runtime locations — never into Git-tracked
production source, never into config/render_truth.json.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # AI_avatar repo root

# --- Production components (READ-ONLY from the controller) ----------------
RENDERER = os.path.join(ROOT, "generate_video_from_script.py")
VALIDATOR = os.path.join(ROOT, "tools", "avatar_source_quality", "validator.py")
GENAVATAR = os.path.join(ROOT, "avatars", "musetalk", "genavatar.py")
TRUTH_PATH = os.path.join(ROOT, "config", "render_truth.json")
SYSTEM_STATUS = os.path.join(ROOT, "system_status.py")

# --- Runtime hardening (V1.6.0) -------------------------------------------
# The ONE torch-capable interpreter that is allowed to run the Studio. The
# launcher and run_studio.py enforce this; a process running under any other
# interpreter is reported RUNTIME_MISMATCH and must not claim READY. May be
# overridden via STUDIO_CANONICAL_INTERPRETER for a relocated runtime.
def _resolve_canonical_interpreter() -> str:
    env_override = os.environ.get("STUDIO_CANONICAL_INTERPRETER", "").strip()
    if env_override:
        return env_override
    candidates = [
        r"D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
        r"C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
        os.path.normpath(os.path.join(ROOT, "..", "runtime", "venv", "Scripts", "python.exe")),
        r"C:\CongThang_AI_Avatar_TikTokLive\runtime\venv\Scripts\python.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[0]


CANONICAL_INTERPRETER = _resolve_canonical_interpreter()
# Single source of truth for the browser<->backend API contract version.
API_CONTRACT_PATH = os.path.join(ROOT, "config", "api_contract.json")

# --- Avatar data ---------------------------------------------------------
AVATARS_ROOT = os.path.join(ROOT, "data", "avatars")
RAW_SOURCES_ROOT = os.path.join(ROOT, "data", "input", "avatar_sources")

# --- Runtime / output (writable, NOT Git-tracked) ------------------------
STUDIO_DIR = HERE
RUNTIME_DIR = os.path.join(ROOT, "data", "studio_runtime")
TEMP_DIR = os.path.join(RUNTIME_DIR, "temp")          # temp scratch audio
PREVIEWS_DIR = os.path.join(RUNTIME_DIR, "audio_previews")  # persistent script voice previews
VOICE_SAMPLES_DIR = os.path.join(RUNTIME_DIR, "voice_samples")  # pre-generated static voice samples


def _resolve_renders_dir() -> str:
    env_dir = os.environ.get("STUDIO_RENDERS_DIR", "").strip()
    if env_dir:
        return env_dir
    candidates = [
        r"C:\CongThang_AI_Avatar\renders",
        r"D:\CongThang_AI_Avatar\renders",
        os.path.normpath(os.path.join(ROOT, "..", "renders")),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]


# Render output directory. Overridable via STUDIO_RENDERS_DIR (V1.4.1 R04) so
# the system is not hard-coupled to the D: drive on another machine.
RENDERS_DIR = _resolve_renders_dir()
DB_PATH = os.path.join(RUNTIME_DIR, "studio.db")
# Runtime instance manifest (process identity + fingerprints). Lives under the
# gitignored studio_runtime namespace so machine-specific state is never tracked.
INSTANCE_MANIFEST_PATH = os.path.join(RUNTIME_DIR, "studio_instance.json")
LOG_DIR = os.path.join(RUNTIME_DIR, "logs")            # per-job technical logs

# --- ElevenLabs ----------------------------------------------------------
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_VOICE_URL = "https://api.elevenlabs.io/v1/voices/{voice_id}"
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
ELEVENLABS_VOICE_SETTINGS_URL = "https://api.elevenlabs.io/v1/voices/{voice_id}/settings"
ELEVENLABS_MODELS_URL = "https://api.elevenlabs.io/v1/models"
ELEVENLABS_HISTORY_URL = "https://api.elevenlabs.io/v1/history"
ELEVENLABS_HISTORY_ITEM_URL = "https://api.elevenlabs.io/v1/history/{history_item_id}"
# pcm_16000 mono: matches the validated offline TTS path (experiments/
# elevenlabs_tts_render.py). Whisper/musetalk run at 16kHz internally.
ELEVENLABS_OUTPUT_FORMAT = "pcm_16000"
ELEVENLABS_TIMEOUT_SEC = 120
# Max chars per TTS request (ElevenLabs hard limit 5000; 4800 safe margin).
TTS_MAX_TEXT_CHARS = 4800
# Vietnamese ~180 wpm (measured in the validated batch).
WORDS_PER_SEC = 3.0
# Server-side cache TTLs for ElevenLabs metadata (seconds). These are metadata
# GETs only (no TTS quota). [LÀM MỚI]/refresh bypasses the cache.
ELEVENLABS_SETTINGS_CACHE_TTL = 300      # voice settings: 5 min
ELEVENLABS_MODELS_CACHE_TTL = 1800      # models: 30 min
ELEVENLABS_HISTORY_CACHE_TTL = 120      # history: 2 min (short — settings change)

# --- Render job scheduling ----------------------------------------------
# One render process per GPU (job-level parallelism). Each subprocess gets
# CUDA_VISIBLE_DEVICES=<gpu> + OFFLINE_USE_MULTI_GPU=false so it binds to a
# single GPU and uses the CUDA-graph path.
RENDER_GPU_TIMEOUT_SEC = 1800  # 30 min hard cap per job (10s test is far under)


def ensure_runtime_dirs() -> None:
    for d in (RUNTIME_DIR, TEMP_DIR, LOG_DIR, PREVIEWS_DIR, VOICE_SAMPLES_DIR):
        os.makedirs(d, exist_ok=True)


def ensure_renders_dir() -> None:
    os.makedirs(RENDERS_DIR, exist_ok=True)


def renders_dir_free_bytes() -> int:
    """Free bytes on the drive holding RENDERS_DIR (Windows). 0 if unknown."""
    try:
        import ctypes
        free = ctypes.c_ulonglong(0)
        d = os.path.dirname(RENDERS_DIR) or RENDERS_DIR
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(d, None, None, ctypes.byref(free))
        return free.value
    except Exception:
        return 0


def validate_renders_dir() -> dict:
    """Existence + writable + free-space check for the resolved render dir.
    Returns {ok, path, exists, writable, free_gb, errors[]}."""
    out = {"ok": False, "path": RENDERS_DIR, "exists": False, "writable": False,
           "free_gb": None, "errors": []}
    try:
        os.makedirs(RENDERS_DIR, exist_ok=True)
    except Exception as e:
        out["errors"].append(f"cannot create renders dir: {e}")
        return out
    out["exists"] = True
    try:
        t = os.path.join(RENDERS_DIR, ".studio_write_probe")
        with open(t, "w") as f:
            f.write("ok")
        os.remove(t)
        out["writable"] = True
    except Exception as e:
        out["errors"].append(f"renders dir not writable: {e}")
        return out
    free = renders_dir_free_bytes()
    out["free_gb"] = round(free / 1e9, 1) if free else 0.0
    if free and free < 20 * (1 << 30):
        out["errors"].append(f"renders drive low: {out['free_gb']} GB free (<20 GB)")
    out["ok"] = out["writable"] and (not free or free >= 20 * (1 << 30))
    return out


def safe_avatar_id(name: str) -> str:
    """Make a safe filesystem avatar_id from a user name. Lowercases, keeps
    [a-z0-9_], collapses runs of underscores. Never path-traversal-able."""
    import re
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "avatar"
    return s[:48]


def unique_avatar_id(name: str) -> str:
    """Return a safe avatar_id that does not already exist under AVATARS_ROOT.
    Appends _2, _3, ... if needed. Never overwrites an existing avatar."""
    base = safe_avatar_id(name)
    aid = base
    n = 2
    while os.path.exists(os.path.join(AVATARS_ROOT, aid)):
        aid = f"{base}_{n}"
        n += 1
    return aid