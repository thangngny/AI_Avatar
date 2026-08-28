#!/usr/bin/env python3
"""AI Avatar Studio — safe SQLite backup (online backup API, transaction-safe).

Does NOT copy the live DB file blindly (WAL mode can be mid-write). Uses
sqlite3's online backup API which is safe against concurrent writers. Also
copies the non-secret-but-critical config + a manifest of avatar/raw-source
lineage. API keys (.env) are copied into the backup bundle (the bundle must be
stored as securely as the original .env — see BACKUP_RESTORE.md).

Usage:
    python scripts/backup_studio.py [DEST_DIR]
Default DEST_DIR = D:\\CongThang_AI_Avatar\\backups
"""
import os, sys, sqlite3, time, shutil, json, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from studio import config

DEFAULT_DEST = r"D:\CongThang_AI_Avatar\backups"
DEST = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEST

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

os.makedirs(DEST, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
bundle = os.path.join(DEST, f"studio_backup_{stamp}")
os.makedirs(bundle, exist_ok=True)
report = {"timestamp": stamp, "bundle": bundle, "items": [], "errors": []}

# 1) SQLite online backup (transaction-safe, works on live WAL db)
try:
    src = sqlite3.connect(config.DB_PATH, timeout=30)
    dst_path = os.path.join(bundle, "studio.db")
    dst = sqlite3.connect(dst_path)
    src.backup(dst)  # online backup API
    dst.close(); src.close()
    report["items"].append({"file": "studio.db", "bytes": os.path.getsize(dst_path),
                            "sha256": sha256_file(dst_path), "method": "sqlite_online_backup_api"})
except Exception as e:
    report["errors"].append(f"DB backup failed: {e}")

# 2) render_truth.json (locked production config)
for f in ("config/render_truth.json",):
    p = os.path.join(ROOT, f)
    if os.path.isfile(p):
        shutil.copy2(p, os.path.join(bundle, os.path.basename(f)))
        report["items"].append({"file": f, "sha256": sha256_file(p)})

# 3) .env (API key) — copied so a restore is self-contained; treat bundle as secret
env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    shutil.copy2(env_path, os.path.join(bundle, ".env"))
    report["items"].append({"file": ".env", "note": "SECRET — store bundle securely"})

# 4) Avatar + raw-source lineage manifest (names + counts, NOT the 35GB binaries)
lineage = {"avatars": [], "raw_sources": []}
av_root = config.AVATARS_ROOT
if os.path.isdir(av_root):
    for d in sorted(os.listdir(av_root)):
        p = os.path.join(av_root, d)
        if os.path.isdir(p):
            artifacts = [x for x in os.listdir(p) if x in ("full_imgs", "coords.pkl", "latents.pt", "mask.png")]
            lineage["avatars"].append({"avatar_id": d, "artifacts": artifacts})
if os.path.isdir(config.RAW_SOURCES_ROOT):
    lineage["raw_sources"] = [f for f in sorted(os.listdir(config.RAW_SOURCES_ROOT))
                              if os.path.isfile(os.path.join(config.RAW_SOURCES_ROOT, f))]
with open(os.path.join(bundle, "lineage.json"), "w", encoding="utf-8") as f:
    json.dump(lineage, f, ensure_ascii=False, indent=2)
report["items"].append({"file": "lineage.json", "avatars": len(lineage["avatars"]),
                        "raw_sources": len(lineage["raw_sources"])})

with open(os.path.join(bundle, "backup_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Backup OK -> {bundle}")
print(f"Items: {len(report['items'])}  Errors: {len(report['errors'])}")
if report["errors"]:
    for e in report["errors"]: print("  ERR:", e)
    sys.exit(1)
print(f"NOTE: bundle contains .env (SECRET) + studio.db. Store securely.")
print(f"NOTE: 35GB prepared-avatar binaries + raw sources NOT included — back up")
print(f"      data/avatars + data/input/avatar_sources separately (file copy).")