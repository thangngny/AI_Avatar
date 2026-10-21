"""Standalone Edge TTS client for the studio controller — the FREE TEST voice.

This is the second user-facing voice path (spec V1.1.5 Part B). It is intended
ONLY for mouth-motion / mask / lipsync TESTING, not final voice production. It
requires NO API key and consumes NO ElevenLabs quota.

CRITICAL CONTRACT (spec Part B/C):
  * Edge TTS and ElevenLabs are EXPLICIT, separate providers. There is NO
    silent fallback between them. If Edge TTS fails -> surface an honest error;
    never silently call ElevenLabs. If ElevenLabs fails -> never use Edge.
  * Edge TTS audio is normalized through the SAME canonical master-audio path
    (16 kHz mono FLOAT wav) as ElevenLabs, then fed to the SAME production
    renderer (generate_video_from_script.py). It does NOT create a second
    lipsync engine and does NOT change the MuseTalk v1.5 truth.
  * Only the test TEXT is sent to the Edge TTS online service. No API keys,
    avatar video, or prepared images are ever sent (spec Part I).

Implementation reuses the established `edge_tts` Python package (already a
project dependency, and already used by the realtime `tts/edge.py`). This is
NOT a second Edge TTS architecture: the realtime `tts/edge.py` is a streaming
BaseTTS for the live avatar; this module is the offline batch wrapper for the
studio controller, mirroring `elevenlabs_client`'s interface so
`render_service` can treat both providers uniformly.

Voice tuning is intentionally FIXED (rate/pitch/volume = +0) so mouth-motion
comparisons stay consistent (spec B6).
"""
import asyncio
import io
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

try:
    import edge_tts
    from edge_tts.exceptions import NoAudioReceived
    _EDGE_OK = True
except Exception:  # pragma: no cover - env without edge_tts
    edge_tts = None
    NoAudioReceived = Exception
    _EDGE_OK = False

from utils.logger import logger

# Canonical master-audio format expected by the production renderer (matches
# elevenlabs_client.synth_to_wav: 16 kHz mono FLOAT wav).
SAMPLE_RATE = 16000

# Fixed Vietnamese test voices (spec B5). Do not assume availability forever;
# list_voices() fetches dynamically and falls back to these.
DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
KNOWN_VOICES: Dict[str, Dict[str, str]] = {
    "vi-VN-HoaiMyNeural": {"name": "Hoài My", "gender": "Female", "label": "Nữ — Hoài My"},
    "vi-VN-NamMinhNeural": {"name": "Nam Minh", "gender": "Male", "label": "Nam — Nam Minh"},
}


class EdgeTTSUnavailable(RuntimeError):
    """Raised when Edge TTS is not installed / unreachable. The controller must
    NOT fall back to ElevenLabs."""


def is_available() -> bool:
    """True if the edge_tts package is importable. Does NOT probe the network."""
    return _EDGE_OK


def _run_coro(coro):
    """Run an async coroutine in a fresh event loop (the studio controller is
    synchronous). Mirrors tts/edge.py._run_coro."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            asyncio.set_event_loop(None)
            loop.close()


async def _fetch_voices() -> List[Dict[str, Any]]:
    """Fetch the live voice list from Edge TTS and filter to Vietnamese."""
    raw = await edge_tts.list_voices()
    out = []
    for v in raw:
        locale = (v.get("ShortName") or v.get("Locale") or "").upper()
        if locale.startswith("VI-VN"):
            out.append({
                "voice_id": v.get("ShortName") or v.get("Locale"),
                "name": v.get("ShortName", "").replace("vi-VN-", "").replace("Neural", ""),
                "gender": v.get("Gender", ""),
                "label": _voice_label(v.get("ShortName"), v.get("Gender")),
            })
    return out


def _voice_label(voice_id: Optional[str], gender: str) -> str:
    vid = (voice_id or "").replace("vi-VN-", "").replace("Neural", "")
    g = "Nữ" if (gender or "").lower().startswith("f") else ("Nam" if (gender or "").lower().startswith("m") else "")
    known = KNOWN_VOICES.get(voice_id or "")
    if known:
        return known["label"]
    return f"{g} — {vid}".strip(" —")


def list_voices() -> Dict[str, Any]:
    """Return {ok, voices: [{voice_id, name, gender, label}], default, fallback}.

    Fetches the live Vietnamese voice list from Edge TTS. If the network call
    fails but the package is installed and a known configured voice still
    works, return the known voices with `dynamic: False` (honest about it).
    Never fabricates voices that are not either returned live or in the known
    configured set."""
    if not _EDGE_OK:
        return {"ok": False, "error": "edge-tts package not installed.",
                "voices": [], "default": DEFAULT_VOICE}
    try:
        voices = _run_coro(_fetch_voices())
    except Exception as e:
        logger.warning("edge_tts list_voices failed (%s); falling back to known voices", e)
        voices = [{"voice_id": vid, "name": m["name"], "gender": m["gender"], "label": m["label"]}
                  for vid, m in KNOWN_VOICES.items()]
        return {"ok": True, "voices": voices, "default": DEFAULT_VOICE,
                "dynamic": False, "fallback_reason": str(e)}
    if not voices:
        # Live list returned no vi-VN voices; fall back to known configured.
        voices = [{"voice_id": vid, "name": m["name"], "gender": m["gender"], "label": m["label"]}
                  for vid, m in KNOWN_VOICES.items()]
        return {"ok": True, "voices": voices, "default": DEFAULT_VOICE,
                "dynamic": False, "fallback_reason": "no vi-VN voices returned live"}
    return {"ok": True, "voices": voices, "default": DEFAULT_VOICE, "dynamic": True}


async def _synthesize(voice: str, text: str, rate: str, pitch: str, volume: str, max_retries: int = 5) -> bytes:
    """Synthesize text -> raw audio bytes (MP3 stream from Edge TTS) with retry."""
    import tempfile, os
    last_err = None
    for attempt in range(1, max_retries + 1):
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
            await communicate.save(tmp_path)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                if attempt > 1:
                    logger.info("edge_tts recovered at attempt %d/%d for voice=%s", attempt, max_retries, voice)
                return data
            last_err = f"Edge TTS returned 0 bytes for voice={voice}."
        except NoAudioReceived as e:
            last_err = f"Edge TTS returned no audio for voice={voice}."
        except EdgeTTSUnavailable:
            raise
        except Exception as e:
            last_err = f"Edge TTS error: {e}"
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        logger.warning("edge_tts attempt %d/%d failed for voice=%s: %s", attempt, max_retries, voice, last_err)
        if attempt < max_retries:
            await asyncio.sleep(0.5 * attempt)

    raise EdgeTTSUnavailable(f"Edge TTS returned no audio for voice={voice}. ({last_err})")


def _decode_to_pcm(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Decode Edge TTS audio bytes -> mono float32 numpy array at the source
    sample rate, then the caller resamples to 16 kHz. Mirrors tts/edge.py."""
    stream, sr = sf.read(io.BytesIO(audio_bytes))  # float64
    stream = stream.astype(np.float32)
    if stream.ndim > 1:
        stream = stream[:, 0]
    return stream, sr


def _resample_to_16k(stream: np.ndarray, sr: int) -> np.ndarray:
    """Resample to the canonical 16 kHz master rate. Uses torchaudio if
    available (matches tts/edge.py); else a linear resample fallback so the
    controller (which may run outside the torch env) still works."""
    if sr == SAMPLE_RATE or stream.shape[0] == 0:
        return stream
    try:
        import torch
        from torchaudio.functional import resample as ta_resample
        _t = torch.from_numpy(np.ascontiguousarray(stream)).float()
        _t = ta_resample(_t, sr, SAMPLE_RATE)
        return _t.numpy()
    except Exception:
        # stdlib linear resample fallback (controller env without torch).
        n_out = int(round(stream.shape[0] * SAMPLE_RATE / sr))
        idx = np.linspace(0, stream.shape[0] - 1, n_out)
        i0 = np.floor(idx).astype(np.int64)
        i1 = np.minimum(i0 + 1, stream.shape[0] - 1)
        frac = (idx - i0).astype(np.float32)
        return stream[i0] * (1 - frac) + stream[i1] * frac


def synth_to_wav(voice: str, text: str, out_wav: str,
                 rate: str = "+0%", pitch: str = "+0Hz",
                 volume: str = "+0%") -> Tuple[str, float]:
    """Synthesize `text` with Edge TTS `voice` -> canonical 16 kHz mono FLOAT
    wav at out_wav. Returns (out_wav, duration_sec).

    Never falls back to ElevenLabs or to a different voice. Raises
    EdgeTTSUnavailable on any failure. Voice tuning defaults are FIXED at +0
    (spec B6) but accepted as params so comparisons stay explicit."""
    text = (text or "").strip()
    if not text:
        raise EdgeTTSUnavailable("Nothing to synthesize (empty text).")
    if not _EDGE_OK:
        raise EdgeTTSUnavailable("edge-tts package not installed.")
    voice = (voice or DEFAULT_VOICE).strip() or DEFAULT_VOICE

    audio_bytes = _run_coro(_synthesize(voice, text, rate, pitch, volume))
    stream, sr = _decode_to_pcm(audio_bytes)
    stream = _resample_to_16k(stream, sr)
    sf.write(out_wav, stream, SAMPLE_RATE, subtype="FLOAT")
    info = sf.info(out_wav)
    logger.info("edge_tts synth voice=%s text_len=%d -> %.2fs", voice, len(text), info.duration)
    return out_wav, float(info.duration)


def preview_voice(voice: str, text: str, out_wav: str,
                  target_sec: float = 9.0) -> Tuple[str, float]:
    """Generate ~target_sec of preview audio from the start of the text (word
    trim, no mid-word cut). Same canonical 16 kHz mono FLOAT wav output."""
    words = (text or "").split()
    # Vietnamese ~3 words/sec (config.WORDS_PER_SEC). Reuse the same estimate.
    target_words = max(1, int(target_sec * 3.0))
    trimmed = " ".join(words[:target_words])
    if not trimmed:
        trimmed = (text or "").strip()[:400]
    return synth_to_wav(voice, trimmed, out_wav)


def voice_label(voice_id: str) -> str:
    """Human label for a voice id, for history/result display."""
    m = KNOWN_VOICES.get(voice_id)
    if m:
        return m["label"]
    return voice_id or "Edge TTS"