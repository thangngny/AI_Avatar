#!/usr/bin/env python3
"""AI Avatar Studio — maintenance menu (V1.4.1 §13). Operator-friendly entry.
Destructive ops (cleanup) ask confirmation. Run via AI_Avatar_Studio_Maintenance.bat."""
import os, sys, subprocess, sqlite3, json, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
PY = sys.executable
from studio import config

def sh(args, **kw):
    return subprocess.run(args, cwd=ROOT, **kw)

def banner():
    print("\n" + "=" * 46)
    print(" AI AVATAR STUDIO — BẢO TRÌ (MAINTENANCE)")
    print("=" * 46)
    print(" 1. Preflight (kiểm tra trước khi chạy)")
    print(" 2. Backup Database")
    print(" 3. Verify Database (integrity)")
    print(" 4. Verify Models")
    print(" 5. Check Disk Space")
    print(" 6. Clean Old Logs (cần xác nhận)")
    print(" 7. Clean Stale Uploads (cần xác nhận)")
    print(" 8. Verify Prepared Avatars")
    print(" 9. Show Backup Status")
    print("10. Exit")

def confirm(msg):
    return input(f"\n {msg} (y/N)? ").strip().lower() == "y"

def m_preflight():
    sh([PY, os.path.join(HERE, "preflight.py"), "--detail"])

def m_backup_db():
    sh([PY, os.path.join(HERE, "backup_studio.py")])

def m_verify_db():
    if not os.path.isfile(config.DB_PATH):
        print("DB không tồn tại."); return
    c = sqlite3.connect(config.DB_PATH, timeout=10)
    integ = c.execute("PRAGMA integrity_check").fetchone()[0]
    jobs = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    avs = c.execute("SELECT COUNT(*) FROM avatars").fetchone()[0]
    c.close()
    print(f"DB: {config.DB_PATH}\n integrity_check={integ}\n jobs={jobs} avatars={avs}")

def m_verify_models():
    crit = ["models/musetalkV15/unet.pth", "models/musetalkV15/musetalk.json",
            "models/whisper/pytorch_model.bin", "models/whisper/config.json",
            "models/sd-vae/diffusion_pytorch_model.bin", "models/sd-vae/config.json",
            "models/face-parse-bisent/79999_iter.pth", "models/face-parse-bisent/resnet18-5c106cde.pth"]
    miss = [m for m in crit if not os.path.isfile(os.path.join(ROOT, m))]
    print("Models:", "ALL PRESENT" if not miss else "MISSING: " + ", ".join(miss))
    # optional checksum vs manifest
    man = os.path.join(ROOT, "diagnostics", "handover", "model_manifest.json")
    if os.path.isfile(man) and not miss:
        try:
            data = {x["path"]: x["sha256"] for x in json.load(open(man, encoding="utf-8"))["models"]}
            import hashlib
            bad = []
            for m in crit:
                p = os.path.join(ROOT, m)
                if m not in data or not data[m]:
                    continue
                h = hashlib.sha256(open(p, "rb").read()).hexdigest()
                if h != data[m]:
                    bad.append(m)
            print("Checksum vs manifest:", "MATCH" if not bad else "MISMATCH: " + ", ".join(bad))
        except Exception as e:
            print(f"Checksum check skipped: {e}")

def m_disk():
    for label, p in (("Renders", config.RENDERS_DIR), ("Repo (C:)", ROOT)):
        try:
            import ctypes
            free = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(os.path.dirname(p) or ".", None, None, ctypes.byref(free))
            print(f" {label}: {free.value/1e9:.1f} GB free  ({p})")
        except Exception as e:
            print(f" {label}: unknown ({e})")

def m_clean_logs():
    if confirm("Xóa log cũ (>30 ngày) và master WAV cũ?"):
        sh([PY, os.path.join(HERE, "cleanup.py"), "--log-days", "30", "--master-days", "30", "--yes"])

def m_clean_uploads():
    if confirm("Xóa upload staging cũ (>1 ngày)?"):
        sh([PY, os.path.join(HERE, "cleanup.py"), "--log-days", "36500", "--master-days", "36500", "--yes"])

def m_verify_avatars():
    from studio import avatar_service
    avs = avatar_service.list_avatars()
    ready = [a for a in avs if a["ready"]]
    inc = [a for a in avs if not a["ready"]]
    print(f"Avatars: {len(avs)} total, {len(ready)} READY, {len(inc)} INCOMPLETE")
    for a in inc[:10]:
        print(f"  INCOMPLETE: {a['avatar_id']}")

def m_backup_status():
    bdir = r"D:\CongThang_AI_Avatar\backups"
    if not os.path.isdir(bdir):
        print("No backups dir at", bdir); return
    bundles = sorted([d for d in os.listdir(bdir) if d.startswith("studio_backup_")])
    print(f"Backup bundles ({len(bundles)}) at {bdir}:")
    for b in bundles[-10:]:
        print(f"  {b}")

ACTIONS = {1:m_preflight,2:m_backup_db,3:m_verify_db,4:m_verify_models,5:m_disk,
           6:m_clean_logs,7:m_clean_uploads,8:m_verify_avatars,9:m_backup_status}
while True:
    banner()
    try:
        choice = input("\nChọn (1-10): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); break
    if choice == "10" or not choice:
        break
    try:
        n = int(choice)
        if n in ACTIONS:
            ACTIONS[n]()
        else:
            print("Lựa chọn không hợp lệ.")
    except ValueError:
        print("Nhập số 1-10.")
    input("\n[Nhấn Enter để quay lại] ")