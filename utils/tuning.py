###############################################################################
#  Central LIVETALKING_* tuning validator + effective-config logger.
#
#  ~40 env knobs drive the realtime pipeline. A typo in a knob name (e.g.
#  LIVETALKING_AUDIO_JITER_FRAMES) silently does nothing and the operator has no
#  way to tell. This module:
#    - defines a schema of known knobs + their expected type/range,
#    - validates the ones that are set (warns on bad values, keeps the env value
#      so the existing per-call os.getenv still picks it up),
#    - warns on any LIVETALKING_* env var that is NOT in the schema (likely typo),
#    - logs the effective runtime config ONCE at startup so the actual tuned
#      state is recorded in wrapper.log (otherwise it is unknowable from logs).
#
#  Called once from app.main() after parse_args + configure_gpu_runtime. Pure
#  read of os.environ — no side effects, no imports of the inference stack.
###############################################################################

import os
from typing import Any

from utils.logger import logger
from utils.envconfig import load_env_file

# name -> (type, min, max)  ; min/max None = unchecked
_SCHEMA: dict[str, tuple[str, Any, Any]] = {
    # GPU / inference
    "LIVETALKING_GPU_ID": ("int", 0, 64),
    "LIVETALKING_MULTI_GPU": ("bool", None, None),
    "LIVETALKING_GPU_IDS": ("str", None, None),
    "LIVETALKING_CUDA_GRAPH": ("bool", None, None),
    "MUSETALK_MULTI_GPU_MODE": ("str", None, None),
    "LIVETALKING_BATCH_SIZE": ("int", 1, 128),
    "LIVETALKING_RES_QUEUE_SIZE": ("int", 1, 256),
    "LIVETALKING_COMPOSITE_MAX_DIM": ("int", 256, 99999),
    "LIVETALKING_FACE_ENHANCE": ("bool", None, None),
    "LIVETALKING_FACE_ENHANCE_WEIGHT": ("float", 0.0, 1.0),
    # Audio / sample rate
    "LIVETALKING_OUTPUT_SAMPLE_RATE": ("int", 16000, 96000),
    "LIVETALKING_AUDIO_JITTER_FRAMES": ("int", 0, 16),
    "LIVETALKING_AUDIO_GAIN": ("float", 0.05, 4.0),
    "LIVETALKING_AUDIO_ENERGY_GATE": ("bool", None, None),
    "LIVETALKING_AUDIO_SPEECH_ON_DB": ("float", -80.0, 0.0),
    "LIVETALKING_AUDIO_SPEECH_OFF_DB": ("float", -80.0, 0.0),
    "LIVETALKING_AUDIO_SPEECH_RELEASE_SEC": ("float", 0.0, 2.0),
    "LIVETALKING_AUDIO_FEAT_LEFT": ("int", 0, 32),
    "LIVETALKING_AUDIO_FEAT_RIGHT": ("int", 0, 32),
    "LIVETALKING_ASR_SPEECH_PRIME_FRAMES": ("int", 0, 64),
    "LIVETALKING_ASR_AUDIO_FRAME_TIMEOUT_SEC": ("float", 0.001, 5.0),
    "LIVETALKING_ASR_SPEECH_FRAME_TIMEOUT_SEC": ("float", 0.001, 5.0),
    "LIVETALKING_AUDIO_ONSET_TRACE": ("bool", None, None),
    # TTS pacing
    "LIVETALKING_TTS_REALTIME_PACING": ("bool", None, None),
    "LIVETALKING_TTS_MAX_BUFFER_SEC": ("float", 0.02, 30.0),
    "LIVETALKING_TTS_MAX_ASR_BUFFER_SEC": ("float", 0.02, 30.0),
    # Visual / mouth
    "LIVETALKING_VISUAL_TRANSITION": ("bool", None, None),
    "LIVETALKING_VISUAL_SPEECH_HANGOVER_SEC": ("float", 0.0, 5.0),
    "LIVETALKING_VISUAL_SILENCE_TO_SPEECH_SEC": ("float", 0.0, 5.0),
    "LIVETALKING_VISUAL_SPEECH_TO_SILENCE_SEC": ("float", 0.0, 5.0),
    "LIVETALKING_MOUTH_TEMPORAL_ALPHA": ("float", 0.0, 1.0),
    "LIVETALKING_MOUTH_ONSET_ATTACK_FRAMES": ("int", 1, 32),
    "LIVETALKING_MOUTH_ONSET_FIRST_MIX": ("float", 0.0, 1.0),
    "LIVETALKING_BODY_LOOP_MODE": ("str", None, None),
    "LIVETALKING_BODY_INDEX_STEP": ("float", 0.05, 10.0),
    # GPU heartbeat / warmup
    "LIVETALKING_GPU_HEARTBEAT": ("bool", None, None),
    "LIVETALKING_GPU_HEARTBEAT_INTERVAL_SEC": ("float", 0.01, 10.0),
    "LIVETALKING_GPU_HEARTBEAT_ITERS": ("int", 1, 10000),
    "LIVETALKING_GPU_HEARTBEAT_MATN": ("int", 16, 16384),
    "LIVETALKING_GPU_HEARTBEAT_IDLE_GRACE_SEC": ("float", 0.0, 60.0),
    "LIVETALKING_WHISPER_WARMUP": ("bool", None, None),
    "LIVETALKING_WHISPER_WARMUP_INTERVAL_SEC": ("float", 0.1, 60.0),
    "LIVETALKING_UNET_WARMUP": ("bool", None, None),
    "LIVETALKING_UNET_WARMUP_INTERVAL_SEC": ("float", 0.1, 60.0),
    "LIVETALKING_WHISPER_DEVICE": ("str", None, None),
    # WebRTC / encode
    "LIVETALKING_H264_PRESET": ("str", None, None),
    "LIVETALKING_WEBRTC_VIDEO_MAX_BITRATE": ("int", 100000, 50000000),
    # Sessions / IPC
    "LIVETALKING_MAX_SESSIONS": ("int", 0, 1024),
    "LIVETALKING_SESSION_CONNECT_TIMEOUT": ("float", 1.0, 600.0),
    "LIVETALKING_STALE_ICE_SEC": ("float", 1.0, 3600.0),
    "LIVETALKING_REAPER_INTERVAL_SEC": ("float", 1.0, 600.0),
    "LIVETALKING_RES_PRIME_FRAMES": ("int", 0, 256),
    # Recording
    "LIVETALKING_RECORD_AUTO_TRIM": ("bool", None, None),
    "LIVETALKING_RECORD_X264_PRESET": ("str", None, None),
    "LIVETALKING_RECORD_CRF": ("str", None, None),
    "LIVETALKING_OFFLINE_X264_PRESET": ("str", None, None),
    "LIVETALKING_OFFLINE_CRF": ("str", None, None),
    # Failure alerting
    "LIVETALKING_INFER_FAIL_ALERT_THRESHOLD": ("int", 1, 100000),
    # Auth / CORS
    "LIVETALKING_API_TOKEN": ("str", None, None),
    "LIVETALKING_CORS_ORIGINS": ("str", None, None),
    # Offline multi-GPU
    "OFFLINE_USE_MULTI_GPU": ("bool", None, None),
}


def _coerce(typ: str, raw: str):
    try:
        if typ == "int":
            return int(raw)
        if typ == "float":
            return float(raw)
        if typ == "bool":
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return raw
    except ValueError:
        return None


def log_effective_config(opt=None) -> None:
    """Validate + log the effective LIVETALKING_* config once at startup."""
    load_env_file()

    # 1. Validate known knobs that are set.
    for name, (typ, lo, hi) in _SCHEMA.items():
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            continue
        if typ in ("int", "float"):
            val = _coerce(typ, raw)
            if val is None:
                logger.warning("tuning: %s=%r is not a valid %s — ignored/default used", name, raw, typ)
                continue
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                logger.warning("tuning: %s=%r out of range [%s,%s] — kept but likely wrong", name, raw, lo, hi)
        elif typ == "bool":
            if raw.strip().lower() not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
                logger.warning("tuning: %s=%r is not a clean bool — kept", name, raw)

    # 2. Typo detection: any LIVETALKING_* env var not in the schema.
    unknown = sorted(
        k for k in os.environ
        if k.startswith("LIVETALKING_") and k not in _SCHEMA
    )
    if unknown:
        logger.warning(
            "tuning: unknown LIVETALKING_* env var(s) — likely a typo, will be "
            "ignored by the code: %s", ", ".join(unknown),
        )

    # 3. Log the effective key config once (compact one-liner).
    def g(name, default=""):
        return os.getenv(name, default).strip()

    summary = (
        f"tuning effective: model={getattr(opt, 'model', '?')} "
        f"gpu_id={getattr(opt, 'gpu_id', '?')} "
        f"multi_gpu={getattr(opt, 'runtime_multi_gpu', '?')} "
        f"batch_size={getattr(opt, 'batch_size', '?')} "
        f"cuda_graph={g('LIVETALKING_CUDA_GRAPH','true')} "
        f"sample_rate={g('LIVETALKING_OUTPUT_SAMPLE_RATE','48000')} "
        f"audio_jitter={g('LIVETALKING_AUDIO_JITTER_FRAMES','2')} "
        f"res_queue={g('LIVETALKING_RES_QUEUE_SIZE','32')} "
        f"composite_max_dim={g('LIVETALKING_COMPOSITE_MAX_DIM','1920')} "
        f"face_enhance={g('LIVETALKING_FACE_ENHANCE','false')} "
        f"h264_preset={g('LIVETALKING_H264_PRESET','ultrafast')} "
        f"heartbeat={g('LIVETALKING_GPU_HEARTBEAT','true')} "
        f"token_set={'yes' if g('LIVETALKING_API_TOKEN') else 'no(loopback-only)'} "
        f"tts={getattr(opt, 'tts', '?')}"
    )
    logger.info(summary)