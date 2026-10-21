"""SQLite persistence for the AI Avatar Studio.

One small local database (data/studio_runtime/studio.db). Stores render jobs,
history, avatar metadata, quality results and override state. Stores PATHS to
large media, never the binary data itself. Stdlib sqlite3 only — no ORM, no
extra dependency.

Schema notes:
  * jobs     — render jobs (active queue + history share this table; status
               distinguishes them).
  * avatars  — prepared-avatar metadata cache (thumbnail path, quality, type,
               ready state, creation date). Re-derived from disk on demand.
  * settings — simple key/value for non-secret UI settings (the ElevenLabs API
               key is NEVER stored here — it lives only in .env).
"""
import os
import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from . import config

_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    config.ensure_runtime_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id            TEXT PRIMARY KEY,
                    created_at        REAL NOT NULL,
                    updated_at        REAL NOT NULL,
                    kind              TEXT NOT NULL,           -- 'test10s' | 'full'
                    avatar_id         TEXT NOT NULL,
                    voice_id          TEXT NOT NULL,
                    voice_meta        TEXT,                     -- JSON, no API key
                    script_text       TEXT,
                    script_name       TEXT,
                    script_segment    TEXT,                     -- JSON description of the segment
                    master_audio_path TEXT,
                    output_path       TEXT,
                    duration_sec      REAL,
                    status            TEXT NOT NULL,             -- queued/preparing_audio/preparing_avatar/rendering/encoding/verifying/complete/failed/cancelled
                    progress          INTEGER DEFAULT 0,         -- 0..100 (stage-level, honest)
                    stage             TEXT,                     -- human stage label
                    gpu_id            INTEGER,
                    pid               INTEGER,
                    log_path          TEXT,
                    error             TEXT,
                    quality_result    TEXT,                      -- JSON of validator output (for avatar-prep jobs)
                    quality_warnings  TEXT,                      -- JSON list of human-readable warnings
                    user_override     INTEGER DEFAULT 0,         -- 1 = used a WARN/POOR source anyway
                    truth_hash        TEXT,                       -- sha1 of render_truth.json at job time
                    tts_provider      TEXT DEFAULT 'ELEVENLABS',  -- 'ELEVENLABS' | 'EDGE_TTS_TEST' (explicit, never fallback)
                    test_mode         INTEGER DEFAULT 0,          -- 1 = a TEST render (mouth-motion test), 0 = production
                    test_type         TEXT,                       -- 'STANDARD_MOUTH_TEST' | 'SCRIPT_PREVIEW' | 'PRODUCTION'
                    edge_voice        TEXT,                       -- Edge TTS voice id when tts_provider='EDGE_TTS_TEST'
                    mouth_state_auto  TEXT,                       -- automated mouth-state evidence (raw, never overwritten)
                    mouth_state_user  TEXT,                       -- user-confirmed mouth state: 'NOT_TALKING'|'TALKING'|'UNSURE'
                    mouth_state_provenance TEXT,                  -- 'AUTO'|'USER_CONFIRMED'|'UNKNOWN'
                    tts_config        TEXT,                       -- JSON: resolved per-voice TTS config snapshot (V1.5.0; no key)
                    tts_config_hash   TEXT,                       -- sha1 of the resolved config (no key)
                    sync_mode         TEXT,                       -- auto_current|history_match|manual|none
                    history_item_id   TEXT,                       -- ElevenLabs history item id (Mode B)
                    display_name      TEXT                        -- V1.6.1: user-set video name (rename); NULL = auto label
                );

                CREATE TABLE IF NOT EXISTS voice_configs (
                    voice_id    TEXT PRIMARY KEY,
                    config      TEXT NOT NULL,    -- JSON: last resolved per-voice TTS config (no key)
                    updated_at  REAL NOT NULL
                );

                -- V1.6.0 — language-aware config identity. The same voice can need a
                -- different config per language. Keyed by (voice_id, language_code,
                -- resolver_policy). The legacy voice_configs (voice_id PK) table is
                -- preserved for backward compatibility (V1.5.0 data is NOT destroyed).
                CREATE TABLE IF NOT EXISTS voice_language_configs (
                    voice_id        TEXT NOT NULL,
                    language_code   TEXT NOT NULL,
                    resolver_policy TEXT NOT NULL,
                    config          TEXT NOT NULL,    -- JSON: resolved TTS config (no key)
                    updated_at      REAL NOT NULL,
                    PRIMARY KEY (voice_id, language_code, resolver_policy)
                );

                -- V1.6.0 — generic human-approved voice/language model preference.
                -- Stores a benchmark-approved model for a SPECIFIC (voice, language)
                -- pair — never a global "language -> model" hardcode. Any future
                -- voice/language pair can use the same mechanism.
                CREATE TABLE IF NOT EXISTS voice_model_profiles (
                    voice_id           TEXT NOT NULL,
                    language_code      TEXT NOT NULL,
                    preferred_model_id TEXT NOT NULL,
                    selection_source   TEXT NOT NULL,   -- HUMAN_BENCHMARK_APPROVED | USER_MANUAL | ...
                    output_format      TEXT,            -- optional requested output format
                    notes              TEXT,
                    approved_at         REAL NOT NULL,
                    PRIMARY KEY (voice_id, language_code)
                );

                -- V1.6.3 — custom/user-approved voices from ElevenLabs account / custom input.
                CREATE TABLE IF NOT EXISTS custom_voices (
                    voice_id     TEXT PRIMARY KEY,
                    name         TEXT,
                    category     TEXT,
                    description  TEXT,
                    labels       TEXT,
                    preview_url  TEXT,
                    added_at     REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS avatars (
                    avatar_id    TEXT PRIMARY KEY,
                    name         TEXT,
                    thumbnail    TEXT,
                    avatar_type  TEXT,                 -- 'Close Up' | 'Full Body' | 'Unknown'
                    ready        INTEGER DEFAULT 0,
                    quality      TEXT,                 -- PASS/WARN/FAIL or NULL
                    quality_data TEXT,                  -- JSON
                    source_video TEXT,
                    created_at   REAL,
                    updated_at   REAL,
                    is_deleted   INTEGER DEFAULT 0,
                    deleted_at   REAL
                );

                CREATE TABLE IF NOT EXISTS activity_logs (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at    REAL NOT NULL,
                    action        TEXT NOT NULL,        -- 'AVATAR_RENAME' | 'AVATAR_DELETE' | 'AVATAR_RESTORE' | 'RENDER_DELETE' | 'RENDER_RESTORE' | 'JOB_CANCEL' | 'JOB_STOP' | 'JOB_RETRY' | 'SCRIPT_PREVIEW_CREATED' | 'RENDER_USED_SCRIPT_PREVIEW'
                    resource_type TEXT NOT NULL,        -- 'avatar' | 'job' | 'render' | 'audio_preview'
                    resource_id   TEXT NOT NULL,
                    details       TEXT,                 -- JSON, sanitized (no API keys)
                    result        TEXT NOT NULL         -- 'SUCCESS' | 'CONFLICT' | 'ERROR'
                );

                CREATE TABLE IF NOT EXISTS audio_previews (
                    id                 TEXT PRIMARY KEY,
                    fingerprint        TEXT UNIQUE NOT NULL,
                    voice_id           TEXT NOT NULL,
                    voice_name         TEXT,
                    language           TEXT NOT NULL,
                    model_id           TEXT NOT NULL,
                    tts_config_json    TEXT NOT NULL,
                    tts_config_hash    TEXT NOT NULL,
                    script_text        TEXT NOT NULL,
                    script_hash        TEXT NOT NULL,
                    master_audio_path  TEXT NOT NULL,
                    duration_sec       REAL NOT NULL,
                    sample_rate        INTEGER NOT NULL,
                    status             TEXT NOT NULL,       -- 'generating' | 'ready' | 'failed'
                    error              TEXT,
                    created_at         REAL NOT NULL,
                    last_used_at       REAL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audio_previews_fingerprint ON audio_previews(fingerprint);
                CREATE INDEX IF NOT EXISTS idx_audio_previews_voice_lang ON audio_previews(voice_id, language);
                CREATE INDEX IF NOT EXISTS idx_audio_previews_created ON audio_previews(created_at DESC);
                """
            )
            # --- Migrations: add columns introduced after the initial schema.
            # ALTER TABLE ... ADD COLUMN is idempotent-guarded by checking the
            # existing columns first, so an existing studio.db upgrades in place
            # without losing data.
            existing_jobs = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            for col, decl in (
                ("tts_provider", "TEXT DEFAULT 'ELEVENLABS'"),
                ("test_mode", "INTEGER DEFAULT 0"),
                ("test_type", "TEXT"),
                ("edge_voice", "TEXT"),
                ("mouth_state_auto", "TEXT"),
                ("mouth_state_user", "TEXT"),
                ("mouth_state_provenance", "TEXT"),
                ("tts_config", "TEXT"),
                ("tts_config_hash", "TEXT"),
                ("sync_mode", "TEXT"),
                ("history_item_id", "TEXT"),
                ("is_deleted", "INTEGER DEFAULT 0"),
                ("deleted_at", "REAL"),
                ("audio_source", "TEXT DEFAULT 'generated'"),
                ("preview_id", "TEXT"),
                ("preview_fingerprint", "TEXT"),
                ("display_name", "TEXT"),
            ):
                if col not in existing_jobs:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")

            existing_avatars = {r[1] for r in conn.execute("PRAGMA table_info(avatars)").fetchall()}
            for col, decl in (
                ("is_deleted", "INTEGER DEFAULT 0"),
                ("deleted_at", "REAL"),
            ):
                if col not in existing_avatars:
                    conn.execute(f"ALTER TABLE avatars ADD COLUMN {col} {decl}")

            # Indices on migrated columns
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_is_deleted ON jobs(is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_avatars_is_deleted ON avatars(is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_preview_id ON jobs(preview_id)")

            # V1.6.0 — idempotent seed of the human-approved voice/language model
            # profile. This is DATA (a generic profile row), not a code branch:
            # there is no `if voice_id == ...` anywhere in the resolver. The user
            # listened to the controlled Vietnamese A/B/C benchmark (Phase A) and
            # approved Candidate C (eleven_v3) for THIS voice + language only.
            # Re-running init_db never overwrites an operator-edited profile.
            conn.execute(
                """INSERT INTO voice_model_profiles
                       (voice_id, language_code, preferred_model_id,
                        selection_source, output_format, notes, approved_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(voice_id, language_code) DO NOTHING""",
                ("N0Z0aL8qHhzwUHwRBcVo", "vi", "eleven_v3",
                 "HUMAN_BENCHMARK_APPROVED", "mp3_44100_128",
                 "Candidate C selected after controlled Vietnamese A/B/C test (Phase A, 2026-08-28)",
                 _now()))
            conn.commit()
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Jobs                                                                        #
# --------------------------------------------------------------------------- #
def _now() -> float:
    return time.time()


def create_job(job: Dict[str, Any]) -> None:
    """Insert a new job row. job must include job_id + the core fields."""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO jobs (job_id, created_at, updated_at, kind, avatar_id,
                       voice_id, voice_meta, script_text, script_name, script_segment,
                       master_audio_path, output_path, duration_sec, status, progress,
                       stage, gpu_id, pid, log_path, error, quality_result,
                       quality_warnings, user_override, truth_hash,
                       tts_provider, test_mode, test_type, edge_voice,
                       mouth_state_auto, mouth_state_user, mouth_state_provenance,
                       tts_config, tts_config_hash, sync_mode, history_item_id,
                       is_deleted, deleted_at, audio_source, preview_id, preview_fingerprint)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job["job_id"], _now(), _now(), job["kind"], job["avatar_id"],
                    job["voice_id"], job.get("voice_meta"), job.get("script_text"),
                    job.get("script_name"), job.get("script_segment"),
                    job.get("master_audio_path"), job.get("output_path"),
                    job.get("duration_sec"), job.get("status", "queued"),
                    job.get("progress", 0), job.get("stage"), job.get("gpu_id"),
                    job.get("pid"), job.get("log_path"), job.get("error"),
                    job.get("quality_result"), job.get("quality_warnings"),
                    job.get("user_override", 0), job.get("truth_hash"),
                    job.get("tts_provider", "ELEVENLABS"), job.get("test_mode", 0),
                    job.get("test_type"), job.get("edge_voice"),
                    job.get("mouth_state_auto"), job.get("mouth_state_user"),
                    job.get("mouth_state_provenance"),
                    job.get("tts_config"), job.get("tts_config_hash"),
                    job.get("sync_mode"), job.get("history_item_id"),
                    job.get("is_deleted", 0), job.get("deleted_at"),
                    job.get("audio_source", "generated"), job.get("preview_id"),
                    job.get("preview_fingerprint"),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(f"UPDATE jobs SET {cols} WHERE job_id=?", vals)
            conn.commit()
        finally:
            conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# V1.6.1 — user-set video name (rename). Sanitize: trim, collapse whitespace,
# strip control chars, cap length. Empty/whitespace -> NULL (revert to auto label).
_RENAME_MAX = 120

def sanitize_display_name(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    # Keep letters/digits/space and common punctuation; drop control chars and
    # path separators that would break a download filename or DB display.
    import unicodedata
    s = unicodedata.normalize("NFC", str(raw)).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = "".join(c for c in s if c.isprintable() and c not in "\x00\\/:*?\"<>|")
    s = " ".join(s.split()).strip()
    if not s:
        return None
    return s[:_RENAME_MAX]

def rename_job(job_id: str, display_name: Optional[str]) -> bool:
    """Set a user-facing video name. Empty -> reverts to the auto label (NULL).
    Returns True if a job row was updated."""
    safe_id = (job_id or "").strip()
    if not safe_id:
        return False
    name = sanitize_display_name(display_name)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET display_name=?, updated_at=? WHERE job_id=?",
                (name, _now(), safe_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_jobs(limit: int = 100, include_cancelled: bool = True,
              include_deleted: bool = False) -> List[Dict[str, Any]]:
    """List render jobs. By default, soft-deleted jobs (is_deleted=1) are excluded."""
    conn = _connect()
    try:
        where_clauses = []
        params: List[Any] = []
        if not include_deleted:
            where_clauses.append("(is_deleted = 0 OR is_deleted IS NULL)")
        if not include_cancelled:
            where_clauses.append("status != 'cancelled'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT * FROM jobs {where_sql} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_trash_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    """List soft-deleted jobs for the Trash view."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE is_deleted = 1 ORDER BY deleted_at DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def soft_delete_job(job_id: str) -> bool:
    """Mark a render job as soft-deleted. Reversible via restore_job."""
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE job_id = ?",
                (_now(), _now(), job_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def restore_job(job_id: str) -> bool:
    """Restore a soft-deleted render job back to active History."""
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET is_deleted = 0, deleted_at = NULL, updated_at = ? WHERE job_id = ?",
                (_now(), job_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_active_jobs() -> List[Dict[str, Any]]:
    """Jobs that are not in a terminal state (and not soft-deleted)."""
    conn = _connect()
    try:
        active = ("queued", "preparing_audio", "preparing_avatar", "rendering",
                  "encoding", "verifying")
        rows = conn.execute(
            f"""SELECT * FROM jobs
                WHERE status IN ({','.join('?'*len(active))})
                AND (is_deleted = 0 OR is_deleted IS NULL)
                ORDER BY created_at""",
            active,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def has_active_jobs_for_avatar(avatar_id: str) -> (bool, List[str]):
    """Check if any non-terminal jobs currently reference avatar_id."""
    conn = _connect()
    try:
        active = ("queued", "preparing_audio", "preparing_avatar", "rendering",
                  "encoding", "verifying")
        rows = conn.execute(
            f"""SELECT job_id FROM jobs
                WHERE avatar_id = ?
                AND status IN ({','.join('?'*len(active))})
                AND (is_deleted = 0 OR is_deleted IS NULL)""",
            (avatar_id, *active),
        ).fetchall()
        active_ids = [r["job_id"] for r in rows]
        return (len(active_ids) > 0, active_ids)
    finally:
        conn.close()


def list_jobs_in_statuses(statuses) -> List[Dict[str, Any]]:
    """Jobs whose status is in the given tuple (V1.4.1 R06 reconciliation)."""
    if not statuses:
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE status IN ({','.join('?'*len(statuses))}) ORDER BY created_at",
            tuple(statuses),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Avatars                                                                     #
# --------------------------------------------------------------------------- #
def upsert_avatar(avatar_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    cols = list(fields.keys())
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols)
    vals = [avatar_id] + list(fields.values())
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                f"""INSERT INTO avatars (avatar_id, {', '.join(cols)}) VALUES (?, {placeholders})
                    ON CONFLICT(avatar_id) DO UPDATE SET {assignments}""",
                vals,
            )
            conn.commit()
        finally:
            conn.close()


def get_avatar(avatar_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM avatars WHERE avatar_id=?", (avatar_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def rename_avatar(avatar_id: str, new_name: str) -> bool:
    """Update display name for an avatar (metadata only; does NOT rename files/folders/IDs)."""
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE avatars SET name=?, updated_at=? WHERE avatar_id=?",
                (new_name, _now(), avatar_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def soft_delete_avatar(avatar_id: str) -> bool:
    """Mark an avatar as soft-deleted. Reversible via restore_avatar."""
    with _LOCK:
        conn = _connect()
        try:
            # Check if row exists in avatars table; if not, create it first as deleted
            existing = conn.execute("SELECT avatar_id FROM avatars WHERE avatar_id=?", (avatar_id,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO avatars (avatar_id, name, is_deleted, deleted_at, created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
                    (avatar_id, avatar_id, _now(), _now(), _now()),
                )
            else:
                conn.execute(
                    "UPDATE avatars SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE avatar_id = ?",
                    (_now(), _now(), avatar_id),
                )
            conn.commit()
            return True
        finally:
            conn.close()


def restore_avatar(avatar_id: str) -> bool:
    """Restore a soft-deleted avatar back to active Library."""
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE avatars SET is_deleted = 0, deleted_at = NULL, updated_at = ? WHERE avatar_id = ?",
                (_now(), avatar_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_avatar_rows(include_deleted: bool = False) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        if include_deleted:
            rows = conn.execute("SELECT * FROM avatars ORDER BY avatar_id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM avatars WHERE (is_deleted = 0 OR is_deleted IS NULL) ORDER BY avatar_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_trash_avatars() -> List[Dict[str, Any]]:
    """List soft-deleted avatars for the Trash view."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM avatars WHERE is_deleted = 1 ORDER BY deleted_at DESC, avatar_id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Voice configs (V1.5.0) — per-voice remembered resolved TTS config            #
# --------------------------------------------------------------------------- #
def save_voice_config(voice_id: str, config: Dict[str, Any]) -> None:
    """Upsert the last resolved per-voice TTS config (sanitized JSON; no key)."""
    cfg_json = json.dumps(config, ensure_ascii=False) if isinstance(config, (dict, list)) else str(config)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO voice_configs (voice_id, config, updated_at)
                   VALUES (?,?,?)
                   ON CONFLICT(voice_id) DO UPDATE SET config=excluded.config, updated_at=excluded.updated_at""",
                (voice_id, cfg_json, _now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_voice_config(voice_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT config FROM voice_configs WHERE voice_id=?", (voice_id,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["config"])
        except Exception:
            return None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# V1.6.0 — language-aware config identity + human-approved profiles           #
# --------------------------------------------------------------------------- #
def save_voice_language_config(voice_id: str, language_code: str,
                               resolver_policy: str, config: Dict[str, Any]) -> None:
    """Upsert a resolved TTS config keyed by (voice_id, language_code,
    resolver_policy). The same voice can hold a different config per language
    with no leak. Sanitized JSON; no API key ever stored here."""
    cfg_json = json.dumps(config, ensure_ascii=False) if isinstance(config, (dict, list)) else str(config)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO voice_language_configs (voice_id, language_code, resolver_policy, config, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(voice_id, language_code, resolver_policy)
                   DO UPDATE SET config=excluded.config, updated_at=excluded.updated_at""",
                (voice_id, language_code, resolver_policy, cfg_json, _now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_voice_language_config(voice_id: str, language_code: str,
                              resolver_policy: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT config FROM voice_language_configs WHERE voice_id=? AND language_code=? AND resolver_policy=?",
            (voice_id, language_code, resolver_policy),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["config"])
        except Exception:
            return None
    finally:
        conn.close()


# --- Human-approved voice/language model profiles (generic mechanism) ------- #
def save_profile(voice_id: str, language_code: str, preferred_model_id: str,
                 selection_source: str = "USER_MANUAL",
                 output_format: Optional[str] = None, notes: Optional[str] = None) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO voice_model_profiles
                       (voice_id, language_code, preferred_model_id, selection_source,
                        output_format, notes, approved_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(voice_id, language_code) DO UPDATE SET
                       preferred_model_id=excluded.preferred_model_id,
                       selection_source=excluded.selection_source,
                       output_format=excluded.output_format,
                       notes=excluded.notes,
                       approved_at=excluded.approved_at""",
                (voice_id, language_code, preferred_model_id, selection_source,
                 output_format, notes, _now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_profile(voice_id: str, language_code: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM voice_model_profiles WHERE voice_id=? AND language_code=?",
            (voice_id, language_code),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_profiles() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM voice_model_profiles ORDER BY approved_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_profile(voice_id: str, language_code: str) -> bool:
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM voice_model_profiles WHERE voice_id=? AND language_code=?",
                (voice_id, language_code),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Custom / User Voices (V1.6.3)                                               #
# --------------------------------------------------------------------------- #
def save_custom_voice(voice_id: str, name: str = "", category: str = "",
                      description: str = "", labels: Optional[Dict[str, Any]] = None,
                      preview_url: str = "") -> None:
    vid = (voice_id or "").strip()
    if not vid:
        return
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO custom_voices (voice_id, name, category, description, labels, preview_url, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(voice_id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    description=excluded.description,
                    labels=excluded.labels,
                    preview_url=excluded.preview_url,
                    added_at=excluded.added_at
                """,
                (vid, name or vid, category or "custom", description or "",
                 json.dumps(labels or {}), preview_url or "", time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def list_custom_voices() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM custom_voices ORDER BY added_at DESC").fetchall()
        out = []
        for r in rows:
            lbl = {}
            try:
                lbl = json.loads(r["labels"]) if r["labels"] else {}
            except Exception:
                pass
            out.append({
                "voice_id": r["voice_id"],
                "name": r["name"],
                "category": r["category"],
                "description": r["description"],
                "labels": lbl,
                "preview_url": r["preview_url"],
                "added_at": r["added_at"],
            })
        return out
    finally:
        conn.close()


def delete_custom_voice(voice_id: str) -> bool:
    vid = (voice_id or "").strip()
    if not vid:
        return False
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM custom_voices WHERE voice_id=?", (vid,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def is_custom_approved_voice(voice_id: str) -> bool:
    vid = (voice_id or "").strip()
    if not vid:
        return False
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM custom_voices WHERE voice_id=?", (vid,)).fetchone()
        return bool(row)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Settings (non-secret only)                                                 #
# --------------------------------------------------------------------------- #
def get_setting(key: str, default: str = "") -> str:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Activity Logs                                                               #
# --------------------------------------------------------------------------- #
def log_activity(action: str, resource_type: str, resource_id: str,
                 details: Optional[Any] = None, result: str = "SUCCESS") -> None:
    """Record an audit trail event for management operations. Never logs secrets."""
    details_str = None
    if details is not None:
        if isinstance(details, (dict, list)):
            # Sanitize any sensitive keys
            clean = _sanitize_log_data(details)
            details_str = json.dumps(clean, ensure_ascii=False)
        else:
            details_str = str(details)[:500]

    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO activity_logs (created_at, action, resource_type, resource_id, details, result)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (_now(), str(action), str(resource_type), str(resource_id), details_str, str(result)),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()


def list_activity_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """List recent activity logs."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _sanitize_log_data(data: Any) -> Any:
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if any(s in k.lower() for s in ("key", "secret", "token", "auth", "password")):
                out[k] = "***REDACTED***"
            else:
                out[k] = _sanitize_log_data(v)
        return out
    elif isinstance(data, list):
        return [_sanitize_log_data(x) for x in data]
    return data


# --------------------------------------------------------------------------- #
# Audio Previews (Script Voice Preview & Audio Reuse)                         #
# --------------------------------------------------------------------------- #
def get_audio_preview_by_fingerprint(fingerprint: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM audio_previews WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_audio_preview(preview_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM audio_previews WHERE id = ?", (preview_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_audio_preview(preview: Dict[str, Any]) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO audio_previews
                   (id, fingerprint, voice_id, voice_name, language, model_id,
                    tts_config_json, tts_config_hash, script_text, script_hash,
                    master_audio_path, duration_sec, sample_rate, status, error,
                    created_at, last_used_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(fingerprint) DO UPDATE SET
                    voice_name = excluded.voice_name,
                    tts_config_json = excluded.tts_config_json,
                    tts_config_hash = excluded.tts_config_hash,
                    master_audio_path = excluded.master_audio_path,
                    duration_sec = excluded.duration_sec,
                    sample_rate = excluded.sample_rate,
                    status = excluded.status,
                    error = excluded.error,
                    last_used_at = excluded.last_used_at""",
                (
                    preview["id"], preview["fingerprint"], preview["voice_id"],
                    preview.get("voice_name"), preview["language"], preview["model_id"],
                    preview["tts_config_json"], preview["tts_config_hash"],
                    preview["script_text"], preview["script_hash"],
                    preview.get("master_audio_path", ""), preview.get("duration_sec", 0.0),
                    preview.get("sample_rate", 0), preview.get("status", "generating"),
                    preview.get("error"), preview.get("created_at", _now()),
                    preview.get("last_used_at", _now()),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_audio_preview(preview_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [preview_id]
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(f"UPDATE audio_previews SET {cols} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()


def touch_audio_preview(preview_id: str) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("UPDATE audio_previews SET last_used_at = ? WHERE id = ?", (_now(), preview_id))
            conn.commit()
        finally:
            conn.close()


def list_audio_previews(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM audio_previews ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def parse_json_field(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None