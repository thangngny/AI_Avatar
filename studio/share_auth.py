"""Trusted-collaborator shared-access gate for the AI Avatar Studio.

This is a SINGLE shared access code + server-side session — NOT a permissions
system, NOT RBAC. After authenticating, the collaborator gets FULL Studio
access identical to the owner. The goal is only to stop random Internet users
who discover the public TryCloudflare URL from opening the Studio (spec §11,
§13, §14, §35).

Design rules (honored):
  * The access code lives IN MEMORY ONLY. It is never written to disk / runtime
    JSON (spec §29). Sessions are invalidated when the process restarts.
  * The code is generated with `secrets` (spec §13).
  * No correct code is ever placed in app.js (spec §13).
  * The gate is DISABLED by default (plain `run_studio.py` local use is
    unchanged — spec §33). It is enabled at share time by the launcher POSTing
    the generated code to the loopback-only `/api/share/enable` endpoint.
  * When enabled, requests that come directly from the owner's loopback (no
    Cloudflare `Cf-Connecting-IP` header) are EXEMPT — the owner never has to
    log in locally. The origin listens on 127.0.0.1 only, so this exemption is
    safe: no external attacker can reach the origin without going through
    cloudflared (which sets the header). Remote (tunnel) requests always
    require auth. `loopback_exempt` can be turned off for paranoid mode.

There is ONE application. This gate only decides whether a request may reach
the existing controller; it never forks features (spec §2, §37).
"""
import secrets
import threading
import time
from typing import Optional

_LOCK = threading.Lock()
_ENABLED = False
_CODE: Optional[str] = None
_LOOPBACK_EXEMPT = True
_ENABLED_AT: Optional[float] = None


def _format_code(raw: str) -> str:
    """Group a 12-char base32-ish string as XXXX-XXXX-XXXX for readability."""
    raw = raw.upper().replace("-", "")
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def generate_code() -> str:
    """Cryptographically random access code, format XXXX-XXXX-XXXX (12 chars,
    no ambiguous 0/O/1/I). Uses `secrets` (spec §13)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    return _format_code(raw)


def is_enabled() -> bool:
    with _LOCK:
        return _ENABLED


def loopback_exempt() -> bool:
    with _LOCK:
        return _LOOPBACK_EXEMPT


def get_code() -> Optional[str]:
    """The current in-memory code (only used by the login check; never
    surfaced to clients)."""
    with _LOCK:
        return _CODE


def enable(access_code: str, loopback_exempt: bool = True) -> None:
    with _LOCK:
        global _ENABLED, _CODE, _LOOPBACK_EXEMPT, _ENABLED_AT
        _ENABLED = True
        _CODE = (access_code or "").strip()
        _LOOPBACK_EXEMPT = bool(loopback_exempt)
        _ENABLED_AT = time.time()


def disable() -> None:
    with _LOCK:
        global _ENABLED, _CODE, _LOOPBACK_EXEMPT, _ENABLED_AT
        _ENABLED = False
        _CODE = None
        _LOOPBACK_EXEMPT = True
        _ENABLED_AT = None


def check_code(access_code: str) -> bool:
    with _LOCK:
        if not _ENABLED or not _CODE:
            return False
        # constant-time-ish compare
        return secrets.compare_digest((access_code or "").strip(), _CODE)