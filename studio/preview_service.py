"""Script voice preview and audio reuse service for AI Avatar Studio (V1.6.0).

Enables users to generate and listen to the full script audio with the selected
production ElevenLabs voice BEFORE rendering the Avatar video, and reuses that
exact generated MASTER audio during subsequent video rendering without
regenerating TTS or consuming extra ElevenLabs quota.

Design Invariants:
  * Deterministic Fingerprinting: SHA256(canonical_effective_tts_request).
  * Storage: Persisted in data/studio_runtime/audio_previews/ + studio.db audio_previews.
  * Duplicate Suppression: In-flight requests for the same fingerprint join the same job.
  * File-Lifetime Safety: Render jobs snapshot/copy the validated MASTER audio into
    the job directory at enqueue time so subsequent preview edits never corrupt jobs.
  * GPU Isolation: Preview generation is TTS/audio only; never starts MuseTalk or reserves GPU.
"""
import os
import re
import time
import json
import uuid
import shutil
import hashlib
import threading
import subprocess
from typing import Dict, Any, Optional, Tuple, List

import soundfile as sf

from . import config
from . import db
from . import elevenlabs_client as el
from . import voices

_LOCK = threading.Lock()
_ACTIVE_GENERATIONS: Dict[str, threading.Event] = {}


def normalize_script_text(text: str) -> str:
    """Normalize script text for deterministic hashing while strictly preserving
    exact words, punctuation, casing, and Vietnamese diacritics."""
    if not text:
        return ""
    # Standardize CRLF -> LF, strip trailing whitespace from each line, trim outer whitespace
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def compute_preview_fingerprint(script_text: str, voice_id: str,
                                target_language: Optional[str],
                                tts_config: Dict[str, Any]) -> str:
    """Calculate deterministic SHA256 fingerprint for a preview TTS request.

    Includes all canonical factors affecting generated audio:
      * normalized exact script text (SHA256)
      * voice_id
      * target_language (e.g. 'vi')
      * model_id (e.g. 'eleven_v3', 'eleven_turbo_v2_5')
      * effective_voice_settings (stability, similarity_boost, style, speed, speaker_boost)
      * requested_output_format
      * language_code
    """
    norm_script = normalize_script_text(script_text)
    script_hash = hashlib.sha256(norm_script.encode("utf-8")).hexdigest()

    vid = (voice_id or "").strip()
    tl = (target_language or "vi").strip().lower()
    mid = tts_config.get("model_id") or el.model_id()
    eff_vs = tts_config.get("effective_voice_settings")
    if eff_vs is None:
        eff_vs = tts_config.get("voice_settings") or {}
    eff_vs_norm = el._norm_settings(eff_vs)
    ofmt = tts_config.get("requested_output_format") or config.ELEVENLABS_OUTPUT_FORMAT
    lc = tts_config.get("language_code") or ""

    payload = {
        "v": 1,
        "script_hash": script_hash,
        "voice_id": vid,
        "target_language": tl,
        "model_id": mid,
        "effective_voice_settings": eff_vs_norm,
        "requested_output_format": ofmt,
        "language_code": lc,
    }
    canonical_str = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def get_or_create_script_preview(script_text: str, voice_id: str,
                                 target_language: Optional[str] = "vi",
                                 tts_config: Optional[Dict[str, Any]] = None,
                                 voice_name: Optional[str] = None,
                                 refresh: bool = False) -> Dict[str, Any]:
    """Get an existing valid matching script voice preview or synthesize a new one.

    Suppresses duplicate concurrent calls for the same fingerprint and stores
    master audio in data/studio_runtime/audio_previews/.
    """
    config.ensure_runtime_dirs()
    norm_text = normalize_script_text(script_text)
    if not norm_text:
        return {"ok": False, "error": "Kịch bản trống."}

    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Chưa chọn giọng đọc."}

    lang = (target_language or "vi").strip().lower()

    # 1. Resolve production config if not provided
    if not tts_config:
        res = el.resolve_config(voice_id=vid, target_language=lang, voice_name=voice_name, refresh=refresh)
        if not res.get("ok"):
            return res
        resolved_cfg = res["config"]
    else:
        resolved_cfg = tts_config

    fingerprint = compute_preview_fingerprint(norm_text, vid, lang, resolved_cfg)

    # 2. Check cache in database (unless explicit refresh requested)
    if not refresh:
        cached = db.get_audio_preview_by_fingerprint(fingerprint)
        if cached and cached.get("status") == "ready":
            master_p = cached.get("master_audio_path")
            if master_p and os.path.isfile(master_p) and os.path.getsize(master_p) > 1000:
                try:
                    info = sf.info(master_p)
                    if info.duration > 0:
                        db.touch_audio_preview(cached["id"])
                        return {
                            "ok": True,
                            "reused": True,
                            "preview": {
                                "id": cached["id"],
                                "fingerprint": cached["fingerprint"],
                                "voice_id": cached["voice_id"],
                                "voice_name": cached.get("voice_name"),
                                "language": cached["language"],
                                "model_id": cached["model_id"],
                                "duration_sec": float(cached["duration_sec"]),
                                "sample_rate": int(cached["sample_rate"]),
                                "status": "ready",
                                "preview_url": f"/api/audio-preview/{cached['id']}/audio",
                                "download_url": f"/api/audio-preview/{cached['id']}/download",
                            }
                        }
                except Exception:
                    pass

    # 3. Check / manage active concurrent generations for this exact fingerprint
    with _LOCK:
        if fingerprint in _ACTIVE_GENERATIONS:
            evt = _ACTIVE_GENERATIONS[fingerprint]
            wait_needed = True
        else:
            evt = threading.Event()
            _ACTIVE_GENERATIONS[fingerprint] = evt
            wait_needed = False

    if wait_needed:
        # Wait up to 120s for ongoing generation to complete
        evt.wait(timeout=120)
        cached = db.get_audio_preview_by_fingerprint(fingerprint)
        if cached and cached.get("status") == "ready":
            master_p = cached.get("master_audio_path")
            if master_p and os.path.isfile(master_p) and os.path.getsize(master_p) > 1000:
                return {
                    "ok": True,
                    "reused": True,
                    "preview": {
                        "id": cached["id"],
                        "fingerprint": cached["fingerprint"],
                        "voice_id": cached["voice_id"],
                        "voice_name": cached.get("voice_name"),
                        "language": cached["language"],
                        "model_id": cached["model_id"],
                        "duration_sec": float(cached["duration_sec"]),
                        "sample_rate": int(cached["sample_rate"]),
                        "status": "ready",
                        "preview_url": f"/api/audio-preview/{cached['id']}/audio",
                        "download_url": f"/api/audio-preview/{cached['id']}/download",
                    }
                }
            return {"ok": False, "error": cached.get("error") or "Tạo bản đọc thất bại."}
        return {"ok": False, "error": "Quá thời gian tạo bản đọc đồng thời."}

    # 4. Perform actual synthesis
    preview_id = f"prev_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    out_master = os.path.join(config.PREVIEWS_DIR, f"{preview_id}_master.wav")
    temp_cond = os.path.join(config.TEMP_DIR, f"{preview_id}_cond.tmp.wav")

    db.create_audio_preview({
        "id": preview_id,
        "fingerprint": fingerprint,
        "voice_id": vid,
        "voice_name": voice_name or resolved_cfg.get("voice_name"),
        "language": lang,
        "model_id": resolved_cfg.get("model_id") or el.model_id(),
        "tts_config_json": json.dumps(resolved_cfg, ensure_ascii=False),
        "tts_config_hash": resolved_cfg.get("tts_config_hash") or el.tts_config_hash(resolved_cfg),
        "script_text": norm_text,
        "script_hash": hashlib.sha256(norm_text.encode("utf-8")).hexdigest(),
        "master_audio_path": out_master,
        "duration_sec": 0.0,
        "sample_rate": 0,
        "status": "generating",
    })

    try:
        m_path, c_path, dur = el.synth_master_cond(
            voice_id=vid,
            text=norm_text,
            cfg=resolved_cfg,
            out_master=out_master,
            out_cond=temp_cond
        )
        if not os.path.isfile(m_path) or os.path.getsize(m_path) < 100:
            raise RuntimeError("File master audio tạo ra rỗng hoặc không tồn tại.")

        info = sf.info(m_path)
        actual_dur = float(info.duration)
        actual_sr = int(info.samplerate)

        # Clean up temporary conditioning audio (only MASTER is stored permanently)
        if os.path.isfile(temp_cond):
            try:
                os.remove(temp_cond)
            except Exception:
                pass

        db.update_audio_preview(
            preview_id,
            status="ready",
            duration_sec=actual_dur,
            sample_rate=actual_sr,
            master_audio_path=m_path,
            error=None
        )

        db.log_activity(
            action="SCRIPT_PREVIEW_CREATED",
            resource_type="audio_preview",
            resource_id=preview_id,
            details={
                "fingerprint": fingerprint,
                "voice_id": vid,
                "language": lang,
                "model_id": resolved_cfg.get("model_id"),
                "duration_sec": actual_dur,
                "sample_rate": actual_sr,
            },
            result="SUCCESS"
        )

        return {
            "ok": True,
            "reused": False,
            "preview": {
                "id": preview_id,
                "fingerprint": fingerprint,
                "voice_id": vid,
                "voice_name": voice_name or resolved_cfg.get("voice_name"),
                "language": lang,
                "model_id": resolved_cfg.get("model_id") or el.model_id(),
                "duration_sec": actual_dur,
                "sample_rate": actual_sr,
                "status": "ready",
                "preview_url": f"/api/audio-preview/{preview_id}/audio",
                "download_url": f"/api/audio-preview/{preview_id}/download",
            }
        }
    except Exception as e:
        err_msg = str(e)
        db.update_audio_preview(preview_id, status="failed", error=err_msg)
        db.log_activity(
            action="SCRIPT_PREVIEW_FAILED",
            resource_type="audio_preview",
            resource_id=preview_id,
            details={"fingerprint": fingerprint, "voice_id": vid, "error": err_msg},
            result="ERROR"
        )
        return {"ok": False, "error": f"Không thể tạo bản đọc: {err_msg}"}
    finally:
        with _LOCK:
            if fingerprint in _ACTIVE_GENERATIONS:
                evt = _ACTIVE_GENERATIONS.pop(fingerprint)
                evt.set()


def derive_cond_from_master(master_path: str, out_cond_path: str) -> Tuple[str, float]:
    """Resample MASTER audio to 16 kHz mono float WAV for MuseTalk conditioning.
    Fast and lossless downsampling without calling ElevenLabs."""
    os.makedirs(os.path.dirname(out_cond_path), exist_ok=True)
    if not os.path.isfile(master_path):
        raise FileNotFoundError(f"Master audio file not found: {master_path}")

    info = sf.info(master_path)
    if info.samplerate == 16000 and info.channels == 1:
        data, sr = sf.read(master_path, dtype="float32")
        sf.write(out_cond_path, data, 16000, subtype="FLOAT")
    else:
        cmd = ["ffmpeg", "-y", "-i", master_path, "-ar", "16000", "-ac", "1", out_cond_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg conditioning resample failed: {res.stderr.decode('utf-8', 'replace')[:200]}")

    cond_info = sf.info(out_cond_path)
    return out_cond_path, float(cond_info.duration)


def snapshot_preview_for_job(preview_id: str, job_id: str) -> Optional[str]:
    """Copy the validated MASTER audio from a preview into an immutable job-owned
    location to guarantee file-lifetime safety even if cache is cleaned up."""
    preview = db.get_audio_preview(preview_id)
    if not preview or preview.get("status") != "ready":
        return None
    src = preview.get("master_audio_path")
    if not src or not os.path.isfile(src):
        return None

    job_audio_dir = os.path.join(config.TEMP_DIR, "job_audio")
    os.makedirs(job_audio_dir, exist_ok=True)
    dst = os.path.join(job_audio_dir, f"{job_id}_master.wav")
    try:
        shutil.copyfile(src, dst)
        return dst
    except Exception:
        return src


def get_static_voice_sample(voice_id: str) -> Optional[str]:
    """Return path to pre-generated static sample file for approved voice."""
    config.ensure_runtime_dirs()
    vid = (voice_id or "").strip()
    if not voices.is_approved_render_voice(vid):
        return None

    sample_path = os.path.join(config.VOICE_SAMPLES_DIR, f"{vid}.wav")
    if os.path.isfile(sample_path) and os.path.getsize(sample_path) > 1000:
        return sample_path

    # Pre-generate on demand once if API key is configured
    if el.is_configured():
        try:
            target_lang = "vi"
            res = el.resolve_config(vid, target_language=target_lang, mode="auto_current")
            if res.get("ok"):
                cfg = res["config"]
                text = "Xin chào, đây là bản nghe thử giọng đọc để bạn lựa chọn trước khi tạo video."
                temp_cond = sample_path + ".cond.tmp.wav"
                el.synth_master_cond(
                    voice_id=vid,
                    text=text,
                    cfg=cfg,
                    out_master=sample_path,
                    out_cond=temp_cond
                )
                if os.path.isfile(temp_cond):
                    try:
                        os.remove(temp_cond)
                    except Exception:
                        pass
                if os.path.isfile(sample_path):
                    return sample_path
        except Exception:
            pass
    return None
