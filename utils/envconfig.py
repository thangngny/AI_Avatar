###############################################################################
#  .env loader + typed env accessors — single source of truth.
#
#  Previously three near-identical copies lived in config.py, llm.py, and
#  tts/elevenlabs.py. They diverged subtly (e.g. elevenlabs.py did NOT override
#  existing os.environ keys, while config.py/llm.py forced NOBLE_RAG_*/AGENT_RAG_*
#  to always override). This module consolidates them with one rule:
#
#    - A key is set into os.environ only if it is NOT already present, EXCEPT
#      keys starting with NOBLE_RAG_ or AGENT_RAG_ which always override (so a
#      caller can force-refresh RAG endpoints without restarting the shell).
#
#  BOM handling: the project .env is sometimes saved UTF-8-with-BOM by Windows
#  editors. The BOM then prefixes the FIRST key line (e.g. "﻿# ELEVEN...")
#  and breaks startswith("#") / key parsing. We strip a leading BOM from the
#  whole file text before splitting lines.
###############################################################################

import os
from pathlib import Path

from utils.app_root import app_root

_ENV_LOADED = False
# Keys whose prefixes always override an existing os.environ value when loaded
# from .env (callers may force-refresh these without a shell restart).
_ALWAYS_OVERRIDE_PREFIXES = ("NOBLE_RAG_", "AGENT_RAG_")

# UTF-8 BOM (EF BB BF) — str form as Python reads it from a BOM-prefixed file.
_BOM = "﻿"


def load_env_file() -> None:
    """Load KEY=VALUE pairs from <repo>/.env into os.environ (idempotent).

    Existing os.environ values win, except NOBLE_RAG_*/AGENT_RAG_* keys which
    always overwrite. Quotes are stripped from values. Comments and blank lines
    are skipped. Safe to call multiple times.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path: Path = app_root() / ".env"
    if not env_path.exists():
        return

    raw = env_path.read_text(encoding="utf-8-sig")  # utf-8-sig strips a BOM if present
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        # Defensive: strip a stray BOM if utf-8-sig didn't (e.g. mid-file).
        if line.startswith(_BOM):
            line = line.lstrip(_BOM).strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        always_override = key.startswith(_ALWAYS_OVERRIDE_PREFIXES)
        if always_override or key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "") -> str:
    """Read a string env var, loading .env first. Empty -> default."""
    load_env_file()
    return os.getenv(name, default).strip()


def env_flag(name: str) -> bool:
    """Read a boolean env flag (1/true/yes/on)."""
    return env(name, "").strip().lower() in {"1", "true", "yes", "on"}


def env_bool(name: str, default: bool) -> bool:
    """Read a boolean env var with an explicit default when unset."""
    value = env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = env(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        from utils.logger import logger
        logger.warning("Invalid %s=%s, using %s", name, value, default)
        return default


def env_int(name: str, default: int) -> int:
    value = env(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        from utils.logger import logger
        logger.warning("Invalid %s=%s, using %s", name, value, default)
        return default