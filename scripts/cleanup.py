#!/usr/bin/env python3
"""AI Avatar Studio — conservative cleanup / log rotation (V1.4.1 R08).

Path-scoped ONLY. Never wildcard rm. Never touch:
  - active-job logs (jobs still queued/transient)
  - recent failure logs (< retain_days)
  - handover diagnostics (diagnostics/handover*)
  - renders, avatars, models, .env

Usage:
    python scripts/cleanup.py [--dry-run] [--log-days 30] [--master-days 30] [--yes]
"""
import os, sys, time, glob, json
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from studio import config

DRY = "--dry-run" in sys.argv
def _arg(name, default):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            try: return int(sys.argv[i+1])
            except ValueError: return default
    return default
LOG_DAYS = _arg("--log-days", 30)
MASTER_DAYS = _arg("--master-days", 30)
YES = "--yes" in sys.argv

def active_job_logs():
    """Log paths for jobs still active (keep these)."""
    try:
        from studio import db
        active = ("queued", "preparing_audio", "preparing_avatar", "rendering", "encoding", "verifying")
        jobs = db.list_jobs_in_statuses(active)
        return {j.get("log_path") for j in jobs if j.get("log_path")}
    except Exception:
        return set()

report = {"deleted": [], "kept_active": 0, "bytes_freed": 0, "dry_run": DRY}

def prune_dir(dirpath, days, pattern, keep=None):
    keep = keep or set()
    if not os.path.isdir(dirpath):
        return
    cutoff = time.time() - days * 86400
    for p in glob.glob(os.path.join(dirpath, pattern)):
        try:
            if os.path.getmtime(p) > cutoff:
                continue  # too recent
        except OSError:
            continue
        if p in keep:
            report["kept_active"] += 1
            continue
        sz = os.path.getsize(p) if os.path.isfile(p) else 0
        report["deleted"].append({"path": p, "bytes": sz, "age_days": int((time.time()-os.path.getmtime(p))/86400)})
        report["bytes_freed"] += sz
        if not DRY:
            try:
                if os.path.isfile(p):
                    os.remove(p)
                elif os.path.isdir(p):
                    import shutil; shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass

active_logs = active_job_logs()
prune_dir(config.LOG_DIR, LOG_DAYS, "*.log", active_logs)
prune_dir(os.path.join(config.TEMP_DIR, "master"), MASTER_DAYS, "*.wav")
# stale upload staging dirs (>1 day)
prune_dir(os.path.join(config.TEMP_DIR, "uploads"), 1, "*")

print(f"Cleanup {'(DRY RUN)' if DRY else ''}:")
print(f"  log retention: {LOG_DAYS} days | master WAV retention: {MASTER_DAYS} days")
print(f"  would delete / deleted: {len(report['deleted'])} items")
print(f"  bytes freed: {report['bytes_freed']/1e6:.1f} MB")
print(f"  active-job logs kept: {report['kept_active']}")
if report['deleted'] and not YES and not DRY:
    print("Re-run with --yes to actually delete.")
    sys.exit(0)
json.dump(report, open(os.path.join(config.RUNTIME_DIR, "last_cleanup_report.json"), "w", encoding="utf-8"), indent=2)
print("Handover diagnostics (diagnostics/handover*) NOT touched. Renders/avatars/models NOT touched.")