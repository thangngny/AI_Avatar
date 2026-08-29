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

# --------------------------------------------------------------------------- #
# V1.6.0 — model capability table (official evidence from Phase A)            #
# --------------------------------------------------------------------------- #
# Built from the live GET /v1/models response (diagnostics/elevenlabs_language_
# rootcause/models_live.json, 2026-08-28) + the official text-to-speech/convert
# doc + empirical benchmark history. This is model-aware serialization evidence
# (Part 5), NOT language-support guessing: language support is always re-checked
# live via /v1/models in check_compatibility().
#
# settings: "all" = the 5 stored fields (stability/similarity_boost/style/
#   use_speaker_boost/speed) are accepted; a list = only those fields are sent.
#   v3 family uses stability only (Phase A Candidate C + v3 history showed the
#   other fields null); v2/v2.5 family accepts all 5 (Candidates A/B + history).
# language_code: whether the model accepts the language_code request field.
#   Official doc: "not supported for multilingual_v2 models."
# max_text: maximum_text_length_per_request from /v1/models (hard limit).
# context: previous_text/next_text are official documented body fields, BUT
#   the live API rejects them for the v3 family ("not yet supported with the
#   'eleven_v3' model" — proven by a 400 in the V1.6.0 multi-chunk test). v3 family
#   = False; v2/v2.5 family = True (the v3-specific exclusion implies the others
#   support context). Model-aware: never send context to a model that rejects it.
MODEL_CAPS: Dict[str, Dict[str, Any]] = {
    "eleven_v3":              {"settings": ["stability"],          "language_code": True,  "max_text": 5000,  "context": False, "deprecated": False},
    "eleven_v3_conversational": {"settings": ["stability"],        "language_code": True,  "max_text": 5000,  "context": False, "deprecated": False},
    "eleven_multilingual_v2": {"settings": "all",                   "language_code": False, "max_text": 10000, "context": True,  "deprecated": False},
    "eleven_flash_v2_5":      {"settings": "all",                   "language_code": True,  "max_text": 40000, "context": True,  "deprecated": False},
    "eleven_turbo_v2_5":      {"settings": "all",                   "language_code": True,  "max_text": 40000, "context": True,  "deprecated": False},
    "eleven_turbo_v2":        {"settings": "all",                   "language_code": False, "max_text": 30000, "context": True,  "deprecated": True},
    "eleven_flash_v2":        {"settings": "all",                   "language_code": False, "max_text": 30000, "context": True,  "deprecated": True},
}
# High-quality requested output format used on the language-aware path (kept
# separate from master_storage_format; never a pronunciation lever).
_HQ_OUTPUT_FORMAT = "mp3_44100_128"


def _caps(model_id: str) -> Dict[str, Any]:
    return MODEL_CAPS.get((model_id or "").strip(), {})


def effective_voice_settings(model_id: str,
                             stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return ONLY the voice_settings fields officially supported by the model.
    v3 family -> stability only; v2/v2.5 family -> all 5 stored fields. None
    values are always omitted. This is the model-aware request subset (Part 5):
    never force similarity_boost/style/speaker_boost/speed into v3; never omit a
    supported field unnecessarily."""
    stored = stored or {}
    caps = _caps(model_id)
    subset = caps.get("settings", "all")
    if subset == "all":
        keys = ("stability", "similarity_boost", "style", "use_speaker_boost", "speed")
    else:
        keys = tuple(subset)
    out: Dict[str, Any] = {}
    for k in keys:
        v = stored.get(k)
        if v is not None:
            out[k] = v
    return out


def language_code_for(model_id: str, target_language: Optional[str]) -> Optional[str]:
    """language_code to send for this model + target language, or None.
    Model-aware: never sent to multilingual_v2 (officially unsupported); never
    sent when no target language was chosen."""
    if not target_language:
        return None
    caps = _caps(model_id)
    if caps.get("language_code"):
        return target_language
    return None


def model_max_text(model_id: str) -> int:
    """Hard per-request text limit for the model (from /v1/models). Falls back to
    a conservative 5000 if unknown."""
    return int(_caps(model_id).get("max_text", 5000))


def model_supports_context(model_id: str) -> bool:
    return bool(_caps(model_id).get("context", True))


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
    """Deterministic sanitized hash of the resolved TTS config (no key).

    V1.6.0: the hash now includes target_language, language_code, resolver_policy,
    and the EFFECTIVE (model-aware) voice settings actually sent — so a vi config
    and an en config for the same voice hash differently when they differ. No API
    key material is ever in the hash input."""
    eff = cfg.get("effective_voice_settings")
    if eff is None:
        eff = cfg.get("voice_settings")
    payload = {
        "voice_id": cfg.get("voice_id"),
        "target_language": cfg.get("target_language") or "",
        "model_id": cfg.get("model_id"),
        "effective_voice_settings": _norm_settings(eff),
        "language_code": cfg.get("language_code") or "",
        "output_format": cfg.get("requested_output_format"),
        "resolver_policy": cfg.get("resolver_policy") or cfg.get("sync_mode") or "",
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
    """GET /v1/models — list of models with full capability info. Cached ~30 min.

    V1.6.0: each model retains the languages array + capability flags (can_use_style,
    can_use_speaker_boost, maximum_text_length_per_request, description) so the
    language-compatibility guard can verify target-language support from LIVE
    official evidence (never from the model name). Returns {ok, models}.
    """
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
    models = []
    for m in (data or []):
        mid = m.get("model_id")
        langs = [L.get("language_id") for L in (m.get("languages") or [])
                 if isinstance(L, dict) and L.get("language_id")]
        models.append({
            "name": m.get("name"), "model_id": mid,
            "can_do_text_to_speech": m.get("can_do_text_to_speech"),
            "can_use_style": m.get("can_use_style"),
            "can_use_speaker_boost": m.get("can_use_speaker_boost"),
            "can_be_finetuned": m.get("can_be_finetuned"),
            "maximum_text_length_per_request": m.get("maximum_text_length_per_request"),
            "description": m.get("description"),
            "languages": langs,
            "deprecated": MODEL_CAPS.get(mid, {}).get("deprecated", False),
        })
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


def _live_model(model_id: str, refresh: bool = False) -> Optional[Dict[str, Any]]:
    """The live /v1/models entry for model_id, or None."""
    r = get_models(refresh=refresh)
    if not r.get("ok"):
        return None
    for m in r["models"]:
        if m.get("model_id") == model_id:
            return m
    return None


def model_supports_language(model_id: str, language_code: str,
                            refresh: bool = False) -> bool:
    """Live check: is `language_code` in the model's /v1/models languages list?
    Never trusts the model name (e.g. 'multilingual'). If the models API is
    unavailable, returns False (fail-closed — no fabricated compatibility)."""
    m = _live_model(model_id, refresh=refresh)
    if not m:
        return False
    return language_code in (m.get("languages") or [])


def get_voice_metadata(voice_id: str, refresh: bool = False) -> Dict[str, Any]:
    """GET /v1/voices/{voice_id} — full public voice metadata, sanitized (no key).
    Keeps the language-relevant fields: name, labels, category, description,
    verified_languages, fine_tuning, high_quality_base_model_ids. Cached 10 min;
    refresh bypasses. Fails closed (never substitutes another voice)."""
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty."}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured."}
    ck = ("voice_meta", vid)
    if not refresh:
        c = _cache_get(ck)
        if c is not None:
            return {"ok": True, "metadata": c, "cached": True}
    url = config.ELEVENLABS_VOICE_URL.format(voice_id=vid)
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
        return {"ok": False, "error": "Unreadable voice metadata response."}
    ft = d.get("fine_tuning") or {}
    meta = {
        "voice_id": d.get("voice_id") or vid,
        "name": d.get("name") or "",
        "category": d.get("category") or "",
        "labels": d.get("labels") or {},
        "description": d.get("description") or "",
        "verified_languages": d.get("verified_languages") or [],
        "high_quality_base_model_ids": d.get("high_quality_base_model_ids") or [],
        "fine_tuning_language": ft.get("language"),
        "fine_tuning_state": ft.get("state") or {},
        "is_legacy": d.get("is_legacy"),
    }
    _cache_set(ck, meta, 600)
    return {"ok": True, "metadata": meta, "cached": False}


def check_compatibility(voice_id: str, model_id: str, target_language: str,
                       refresh: bool = False) -> Dict[str, Any]:
    """Live capability guard (Part 3). Verifies the selected model:
      - exists in /v1/models and is TTS-capable (model_available, tts_capable)
      - officially supports target_language (language_supported) — from LIVE
        /v1/models languages, never the model name
      - voice_compatible: 'verified' if (model,language) is in the voice's
        verified_languages; 'hq_base' if in high_quality_base_model_ids; else
        None (unknown — a soft signal, never fabricated, never a hard block)
      - model_deprecated: from MODEL_CAPS (legacy superseded models)
    Models API unavailable -> ok=False (fail-closed; no fabricated compatibility).
    Returns {ok, compatibility, reasons}. `ok` reflects whether the guard could
    run; the caller decides pass/fail from the compatibility fields."""
    vid = (voice_id or "").strip()
    mid = (model_id or "").strip()
    lang = (target_language or "").strip()
    compat = {"model_available": False, "tts_capable": False,
              "language_supported": False, "voice_compatible": None,
              "model_deprecated": bool(MODEL_CAPS.get(mid, {}).get("deprecated", False))}
    reasons: List[str] = []
    if not mid:
        return {"ok": False, "compatibility": compat, "reasons": ["No model selected."]}
    if not lang:
        return {"ok": False, "compatibility": compat, "reasons": ["No target language."]}
    m = _live_model(mid, refresh=refresh)
    if not m:
        reasons.append("Models API unavailable or model not found — cannot verify compatibility.")
        return {"ok": False, "compatibility": compat, "reasons": reasons}
    compat["model_available"] = True
    compat["tts_capable"] = bool(m.get("can_do_text_to_speech"))
    if not compat["tts_capable"]:
        reasons.append(f"{mid} is not TTS-capable.")
    compat["language_supported"] = lang in (m.get("languages") or [])
    if not compat["language_supported"]:
        reasons.append(f"{mid} does not officially support language '{lang}'.")
    # Voice compatibility — soft signal from official metadata only.
    vm = get_voice_metadata(vid, refresh=refresh)
    if vm.get("ok"):
        meta = vm["metadata"]
        vl = meta.get("verified_languages") or []
        if any((v.get("language") == lang and v.get("model_id") == mid) for v in vl
               if isinstance(v, dict)):
            compat["voice_compatible"] = "verified"
        elif mid in (meta.get("high_quality_base_model_ids") or []):
            compat["voice_compatible"] = "hq_base"
    return {"ok": True, "compatibility": compat, "reasons": reasons}


def _guard_passes(compat: Dict[str, Any]) -> bool:
    """Hard requirements for auto-generation: model available + TTS-capable +
    language supported. voice_compatible is a preference signal, not a block."""
    c = compat.get("compatibility", {}) if "compatibility" in compat else compat
    return bool(c.get("model_available") and c.get("tts_capable")
                and c.get("language_supported"))


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


def _finalize(cfg: Dict[str, Any], model_id: str, stored_settings: Dict[str, Any],
              output_format: str, target_language: Optional[str],
              refresh: bool = False) -> None:
    """Fill the model-aware, language-aware fields of a resolved config in place:
    effective_voice_settings (only the model-supported subset), language_code
    (only if the model accepts it), master_storage_format, compatibility (when a
    target language is set), and the deterministic tts_config_hash."""
    cfg["model_id"] = model_id
    cfg["effective_voice_settings"] = effective_voice_settings(model_id, stored_settings)
    cfg["language_code"] = language_code_for(model_id, target_language)
    cfg["master_storage_format"] = _master_storage_format(output_format)
    if target_language:
        g = check_compatibility(cfg["voice_id"], model_id, target_language, refresh)
        cfg["compatibility"] = g.get("compatibility")
        cfg["compatibility_reasons"] = g.get("reasons")
    cfg["tts_config_hash"] = tts_config_hash(cfg)


def _pick_language_model(vid: str, lang: str,
                         refresh: bool = False) -> Tuple[Optional[str], str]:
    """Priority 5 — pick a model for (voice, language) from official live evidence.
    Returns (model_id, source). Prefers a verified_languages model for this voice
    (BEST_VOICE_MATCH); else a non-deprecated available TTS model that supports
    the language, preferring the Studio default when it qualifies. Never invents
    certainty: returns (None, reason) if no model supports the language."""
    r = get_models(refresh=refresh)
    if not r.get("ok"):
        return None, "models_api_unavailable"
    models = {m["model_id"]: m for m in r["models"]
              if m.get("can_do_text_to_speech") and lang in (m.get("languages") or [])}
    if not models:
        return None, "no_model_supports_language"
    vm = get_voice_metadata(vid, refresh=refresh)
    verified_mids: List[str] = []
    if vm.get("ok"):
        for v in (vm["metadata"].get("verified_languages") or []):
            if isinstance(v, dict) and v.get("language") == lang:
                mid = v.get("model_id")
                if mid in models and not MODEL_CAPS.get(mid, {}).get("deprecated", False):
                    verified_mids.append(mid)
    default_mid = model_id()
    # BEST_VOICE_MATCH: among the officially-verified models for this voice+
    # language, prefer the Studio production default when it is itself verified
    # (it is the product's chosen default and is officially verified here), else
    # the first verified model. Never invents certainty when none is verified.
    if default_mid in verified_mids:
        return default_mid, "VERIFIED_LANGUAGE"
    if verified_mids:
        return verified_mids[0], "VERIFIED_LANGUAGE"
    if default_mid in models and not MODEL_CAPS.get(default_mid, {}).get("deprecated", False):
        return default_mid, "STUDIO_LANGUAGE_POLICY"
    for mid in models:
        if not MODEL_CAPS.get(mid, {}).get("deprecated", False):
            return mid, "STUDIO_LANGUAGE_POLICY"
    # No non-deprecated compatible model — surface a legacy one, honestly marked.
    return next(iter(models)), "LEGACY_COMPATIBILITY"


def resolve_config(voice_id: str, mode: str = "auto_current",
                   history_item_id: Optional[str] = None,
                   overrides: Optional[Dict[str, Any]] = None,
                   voice_name: Optional[str] = None,
                   refresh: bool = False,
                   target_language: Optional[str] = None,
                   resolver_policy: Optional[str] = None) -> Dict[str, Any]:
    """Resolve an explicit TTS config for (Voice ID, Target Language, Resolver Policy).

    V1.6.0 — language-aware. Generic: no voice-id special-casing, no global
    `language -> model` hardcode. The Thanh+vi->eleven_v3 preference lives as a
    DATA row in voice_model_profiles, looked up generically by (voice_id, language).

    Priority order (Part 4):
      P1 manual        — advanced override (mode='manual'); compatibility-guarded.
      P2 human profile — a HUMAN_BENCHMARK_APPROVED profile for (voice, language),
                         used only while its model still passes the live guard.
      P3 history_match  — Mode B exact public config of a selected history item;
                         rejected if its model is incompatible with the language.
      P4 auto_current   — Mode A: current API settings + a matching-history item
                         whose model also passes the language guard.
      P5 language policy — construct candidates from available ∩ TTS ∩ language ∩
                         non-deprecated; prefer a verified_languages model
                         (BEST_VOICE_MATCH); else Studio default if compatible.

    target_language=None preserves the exact V1.5.0 behavior (no language guard,
    no language_code, no profile lookup) so existing callers/tests are unaffected.

    Returns {ok, config} with per-field provenance + tts_config_hash, or
    {ok:False, error, ...} (fail-closed on settings-API failure; incompatible-model
    returns ok=False with incompatible=True so the UI can warn, not silently gen).
    """
    vid = (voice_id or "").strip()
    if not vid:
        return {"ok": False, "error": "Voice ID is empty.", "fail_closed": True}
    if not is_configured():
        return {"ok": False, "error": "ElevenLabs API key not configured.",
                "fail_closed": True}
    tl = (target_language or "").strip().lower() or None
    rpol = resolver_policy or mode
    cfg: Dict[str, Any] = {
        "voice_id": vid, "voice_name": voice_name,
        "target_language": tl, "resolver_policy": rpol,
        "sync_mode": mode, "config_ts": int(time.time()),
        "provenance": {"voice_id": "USER_SELECTION"},
        "history_item_id": None,
    }
    if tl:
        cfg["provenance"]["target_language"] = "USER_SELECTION"

    # ---- Mode B / Priority 3 ------------------------------------------------ #
    if mode == "history_match":
        if not history_item_id:
            return {"ok": False, "error": "No history item selected.", "fail_closed": True}
        item = get_history_item(history_item_id)
        if not item.get("ok"):
            return {"ok": False, "error": item.get("error", "History item unavailable."),
                    "fail_closed": False}
        h = item["item"]
        mid = h.get("model_id") or model_id()
        stored = h.get("settings") or _norm_settings({})
        out = h.get("output_format") or config.ELEVENLABS_OUTPUT_FORMAT
        if tl:
            g = check_compatibility(vid, mid, tl, refresh)
            if not _guard_passes(g):
                return {"ok": False,
                        "error": f"Model '{mid}' không được xác nhận phù hợp với ngôn ngữ '{tl}'.",
                        "incompatible": True, "compatibility": g.get("compatibility"),
                        "reasons": g.get("reasons")}
        cfg["history_item_id"] = history_item_id
        cfg["voice_settings"] = stored
        cfg["requested_output_format"] = out
        cfg["match_strength"] = "history_item"
        cfg["provenance"].update({"model_id": "ELEVENLABS_HISTORY_ITEM",
                                  "voice_settings": "ELEVENLABS_HISTORY_ITEM",
                                  "output_format": "ELEVENLABS_HISTORY_ITEM"})
        _finalize(cfg, mid, stored, out, tl, refresh)
        return {"ok": True, "config": cfg}

    # ---- Mode C / Priority 1 — manual override ------------------------------ #
    if mode == "manual":
        ov = overrides or {}
        mid = ov.get("model_id", model_id())
        stored = _norm_settings(ov.get("voice_settings"))
        out = ov.get("output_format", config.ELEVENLABS_OUTPUT_FORMAT)
        if tl:
            g = check_compatibility(vid, mid, tl, refresh)
            if not _guard_passes(g):
                return {"ok": False,
                        "error": f"Model '{mid}' không được xác nhận phù hợp với ngôn ngữ '{tl}'.",
                        "incompatible": True, "compatibility": g.get("compatibility"),
                        "reasons": g.get("reasons"),
                        "user_override_incompatible": True}
        cfg["voice_settings"] = stored
        cfg["requested_output_format"] = out
        cfg["match_strength"] = "manual"
        cfg["provenance"].update({"model_id": "USER_MANUAL",
                                  "voice_settings": "USER_MANUAL",
                                  "output_format": "USER_MANUAL"})
        _finalize(cfg, mid, stored, out, tl, refresh)
        return {"ok": True, "config": cfg}

    # ---- Mode A / auto_current --------------------------------------------- #
    # 1) Current stored voice settings (fail-closed on API failure).
    vs = get_voice_settings(vid, refresh=refresh)
    if not vs.get("ok"):
        return {"ok": False, "error": vs.get("error", "Không thể đồng bộ cấu hình ElevenLabs."),
                "fail_closed": True, "stage": "settings_api_failed"}
    stored = vs["settings"]
    cfg["voice_settings"] = stored
    cfg["provenance"]["voice_settings"] = "ELEVENLABS_VOICE_SETTINGS_API"

    if tl:
        # Priority 2 — human-approved (voice, language) profile.
        try:
            from . import db
            prof = db.get_profile(vid, tl)
        except Exception:
            prof = None
        if prof:
            mid = prof["preferred_model_id"]
            g = check_compatibility(vid, mid, tl, refresh)
            if _guard_passes(g):
                out = prof.get("output_format") or _HQ_OUTPUT_FORMAT
                src = prof.get("selection_source") or "USER_MANUAL"
                cfg["requested_output_format"] = out
                cfg["match_strength"] = "human_approved_profile"
                cfg["resolver_source"] = src
                cfg["profile"] = {"selection_source": src,
                                  "approved_at": prof.get("approved_at"),
                                  "notes": prof.get("notes")}
                cfg["provenance"].update({
                    "model_id": src,
                    "output_format": src if prof.get("output_format") else "STUDIO_LANGUAGE_POLICY",
                    "target_language": "USER_SELECTION"})
                _finalize(cfg, mid, stored, out, tl, refresh)
                _persist_language_config(vid, tl, cfg)
                return {"ok": True, "config": cfg}

        # Priority 4 — current settings + matching history (model must pass guard).
        match = None
        hist = get_voice_history(vid, limit=10, refresh=refresh)
        if hist.get("ok"):
            for it in hist["items"]:
                if not it.get("model_id"):
                    continue
                if _settings_match(it.get("settings"), stored):
                    cand_mid = it["model_id"]
                    if not _guard_passes(check_compatibility(vid, cand_mid, tl, refresh)):
                        continue  # History Rule: incompatible history is skipped
                    det = get_history_item(it["history_item_id"])
                    ofmt = ((det.get("item") or {}).get("output_format")
                            if det.get("ok") else None) or "pcm_16000"
                    match = {"model_id": cand_mid, "output_format": ofmt,
                             "history_item_id": it["history_item_id"]}
                    break
        if match:
            cfg["requested_output_format"] = match["output_format"]
            cfg["history_item_id"] = match["history_item_id"]
            cfg["match_strength"] = "history_matched"
            cfg["provenance"].update({"model_id": "MATCHING_HISTORY_GENERATION",
                                      "output_format": "MATCHING_HISTORY_GENERATION"})
            _finalize(cfg, match["model_id"], stored, match["output_format"], tl, refresh)
            _persist_language_config(vid, tl, cfg)
            return {"ok": True, "config": cfg}

        # Priority 5 — verified-language policy.
        mid, src = _pick_language_model(vid, tl, refresh)
        if not mid:
            return {"ok": False, "error": f"Không có model nào hỗ trợ ngôn ngữ '{tl}'.",
                    "unsupported_language": True}
        out = _HQ_OUTPUT_FORMAT
        cfg["requested_output_format"] = out
        cfg["match_strength"] = "verified_language_policy" if src == "VERIFIED_LANGUAGE" else "language_policy"
        cfg["resolver_source"] = src
        cfg["provenance"].update({"model_id": src, "output_format": src,
                                  "target_language": "USER_SELECTION"})
        _finalize(cfg, mid, stored, out, tl, refresh)
        _persist_language_config(vid, tl, cfg)
        return {"ok": True, "config": cfg}

    # ---- V1.5.0 behavior (no target language) ------------------------------- #
    match = None
    hist = get_voice_history(vid, limit=10, refresh=refresh)
    if hist.get("ok"):
        for it in hist["items"]:
            if not it.get("model_id"):
                continue
            if _settings_match(it.get("settings"), stored):
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
        cfg["model_id"] = model_id()
        cfg["requested_output_format"] = config.ELEVENLABS_OUTPUT_FORMAT
        cfg["match_strength"] = "settings_only"
        cfg["provenance"].update({"model_id": "STUDIO_POLICY",
                                  "output_format": "STUDIO_POLICY"})
    _finalize(cfg, cfg["model_id"], stored,
              cfg["requested_output_format"], None, refresh)
    return {"ok": True, "config": cfg}


def _persist_language_config(vid: str, lang: str, cfg: Dict[str, Any]) -> None:
    """Remember the resolved config keyed by (voice_id, language_code,
    resolver_policy). Best-effort; never fails the resolve on a DB error."""
    try:
        from . import db
        db.save_voice_language_config(vid, lang, cfg.get("resolver_policy") or "auto_current", cfg)
    except Exception:
        pass


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
                  cfg: Dict[str, Any],
                  previous_text: Optional[str] = None,
                  next_text: Optional[str] = None) -> bytes:
    """Synthesize one text chunk with the RESOLVED config. V1.6.0:
      - sends the EFFECTIVE (model-aware) voice_settings subset only — v3 omits
        similarity_boost/style/use_speaker_boost/speed; v2/v2.5 sends all 5
      - sends language_code only when the model supports it (never to
        multilingual_v2)
      - sends previous_text/next_text only when the model supports official
        context fields and a context value is provided (long-form continuity)
    Same fail-closed retries; never substitutes another voice. None values are
    omitted from the request body (let ElevenLabs use its defaults)."""
    vid = (voice_id or "").strip()
    if not vid:
        raise VoiceError("Voice ID is empty.")
    if not is_configured():
        raise TTSUnavailable("ElevenLabs API key not configured.")
    if not text.strip():
        raise VoiceError("Empty text.")
    mid = cfg.get("model_id") or model_id()
    # Effective (model-aware) settings; fall back to voice_settings for legacy cfgs.
    vs = cfg.get("effective_voice_settings")
    if vs is None:
        vs = cfg.get("voice_settings") or {}
    voice_settings = {k: v for k, v in vs.items() if v is not None}
    body: Dict[str, Any] = {
        "text": text,
        "model_id": mid,
        "voice_settings": voice_settings,
    }
    lc = cfg.get("language_code")
    if lc:
        body["language_code"] = lc
    # Context: only official fields, only when the model supports them and a
    # value is supplied. Never send undocumented parameters.
    if model_supports_context(mid):
        if previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text
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


# --------------------------------------------------------------------------- #
# V1.6.0 — semantic chunking (long-form TTS)                                   #
# --------------------------------------------------------------------------- #
# Boundary positions for semantic chunking. We record candidate split points
# (positions where a higher-priority boundary ends) and greedily fill a chunk
# up to max_chars, breaking at the latest candidate <= max_chars. The
# concatenation of all chunks EXACTLY equals the input text — no characters are
# dropped, duplicated, reordered, or normalized. We never split inside a word,
# number, or punctuation sequence when a sentence/clause boundary fits.
_PARA_RE = re.compile(r"\n\s*\n")
_SENT_RE = re.compile(r"[.!?…]+[\s\n]+")
_CLAUSE_RE = re.compile(r"[,;:][\s\n]+")


def _boundary_positions(text: str) -> List[int]:
    """Sorted positions (end indices) of paragraph/sentence/clause boundaries,
    plus the final text length. Used as candidate split points."""
    pts: List[int] = []
    for rx in (_PARA_RE, _SENT_RE, _CLAUSE_RE):
        for m in rx.finditer(text):
            pts.append(m.end())
    pts.append(len(text))
    # de-dup + sort
    return sorted(set(pts))


def semantic_chunks(text: str, max_chars: int) -> List[str]:
    """Split `text` into chunks of at most `max_chars` at semantic boundaries
    (paragraph -> sentence -> clause -> safe space). Guarantee: the exact
    concatenation of the returned chunks equals `text` (text integrity). A
    chunk longer than max_chars with no internal boundary is split at the last
    whitespace before max_chars (never inside a token unless the token itself
    exceeds max_chars)."""
    text = text or ""
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    bounds = _boundary_positions(text)
    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        if n - i <= max_chars:
            chunks.append(text[i:])
            break
        # latest semantic boundary within [i+1, i+max_chars]
        end_limit = i + max_chars
        chosen = None
        for b in bounds:
            if b <= i:
                continue
            if b > end_limit:
                break
            chosen = b
        if chosen and chosen > i:
            chunks.append(text[i:chosen])
            i = chosen
            continue
        # No semantic boundary fits -> split at the last whitespace before the
        # limit (never inside a word). The space stays in the left chunk so the
        # exact concatenation is preserved. If the next word itself is longer
        # than max_chars, split hard at max_chars as a last resort.
        window = text[i:end_limit]
        ws = window.rfind(" ")
        if ws > 0:
            cut = i + ws + 1  # cut just after the space (space stays in left chunk)
            chunks.append(text[i:cut])
            i = cut
        else:
            chunks.append(text[i:end_limit])
            i = end_limit
    # Integrity guarantee: reconstruction must equal the original text.
    if "".join(chunks) != text:
        # Fallback: the splitter must never silently alter text. If a future
        # edge case breaks the invariant, fall back to exact slicing by max_chars
        # rather than emit altered content.
        chunks = [text[k:k + max_chars] for k in range(0, len(text), max_chars)]
    return chunks


def synth_master_cond(voice_id: str, text: str, cfg: Dict[str, Any],
                      out_master: str, out_cond: str,
                      max_chars_override: Optional[int] = None) -> Tuple[str, str, float]:
    """Synthesize `text` with the resolved config, producing TWO files:
      - out_master: a LOSSLESS WAV at the native sample rate of the resolved
        requested_output_format (e.g. 44.1 kHz for mp3_44100_128). Used for the
        final MP4 audio. NEVER downsampled to 16 kHz; never kept as MP3.
      - out_cond:   a 16 kHz mono WAV derived from the master, for MuseTalk/
        Whisper conditioning only.

    V1.6.0 long-form hardening:
      - semantic chunking (paragraph -> sentence -> clause -> safe space) with a
        model-aware soft limit below the model's hard maximum_text_length_per_request
      - text integrity: the concatenation of all chunks EXACTLY equals the input
      - official context continuity (previous_text/next_text) across chunks where
        the model supports it; no undocumented parameters; no enormous context
      - each chunk decoded to lossless PCM before join (never MP3 byte concat)
    The ElevenLabs voice_id is used EXACTLY (fail-closed, no substitution).
    Returns (out_master, out_cond, duration_sec) (duration from the 16k cond).
    """
    text = (text or "").strip()
    if not text:
        raise VoiceError("Nothing to synthesize (empty script).")
    ofmt = cfg.get("requested_output_format") or config.ELEVENLABS_OUTPUT_FORMAT
    sr = _output_sample_rate(ofmt)
    mid = cfg.get("model_id") or model_id()
    # Model-aware soft target: stay below the model's hard per-request limit.
    # max_chars_override is TEST/DIAGNOSTIC ONLY (forces multi-chunking of a short
    # script to exercise the real chunk/context/join path). When None, normal
    # production behavior is unchanged.
    hard = model_max_text(mid)
    if max_chars_override and max_chars_override > 0:
        max_chars = max_chars_override
    else:
        max_chars = min(config.TTS_MAX_TEXT_CHARS, max(500, hard - 200))
    chunks = semantic_chunks(text, max_chars)
    if not chunks:
        chunks = [text[:max_chars]]
    use_ctx = model_supports_context(mid) and len(chunks) > 1
    master_parts: List[np.ndarray] = []
    cond_parts: List[np.ndarray] = []
    for idx, ch in enumerate(chunks):
        prev_t = chunks[idx - 1] if (use_ctx and idx > 0) else None
        next_t = chunks[idx + 1] if (use_ctx and idx < len(chunks) - 1) else None
        # Cap context to a reasonable window (no enormous previous_text).
        if prev_t and len(prev_t) > 600:
            prev_t = prev_t[-600:]
        if next_t and len(next_t) > 600:
            next_t = next_t[:600]
        raw = _synth_config(voice_id, ch, cfg, previous_text=prev_t, next_text=next_t)
        master_parts.append(_decode_to_float(raw, ofmt, sr))
        cond_parts.append(_decode_to_float(raw, ofmt, 16000))
    master = np.concatenate(master_parts) if master_parts else np.zeros(0, dtype=np.float32)
    cond = np.concatenate(cond_parts) if cond_parts else np.zeros(0, dtype=np.float32)
    sf.write(out_master, master, sr, subtype="FLOAT")
    sf.write(out_cond, cond, 16000, subtype="FLOAT")
    info = sf.info(out_cond)
    return out_master, out_cond, float(info.duration)