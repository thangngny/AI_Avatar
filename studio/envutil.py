"""Tiny .env loader + secret redaction. The controller never logs secrets.

Reads the project .env (the same file the realtime server / launcher uses),
exposes values to the rest of the studio package, and provides redaction
helpers so the ElevenLabs API key never reaches a response body or log line.
"""
import os
from typing import Optional

_LOADED = False
_ENV_PATH = None


def _resolve_env_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    # studio/ -> project root
    root = os.path.dirname(here)
    return os.path.join(root, ".env")


def load_env(force: bool = False) -> None:
    """Load .env into os.environ (without overriding already-set env vars
    unless force=True). Safe to call repeatedly."""
    global _LOADED, _ENV_PATH
    if _LOADED and not force:
        return
    path = _resolve_env_path()
    _ENV_PATH = path
    if not os.path.exists(path):
        _LOADED = True
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if force or k not in os.environ:
                    os.environ[k] = v
    except Exception:
        # Never raise on a bad .env — the controller must stay alive.
        pass
    _LOADED = True


def env_str(key: str, default: str = "") -> str:
    load_env()
    return os.environ.get(key, default)


def env_int(key: str, default: int = 0) -> int:
    load_env()
    v = os.environ.get(key, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def env_bool(key: str, default: bool = False) -> bool:
    load_env()
    v = os.environ.get(key, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def redact_secret(value: Optional[str], visible: int = 4) -> str:
    """Show only the last `visible` chars of a secret, prefixed with bullets.
    Empty/None -> 'not set'."""
    if not value:
        return "not set"
    if len(value) <= visible:
        return "•" * len(value)
    return "•" * (len(value) - visible) + value[-visible:]


def mask_api_key() -> str:
    return redact_secret(env_str("ELEVENLABS_API_KEY"))