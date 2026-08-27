"""Standalone ElevenLabs client for the studio controller.

Reuses the VALIDATED offline TTS API pattern from
experiments/elevenlabs_tts_render.py (xi-api-key header,
output_format=pcm_16000, 16kHz mono). This is the SAME production path; the
controller just wraps it for the UI.

CRITICAL CONTRACT (spec section 19):
  * The exact Voice ID the user enters is used. NO SILENT FALLBACK.
  * If a Voice ID is invalid/unavailable -> error. Never substitute another
    voice (Sarah / EXAVITQu4vr4xnSDxMaLC / default). The ElevenLabsTTS realtime
    class enforces the same rule.
  * The API key is read from .env (ELEVENLABS_API_KEY). Never written to disk,
    never returned in any API response, never put in render manifests/logs.
"""
import os
import re
import time
import numpy as np
import soundfile as sf
import requests
from typing import Optional, Tuple, Dict, Any

from . import config
from .envutil import env_str

_API_KEY = None


def _key() -> str:
    """Lazily read the API key from .env on first use."""
    global _API_KEY
    if _API_KEY is None:
        from . import envutil
        envutil.load_env(force=True)
        _API_KEY = env_str("ELEVENLABS_API_KEY", "")
    return _API_KEY


def model_id() -> str:
    """TTS model id for the OFFLINE studio render path.

    The validated production batch (spec section 21) used eleven_turbo_v2_5
    with voice pGapy9MNHCukzJtjavF0 (Hạnh). The realtime server's
    ELEVENLABS_MODEL_ID=eleven_v3 is a SEPARATE concern (realtime streaming
    quality) and is intentionally NOT reused here — the offline batch truth is
    eleven_turbo_v2_5. An explicit ELEVENLABS_STUDIO_MODEL_ID overrides for
    testing only. No user-facing control is exposed (spec: do not expose TTS
    model tuning).
    """
    return env_str("ELEVENLABS_STUDIO_MODEL_ID", "eleven_turbo_v2_5")


def is_configured() -> bool:
    return bool(_key())


def account_status() -> Dict[str, Any]:
    """LIVE, uncached account/subscription status from GET /v1/user/subscription.

    Returns only fields ElevenLabs actually returns — never fabricates
    "remaining characters" or quota numbers. No caching: each call hits the
    API so a topped-up / changed key is reflected immediately. Never falls
    back to another key. Used by the Settings view (read-only).

    Returns {ok, tier, status, character_count, character_limit, remaining,
    reset_unix, reset_date_utc, error?}. `remaining` is computed strictly as
    character_limit - character_count (the documented binding counter); if the
    API does not return these fields, remaining is null (not fabricated).
    """
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    try:
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription",
                         headers=_headers(), timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"ElevenLabs returned {r.status_code}",
                "http_status": r.status_code}
    try:
        d = r.json()
    except ValueError:
        return {"ok": False, "error": "Unreadable subscription response."}
    cc = d.get("character_count")
    cl = d.get("character_limit")
    remaining = (cl - cc) if (isinstance(cc, int) and isinstance(cl, int)) else None
    reset_unix = d.get("next_character_count_reset_unix")
    reset_date = None
    if isinstance(reset_unix, int):
        try:
            import datetime as _dt
            reset_date = _dt.datetime.utcfromtimestamp(reset_unix).strftime(
                "%Y-%m-%d %H:%M UTC")
        except Exception:
            reset_date = None
    return {
        "ok": True,
        "tier": d.get("tier"),
        "status": d.get("status"),
        "character_count": cc,
        "character_limit": cl,
        "remaining": remaining,
        "reset_unix": reset_unix,
        "reset_date_utc": reset_date,
        "can_extend_character_limit": d.get("can_extend_character_limit"),
    }


class VoiceError(RuntimeError):
    """Raised when a Voice ID is invalid/unavailable. The controller must NOT
    fall back to another voice."""


class TTSUnavailable(RuntimeError):
    """Raised when ElevenLabs is unreachable / API key missing."""


def _headers() -> Dict[str, str]:
    return {"xi-api-key": _key(), "Content-Type": "application/json",
            "Accept": "application/json"}


def _audio_headers() -> Dict[str, str]:
    return {"xi-api-key": _key(), "Content-Type": "application/json",
            "Accept": "application/octet-stream"}


def check_voice(voice_id: str) -> Dict[str, Any]:
    """Verify a Voice ID via GET /v1/voices/{voice_id}.

    Returns {ok, voice_id, name, labels, category, preview_url, ...} using only
    metadata ElevenLabs actually returns. Does NOT fabricate metadata. Fails
    closed on invalid/unknown voice — never substitutes a default.

    A voice is considered usable if either the metadata GET succeeds OR a
    short TTS probe returns audio (some keys restrict the GET endpoint). In
    the probe case we report only that the voice is reachable, not fabricated
    metadata.
    """
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty.", "voice_id": vid}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured.",
                "voice_id": vid}

    # 1) Metadata GET (preferred — gives name/labels).
    url = config.ELEVENLABS_VOICE_URL.format(voice_id=vid)
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}", "voice_id": vid}

    if r.status_code == 200:
        try:
            data = r.json()
        except ValueError:
            data = {}
        # Some accounts can't GET /voices/{id} but CAN synthesize. Treat a
        # generic/empty name as inconclusive and probe TTS below.
        name = data.get("name") or ""
        labels = data.get("labels") or {}
        category = data.get("category") or ""
        preview_url = data.get("preview_url") or ""
        # If we got a real name, the voice definitely exists.
        if name:
            return {"ok": True, "voice_id": vid, "name": name,
                    "labels": labels, "category": category,
                    "preview_url": preview_url}
        # Fall through to TTS probe.

    # 2) TTS probe — synthesize a short throwaway clip. If it returns audio,
    # the voice is usable; report only that, no fabricated name.
    if r.status_code in (401, 403):
        # Auth/quota — distinguish from "voice not found".
        try:
            detail = r.text[:200]
        except Exception:
            detail = ""
        # 401/403 with "voice" wording often means the voice id is wrong.
        low = detail.lower()
        if "voice" in low and ("not found" in low or "invalid" in low):
            return {"ok": False, "error": "Voice ID invalid or unavailable.",
                    "voice_id": vid}
        return {"ok": False, "error": f"ElevenLabs rejected request ({r.status_code}).",
                "voice_id": vid, "detail": detail}
    if r.status_code == 404:
        return {"ok": False, "error": "Voice ID invalid or unavailable.",
                "voice_id": vid}

    # Metadata inconclusive (e.g. 400/403 on GET) -> probe with TTS.
    probe = _probe_tts(vid)
    if probe[0]:
        return {"ok": True, "voice_id": vid, "name": "",
                "labels": {}, "category": "",
                "note": "Voice is reachable (metadata not exposed by this account)."}
    return {"ok": False, "error": probe[1] or "Voice ID invalid or unavailable.",
            "voice_id": vid}


def _probe_tts(voice_id: str) -> Tuple[bool, Optional[str]]:
    """Synthesize ~1s of audio to confirm the voice is usable. Returns
    (ok, error)."""
    try:
        pcm = _synth(voice_id, "Xin chào.", allow_empty=False)
        return (len(pcm) > 1000, None)
    except VoiceError as e:
        return False, str(e)
    except Exception as e:
        return False, f"TTS probe failed: {e}"


def _split_into_chunks(text: str, max_chars: int = 1800) -> list:
    """Sentence-boundary chunking so no word is cut in half. Matches the
    validated experiments/elevenlabs_tts_render.py splitter."""
    parts = re.split(r"(?<=[.!?…,;:])\s+", text.strip())
    chunks, buf = [], ""
    for sent in parts:
        if not sent:
            continue
        if len(buf) + len(sent) + 1 > max_chars and buf:
            chunks.append(buf)
            buf = sent
        else:
            buf = (buf + " " + sent).strip()
    if buf:
        chunks.append(buf)
    return chunks


def _synth(voice_id: str, text: str, allow_empty: bool = True) -> bytes:
    """Synthesize one text chunk -> raw 16-bit PCM mono 16kHz. Raises VoiceError
    on a voice-level rejection (never falls back)."""
    vid = (voice_id or "").strip()
    if not vid:
        raise VoiceError("Voice ID is empty.")
    if not is_configured():
        raise TTSUnavailable("ElevenLabs API key not configured.")
    if not text.strip() and not allow_empty:
        raise VoiceError("Empty text.")

    url = config.ELEVENLABS_TTS_URL.format(voice_id=vid)
    body = {
        "text": text,
        "model_id": model_id(),
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                            "style": 0.0, "use_speaker_boost": True, "speed": 1.0},
    }
    # 4 retries with backoff (transient network/quota hiccups), but a 400/404
    # "voice not found" is raised immediately and NOT retried.
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(url + f"?output_format={config.ELEVENLABS_OUTPUT_FORMAT}",
                               headers=_audio_headers(), json=body,
                               timeout=config.ELEVENLABS_TIMEOUT_SEC)
            if r.status_code == 200:
                return r.content
            low = r.text.lower() if r.text else ""
            if r.status_code in (400, 404) and ("voice" in low or "not found" in low):
                raise VoiceError(f"Voice ID invalid or unavailable ({r.status_code}).")
            if r.status_code in (401, 403):
                raise TTSUnavailable(f"ElevenLabs auth/quota error ({r.status_code}).")
            last_err = f"elevenlabs {r.status_code}: {r.text[:200]}"
        except (VoiceError, TTSUnavailable):
            raise
        except requests.RequestException as e:
            last_err = f"network: {e}"
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise TTSUnavailable(last_err or "ElevenLabs TTS failed.")


def synth_to_wav(voice_id: str, text: str, out_wav: str,
                 max_chars: int = config.TTS_MAX_TEXT_CHARS) -> Tuple[str, float]:
    """Synthesize `text` with the EXACT voice_id, concatenate PCM, write a
    16kHz mono FLOAT wav to out_wav. Returns (out_wav, duration_sec).

    Never falls back to a different voice. Raises on any failure.
    """
    text = (text or "").strip()
    if not text:
        raise VoiceError("Nothing to synthesize (empty script).")

    chunks = _split_into_chunks(text, max_chars=max_chars)
    if not chunks:
        chunks = [text[:max_chars]]

    all_pcm = b""
    for i, ch in enumerate(chunks):
        pcm = _synth(voice_id, ch)
        all_pcm += pcm

    audio = np.frombuffer(all_pcm, dtype=np.int16).astype(np.float32) / 32768.0
    sf.write(out_wav, audio, 16000, subtype="FLOAT")
    info = sf.info(out_wav)
    return out_wav, float(info.duration)


def preview_voice(voice_id: str, text: str, out_wav: str,
                  target_sec: float = 9.0) -> Tuple[str, float]:
    """Generate ~8-10s of preview audio from the start of the script using the
    EXACT voice_id. Trims by words (no mid-word cuts)."""
    words = (text or "").split()
    target_words = max(1, int(target_sec * config.WORDS_PER_SEC))
    trimmed = " ".join(words[:target_words])
    if not trimmed:
        trimmed = (text or "").strip()[:400]
    return synth_to_wav(voice_id, trimmed, out_wav)