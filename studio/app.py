"""AI Avatar Studio — Flask application controller.

Exposes a clean /api/* contract and serves the static single-page UI. The
controller drives EXISTING production entrypoints as subprocesses; it has no
independent lip-sync truth and exposes no editable gain/ctx/offset/fps
controls. The ElevenLabs API key is read from .env and never returned in full.
"""
import os
import json
import re
import time
import subprocess
import shutil
import secrets
import hashlib
import math
from typing import Dict, Any

from flask import (Flask, request, jsonify, send_file, send_from_directory,
                   abort, Response, session, redirect, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config, db, gpu_service
from . import envutil
from . import avatar_service
from . import avatar_quality
from . import script_service
from . import render_service
from . import elevenlabs_client as el
from . import edge_tts_client as edge
from . import share_auth

app = Flask(__name__, static_folder=None)
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB upload cap
# Per-process signing key for the session cookie, generated with `secrets`
# and held IN MEMORY ONLY. Sessions are invalidated when the Studio process
# restarts (spec §13). Never persisted to disk.
app.secret_key = secrets.token_hex(32)
# Cookie hardening (spec §13). HttpOnly + SameSite=Lax are static. The Secure
# flag is set DYNAMICALLY per request (see _share_gate) to reflect proxy-
# terminated TLS: True only when the request arrived over HTTPS — which, behind
# the Cloudflare tunnel, is reported via X-Forwarded-Proto (made visible to
# Flask by ProxyFix below). Local loopback HTTP (owner-direct) is never given a
# Secure cookie, so local HTTP Studio behavior is unchanged.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # default for local/HTTP; set True per-request when behind TLS
)

# Trust EXACTLY ONE hop of Cloudflare's forwarded headers so request.is_secure /
# request.scheme / request.host reflect the browser-facing HTTPS URL, not the
# loopback HTTP hop from cloudflared to the origin.
#
# WHY THIS IS SAFE (do not widen it):
#   * The Studio origin binds to 127.0.0.1 only (run_studio.py host=127.0.0.1).
#     No external host can open a TCP connection to the origin, so no outside
#     attacker can inject X-Forwarded-* headers directly.
#   * The only forwarder is cloudflared running on the same host (loopback).
#     Cloudflare OVERWRITES Cf-Connecting-IP and X-Forwarded-Proto on the
#     edge; client-supplied values do not pass through.
#   * x_for=1 / x_proto=1 / x_host=1 trust a single proxy hop. A local process
#     could spoof X-Forwarded-Proto, but (a) that only affects the cookie Secure
#     flag — no authz impact — and (b) the owner's machine is a trusted
#     environment. The gate still keys off Cf-Connecting-IP (not spoofable from
#     outside) for owner-vs-tunnel discrimination.
# Do NOT raise these counts or expose the origin on 0.0.0.0.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

_WORKAROUND = None


# --------------------------------------------------------------------------- #
# Static UI                                                                   #
# --------------------------------------------------------------------------- #
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:fname>")
def static_root(fname):
    # Serve top-level static files (app.js, styles.css, favicon).
    safe = _safe_relpath(fname)
    if not safe:
        abort(404)
    return send_from_directory(STATIC_DIR, safe)


@app.route("/static/<path:fname>")
def static_sub(fname):
    safe = _safe_relpath(fname)
    if not safe:
        abort(404)
    return send_from_directory(STATIC_DIR, safe)


def _safe_relpath(fname: str) -> str:
    """Reject path traversal: only allow a simple relative filename inside
    STATIC_DIR (no .., no absolute, no separators that escape)."""
    if not fname or fname.startswith("/") or "\\" in fname or ".." in fname.split("/"):
        return ""
    return fname


# --------------------------------------------------------------------------- #
# Trusted-collaborator shared access gate                                     #
# --------------------------------------------------------------------------- #
# ONE application, ONE feature set. This gate only decides whether a request
# may reach the existing controller. It never forks local vs remote behavior
# (spec §2, §37). Disabled by default (plain local run_studio.py is unchanged).
#
# Auth model (spec §11/§13/§14/§35): a single in-memory access code + signed
# session cookie. After login the collaborator gets FULL Studio access. The
# owner's direct loopback access is exempt (no Cf-Connecting-IP header → the
# request did not come through the tunnel), so the owner never logs in locally
# even while sharing is enabled.

_PUBLIC_API = ("/api/auth/status", "/api/auth/login", "/api/share/status")


def _is_loopback(addr: str) -> bool:
    return addr in ("127.0.0.1", "::1", "localhost")


def _via_tunnel() -> bool:
    """True if the request reached the origin through the Cloudflare tunnel.

    cloudflared runs ON the owner's machine, so `request.remote_addr` is
    loopback for BOTH the owner and the tunnel — remote_addr cannot tell them
    apart. Cloudflare always sets `Cf-Connecting-IP` (and overwrites any
    client-supplied value), so its presence is a reliable tunnel indicator.
    Direct owner requests never have it."""
    return bool(request.headers.get("Cf-Connecting-IP"))


def _is_owner_direct() -> bool:
    """True for the owner browsing localhost directly (loopback, not via the
    tunnel). Used to gate owner-only admin endpoints and local-path disclosure."""
    return _is_loopback(request.remote_addr or "") and not _via_tunnel()


@app.before_request
def _share_gate():
    if not share_auth.is_enabled():
        return None
    # Reflect the browser-facing transport on the session cookie. Behind the
    # Cloudflare tunnel, X-Forwarded-Proto: https (made visible by ProxyFix)
    # makes request.is_secure True → the login cookie is emitted with Secure so
    # the browser only sends it over HTTPS. Local loopback HTTP (owner-direct,
    # exempt) stays is_secure=False → no Secure flag → local HTTP unaffected.
    # Mutated per request; safe under the Studio's low concurrency.
    app.config["SESSION_COOKIE_SECURE"] = bool(request.is_secure)
    # Owner direct loopback exemption: requests that did not traverse the
    # tunnel bypass the gate. Safe because the origin listens on 127.0.0.1
    # only — no external host can reach it without cloudflared.
    if share_auth.loopback_exempt() and not _via_tunnel():
        return None
    p = request.path
    # Public API + loopback admin endpoints (admin endpoints also check
    # loopback themselves below).
    if p in _PUBLIC_API or p.startswith("/api/auth/") or p.startswith("/api/share/"):
        return None
    if session.get("authed"):
        return None
    # Not authenticated.
    if p.startswith("/api/"):
        return jsonify({"ok": False, "error": "auth_required",
                        "require_auth": True}), 401
    # Browser navigation: serve the self-contained login page (for "/") or a
    # redirect to it for any other non-API path (stale SPA deep links).
    if p == "/login":
        return _login_page()
    if p == "/":
        return _login_page()
    return redirect("/login")


def _login_page() -> Response:
    html = """<!doctype html><html lang="vi" data-theme="dark"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AI Avatar Studio — Đăng nhập</title>
<style>
:root{--bg:#0e1116;--panel:#161b22;--border:#2a313c;--accent:#4f8cff;--good:#3fb950;--bad:#f85149;--muted:#8b949e;--text:#e6edf3}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh;align-items:center;justify-content:center}
.card{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:32px 30px;width:380px;max-width:92vw}
h1{font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:8px}
.muted{color:var(--muted);font-size:13px;margin-bottom:22px}
label{font-size:12px;color:var(--muted);display:block;margin-bottom:6px}
input{width:100%;padding:12px 14px;border-radius:8px;border:1px solid var(--border);background:#0d1117;color:var(--text);font-size:16px;letter-spacing:2px;text-align:center;outline:none}
input:focus{border-color:var(--accent)}
button{width:100%;margin-top:16px;padding:12px;border:0;border-radius:8px;background:var(--accent);color:#fff;font-size:15px;font-weight:600;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
.err{color:var(--bad);font-size:13px;margin-top:12px;min-height:18px}
.hint{color:var(--muted);font-size:11px;margin-top:18px;text-align:center;line-height:1.5}
</style></head><body>
<form class="card" id="f" autocomplete="off">
  <h1>🎬 AI Avatar Studio</h1>
  <div class="muted">Mã truy cập cộng sự</div>
  <label for="code">MÃ TRUY CẬP</label>
  <input id="code" name="code" placeholder="XXXX-XXXX-XXXX" autofocus required
   pattern="[A-Za-z0-9-]{6,}" title="Nhập mã truy cập được chia sẻ"/>
  <button type="submit" id="btn">ĐĂNG NHẬP</button>
  <div class="err" id="err"></div>
  <div class="hint">Truy cập đầy đủ Studio cho cộng sự đáng tin cậy.<br/>Avatar · ElevenLabs · Edge TTS · Render · History · Settings.</div>
</form>
<script>
const f=document.getElementById('f'),code=document.getElementById('code'),btn=document.getElementById('btn'),err=document.getElementById('err');
f.addEventListener('submit',async(e)=>{
  e.preventDefault();btn.disabled=true;err.textContent='';
  try{
    const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code.value.trim()})});
    const d=await r.json().catch(()=>({}));
    if(r.ok&&d.ok){window.location='/';return;}
    err.textContent=d.error||('Đăng nhập thất bại (HTTP '+r.status+').');
  }catch(x){err.textContent='Lỗi mạng — thử lại.';}
  finally{btn.disabled=false;}
});
</script>
</body></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route("/login")
def login_route():
    # Public route (also reached via the gate for unauthed browser nav).
    if not share_auth.is_enabled():
        return redirect("/")
    return _login_page()


@app.route("/api/auth/status")
def auth_status():
    return jsonify({"require_auth": share_auth.is_enabled(),
                    "loopback_exempt": share_auth.loopback_exempt(),
                    "via_tunnel": _via_tunnel()})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    if not share_auth.is_enabled():
        # Gate disabled → already full access; nothing to log into.
        return jsonify({"ok": True, "require_auth": False})
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Nhập mã truy cập."}), 400
    if not share_auth.check_code(code):
        # Constant, non-leaky failure. Do NOT reveal whether the gate is on.
        time.sleep(0.4)
        return jsonify({"ok": False, "error": "Mã truy cập không đúng."}), 401
    session.clear()
    session.permanent = False
    session["authed"] = True
    session["authed_at"] = time.time()
    return jsonify({"ok": True, "require_auth": True})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/share/status")
def share_status():
    """Public (no-auth) indicator the launcher/UI reads to know whether the
    share gate is active. Never returns the code or any secret."""
    return jsonify({"share_enabled": share_auth.is_enabled(),
                    "loopback_exempt": share_auth.loopback_exempt()})


@app.route("/api/share/enable", methods=["POST"])
def share_enable():
    """OWNER-DIRECT-ONLY admin endpoint. The Share launcher POSTs the freshly
    generated access code here to arm the gate. The code is held in memory only
    (spec §29). cloudflared is loopback, so remote_addr alone can't tell owner
    from tunnel — we additionally reject any request that arrived through the
    tunnel (Cf-Connecting-IP present)."""
    if not _is_owner_direct():
        return jsonify({"ok": False, "error": "owner-direct only"}), 403
    data = request.get_json(silent=True) or {}
    code = (data.get("access_code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "access_code required"}), 400
    loopback_exempt = data.get("loopback_exempt", True)
    share_auth.enable(code, loopback_exempt=bool(loopback_exempt))
    return jsonify({"ok": True, "share_enabled": True,
                    "loopback_exempt": share_auth.loopback_exempt()})


@app.route("/api/share/disable", methods=["POST"])
def share_disable():
    """OWNER-DIRECT-ONLY admin endpoint. Called when the owner stops sharing."""
    if not _is_owner_direct():
        return jsonify({"ok": False, "error": "owner-direct only"}), 403
    share_auth.disable()
    return jsonify({"ok": True, "share_enabled": False})


# --------------------------------------------------------------------------- #
# Chunked upload (Cloudflare >100 MB request-body safe)                       #
# --------------------------------------------------------------------------- #
# Cloudflare Free proxy caps a single request body near 100 MB. Raw avatar
# sources can exceed that, so the Create-Avatar upload is chunked: init ->
# repeated chunk POSTs (16 MiB each, well under the limit) -> complete, which
# atomically assembles the file into RAW_SOURCES_ROOT and hands the local path
# to the EXISTING analyze/prepare pipeline (no second importer — spec §16).
UPLOAD_STAGING = os.path.join(config.TEMP_DIR, "uploads")
CHUNK_HINT = 16 * 1024 * 1024              # 16 MiB recommended chunk size
UPLOAD_MAX_TOTAL = 512 * 1024 * 1024       # 512 MB cap (matches MAX_CONTENT_LENGTH)
UPLOAD_TTL_SEC = 2 * 60 * 60               # stale staging cleanup horizon


def _upload_dir(upload_id: str) -> str:
    return os.path.join(UPLOAD_STAGING, _sanitize_filename(upload_id))


def _sweep_stale_uploads() -> None:
    """Remove staging dirs older than UPLOAD_TTL_SEC. Best-effort."""
    try:
        if not os.path.isdir(UPLOAD_STAGING):
            return
        now = time.time()
        for name in os.listdir(UPLOAD_STAGING):
            d = os.path.join(UPLOAD_STAGING, name)
            if not os.path.isdir(d):
                continue
            if now - os.path.getmtime(d) > UPLOAD_TTL_SEC:
                shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


@app.route("/api/uploads/init", methods=["POST"])
def uploads_init():
    data = request.get_json(silent=True) or {}
    filename = _sanitize_filename(data.get("filename") or "source.mp4")
    size = int(data.get("size") or 0)
    if size <= 0:
        return jsonify({"ok": False, "error": "size required (bytes)"}), 400
    if size > UPLOAD_MAX_TOTAL:
        return jsonify({"ok": False, "error": "File too large (max 512 MB)."}), 400
    _sweep_stale_uploads()
    os.makedirs(UPLOAD_STAGING, exist_ok=True)
    upload_id = secrets.token_hex(12)
    d = _upload_dir(upload_id)
    os.makedirs(d, exist_ok=True)
    meta = {"filename": filename, "size": size, "created_at": time.time()}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    # Transport-aware chunk hint (spec §15/§16). The Cloudflare Free proxy caps
    # a single request body near 100 MB, AND a Quick Tunnel origin read that
    # exceeds ~100 s returns 524. At the tunnel's throttled ~1 Mbps, a 16 MiB
    # chunk can take >100 s -> 524; a 2 MiB chunk is ~17 s (6x margin). Local
    # loopback is effectively unlimited, so 16 MiB keeps local uploads fast.
    # The client MUST honor this hint (the server only advises).
    hint = 2 * 1024 * 1024 if _via_tunnel() else CHUNK_HINT
    return jsonify({"ok": True, "upload_id": upload_id,
                    "max_chunk_bytes": hint,
                    "max_total_bytes": UPLOAD_MAX_TOTAL})


@app.route("/api/uploads/<upload_id>/chunk", methods=["POST"])
def uploads_chunk(upload_id):
    uid = _sanitize_filename(upload_id)
    d = _upload_dir(uid)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.isfile(meta_path):
        return jsonify({"ok": False, "error": "unknown upload_id"}), 404
    try:
        idx = int(request.form.get("chunk_index", "-1"))
    except ValueError:
        return jsonify({"ok": False, "error": "bad chunk_index"}), 400
    if idx < 0:
        return jsonify({"ok": False, "error": "bad chunk_index"}), 400
    f = request.files.get("chunk_data")
    if not f:
        return jsonify({"ok": False, "error": "no chunk_data"}), 400
    part = os.path.join(d, f"chunk_{idx:08d}.part")
    f.save(part)
    return jsonify({"ok": True, "received": idx, "bytes": os.path.getsize(part)})


@app.route("/api/uploads/<upload_id>/complete", methods=["POST"])
def uploads_complete(upload_id):
    uid = _sanitize_filename(upload_id)
    d = _upload_dir(uid)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.isfile(meta_path):
        return jsonify({"ok": False, "error": "unknown upload_id"}), 404
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    expected_size = int(meta.get("size", 0))
    data = request.get_json(silent=True) or {}
    expected_chunks = int(data.get("expected_chunks", 0))

    parts = sorted(n for n in os.listdir(d) if n.startswith("chunk_") and n.endswith(".part"))
    if expected_chunks and len(parts) != expected_chunks:
        return jsonify({"ok": False, "error": f"missing chunks ({len(parts)}/{expected_chunks})"}), 400

    # Atomic assemble: write to a temp file in the staging dir, then move into
    # RAW_SOURCES_ROOT with a unique sanitized name.
    os.makedirs(config.RAW_SOURCES_ROOT, exist_ok=True)
    base, ext = os.path.splitext(meta.get("filename", "source.mp4"))
    ext = ext or ".mp4"
    final_name = f"{base}{ext}"
    final_path = os.path.join(config.RAW_SOURCES_ROOT, final_name)
    n = 2
    while os.path.exists(final_path):
        final_path = os.path.join(config.RAW_SOURCES_ROOT, f"{base}_{n}{ext}")
        n += 1

    tmp = os.path.join(d, "assembled.bin")
    total = 0
    sha = hashlib.sha1()
    try:
        with open(tmp, "wb") as out:
            for part in parts:
                with open(os.path.join(d, part), "rb") as pf:
                    while True:
                        buf = pf.read(65536)
                        if not buf:
                            break
                        out.write(buf)
                        sha.update(buf)
                        total += len(buf)
        if expected_size and total != expected_size:
            return jsonify({"ok": False,
                            "error": f"size mismatch ({total} != {expected_size})"}), 400
        shutil.move(tmp, final_path)
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return jsonify({"ok": False, "error": f"assemble failed: {e}"}), 500
    finally:
        shutil.rmtree(d, ignore_errors=True)

    return jsonify({"ok": True, "path": os.path.abspath(final_path),
                    "size": total, "sha1": sha.hexdigest(),
                    "filename": os.path.basename(final_path)})


# --------------------------------------------------------------------------- #
# System status                                                               #
# --------------------------------------------------------------------------- #
@app.route("/api/system/status")
def system_status():
    from .render_service import load_truth
    truth = load_truth()
    avatars = avatar_service.list_avatars()
    counts = avatar_service.avatar_counts()
    gpus = gpu_service.status()
    return jsonify({
        "renderer_ready": os.path.exists(config.RENDERER),
        "musetalk_ready": os.path.isdir(os.path.join(config.ROOT, "models", "musetalkV15")),
        "elevenlabs_connected": el.is_configured(),
        "edge_tts_available": edge.is_available(),
        "elevenlabs_key_masked": envutil.mask_api_key(),
        "gpus": gpus,
        "gpu_count": len(gpus),
        "renders_dir": config.RENDERS_DIR,
        "renders_dir_writable": _dir_writable(config.RENDERS_DIR),
        "output_disk_available": _dir_writable(config.RENDERS_DIR),
        "truth_valid": truth["ok"],
        "truth": truth.get("truth") if truth["ok"] else None,
        "truth_hash": truth.get("hash") if truth["ok"] else None,
        "truth_error": truth.get("error"),
        "avatar_total_dirs": counts["total_dirs"],
        "ready_avatars": counts["ready_avatars"],
        "incomplete_avatars": counts["incomplete_avatars"],
        "active_jobs": [j for j in db.list_active_jobs()],
    })


def _dir_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        p = os.path.join(path, ".studio_write_test")
        with open(p, "w") as f:
            f.write("ok")
        os.remove(p)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Avatars                                                                     #
# --------------------------------------------------------------------------- #
@app.route("/api/avatars")
def list_avatars():
    return jsonify({"avatars": avatar_service.list_avatars()})


@app.route("/api/avatars/quality/backfill", methods=["POST"])
def avatars_quality_backfill():
    """Evaluate (read-only validator) every prepared avatar that still has an
    on-disk raw source. Caches the result. Never fabricates; missing-source
    avatars stay CHƯA CÓ DỮ LIỆU."""
    force = (request.get_json(silent=True) or {}).get("force", False)
    return jsonify(avatar_quality.evaluate_all(force=force))


@app.route("/api/avatars/<avatar_id>/quality", methods=["GET", "POST"])
def avatar_quality_route(avatar_id):
    """Return cached quality, or run a read-only validator on the avatar's raw
    source (POST) and cache it. Honest no-data when the source is missing."""
    if request.method == "POST":
        force = (request.get_json(silent=True) or {}).get("force", False)
        return jsonify(avatar_quality.evaluate_avatar(avatar_id, force=force))
    # GET: cached first, else evaluate (without forcing a re-run)
    q = avatar_quality.evaluate_avatar(avatar_id, force=False)
    return jsonify(q)


@app.route("/api/avatars/<avatar_id>/thumbnail")
def avatar_thumbnail(avatar_id):
    p = avatar_service.avatar_thumbnail_path(avatar_id)
    if not p or not os.path.isfile(p):
        abort(404)
    return send_file(p, mimetype="image/png")


@app.route("/api/avatar/analyze", methods=["POST"])
def analyze_avatar():
    """Analyze a raw avatar source video. Accepts an uploaded file or a JSON
    {path} for an existing file. Returns human-language quality results +
    technical_failure / can_proceed / override availability."""
    video_path = _receive_video("video")
    if not video_path:
        return jsonify({"ok": False, "error": "No video file provided."}), 400
    result = avatar_service.analyze_source(video_path)
    result["video_path"] = video_path
    return jsonify(result)


@app.route("/api/avatar/prepare", methods=["POST"])
def prepare_avatar():
    data = request.get_json(silent=True) or {}
    video_path = data.get("video_path") or _receive_video("video")
    name = (data.get("avatar_name") or data.get("name") or "").strip()
    override = bool(data.get("allow_warning_override", False))
    if not video_path or not os.path.isfile(video_path):
        return jsonify({"ok": False, "error": "Source video not found."}), 400
    if not name:
        return jsonify({"ok": False, "error": "Avatar name is required."}), 400
    res = avatar_service.prepare_avatar(video_path, name, override)
    # Persist quality/override/mouth-state for future debugging. Mouth state is
    # stored SEPARATELY and never overwrites the raw automated evidence (spec A10):
    #   mouth_state_auto        — raw automated evidence (validator SOURCE_MOUTH_STATE)
    #   mouth_state_user        — user-confirmed: 'NOT_TALKING'|'TALKING'|'UNSURE'
    #   mouth_state_provenance  — 'AUTO'|'USER_CONFIRMED'|'UNKNOWN'
    if res.get("ok"):
        quality = data.get("quality_result")
        warnings = data.get("quality_warnings")
        mouth_user = (data.get("mouth_state_user") or "").strip()
        mouth_auto = data.get("mouth_state_auto")
        provenance = (data.get("mouth_state_provenance")
                      or ("USER_CONFIRMED" if mouth_user else "UNKNOWN"))
        qd = {"quality_result": quality,
              "quality_warnings": warnings,
              "user_override": override,
              "mouth_state_auto": mouth_auto,
              "mouth_state_user": mouth_user or None,
              "mouth_state_provenance": provenance}
        db.upsert_avatar(res["avatar_id"], name=name,
                         ready=0,
                         quality=(data.get("overall") or ("WARN" if warnings else "PASS")),
                         quality_data=json.dumps(qd, ensure_ascii=False)
                         if (quality or warnings or mouth_user) else None,
                         source_video=video_path,
                         created_at=time.time())
    return jsonify(res)


@app.route("/api/avatar/prepare/<avatar_id>/status")
def prepare_status(avatar_id):
    return jsonify(avatar_service.get_prep_status(avatar_id))


@app.route("/api/avatar/prepare/<avatar_id>/log")
def prepare_log(avatar_id):
    n = int(request.args.get("n", "60"))
    return jsonify({"log": avatar_service.get_prep_log_tail(avatar_id, n)})


@app.route("/api/avatar/sources", methods=["POST"])
def list_source():
    """List raw source files in data/input/avatar_sources for the Create
    Avatar 'choose existing file' convenience."""
    out = []
    if os.path.isdir(config.RAW_SOURCES_ROOT):
        for f in os.listdir(config.RAW_SOURCES_ROOT):
            p = os.path.join(config.RAW_SOURCES_ROOT, f)
            if os.path.isfile(p) and f.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
                out.append({"name": f, "path": p,
                            "size": os.path.getsize(p)})
    return jsonify({"sources": out})


@app.route("/api/avatar/sample")
def avatar_sample():
    """Report whether a sample video is available for the guided Create Avatar
    flow (spec A7/A8/H).

    Two eligible kinds (both require sample.mp4 + manifest.json with
    approved=true under studio/static/assets/avatar_source_example/):

      * TEMPORARY_BEST_EXISTING_SOURCE — the operator explicitly chose the best
        raw source currently on disk as a TEMPORARY example, NOT a perfect
        standard source. The UI must label this honestly as 'mẫu tạm thời'.
      * REAL_COMPLIANT_SOURCE — a human-approved compliant MP4 (manifest has no
        "temporary": true). The UI shows 'Video mẫu đúng chuẩn'.

    Known talking sources (e.g. test17_8/Close Up.mp4) are explicitly NOT used
    as the ideal-source example. If no approved sample exists, returns
    status='SAMPLE_ASSET_PENDING_HUMAN_APPROVAL' with the schematic framing
    guide fallback — never fabricates a real-person sample. The UI shows
    'Video mẫu chuẩn đang được cập nhật.' in that case."""
    sample_dir = os.path.join(STATIC_DIR, "assets", "avatar_source_example")
    sample_path = os.path.join(sample_dir, "sample.mp4")
    manifest_path = os.path.join(sample_dir, "manifest.json")
    if os.path.isfile(sample_path) and os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if manifest.get("approved"):
                temporary = bool(manifest.get("temporary", False))
                # The local source path is owner-only (spec §10): never expose
                # the on-disk raw-source path to a remote/tunnel caller.
                source_path = manifest.get("source_path", "")
                if _via_tunnel():
                    source_path = ""
                return jsonify({
                    "status": "TEMPORARY_BEST_EXISTING_SOURCE" if temporary
                              else "REAL_COMPLIANT_SOURCE",
                    "available": True,
                    "temporary": temporary,
                    "url": "/assets/avatar_source_example/sample.mp4",
                    "why_eligible": manifest.get("why_eligible", ""),
                    "source_path": source_path,
                    "checks": manifest.get("checks", []),
                    "caveats": manifest.get("caveats", []),
                })
        except Exception:
            pass
    return jsonify({
        "status": "SAMPLE_ASSET_PENDING_HUMAN_APPROVAL",
        "available": False,
        "message": "Video mẫu chuẩn đang được cập nhật.",
        "note": "A human-approved compliant raw-source MP4 + manifest.json is "
                "required under studio/static/assets/avatar_source_example/.",
    })


def _receive_video(field: str) -> str:
    """Accept an uploaded video file OR a JSON {path} to an existing file.
    Uploaded files are saved to RAW_SOURCES_ROOT with a sanitized unique name.
    Returns the on-disk path, or '' on failure."""
    if field in request.files:
        f = request.files[field]
        if not f or not f.filename:
            return ""
        safe = _sanitize_filename(f.filename)
        os.makedirs(config.RAW_SOURCES_ROOT, exist_ok=True)
        # Unique-ify to avoid collisions.
        base, ext = os.path.splitext(safe)
        dest = os.path.join(config.RAW_SOURCES_ROOT, safe)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(config.RAW_SOURCES_ROOT, f"{base}_{n}{ext}")
            n += 1
        f.save(dest)
        return dest
    data = request.get_json(silent=True) or {}
    p = data.get("path") or data.get("video_path")
    if p and os.path.isfile(p) and _within_allowed(p):
        return os.path.abspath(p)
    return ""


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name)  # strip any path components
    name = re.sub(r"[^A-Za-z0-9_.\- ]+", "_", name)
    return name[:120] or "source.mp4"


def _within_allowed(path: str) -> bool:
    """Only allow analyzing existing files under approved roots (no random
    filesystem access via UI input)."""
    path = os.path.abspath(path)
    allowed_roots = [config.RAW_SOURCES_ROOT, config.AVATARS_ROOT,
                     config.TEMP_DIR, config.RENDERS_DIR]
    for r in allowed_roots:
        try:
            if os.path.commonpath([path, os.path.abspath(r)]) == os.path.abspath(r):
                return True
        except ValueError:
            continue
    return False


# --------------------------------------------------------------------------- #
# Voice                                                                       #
# --------------------------------------------------------------------------- #
@app.route("/api/voice/check", methods=["POST"])
def voice_check():
    data = request.get_json(silent=True) or {}
    vid = (data.get("voice_id") or "").strip()
    return jsonify(el.check_voice(vid))


@app.route("/api/voice/preview", methods=["POST"])
def voice_preview():
    data = request.get_json(silent=True) or {}
    vid = (data.get("voice_id") or "").strip()
    text = data.get("script_text") or data.get("text") or ""
    if not vid:
        return jsonify({"ok": False, "error": "No Voice ID provided."}), 400
    if not text.strip():
        return jsonify({"ok": False, "error": "No script to preview."}), 400
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    out = os.path.join(config.TEMP_DIR, f"preview_{int(time.time())}_{abs(hash(vid))%100000}.wav")
    try:
        path, dur = el.preview_voice(vid, text, out)
    except el.VoiceError as e:
        return jsonify({"ok": False, "error": str(e), "fail_closed": True}), 400
    except el.TTSUnavailable as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": f"Preview failed: {e}"}), 500
    return jsonify({"ok": True, "path": path, "duration_sec": dur,
                    "preview_url": f"/api/voice/preview/file/{os.path.basename(path)}"})


@app.route("/api/voice/preview/file/<name>")
def voice_preview_file(name):
    safe = _sanitize_filename(name)
    p = os.path.join(config.TEMP_DIR, safe)
    if not os.path.isfile(p) or not safe.startswith("preview_"):
        abort(404)
    return send_file(p, mimetype="audio/wav", conditional=True)


# --------------------------------------------------------------------------- #
# Voice — Edge TTS free test provider (spec Part B)                          #
# --------------------------------------------------------------------------- #
@app.route("/api/voice/edge/voices")
def edge_voices():
    """List available Vietnamese Edge TTS voices (dynamic, with known-voice
    fallback). No API key. Never calls ElevenLabs."""
    return jsonify(edge.list_voices())


@app.route("/api/voice/edge/preview", methods=["POST"])
def edge_preview():
    """Generate a short Edge TTS preview clip. No ElevenLabs quota consumed.
    Only the test text is sent to the Edge TTS online service (spec Part I)."""
    data = request.get_json(silent=True) or {}
    voice = (data.get("voice_id") or data.get("edge_voice") or edge.DEFAULT_VOICE).strip()
    text = data.get("script_text") or data.get("text") or ""
    if not text.strip():
        return jsonify({"ok": False, "error": "No script to preview."}), 400
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    out = os.path.join(config.TEMP_DIR, f"preview_edge_{int(time.time())}_{abs(hash(voice))%100000}.wav")
    try:
        path, dur = edge.preview_voice(voice, text, out)
    except edge.EdgeTTSUnavailable as e:
        # Explicit failure — never silently fall back to ElevenLabs.
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": f"Edge TTS preview failed: {e}"}), 500
    return jsonify({"ok": True, "path": path, "duration_sec": dur,
                    "voice_id": voice, "voice_label": edge.voice_label(voice),
                    "preview_url": f"/api/voice/preview/file/{os.path.basename(path)}"})


# --------------------------------------------------------------------------- #
# Script                                                                      #
# --------------------------------------------------------------------------- #
@app.route("/api/script/parse", methods=["POST"])
def script_parse():
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            safe = _sanitize_filename(f.filename)
            os.makedirs(config.TEMP_DIR, exist_ok=True)
            dest = os.path.join(config.TEMP_DIR, f"script_{int(time.time())}_{safe}")
            f.save(dest)
            res = script_service.parse_script(file_path=dest)
            if res.get("ok"):
                res["source"] = f.filename
            return jsonify(res)
    data = request.get_json(silent=True) or {}
    if data.get("text") is not None:
        return jsonify(script_service.parse_script(text=data["text"]))
    if data.get("path") and _within_allowed(data["path"]):
        return jsonify(script_service.parse_script(file_path=data["path"]))
    return jsonify({"ok": False, "error": "No script file or text provided."}), 400


@app.route("/api/script/split", methods=["POST"])
def script_split():
    data = request.get_json(silent=True) or {}
    text = data.get("script_text") or data.get("text") or ""
    mode = data.get("mode", "full")
    return jsonify(script_service.split_script(text, mode))


# --------------------------------------------------------------------------- #
# Render                                                                      #
# --------------------------------------------------------------------------- #
@app.route("/api/render/test", methods=["POST"])
def render_test():
    data = request.get_json(silent=True) or {}
    return jsonify(render_service.create_test_job(
        data.get("avatar_id", ""), data.get("voice_id", ""),
        data.get("script_text", ""), data.get("voice_meta"),
        tts_provider=data.get("tts_provider", render_service.ELEVENLABS),
        test_mode=bool(data.get("test_mode", False)),
        test_type=data.get("test_type")))


@app.route("/api/render/mouth-test", methods=["POST"])
def render_mouth_test():
    """Standard mouth-motion test via the FREE Edge TTS voice (spec B9/B10).
    No ElevenLabs quota. LOCKED production lipsync profile. Uses the standard
    diagnostic script unless the caller supplies its own text."""
    data = request.get_json(silent=True) or {}
    avatar_id = (data.get("avatar_id") or "").strip()
    edge_voice = (data.get("edge_voice") or data.get("voice_id") or "").strip()
    script_text = data.get("script_text") or ""
    if not avatar_id:
        return jsonify({"ok": False, "error": "Chọn AI Avatar trước."}), 400
    return jsonify(render_service.create_mouth_test_job(avatar_id, edge_voice, script_text))


@app.route("/api/render", methods=["POST"])
def render_full():
    data = request.get_json(silent=True) or {}
    return jsonify(render_service.create_full_jobs(
        data.get("avatar_id", ""), data.get("voice_id", ""),
        data.get("script_text", ""), data.get("split_mode", "full"),
        data.get("voice_meta"),
        tts_provider=data.get("tts_provider", render_service.ELEVENLABS)))


@app.route("/api/render/jobs")
def render_jobs():
    limit = int(request.args.get("limit", "100"))
    return jsonify({"jobs": db.list_jobs(limit=limit)})


@app.route("/api/render/jobs/<job_id>")
def render_job(job_id):
    j = db.get_job(job_id)
    if not j:
        abort(404)
    return jsonify(j)


@app.route("/api/render/jobs/<job_id>/retry", methods=["POST"])
def render_retry(job_id):
    return jsonify(render_service.retry_job(job_id))


@app.route("/api/render/jobs/<job_id>/cancel", methods=["POST"])
def render_cancel(job_id):
    return jsonify(render_service.cancel_job(job_id))


@app.route("/api/render/jobs/<job_id>/log")
def render_job_log(job_id):
    j = db.get_job(job_id)
    if not j:
        abort(404)
    p = j.get("log_path")
    if not p or not os.path.isfile(p):
        return jsonify({"log": ""})
    n = int(request.args.get("n", "120"))
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return jsonify({"log": "".join(lines[-n:])})
    except Exception as e:
        return jsonify({"log": "", "error": str(e)})


@app.route("/api/render/jobs/<job_id>/preview")
def render_job_preview(job_id):
    """Stream the render output for in-UI preview (Range-supported)."""
    j = db.get_job(job_id)
    if not j or not j.get("output_path"):
        abort(404)
    p = j["output_path"]
    if not os.path.isfile(p):
        abort(404)
    return send_file(p, mimetype="video/mp4", conditional=True)


@app.route("/api/render/jobs/<job_id>/open-folder", methods=["POST"])
def render_open_folder(job_id):
    """Open the file's folder in Explorer (local tool only)."""
    j = db.get_job(job_id)
    if not j or not j.get("output_path"):
        abort(404)
    p = j["output_path"]
    if os.name == "nt":
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        except Exception:
            pass
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Settings (non-secret display; key update writes to .env)                   #
# --------------------------------------------------------------------------- #
@app.route("/api/settings")
def settings_get():
    return jsonify({
        "elevenlabs_connected": el.is_configured(),
        "elevenlabs_key_masked": envutil.mask_api_key(),
        "elevenlabs_model_id": el.model_id(),
        "edge_tts_available": edge.is_available(),
        "edge_tts_default_voice": edge.DEFAULT_VOICE,
        "renders_dir": config.RENDERS_DIR,
    })


@app.route("/api/elevenlabs/quota")
def elevenlabs_quota():
    """LIVE account/subscription status (uncached, non-fabricating). Returns
    the real character_count/character_limit/remaining + reset date, or an
    honest error. Used by the Settings view."""
    return jsonify(el.account_status())


@app.route("/api/settings/elevenlabs", methods=["POST"])
def settings_set_key():
    """Update the ElevenLabs API key in .env (never logged, never returned in
    full). Mirrors launcher.write_env: preserves every other line."""
    data = request.get_json(silent=True) or {}
    key = (data.get("api_key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "Empty key."}), 400
    ok = _update_env_key("ELEVENLABS_API_KEY", key)
    if not ok:
        return jsonify({"ok": False, "error": "Could not write .env."}), 500
    # Force reload so the new key takes effect immediately.
    envutil.load_env(force=True)
    el._API_KEY = None  # reset cached key so the new value is read on next use
    return jsonify({"ok": True, "key_masked": envutil.mask_api_key(),
                    "connected": el.is_configured()})


def _update_env_key(key: str, value: str) -> bool:
    """Update one key=value line in .env, preserving all other lines. Creates
    .env from .env.example if missing. Never logs the value."""
    path = envutil._resolve_env_path()
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    out = []
    for line in lines:
        s = line.lstrip()
        if s.startswith(f"{key}="):
            out.append(f"{key}={value}\n")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}\n")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out)
        return True
    except Exception:
        return False