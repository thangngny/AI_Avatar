#!/usr/bin/env python3
"""Optional backup scheduler installer (V1.4.1 §9 R13).

Registers a Windows Task Scheduler task that runs the Studio DB backup daily.
Requires EXPLICIT operator execution — never auto-registers on install.
No secrets printed. Operator can uninstall.

Usage:
    python scripts/setup_backup_schedule.py install   # create daily 03:17 task
    python scripts/setup_backup_schedule.py verify    # show task status
    python scripts/setup_backup_schedule.py remove    # delete the task
"""
import os, sys, subprocess
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = r"C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
if not os.path.exists(PY):
    PY = "python"
TASK = "AI_Avatar_Studio_DailyBackup"
BACKUP_SCRIPT = os.path.join(ROOT, "scripts", "backup_studio.py")

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

def install():
    action = f'{PY} "{BACKUP_SCRIPT}"'
    # schtask: daily at 03:17 (off-the-hour), run whether logged on or not is NOT set
    # (requires the operator to be logged on; simplest, no password needed).
    cmd = ["schtasks", "/Create", "/TN", TASK, "/TR", f'"{PY}" "{BACKUP_SCRIPT}"',
           "/SC", "DAILY", "/ST", "03:17", "/F"]
    r = run(cmd)
    if r.returncode == 0:
        print(f"Đã đăng ký task '{TASK}' — chạy backup DB hằng ngày 03:17.")
        print(f"Lệnh backup: {action}")
        print("Verify: python scripts/setup_backup_schedule.py verify")
        print("Remove: python scripts/setup_backup_schedule.py remove")
    else:
        print(f"Lỗi đăng ký: {r.stderr.strip() or r.stdout.strip()}")
        sys.exit(1)

def verify():
    r = run(["schtasks", "/Query", "/TN", TASK])
    if r.returncode == 0:
        print(f"Task '{TASK}' đang tồn tại (đã đăng ký).")
        # show next run
        r2 = run(["schtasks", "/Query", "/TN", TASK, "/FO", "LIST"])
        for line in r2.stdout.splitlines():
            if line.strip().startswith(("Next Run", "Last Run", "Status", "Task To Run")):
                print("  " + line.strip())
    else:
        print(f"Task '{TASK}' chưa đăng ký.")

def remove():
    r = run(["schtasks", "/Delete", "/TN", TASK, "/F"])
    print(f"Đã xóa task '{TASK}'." if r.returncode == 0 else f"Không xóa được: {r.stderr.strip()}")

if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else "verify"
    {"install": install, "verify": verify, "remove": remove}.get(op, verify)()