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
                    mouth_state_provenance TEXT                   -- 'AUTO'|'USER_CONFIRMED'|'UNKNOWN'
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
                    updated_at   REAL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
                """
            )
            # --- Migrations: add columns introduced after the initial schema.
            # ALTER TABLE ... ADD COLUMN is idempotent-guarded by checking the
            # existing columns first, so an existing studio.db upgrades in place
            # without losing data.
            existing = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            for col, decl in (
                ("tts_provider", "TEXT DEFAULT 'ELEVENLABS'"),
                ("test_mode", "INTEGER DEFAULT 0"),
                ("test_type", "TEXT"),
                ("edge_voice", "TEXT"),
                ("mouth_state_auto", "TEXT"),
                ("mouth_state_user", "TEXT"),
                ("mouth_state_provenance", "TEXT"),
            ):
                if col not in existing:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {decl}")
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
                       mouth_state_auto, mouth_state_user, mouth_state_provenance)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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


def list_jobs(limit: int = 100, include_cancelled: bool = True) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        if include_cancelled:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status!='cancelled' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_active_jobs() -> List[Dict[str, Any]]:
    """Jobs that are not in a terminal state."""
    conn = _connect()
    try:
        active = ("queued", "preparing_audio", "preparing_avatar", "rendering",
                  "encoding", "verifying")
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE status IN ({','.join('?'*len(active))}) ORDER BY created_at",
            active,
        ).fetchall()
        return [dict(r) for r in rows]
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


def list_avatar_rows() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM avatars ORDER BY avatar_id").fetchall()
        return [dict(r) for r in rows]
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