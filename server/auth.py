###############################################################################
#  Auth middleware + loopback gating for the LiveTalking API.
#
#  Threat model (pre-fix): the server binds 0.0.0.0:8010 with NO auth and CORS
#  "*" + credentials. Anyone who can reach the port can: drain ElevenLabs
#  credits via /human, change the API key via /settings/elevenlabs, kill the
#  process via /server/restart, delete avatars, and download recordings.
#
#  Post-fix policy (defense in depth):
#    1. If LIVETALKING_API_TOKEN is set -> every API route requires an
#       `X-LT-Token` header that compares equal (secrets.compare_digest).
#       Loopback (127.0.0.1/::1) is exempt so the local launcher / dashboard
#       keeps working without the browser knowing a token. A remote programmatic
#       client passes the header; a remote BROWSER (which cannot hold a secret)
#       must go through a reverse proxy / SSH tunnel — that is the correct
#       posture for exposing a no-auth-UI service.
#    2. If LIVETALKING_API_TOKEN is NOT set -> only loopback is allowed; any
#       non-loopback request is 401. This makes "forgot to set a token but bound
#       0.0.0.0" safe by default instead of wide open.
#    3. /health is always public (liveness probe).
#    4. Sensitive routes (restart, elevenlabs settings, open_folder) are
#       loopback-ONLY regardless of token — see require_loopback().
#
#  This module is intentionally self-contained (no import of rtc_manager /
#  session_manager) to avoid pulling the inference stack into the middleware
#  import graph.
###############################################################################

import ipaddress
import os
import secrets
from typing import Optional

from aiohttp import web

from utils.logger import logger
from utils.envconfig import env

# Routes that must stay public (liveness probe).
PUBLIC_PATHS = frozenset({"/health"})

_WARNED_NO_TOKEN = False


def remote_ip(request: web.Request) -> str:
    """Best-effort client IP. Honors X-Forwarded-For (first hop) when present
    (e.g. behind a reverse proxy), else request.remote."""
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return (request.remote or "").strip()


def is_loopback(value: str) -> bool:
    if not value:
        return False
    if value in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def configured_token() -> Optional[str]:
    """The expected API token, or None if auth is loopback-only."""
    return (env("LIVETALKING_API_TOKEN") or "").strip() or None


def require_loopback(request: web.Request) -> bool:
    """Return True if the request is from loopback, else emit a 403 response on
    the request and return False. Used to gate sensitive routes (restart,
    elevenlabs settings, open_folder) that must never be callable remotely even
    with a valid token."""
    if is_loopback(remote_ip(request)):
        return True
    logger.warning(
        "denied non-loopback access to sensitive route %s from %s",
        request.path, remote_ip(request),
    )
    request["loopback_denied"] = True
    return False


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Token-or-loopback gate for every request except PUBLIC_PATHS."""
    path = request.path
    # Static UI pages (served from web/) carry no data; allow them so the
    # dashboard HTML loads. API routes under known prefixes are gated below.
    if path in PUBLIC_PATHS:
        return await handler(request)

    ip = remote_ip(request)
    token = configured_token()

    if token is not None:
        # Token mode: accept a matching header, OR loopback (local UI).
        presented = request.headers.get("X-LT-Token", "")
        if secrets.compare_digest(presented, token) or is_loopback(ip):
            return await handler(request)
        logger.warning("denied unauthenticated %s from %s (token mismatch/missing)", path, ip)
        return web.Response(
            status=401,
            content_type="application/json",
            text='{"code":-1,"msg":"unauthorized: set X-LT-Token header"}',
        )

    # No token configured: loopback only.
    global _WARNED_NO_TOKEN
    if not _WARNED_NO_TOKEN:
        _WARNED_NO_TOKEN = True
        logger.warning(
            "LIVETALKING_API_TOKEN not set -> API restricted to loopback only. "
            "Set LIVETALKING_API_TOKEN to allow remote programmatic access."
        )
    if is_loopback(ip):
        return await handler(request)
    logger.warning("denied non-loopback %s from %s (no token configured)", path, ip)
    return web.Response(
        status=401,
        content_type="application/json",
        text='{"code":-1,"msg":"unauthorized: loopback only (set LIVETALKING_API_TOKEN)"}',
    )