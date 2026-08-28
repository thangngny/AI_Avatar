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
import json
import hashlib
import tempfile
import subprocess
import numpy as np
import soundfile as sf
import requests
from typing import Optional, Tuple, Dict, Any, List

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


# --------------------------------------------------------------------------- #
# V1.5.0 — ElevenLabs voice config auto-sync + generation matching            #
# --------------------------------------------------------------------------- #
# Generic per-voice resolution. For ANY Voice ID the user enters, fetch that
# voice's real stored settings from the official ElevenLabs API (server-side;
# key stays in .env), resolve an explicit TTS config, and synthesize with it.
# No `if voice_id == ...` special-casing; no global hardcoding of any specific
# model/output_format. The API key is NEVER returned in any of these results.

# In-process cache for ElevenLabs metadata GETs (settings/models/history).
_CACHE: Dict[Tuple, Any] = {}


def _cache_get(key):
    item = _CACHE.get(key)
    if item and item[0] > time.time():
        return item[1]
    return None


def _cache_set(key, value, ttl):
    _CACHE[key] = (time.time() + ttl, value)


def _short(text: str, n: int = 48) -> str:
    s = (text or "").strip().replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s


def _norm_settings(s: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize a voice_settings dict to the 5 canonical fields with stable
    types (floats for the 4 numeric, bool for speaker boost). None preserved."""
    s = s or {}
    out: Dict[str, Any] = {}
    for k in ("stability", "similarity_boost", "style", "speed"):
        v = s.get(k)
        try:
            out[k] = float(v) if v is not None else None
        except (TypeError, ValueError):
            out[k] = None
    usb = s.get("use_speaker_boost")
    out["use_speaker_boost"] = (None if usb is None else bool(usb))
    return out


def _settings_match(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Strict comparison of two normalized voice_settings. A history item is only
    accepted if ALL five fields are present in BOTH and equal (no loose matching
    that could select a materially different config). null in either = no match
    for that field => not a match."""
    keys = ("stability", "similarity_boost", "style", "use_speaker_boost", "speed")
    for k in keys:
        av, bv = a.get(k), b.get(k)
        if av is None or bv is None:
            return False
        if isinstance(av, bool) or isinstance(bv, bool):
            if bool(av) != bool(bv):
                return False
            continue
        try:
            if abs(float(av) - float(bv)) > 1e-6:
                return False
        except (TypeError, ValueError):
            if av != bv:
                return False
    return True


def _output_sample_rate(output_format: str) -> int:
    """Parse the sample rate from an ElevenLabs output_format string
    (e.g. mp3_44100_128 -> 44100, pcm_16000 -> 16000)."""
    ofmt = (output_format or "pcm_16000").lower()
    for p in ofmt.split("_"):
        if p.isdigit():
            return int(p)
    return 16000


def _master_storage_format(output_format: str) -> str:
    """The internal lossless master is a WAV at the native sample rate of the
    requested output_format. Honestly reported (never 'MP3' after decode)."""
    return f"wav_{_output_sample_rate(output_format)}"


def tts_config_hash(cfg: Dict[str, Any]) -> str:
    """Deterministic sanitized hash of the resolved TTS config (no key)."""
    payload = {
        "voice_id": cfg.get("voice_id"),
        "model_id": cfg.get("model_id"),
        "voice_settings": _norm_settings(cfg.get("voice_settings")),
        "output_format": cfg.get("requested_output_format"),
    }
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def get_voice_settings(voice_id: str, refresh: bool = False) -> Dict[str, Any]:
    """GET /v1/voices/{voice_id}/settings — the authoritative CURRENT stored
    voice settings. Returns {ok, settings} (sanitized, no key). Cached 5 min;
    refresh bypasses. Fails closed (never substitutes another voice)."""
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty."}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    ck = ("settings", vid)
    if not refresh:
        c = _cache_get(ck)
        if c is not None:
            return {"ok": True, "settings": c, "cached": True}
    url = config.ELEVENLABS_VOICE_SETTINGS_URL.format(voice_id=vid)
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"ElevenLabs returned {r.status_code}",
                "http_status": r.status_code}
    try:
        d = r.json()
    except ValueError:
        return {"ok": False, "error": "Unreadable settings response."}
    settings = _norm_settings(d)
    _cache_set(ck, settings, config.ELEVENLABS_SETTINGS_CACHE_TTL)
    return {"ok": True, "settings": settings, "cached": False}


def get_models(refresh: bool = False) -> Dict[str, Any]:
    """GET /v1/models — list of models. Cached ~30 min. Returns {ok, models}."""
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    ck = ("models",)
    if not refresh:
        c = _cache_get(ck)
        if c is not None:
            return {"ok": True, "models": c, "cached": True}
    try:
        r = requests.get(config.ELEVENLABS_MODELS_URL, headers=_headers(), timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"ElevenLabs returned {r.status_code}",
                "http_status": r.status_code}
    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "error": "Unreadable models response."}
    models = [{"name": m.get("name"), "model_id": m.get("model_id"),
               "can_do_text_to_speech": m.get("can_do_text_to_speech")} for m in data]
    _cache_set(ck, models, config.ELEVENLABS_MODELS_CACHE_TTL)
    return {"ok": True, "models": models, "cached": False}


def model_supports_tts(model_id: str, refresh: bool = False) -> bool:
    """True if model_id exists in /v1/models and can_do_text_to_speech. Best
    effort: if the models API is unavailable, returns False (caller decides)."""
    r = get_models(refresh=refresh)
    if not r.get("ok"):
        return False
    return any(m.get("model_id") == model_id and m.get("can_do_text_to_speech")
               for m in r["models"])


def get_voice_history(voice_id: str, limit: int = 10,
                       refresh: bool = False) -> Dict[str, Any]:
    """GET /v1/history?voice_id=…&source=TTS&sort_direction=desc — recent TTS
    history for this voice, newest-first. Returns {ok, items} where each item
    has a SHORT text preview only (full history text is never returned/logged).
    output_format is fetched on demand via get_history_item (not in the list)."""
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty."}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    ck = ("history", vid)
    if not refresh:
        c = _cache_get(ck)
        if c is not None:
            return {"ok": True, "items": c, "cached": True}
    try:
        r = requests.get(config.ELEVENLABS_HISTORY_URL, headers=_headers(), timeout=30,
                         params={"voice_id": vid, "source": "TTS",
                                 "sort_direction": "desc", "page_size": limit})
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"ElevenLabs returned {r.status_code}",
                "http_status": r.status_code}
    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "error": "Unreadable history response."}
    items: List[Dict[str, Any]] = []
    for it in (data.get("history") or [])[:limit]:
        items.append({
            "history_item_id": it.get("history_item_id"),
            "date_unix": it.get("date_unix"),
            "voice_id": it.get("voice_id"),
            "voice_name": it.get("voice_name") or "",
            "model_id": it.get("model_id"),
            "source": it.get("source"),
            "settings": _norm_settings(it.get("settings")),
            "text_preview": _short(it.get("text"), 48),
        })
    _cache_set(ck, items, config.ELEVENLABS_HISTORY_CACHE_TTL)
    return {"ok": True, "items": items, "cached": False}


def get_history_item(history_item_id: str) -> Dict[str, Any]:
    """GET /v1/history/{history_item_id} — one history item's public config
    (voice_id, model_id, settings, output_format). Full text is NOT returned —
    only a short preview (config matching, not script replacement)."""
    if not history_item_id:
        return {"ok": False, "error": "No history item id."}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    url = config.ELEVENLABS_HISTORY_ITEM_URL.format(history_item_id=history_item_id)
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error: {e}"}
    if r.status_code != 200:
        return {"ok": False, "error": f"ElevenLabs returned {r.status_code}",
                "http_status": r.status_code}
    try:
        d = r.json()
    except ValueError:
        return {"ok": False, "error": "Unreadable history item."}
    item = {
        "history_item_id": d.get("history_item_id") or history_item_id,
        "voice_id": d.get("voice_id"),
        "model_id": d.get("model_id"),
        "settings": _norm_settings(d.get("settings")),
        "output_format": d.get("output_format") or "pcm_16000",
        "source": d.get("source"),
        "date": d.get("date"),
        "text_preview": _short(d.get("text"), 48),
    }
    return {"ok": True, "item": item}


def resolve_config(voice_id: str, mode: str = "auto_current",
                   history_item_id: Optional[str] = None,
                   overrides: Optional[Dict[str, Any]] = None,
                   voice_name: Optional[str] = None,
                   refresh: bool = False) -> Dict[str, Any]:
    """Resolve an explicit per-voice TTS config. Generic — no voice-id
    special-casing, no global hardcoding of model/output.

    mode:
      'auto_current'   — Mode A: current API settings + matching-history model/output
                         (search newest->oldest for an item whose settings match the
                         current stored settings); else STUDIO_POLICY (truthful).
      'history_match'  — Mode B: exact public-config match of one selected item.
      'manual'         — Mode C: advanced overrides.

    Returns {ok, config} with per-field provenance + tts_config_hash, or
    {ok:False, error, fail_closed} on a settings-API/resolution failure (never
    silently falls back). API-success-no-matching-history is NOT a failure
    (returns ok with match_strength='settings_only', provenance STUDIO_POLICY).
    """
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty.", "fail_closed": True}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured.",
                "fail_closed": True}
    cfg: Dict[str, Any] = {
        "voice_id": vid, "voice_name": voice_name,
        "sync_mode": mode, "config_ts": int(time.time()),
        "provenance": {"voice_id": "USER_SELECTION"},
        "history_item_id": None,
    }
    if mode == "history_match":
        if not history_item_id:
            return {"ok": False, "error": "No history item selected.", "fail_closed": True}
        item = get_history_item(history_item_id)
        if not item.get("ok"):
            return {"ok": False, "error": item.get("error", "History item unavailable."),
                    "fail_closed": False}
        h = item["item"]
        cfg["model_id"] = h.get("model_id") or model_id()
        cfg["voice_settings"] = h.get("settings") or _norm_settings({})
        cfg["requested_output_format"] = h.get("output_format") or config.ELEVENLABS_OUTPUT_FORMAT
        cfg["history_item_id"] = history_item_id
        cfg["match_strength"] = "history_item"
        cfg["provenance"].update({"model_id": "ELEVENLABS_HISTORY_ITEM",
                                  "voice_settings": "ELEVENLABS_HISTORY_ITEM",
                                  "output_format": "ELEVENLABS_HISTORY_ITEM"})
    elif mode == "manual":
        ov = overrides or {}
        cfg["model_id"] = ov.get("model_id", model_id())
        cfg["voice_settings"] = _norm_settings(ov.get("voice_settings"))
        cfg["requested_output_format"] = ov.get("output_format", config.ELEVENLABS_OUTPUT_FORMAT)
        cfg["match_strength"] = "manual"
        cfg["provenance"].update({"model_id": "USER_MANUAL",
                                  "voice_settings": "USER_MANUAL",
                                  "output_format": "USER_MANUAL"})
    else:
        # Mode A — auto_current.
        # 1) Current stored voice settings (fail-closed on API failure).
        vs = get_voice_settings(vid, refresh=refresh)
        if not vs.get("ok"):
            return {"ok": False, "error": vs.get("error", "Không thể đồng bộ cấu hình ElevenLabs."),
                    "fail_closed": True, "stage": "settings_api_failed"}
        cfg["voice_settings"] = vs["settings"]
        cfg["provenance"]["voice_settings"] = "ELEVENLABS_VOICE_SETTINGS_API"
        # 2) Search history newest->oldest for an item whose settings MATCH the
        #    current stored settings (strict, no loose matching). The newest item
        #    is NOT blindly used — a past experiment with different settings is
        #    skipped.
        match = None
        hist = get_voice_history(vid, limit=10, refresh=refresh)
        if hist.get("ok"):
            for it in hist["items"]:
                if not it.get("model_id"):
                    continue
                if _settings_match(it.get("settings"), cfg["voice_settings"]):
                    det = get_history_item(it["history_item_id"])
                    ofmt = ((det.get("item") or {}).get("output_format")
                            if det.get("ok") else None) or "pcm_16000"
                    match = {"model_id": it["model_id"], "output_format": ofmt,
                             "history_item_id": it["history_item_id"]}
                    break
        if match:
            cfg["model_id"] = match["model_id"]
            cfg["requested_output_format"] = match["output_format"]
            cfg["history_item_id"] = match["history_item_id"]
            cfg["match_strength"] = "history_matched"
            cfg["provenance"].update({"model_id": "MATCHING_HISTORY_GENERATION",
                                      "output_format": "MATCHING_HISTORY_GENERATION"})
        else:
            # 3) No matching history -> explicit Studio policy (truthful, NOT
            #    labeled an exact-generation match). Global default unchanged.
            cfg["model_id"] = model_id()
            cfg["requested_output_format"] = config.ELEVENLABS_OUTPUT_FORMAT
            cfg["match_strength"] = "settings_only"
            cfg["provenance"].update({"model_id": "STUDIO_POLICY",
                                      "output_format": "STUDIO_POLICY"})
    cfg["master_storage_format"] = _master_storage_format(cfg["requested_output_format"])
    cfg["tts_config_hash"] = tts_config_hash(cfg)
    return {"ok": True, "config": cfg}


def _decode_to_float(raw: bytes, output_format: str, target_sr: int) -> np.ndarray:
    """Decode ElevenLabs response bytes to a float32 mono numpy array at
    target_sr. For pcm_16000 -> 16k target, the fast in-memory int16 path
    (validated production path). For any other format/target, ffmpeg decodes
    (and resamples to target_sr mono)."""
    ofmt = (output_format or "pcm_16000").lower()
    if ofmt == "pcm_16000" and target_sr == 16000:
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    ext = ".mp3" if ofmt.startswith("mp3") else ".wav"
    src_sr = _output_sample_rate(ofmt)
    with tempfile.TemporaryDirectory(prefix="eltts_") as td:
        src = os.path.join(td, "in" + ext)
        with open(src, "wb") as f:
            f.write(raw)
        dst = os.path.join(td, "out.wav")
        cmd = ["ffmpeg", "-y"]
        if ofmt.startswith("pcm_") and ext == ".wav":
            # raw 16-bit little-endian mono PCM, no container -> tell ffmpeg.
            cmd += ["-f", "s16le", "-ar", str(src_sr), "-ac", "1"]
        cmd += ["-i", src, "-ar", str(target_sr), "-ac", "1", dst]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60)
        except Exception as e:
            raise TTSUnavailable(f"Audio decode failed: {e}")
        a, _ = sf.read(dst, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        return a.astype(np.float32)


def _synth_config(voice_id: str, text: str,
                  cfg: Dict[str, Any]) -> bytes:
    """Synthesize one text chunk with the RESOLVED config (model_id +
    voice_settings + requested_output_format). Like _synth but config-driven;
    same fail-closed retries; never substitutes another voice. None settings
    are omitted from the request body (let ElevenLabs use its defaults)."""
    vid = (voice_id or "").strip()
    if not vid:
        raise VoiceError("Voice ID is empty.")
    if not is_configured():
        raise TTSUnavailable("ElevenLabs API key not configured.")
    if not text.strip():
        raise VoiceError("Empty text.")
    vs = cfg.get("voice_settings") or {}
    voice_settings = {k: v for k, v in vs.items() if v is not None}
    body = {
        "text": text,
        "model_id": cfg.get("model_id") or model_id(),
        "voice_settings": voice_settings,
    }
    ofmt = cfg.get("requested_output_format") or config.ELEVENLABS_OUTPUT_FORMAT
    url = config.ELEVENLABS_TTS_URL.format(voice_id=vid)
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(url + f"?output_format={ofmt}",
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


def synth_master_cond(voice_id: str, text: str, cfg: Dict[str, Any],
                      out_master: str, out_cond: str) -> Tuple[str, str, float]:
    """Synthesize `text` with the resolved config, producing TWO files:
      - out_master: a LOSSLESS WAV at the native sample rate of the resolved
        requested_output_format (e.g. 44.1 kHz for mp3_44100_128). Used for the
        final MP4 audio. NEVER downsampled to 16 kHz; never kept as MP3.
      - out_cond:   a 16 kHz mono WAV derived from the master, for MuseTalk/
        Whisper conditioning only.

    The ElevenLabs voice_id is used EXACTLY (fail-closed, no substitution).
    Returns (out_master, out_cond, duration_sec) (duration from the 16k cond).
    """
    text = (text or "").strip()
    if not text:
        raise VoiceError("Nothing to synthesize (empty script).")
    ofmt = cfg.get("requested_output_format") or config.ELEVENLABS_OUTPUT_FORMAT
    sr = _output_sample_rate(ofmt)
    chunks = _split_into_chunks(text, max_chars=config.TTS_MAX_TEXT_CHARS)
    if not chunks:
        chunks = [text[:config.TTS_MAX_TEXT_CHARS]]
    master_parts: List[np.ndarray] = []
    cond_parts: List[np.ndarray] = []
    for ch in chunks:
        raw = _synth_config(voice_id, ch, cfg)
        master_parts.append(_decode_to_float(raw, ofmt, sr))
        cond_parts.append(_decode_to_float(raw, ofmt, 16000))
    master = np.concatenate(master_parts) if master_parts else np.zeros(0, dtype=np.float32)
    cond = np.concatenate(cond_parts) if cond_parts else np.zeros(0, dtype=np.float32)
    sf.write(out_master, master, sr, subtype="FLOAT")
    sf.write(out_cond, cond, 16000, subtype="FLOAT")
    info = sf.info(out_cond)
    return out_master, out_cond, float(info.duration)