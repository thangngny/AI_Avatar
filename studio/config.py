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

# --- Avatar data ---------------------------------------------------------
AVATARS_ROOT = os.path.join(ROOT, "data", "avatars")
RAW_SOURCES_ROOT = os.path.join(ROOT, "data", "input", "avatar_sources")

# --- Runtime / output (writable, NOT Git-tracked) ------------------------
STUDIO_DIR = HERE
RUNTIME_DIR = os.path.join(ROOT, "data", "studio_runtime")
TEMP_DIR = os.path.join(RUNTIME_DIR, "temp")          # previews, temp audio
RENDERS_DIR = r"D:\CongThang_AI_Avatar\renders"        # production render output
DB_PATH = os.path.join(RUNTIME_DIR, "studio.db")
LOG_DIR = os.path.join(RUNTIME_DIR, "logs")            # per-job technical logs

# --- ElevenLabs ----------------------------------------------------------
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_VOICE_URL = "https://api.elevenlabs.io/v1/voices/{voice_id}"
# pcm_16000 mono: matches the validated offline TTS path (experiments/
# elevenlabs_tts_render.py). Whisper/musetalk run at 16kHz internally.
ELEVENLABS_OUTPUT_FORMAT = "pcm_16000"
ELEVENLABS_TIMEOUT_SEC = 120
# Max chars per TTS request (ElevenLabs hard limit 5000; 4800 safe margin).
TTS_MAX_TEXT_CHARS = 4800
# Vietnamese ~180 wpm (measured in the validated batch).
WORDS_PER_SEC = 3.0

# --- Render job scheduling ----------------------------------------------
# One render process per GPU (job-level parallelism). Each subprocess gets
# CUDA_VISIBLE_DEVICES=<gpu> + OFFLINE_USE_MULTI_GPU=false so it binds to a
# single GPU and uses the CUDA-graph path.
RENDER_GPU_TIMEOUT_SEC = 1800  # 30 min hard cap per job (10s test is far under)


def ensure_runtime_dirs() -> None:
    for d in (RUNTIME_DIR, TEMP_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


def ensure_renders_dir() -> None:
    os.makedirs(RENDERS_DIR, exist_ok=True)


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