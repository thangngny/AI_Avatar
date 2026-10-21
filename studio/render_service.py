"""Render controller: the service layer between the UI and the EXISTING
production renderer.

Flow:
  script -> ElevenLabs TTS (EXACT voice_id, fail-closed, no fallback)
         -> master 16kHz mono WAV
         -> generate_video_from_script.py --avatar_id <id> --audio <wav> --output <mp4>
         -> post-render verify

The controller NEVER duplicates the lip-sync truth. It passes only --avatar_id
/ --audio / --output to the renderer; the renderer itself forces the locked
config from config/render_truth.json. The controller reads render_truth.json
READ-ONLY for display + a hash recorded on each job (regression evidence).

GPU scheduling is job-level: one renderer subprocess per GPU, via
CUDA_VISIBLE_DEVICES + OFFLINE_USE_MULTI_GPU=false. Normal users never pick a
GPU; the worker assigns queued jobs automatically.
"""
import os
import re
import json
import time
import hashlib
import shutil
import subprocess
import threading
import uuid
from typing import Dict, Any, List, Optional, Tuple

from . import config, db, gpu_service
from . import elevenlabs_client as el
from . import edge_tts_client as edge
from . import avatar_service
from . import verify as verify_mod
from . import runtime
from .avatar_service import _torch_python


# --------------------------------------------------------------------------- #
# TTS providers (spec Part B/D) — EXPLICIT, never fallback                    #
# --------------------------------------------------------------------------- #
ELEVENLABS = "ELEVENLABS"
EDGE_TTS_TEST = "EDGE_TTS_TEST"

# Test type taxonomy (spec Part D / B11).
TEST_TYPE_STANDARD_MOUTH = "STANDARD_MOUTH_TEST"
TEST_TYPE_SCRIPT_PREVIEW = "SCRIPT_PREVIEW"
TEST_TYPE_PRODUCTION = "PRODUCTION"

# Standardized Vietnamese mouth-motion diagnostic script (spec B10). A
# repeatable visual test stimulus: bilabials (m/b/p), wide/open + rounded
# vowels, natural sentence flow. The renderer is NOT optimized for this — it
# only makes Avatar A vs Avatar B comparable under identical text/voice/profile.
STANDARD_MOUTH_TEST_SCRIPT = (
    "Ba mẹ mỉm cười và Minh mua một hộp bánh mì. "
    "Phương nói hôm nay trời đẹp, chúng ta cùng quay video thật tự nhiên."
)


# --------------------------------------------------------------------------- #
# Production truth (read-only)                                                #
# --------------------------------------------------------------------------- #
_TRUTH_CACHE = None
_TRUTH_HASH = None


def _sha1_file(path: str) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def load_truth() -> Dict[str, Any]:
    """Read render_truth.json (read-only). Returns {ok, truth, hash, error}."""
    global _TRUTH_CACHE, _TRUTH_HASH
    if _TRUTH_CACHE is None:
        if not os.path.exists(config.TRUTH_PATH):
            return {"ok": False, "error": "config/render_truth.json not found."}
        try:
            with open(config.TRUTH_PATH, "r", encoding="utf-8") as f:
                _TRUTH_CACHE = json.load(f)
            _TRUTH_HASH = _sha1_file(config.TRUTH_PATH)
        except Exception as e:
            return {"ok": False, "error": f"render_truth.json unreadable: {e}"}
    return {"ok": True, "truth": _TRUTH_CACHE, "hash": _TRUTH_HASH}


def truth_hash() -> str:
    r = load_truth()
    return r.get("hash", "") if r["ok"] else ""


# --------------------------------------------------------------------------- #
# Master audio (reuse for same script+voice+provider)                        #
# --------------------------------------------------------------------------- #
def _master_key(script_text: str, voice_id: str, tts_provider: str) -> str:
    h = hashlib.sha1((script_text + "||" + voice_id + "||" + tts_provider).encode("utf-8")).hexdigest()
    return h[:24]


def _master_path(script_text: str, voice_id: str, tts_provider: str) -> str:
    os.makedirs(os.path.join(config.TEMP_DIR, "master"), exist_ok=True)
    return os.path.join(config.TEMP_DIR, "master", f"{_master_key(script_text, voice_id, tts_provider)}_{tts_provider}_{voice_id}.wav")


def generate_master_audio(script_text: str, voice_id: str,
                           target_sec: Optional[float] = None,
                           tts_provider: str = ELEVENLABS,
                           tts_config: Optional[Dict[str, Any]] = None,
                           master_audio_override: Optional[str] = None) -> Dict[str, Any]:
    """Generate the audio for a script part + voice + provider.

    V1.5.0 two-audio-path (ElevenLabs with a resolved tts_config):
      - master_path : lossless WAV at the native sample rate of the resolved
        requested_output_format (used for the FINAL MP4 audio). Never downsampled
        to 16 kHz; never kept as MP3.
      - cond_path   : 16 kHz mono WAV derived from the master (MuseTalk/Whisper
        conditioning only).
    Without a tts_config (legacy ElevenLabs / Edge TTS): master_path == cond_path
    (the existing 16 kHz mono path) — backward compatible.

    V1.6.0 Script Voice Preview reuse:
      - If master_audio_override (or matching cached preview) is valid, reuses the
        lossless MASTER audio directly and resamples to 16 kHz conditioning without
        calling ElevenLabs again.

    Providers are EXPLICIT and never fall back to each other (spec B8):
      ELEVENLABS     -> elevenlabs_client (exact voice_id, fail-closed)
      EDGE_TTS_TEST  -> edge_tts_client.synth_to_wav (no API key, no quota)

    Returns {ok, master_path, cond_path, duration_sec, reused}."""
    text = (script_text or "").strip()
    if not text:
        return {"ok": False, "error": "Empty script — nothing to synthesize."}
    if not voice_id:
        return {"ok": False, "error": "No voice provided."}

    # Test render: trim by words (no mid-word cut) — applies to all paths.
    if target_sec:
        words = text.split()
        target_words = max(1, int(target_sec * config.WORDS_PER_SEC))
        text = " ".join(words[:target_words])
        if not text:
            return {"ok": False, "error": "Script too short for a test render."}

    # 1. Direct Master Audio Override (e.g. reused from Script Voice Preview)
    if master_audio_override and os.path.isfile(master_audio_override) and os.path.getsize(master_audio_override) > 1000:
        try:
            from . import preview_service
            import soundfile as sf
            os.makedirs(os.path.join(config.TEMP_DIR, "master"), exist_ok=True)
            cond_path = os.path.join(config.TEMP_DIR, "master", f"cond_{abs(hash(master_audio_override))%10000000}.wav")
            preview_service.derive_cond_from_master(master_audio_override, cond_path)
            dur = float(sf.info(cond_path).duration)
            db.log_activity("RENDER_USED_SCRIPT_PREVIEW", "render", voice_id,
                            {"master_path": master_audio_override, "duration_sec": dur})
            return {"ok": True, "master_path": master_audio_override, "cond_path": cond_path,
                    "duration_sec": dur, "reused": True, "source": "script_preview"}
        except Exception:
            pass

    # 2. Check if matching valid Script Preview exists in database
    if tts_provider == ELEVENLABS and tts_config and not target_sec:
        try:
            from . import preview_service
            import soundfile as sf
            lang = tts_config.get("target_language") or "vi"
            fp = preview_service.compute_preview_fingerprint(text, voice_id, lang, tts_config)
            prev_row = db.get_audio_preview_by_fingerprint(fp)
            if prev_row and prev_row.get("status") == "ready":
                p_master = prev_row.get("master_audio_path")
                if p_master and os.path.isfile(p_master) and os.path.getsize(p_master) > 1000:
                    cond_path = os.path.join(config.TEMP_DIR, "master", f"cond_prev_{prev_row['id']}.wav")
                    preview_service.derive_cond_from_master(p_master, cond_path)
                    dur = float(sf.info(cond_path).duration)
                    db.touch_audio_preview(prev_row["id"])
                    db.log_activity("RENDER_USED_SCRIPT_PREVIEW", "render", prev_row["id"],
                                    {"master_path": p_master, "duration_sec": dur})
                    return {"ok": True, "master_path": p_master, "cond_path": cond_path,
                            "duration_sec": dur, "reused": True, "source": "script_preview", "preview_id": prev_row["id"]}
        except Exception:
            pass

    if tts_provider == EDGE_TTS_TEST:
        if not edge.is_available():
            return {"ok": False, "error": "Giọng test miễn phí (Edge TTS) hiện không khả dụng."}
        out = _master_path(text, voice_id, tts_provider)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            try:
                import soundfile as sf
                return {"ok": True, "master_path": out, "cond_path": out,
                        "duration_sec": float(sf.info(out).duration), "reused": True}
            except Exception:
                pass
        try:
            path, dur = edge.synth_to_wav(voice_id, text, out)
        except edge.EdgeTTSUnavailable as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Edge TTS failed: {e}"}
        return {"ok": True, "master_path": path, "cond_path": path,
                "duration_sec": dur, "reused": False}

    # ELEVENLABS
    if not el.is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}

    if tts_config:
        # Two-audio-path: keyed by the script text key + resolved config hash
        # (different text/model/settings/output_format -> fresh master). master != cond
        # when the resolved output_format is higher-bandwidth than 16 kHz.
        ch = el.tts_config_hash(tts_config)
        mk = _master_key(text, voice_id, ELEVENLABS)
        os.makedirs(os.path.join(config.TEMP_DIR, "master"), exist_ok=True)
        master = os.path.join(config.TEMP_DIR, "master", f"{mk}_{ch}_master.wav")
        cond = os.path.join(config.TEMP_DIR, "master", f"{mk}_{ch}_cond.wav")
        if os.path.exists(cond) and os.path.getsize(cond) > 1000:
            try:
                import soundfile as sf
                return {"ok": True, "master_path": master, "cond_path": cond,
                        "duration_sec": float(sf.info(cond).duration), "reused": True}
            except Exception:
                pass
        try:
            m, c, dur = el.synth_master_cond(voice_id, text, tts_config, master, cond)
        except el.VoiceError as e:
            return {"ok": False, "error": str(e), "fail_closed": True}
        except el.TTSUnavailable as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"TTS failed: {e}"}
        return {"ok": True, "master_path": m, "cond_path": c,
                "duration_sec": dur, "reused": False}

    # Legacy ELEVENLABS (no resolved config): master == cond == 16 kHz mono.
    out = _master_path(text, voice_id, tts_provider)
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        try:
            import soundfile as sf
            return {"ok": True, "master_path": out, "cond_path": out,
                    "duration_sec": float(sf.info(out).duration), "reused": True}
        except Exception:
            pass
    try:
        path, dur = el.synth_to_wav(voice_id, text, out)
    except el.VoiceError as e:
        return {"ok": False, "error": str(e), "fail_closed": True}
    except el.TTSUnavailable as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"TTS failed: {e}"}
    return {"ok": True, "master_path": path, "cond_path": path,
            "duration_sec": dur, "reused": False}


# --------------------------------------------------------------------------- #
# Job creation                                                                #
# --------------------------------------------------------------------------- #
def _new_job_id() -> str:
    return f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def _uuid_from_job_id(job_id: str) -> str:
    """Extract the unique 8-char uuid suffix from a job_id
    (`job_<ts>_<uuid8>`). Falls back to a fresh uuid if the shape is unexpected."""
    try:
        return job_id.rsplit("_", 1)[-1]
    except Exception:
        return uuid.uuid4().hex[:8]


def _output_path(kind: str, avatar_id: str, label: str,
                 job_id: Optional[str] = None) -> str:
    """Production render output under D:\\CongThang_AI_Avatar\\renders\\studio\\.

    Globally unique per job: the filename embeds the job's uuid suffix, so two
    jobs created in the same wall-clock second (e.g. concurrent multi-GPU jobs)
    can NEVER resolve to the same path. Uniqueness does NOT depend only on the
    wall clock. An existence guard additionally avoids overwriting any existing
    real artifact (retry safety).
    """
    config.ensure_renders_dir()
    base_dir = os.path.join(config.RENDERS_DIR, "studio")
    os.makedirs(base_dir, exist_ok=True)
    safe_avatar = re.sub(r"[^A-Za-z0-9_]+", "_", avatar_id).strip("_") or "avatar"
    safe_label = re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_") or "render"
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = _uuid_from_job_id(job_id) if job_id else uuid.uuid4().hex[:8]
    name = f"{ts}_{kind}_{safe_avatar}_{safe_label}_{suffix}.mp4"
    path = os.path.join(base_dir, name)
    # Existence guard: never silently overwrite an existing non-trivial file.
    # (Normal jobs never collide because of the uuid; this only protects against
    # an explicit retry whose target already exists.)
    n = 2
    while os.path.exists(path) and os.path.getsize(path) > 1000:
        path = os.path.join(base_dir,
                            f"{ts}_{kind}_{safe_avatar}_{safe_label}_{suffix}_{n}.mp4")
        n += 1
    return path


def _provider_for(tts_provider: Optional[str]) -> str:
    """Normalize an incoming tts_provider to a known value (default ELEVENLABS).
    Unknown values default to ELEVENLABS so a malformed request can never
    accidentally route to the free path."""
    return EDGE_TTS_TEST if tts_provider == EDGE_TTS_TEST else ELEVENLABS


def _resolve_tts_config_for_submission(voice_id: str,
                                       tts_config: Optional[Dict[str, Any]],
                                       target_language: Optional[str]
                                       ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """V1.6.0 TTS consistency guard (defense-in-depth).

    Guarantees an ElevenLabs render job ALWAYS carries a resolved, language-aware
    tts_config snapshot — the SAME config the Preview/Script-Preview path resolves
    (eleven_v3 for Thanh/vi via the HUMAN_BENCHMARK_APPROVED profile). Without this,
    a job submitted with tts_config=None silently falls into the legacy
    ``eleven_turbo_v2_5`` branch of generate_master_audio (hardcoded model, 16 kHz,
    no language_code) — a different model than the voice the user auditioned in
    "Listen to a sample". That silent model fallback is the preview-vs-render
    voice divergence root cause.

    Behavior:
      * Caller supplied a resolved tts_config -> trust it (immutable snapshot).
      * Caller supplied None -> resolve server-side via el.resolve_config(
        voice_id, target_language), exactly like preview_service does.
      * Resolution fails (incompatible / unsupported / API down) -> return an
        error so the caller FAILS CLOSED instead of queuing a wrong-model job.
        Never silently substitutes the legacy Studio default.

    Returns (tts_config_or_None, error_response_or_None). Edge TTS never calls
    this (it is a separate, explicit provider)."""
    if tts_config:
        return tts_config, None
    tl = (target_language or "vi").strip().lower() or "vi"
    try:
        res = el.resolve_config(voice_id, mode="auto_current", target_language=tl)
    except Exception as e:
        return None, {"ok": False, "fail_closed": True,
                      "error": f"Không thể xác định cấu hình giọng ElevenLabs cho render: {e}"}
    if not res.get("ok"):
        return None, {"ok": False, "fail_closed": True,
                      "error": res.get("error") or "Không thể xác nhận cấu hình giọng ElevenLabs để render.",
                      "incompatible": res.get("incompatible"),
                      "unsupported_language": res.get("unsupported_language")}
    return res["config"], None


def create_test_job(avatar_id: str, voice_id: str, script_text: str,
                    voice_meta: Optional[Dict] = None,
                    tts_provider: str = ELEVENLABS,
                    test_mode: bool = False,
                    test_type: Optional[str] = None,
                    tts_config: Optional[Dict] = None,
                    sync_mode: Optional[str] = None,
                    target_language: Optional[str] = None) -> Dict[str, Any]:
    """Create a 10-second test render job (SAME production quality as full).

    tts_provider selects the voice source (ELEVENLABS / EDGE_TTS_TEST). Both
    feed the same locked production renderer; only the audio source differs.
    V1.5.0: a resolved ElevenLabs tts_config is snapshotted into the job.
    V1.6.0: an ElevenLabs job with no tts_config is resolved server-side (same
    resolver as Preview) and fails closed instead of silently using the legacy
    eleven_turbo_v2_5 default — prevents preview-vs-render voice divergence."""
    provider = _provider_for(tts_provider)
    av_row = db.get_avatar(avatar_id)
    if av_row and av_row.get("is_deleted") == 1:
        return {"ok": False, "error": f"Avatar '{avatar_id}' đã bị chuyển vào Thùng rác. Hãy khôi phục trước khi render."}
    av = avatar_service.list_avatars()
    match = next((a for a in av if a["avatar_id"] == avatar_id), None)
    if not match or not match["ready"]:
        return {"ok": False, "error": f"Avatar '{avatar_id}' is not READY."}
    if not voice_id:
        return {"ok": False, "error": "No voice provided."}
    if not (script_text or "").strip():
        return {"ok": False, "error": "Script is empty."}

    # V1.6.0 TTS consistency: never queue an ElevenLabs job without a resolved
    # language-aware config. Re-resolve server-side if the caller omitted it.
    if provider == ELEVENLABS:
        tts_config, err = _resolve_tts_config_for_submission(voice_id, tts_config, target_language)
        if err:
            return err

    job_id = _new_job_id()
    out = _output_path("test10s", avatar_id, "test10s", job_id)
    tts_config_json = json.dumps(tts_config, ensure_ascii=False) if tts_config else None
    tts_config_hash = el.tts_config_hash(tts_config) if tts_config else None
    hist_id = (tts_config or {}).get("history_item_id") if tts_config else None

    audio_src = "generated"
    p_id = None
    p_fp = None
    m_path = None
    if provider == ELEVENLABS and tts_config and not test_mode:
        try:
            from . import preview_service
            lang = tts_config.get("target_language") or "vi"
            p_fp = preview_service.compute_preview_fingerprint(script_text, voice_id, lang, tts_config)
            prev_row = db.get_audio_preview_by_fingerprint(p_fp)
            if prev_row and prev_row.get("status") == "ready":
                p_id = prev_row["id"]
                m_path = preview_service.snapshot_preview_for_job(p_id, job_id)
                if m_path:
                    audio_src = "script_preview"
        except Exception:
            pass

    db.create_job({
        "job_id": job_id, "kind": "test10s", "avatar_id": avatar_id,
        "voice_id": voice_id, "voice_meta": json.dumps(voice_meta, ensure_ascii=False) if voice_meta else None,
        "script_text": script_text[:8000], "script_name": "test10s",
        "script_segment": json.dumps({"mode": "test10s", "target_sec": 10}, ensure_ascii=False),
        "output_path": out, "status": "queued", "stage": "Queued",
        "truth_hash": truth_hash(),
        "tts_provider": provider, "test_mode": 1 if test_mode else 0,
        "test_type": test_type or (TEST_TYPE_SCRIPT_PREVIEW if test_mode else None),
        "edge_voice": voice_id if provider == EDGE_TTS_TEST else None,
        "tts_config": tts_config_json, "tts_config_hash": tts_config_hash,
        "sync_mode": sync_mode, "history_item_id": hist_id,
        "audio_source": audio_src,
        "preview_id": p_id,
        "preview_fingerprint": p_fp,
        "master_audio_path": m_path,
    })
    _wake_worker()
    return {"ok": True, "job_id": job_id}


def create_mouth_test_job(avatar_id: str, edge_voice: str,
                          script_text: Optional[str] = None) -> Dict[str, Any]:
    """Create a STANDARD MOUTH TEST render job using the FREE Edge TTS voice
    (spec B9/B10/B11). 8–12 seconds, LOCKED production lipsync profile, no
    ElevenLabs quota consumed. Uses the standardized Vietnamese diagnostic
    script by default so Avatar A vs Avatar B is comparable under identical
    text/voice/profile. Never falls back to ElevenLabs."""
    provider = EDGE_TTS_TEST
    av_row = db.get_avatar(avatar_id)
    if av_row and av_row.get("is_deleted") == 1:
        return {"ok": False, "error": f"Avatar '{avatar_id}' đã bị chuyển vào Thùng rác. Hãy khôi phục trước khi render."}
    av = avatar_service.list_avatars()
    match = next((a for a in av if a["avatar_id"] == avatar_id), None)
    if not match or not match["ready"]:
        return {"ok": False, "error": f"Avatar '{avatar_id}' is not READY."}
    voice = (edge_voice or edge.DEFAULT_VOICE).strip() or edge.DEFAULT_VOICE
    text = (script_text or "").strip() or STANDARD_MOUTH_TEST_SCRIPT

    job_id = _new_job_id()
    out = _output_path("mouhtest", avatar_id, "mouthtest", job_id)
    db.create_job({
        "job_id": job_id, "kind": "mouhtest", "avatar_id": avatar_id,
        "voice_id": voice, "voice_meta": json.dumps(
            {"provider": "edge_tts", "voice_label": edge.voice_label(voice)},
            ensure_ascii=False),
        "script_text": text[:8000], "script_name": "mouthtest",
        "script_segment": json.dumps({"mode": "mouthtest", "target_sec": 10,
                                       "standard_script": (script_text or "").strip() == ""},
                                      ensure_ascii=False),
        "output_path": out, "status": "queued", "stage": "Queued",
        "truth_hash": truth_hash(),
        "tts_provider": provider, "test_mode": 1,
        "test_type": TEST_TYPE_STANDARD_MOUTH, "edge_voice": voice,
    })
    _wake_worker()
    return {"ok": True, "job_id": job_id}


def create_full_jobs(avatar_id: str, voice_id: str, script_text: str,
                     split_mode: str = "full",
                     voice_meta: Optional[Dict] = None,
                     tts_provider: str = ELEVENLABS,
                     tts_config: Optional[Dict] = None,
                     sync_mode: Optional[str] = None,
                     target_language: Optional[str] = None,
                     video_name: Optional[str] = None) -> Dict[str, Any]:
    """Create one or more full-render jobs (one per script part).

    V1.5.0: tts_config (the resolved per-voice ElevenLabs config) is snapshotted
    into each job at submission, with a deterministic tts_config_hash. The
    render uses that snapshot — it never re-fetches/settings mid-job.

    V1.6.0: if a matching Script Voice Preview exists, its validated MASTER audio
    is snapshotted directly into the job, saving ElevenLabs quota and guaranteeing
    identical acoustic output. An ElevenLabs job submitted without a tts_config is
    resolved server-side (same resolver as Preview) and fails closed instead of
    silently using the legacy eleven_turbo_v2_5 default — prevents preview-vs-render
    voice divergence."""
    provider = _provider_for(tts_provider)
    from . import script_service
    av_row = db.get_avatar(avatar_id)
    if av_row and av_row.get("is_deleted") == 1:
        return {"ok": False, "error": f"Avatar '{avatar_id}' đã bị chuyển vào Thùng rác. Hãy khôi phục trước khi render."}
    av = avatar_service.list_avatars()
    match = next((a for a in av if a["avatar_id"] == avatar_id), None)
    if not match or not match["ready"]:
        return {"ok": False, "error": f"Avatar '{avatar_id}' is not READY."}
    if not voice_id:
        return {"ok": False, "error": "No voice provided."}
    if not (script_text or "").strip():
        return {"ok": False, "error": "Script is empty."}

    # V1.6.0 TTS consistency: never queue an ElevenLabs job without a resolved
    # language-aware config. Re-resolve server-side if the caller omitted it.
    if provider == ELEVENLABS:
        tts_config, err = _resolve_tts_config_for_submission(voice_id, tts_config, target_language)
        if err:
            return err

    sp = script_service.split_script(script_text, split_mode)
    if not sp["ok"]:
        return sp
    tts_config_json = json.dumps(tts_config, ensure_ascii=False) if tts_config else None
    tts_config_hash = el.tts_config_hash(tts_config) if tts_config else None
    hist_id = (tts_config or {}).get("history_item_id") if tts_config else None
    job_ids = []
    for part in sp["parts"]:
        job_id = _new_job_id()
        out = _output_path("full", avatar_id, part["label"], job_id)
        audio_src = "generated"
        p_id = None
        p_fp = None
        m_path = None
        if provider == ELEVENLABS and tts_config:
            try:
                from . import preview_service
                lang = tts_config.get("target_language") or "vi"
                p_fp = preview_service.compute_preview_fingerprint(part["text"], voice_id, lang, tts_config)
                prev_row = db.get_audio_preview_by_fingerprint(p_fp)
                if prev_row and prev_row.get("status") == "ready":
                    p_id = prev_row["id"]
                    m_path = preview_service.snapshot_preview_for_job(p_id, job_id)
                    if m_path:
                        audio_src = "script_preview"
            except Exception:
                pass

        display_name_val = db.sanitize_display_name(video_name) if video_name else None
        db.create_job({
            "job_id": job_id, "kind": "full", "avatar_id": avatar_id,
            "display_name": display_name_val,
            "voice_id": voice_id,
            "voice_meta": json.dumps(voice_meta, ensure_ascii=False) if voice_meta else None,
            "script_text": part["text"][:8000], "script_name": part["label"],
            "script_segment": json.dumps({"mode": split_mode, "label": part["label"],
                                           "words": part["words"],
                                           "duration_sec": part["duration_sec"]},
                                          ensure_ascii=False),
            "output_path": out, "status": "queued", "stage": "Queued",
            "truth_hash": truth_hash(),
            "tts_provider": provider, "test_mode": 0,
            "test_type": TEST_TYPE_PRODUCTION,
            "edge_voice": voice_id if provider == EDGE_TTS_TEST else None,
            "tts_config": tts_config_json, "tts_config_hash": tts_config_hash,
            "sync_mode": sync_mode, "history_item_id": hist_id,
            "audio_source": audio_src,
            "preview_id": p_id,
            "preview_fingerprint": p_fp,
            "master_audio_path": m_path,
        })
        job_ids.append(job_id)
    _wake_worker()
    return {"ok": True, "job_ids": job_ids}


def retry_job(job_id: str) -> Dict[str, Any]:
    """Re-queue a FAILED job. Does NOT touch successful jobs. Preserves the
    original voice/avatar/config (never silently changes them). A retry gets a
    FRESH output path (new uuid) so it can never silently overwrite a previous
    artifact, even if one somehow exists at the old path."""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found."}
    if job["status"] not in ("failed", "cancelled", "timed_out"):
        return {"ok": False, "error": "Only failed/cancelled/timed_out jobs can be retried."}
    new_out = _output_path(job["kind"], job["avatar_id"],
                           job.get("script_name") or job["kind"], job_id)
    db.update_job(job_id, status="queued", progress=0, stage="Queued",
                  error=None, output_path=new_out)
    db.log_activity("JOB_RETRY", "job", job_id,
                    {"avatar_id": job.get("avatar_id"), "output_path": new_out})
    _wake_worker()
    return {"ok": True, "job_id": job_id}


def cancel_job(job_id: str) -> Dict[str, Any]:
    """Cancel a queued/in-flight job safely. Kills the subprocess if running."""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found."}
    if job["status"] in ("complete", "failed", "cancelled"):
        return {"ok": False, "error": f"Job already {job['status']}."}
    
    action = "JOB_STOP" if job.get("status") in ("preparing_audio", "rendering", "encoding", "verifying") else "JOB_CANCEL"
    db.update_job(job_id, status="cancelled", stage="Cancelled")
    pid = job.get("pid")
    if pid:
        _kill_pid(pid)
    gpu = job.get("gpu_id")
    if gpu is not None:
        gpu_service.release(gpu)
    db.log_activity(action, "job", job_id, {"status": job.get("status")})
    return {"ok": True, "job_id": job_id}


def delete_render(job_id: str) -> Dict[str, Any]:
    """Soft delete a completed/failed/cancelled render from active History."""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found."}
    if job.get("status") in ("preparing_audio", "rendering", "encoding", "verifying"):
        return {"ok": False, "error": "Không thể xóa tác vụ đang render. Hãy dừng tác vụ trước."}
    db.soft_delete_job(job_id)
    db.log_activity("RENDER_DELETE", "render", job_id, {"output_path": job.get("output_path")})
    return {"ok": True, "job_id": job_id, "deleted": True}


def restore_render(job_id: str) -> Dict[str, Any]:
    """Restore a soft-deleted render back to active History."""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found."}
    if job.get("status") == "complete" and job.get("output_path"):
        if not os.path.exists(job["output_path"]):
            return {"ok": False, "error": "Không thể khôi phục: Tệp video kết quả không còn tồn tại trên đĩa."}
    db.restore_job(job_id)
    db.log_activity("RENDER_RESTORE", "render", job_id, {"output_path": job.get("output_path")})
    return {"ok": True, "job_id": job_id, "restored": True}


def _kill_pid(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Background worker (one process per GPU)                                    #
# --------------------------------------------------------------------------- #
_WORKER_THREAD = None
_WORKER_EVENT = threading.Event()
# When True, job creation does NOT auto-start the background worker. Used by
# tests so they can inspect persisted jobs without the worker racing to claim
# them (and without triggering real ElevenLabs TTS / GPU renders).
_WORKER_DISABLED = False


def _wake_worker():
    if _WORKER_DISABLED:
        return
    global _WORKER_THREAD
    if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
        _WORKER_THREAD = threading.Thread(target=_worker_loop, daemon=True)
        _WORKER_THREAD.start()
    _WORKER_EVENT.set()


def _worker_loop():
    while True:
        _WORKER_EVENT.wait(timeout=5)
        _WORKER_EVENT.clear()
        # Drain queued jobs while GPUs are free.
        while True:
            job = _claim_queued_job()
            if not job:
                break
            gpu = gpu_service.acquire()
            if gpu is None:
                # No free GPU; put the job back and wait.
                db.update_job(job["job_id"], status="queued", stage="Queued (waiting for GPU)")
                break
            t = threading.Thread(target=_run_job, args=(job["job_id"], gpu),
                                  daemon=True)
            t.start()
        # Loop again if more jobs were queued in the meantime.
        if not db.list_active_jobs():
            # Nothing active; sleep until woken.
            _WORKER_EVENT.wait(timeout=2)
            _WORKER_EVENT.clear()


def _claim_queued_job() -> Optional[Dict[str, Any]]:
    """Atomically claim one QUEUED job (set -> preparing_audio) so two workers
    don't grab the same row."""
    with db._LOCK:
        conn = db._connect()
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            job = dict(row)
            conn.execute("UPDATE jobs SET status='preparing_audio', stage='Preparing audio', updated_at=? WHERE job_id=?",
                         (time.time(), job["job_id"]))
            conn.commit()
            return job
        finally:
            conn.close()


# Progress parsing from renderer stdout.
_TQDM = re.compile(r"Rendering:\s+(\d+)%")
_STAGE_PATTERNS = [
    (re.compile(r"Extracting Whisper audio features", re.I), "Rendering Lip-sync", None),
    (re.compile(r"Rendering .* frames in batches", re.I), "Rendering Lip-sync", 2),
    (re.compile(r"Muxing audio \+ video", re.I), "Encoding", 90),
    (re.compile(r"Render done:", re.I), "Encoding", 92),
]


def _run_job(job_id: str, gpu_id: int) -> None:
    job = db.get_job(job_id)
    if not job:
        return
    if job["status"] == "cancelled":
        gpu_service.release(gpu_id)
        return

    log_path = os.path.join(config.LOG_DIR, f"{job_id}.log")
    db.update_job(job_id, gpu_id=gpu_id, log_path=log_path, stage="Preparing audio")

    # 1) Generate master audio. Provider is EXPLICIT per job (ELEVENLABS or
    #    EDGE_TTS_TEST); never falls back between providers (spec B8). Both feed
    #    the same locked production renderer. test10s / mouhtest -> ~10s trim.
    provider = job.get("tts_provider") or ELEVENLABS
    target_sec = 10.0 if job["kind"] in ("test10s", "mouhtest") else None
    tts_config = db.parse_json_field(job.get("tts_config"))  # resolved per-voice config (V1.5.0) or None
    master_override = job.get("master_audio_path") if job.get("audio_source") == "script_preview" else None
    audio = generate_master_audio(job["script_text"], job["voice_id"],
                                  target_sec=target_sec, tts_provider=provider,
                                  tts_config=tts_config,
                                  master_audio_override=master_override)
    if not audio["ok"]:
        db.update_job(job_id, status="failed", stage="Failed", error=audio["error"])
        gpu_service.release(gpu_id)
        return
    cond_path = audio["cond_path"]
    master_path = audio["master_path"]
    db.update_job(job_id, master_audio_path=master_path,
                  duration_sec=audio.get("duration_sec"),
                  stage="Rendering Lip-sync", progress=5)

    # 2) Run the production renderer with the locked truth. MuseTalk conditioning
    #    uses cond_path (16 kHz mono, unchanged). The final MP4 audio comes from
    #    master_path when it differs from cond_path (V1.5.0 two-audio-path); else
    #    --master-audio is omitted (legacy backward-compatible behavior).
    out = job["output_path"]
    cmd = [_torch_python(),
           config.RENDERER,
           "--avatar_id", job["avatar_id"],
           "--audio", cond_path,
           "--output", out]
    if master_path and master_path != cond_path:
        cmd += ["--master-audio", master_path]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["LIVETALKING_GPU_ID"] = "0"
    env["OFFLINE_USE_MULTI_GPU"] = "false"
    env["LIVETALKING_CUDA_GRAPH"] = "true"
    # Keep the renderer on the locked truth path (no experimental config).
    env.pop("LIVETALKING_EXPERIMENTAL_CONFIG", None)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, cwd=config.ROOT, env=env,
                                encoding="utf-8", errors="replace")
    except Exception as e:
        db.update_job(job_id, status="failed", stage="Failed",
                      error=f"Failed to start renderer: {e}")
        gpu_service.release(gpu_id)
        return

    db.update_job(job_id, pid=proc.pid)
    last_pct = 5
    # Progress-aware timeout: a watchdog kills the renderer only if it produces
    # NO stdout for STUDIO_RENDER_NO_PROGRESS_SEC (default 300s). A slow but
    # progressing long render is NOT killed — only a truly hung process is.
    # Plus a hard backstop STUDIO_RENDER_HARD_TIMEOUT_SEC (default 14400s/4h).
    no_progress_timeout = float(os.environ.get("STUDIO_RENDER_NO_PROGRESS_SEC", "300"))
    hard_timeout = float(os.environ.get("STUDIO_RENDER_HARD_TIMEOUT_SEC", "14400"))
    start = time.monotonic()
    last_activity = {"t": time.monotonic()}
    timed_out = {"flag": False}

    def _watchdog():
        while proc.poll() is None:
            time.sleep(5)
            now = time.monotonic()
            if now - last_activity["t"] > no_progress_timeout:
                timed_out["flag"] = True
                runtime.terminate_tree(proc)
                return
            if now - start > hard_timeout:
                timed_out["flag"] = True
                runtime.terminate_tree(proc)
                return

    import threading as _th
    wd = _th.Thread(target=_watchdog, daemon=True)
    wd.start()

    try:
        with open(log_path, "w", encoding="utf-8") as logf:
            for line in proc.stdout:
                logf.write(line)
                logf.flush()
                last_activity["t"] = time.monotonic()
                m = _TQDM.search(line)
                if m:
                    pct = int(m.group(1))
                    # Map tqdm 0..100 (render phase) into 5..88 of overall.
                    overall = 5 + int(pct * 0.83)
                    if overall > last_pct:
                        last_pct = overall
                        db.update_job(job_id, progress=overall)
                    continue
                for pat, stage, pct in _STAGE_PATTERNS:
                    if pat.search(line):
                        db.update_job(job_id, stage=stage)
                        if pct is not None and pct > last_pct:
                            last_pct = pct
                            db.update_job(job_id, progress=pct)
                        break
        proc.wait(timeout=60)
    except Exception as e:
        db.update_job(job_id, status="failed", stage="Failed",
                      error=f"Renderer error: {e}")
        gpu_service.release(gpu_id)
        return

    if timed_out["flag"]:
        try:
            proc.wait(timeout=15)
        except Exception:
            runtime.terminate_tree(proc)
        db.update_job(job_id, status="timed_out", stage="Timed Out", progress=0,
                      error="Renderer hung (no progress for %.0fs) — terminated."
                            % no_progress_timeout)
        gpu_service.release(gpu_id)
        return

    rc = proc.returncode
    if rc != 0:
        tail = _tail(log_path, 15)
        db.update_job(job_id, status="failed", stage="Failed", progress=0,
                      error=f"Renderer exited code {rc}. {tail}")
        gpu_service.release(gpu_id)
        return

    # 3) Verify.
    db.update_job(job_id, status="verifying", stage="Verifying", progress=95)
    vr = verify_mod.verify(out)
    if not vr["ok"]:
        db.update_job(job_id, status="failed", stage="Failed",
                      error="Post-render verification failed: " + "; ".join(vr["warnings"]))
        gpu_service.release(gpu_id)
        return

    db.update_job(job_id, status="complete", stage="Complete", progress=100,
                  error=None)
    gpu_service.release(gpu_id)


def _tail(path: str, n: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]).strip()
    except Exception:
        return ""


# Initialize the worker on import (lazy; first job wakes it).
def start() -> None:
    load_truth()
    db.init_db()
    _reconcile_inflight_jobs()
    # V1.6.0 — runtime preflight at launch (fail-fast). Populates the cached
    # preflight so /api/system/status surfaces renderer readiness immediately; a
    # wrong/broken interpreter is discovered here, not at the first render.
    try:
        from . import runtime as _rt
        rt = _rt.preflight(refresh=True, ttl=0)
        if not rt.get("renderer_ready"):
            print(f"[runtime] NOT_READY: {rt.get('torch_error') or rt.get('error') or 'CUDA unavailable'} "
                  f"(interpreter={rt.get('interpreter')})")
    except Exception as _e:
        print(f"[runtime] preflight failed: {_e}")


# Transient states that imply a child process was running. If the Studio process
# died and restarted, those children are gone — the jobs cannot still be running.
_TRANSIENT = ("preparing_audio", "preparing_avatar", "rendering", "encoding", "verifying")


def _reconcile_inflight_jobs() -> None:
    """On startup, any job left in a transient state by a previous Studio crash
    is honestly marked failed — its child process died with the old Studio and
    the in-memory GPU busy-set is fresh (so GPUs are already reusable). Does NOT
    auto-retry expensive jobs; the operator chooses retry from History. (V1.4.1 R06)"""
    try:
        stuck = db.list_jobs_in_statuses(_TRANSIENT)
    except Exception:
        return
    for j in stuck:
        db.update_job(j["job_id"], status="failed", stage="Interrupted",
                      progress=0,
                      error="Studio đã khởi động lại trong khi job đang chạy.")