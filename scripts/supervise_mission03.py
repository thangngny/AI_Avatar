"""
AI Avatar NextGen V2 - Resilient Self-Healing Supervisor for Mission 03
Ensures the downloader and handoff watchdog remain active and un-duplicated.
If the agent session disconnects or an unexpected failure occurs, this supervisor
safely resumes without data loss or duplicate processes.
"""
import os
import sys
import time
import subprocess
import shutil

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission03")
STAGING_DIR = r"D:\CongThang_AI_Avatar\staging_weights\SoulX-FlashHead-1_3B\Model_Pro"
WEIGHTS_DIR = os.path.join(REPO_ROOT, "weights", "SoulX-FlashHead-1_3B", "Model_Pro")
PYTHON_EXE = r"C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"

EXPECTED_SIZE = 6030864656
PRO_SAFETENSORS_NAME = "diffusion_pytorch_model.safetensors"
pro_staged_part = os.path.join(STAGING_DIR, PRO_SAFETENSORS_NAME + ".part")
pro_staged_final = os.path.join(STAGING_DIR, PRO_SAFETENSORS_NAME)
pro_final = os.path.join(WEIGHTS_DIR, PRO_SAFETENSORS_NAME)

SUPERVISOR_LOG = os.path.join(REPORTS_DIR, "supervisor.log")

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] [SUPERVISOR] {msg}"
    print(formatted, flush=True)
    with open(SUPERVISOR_LOG, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

def get_running_scripts():
    """Returns set of python scripts currently running via Win32_Process"""
    running = {}
    try:
        ps_cmd = 'Get-CimInstance Win32_Process -Filter "Name = \'python.exe\'" | Select-Object ProcessId, CommandLine | ConvertTo-Json'
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=10).decode("utf-8", errors="ignore").strip()
        if out:
            import json
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                cmd = p.get("CommandLine", "") or ""
                pid = p.get("ProcessId")
                if "download_safetensors_direct.py" in cmd:
                    running["downloader"] = pid
                elif "watch_and_handoff.py" in cmd:
                    running["watchdog"] = pid
                elif "run_mission03_inference.py" in cmd:
                    running["inference"] = pid
    except Exception as e:
        log(f"Error checking processes: {e}")
    return running

def check_progress():
    running = get_running_scripts()
    downloader_pid = running.get("downloader")
    watchdog_pid = running.get("watchdog")
    inference_pid = running.get("inference")

    # 1. Check if final weights exist
    if os.path.exists(pro_final) and os.path.getsize(pro_final) == EXPECTED_SIZE:
        log(f"Model_Pro weights verified complete at {pro_final}")
        # Check if inference already ran
        out_3s = os.path.join(REPORTS_DIR, "soulx_pro_3s.mp4")
        out_10s = os.path.join(REPORTS_DIR, "soulx_pro_10s.mp4")
        if os.path.exists(out_3s) and os.path.exists(out_10s):
            log("Real inference videos already completed! Mission 03 pipeline satisfied.")
            return True

        if not watchdog_pid and not inference_pid:
            log("Weights complete but inference not running. Launching watch_and_handoff...")
            subprocess.Popen([PYTHON_EXE, os.path.join(REPO_ROOT, "scripts", "watch_and_handoff.py")],
                             cwd=REPO_ROOT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        return False

    # 2. Check staged final
    if os.path.exists(pro_staged_final) and os.path.getsize(pro_staged_final) == EXPECTED_SIZE:
        log(f"Staged file complete! Copying to {pro_final}...")
        os.makedirs(os.path.dirname(pro_final), exist_ok=True)
        shutil.copy2(pro_staged_final, pro_final)
        log("Copy complete.")
        return False

    # 3. Check partial download
    current_sz = os.path.getsize(pro_staged_part) if os.path.exists(pro_staged_part) else 0
    pct = (current_sz / EXPECTED_SIZE) * 100
    log(f"Current download state: {current_sz / (1024*1024):.1f} / {EXPECTED_SIZE / (1024*1024):.1f} MB ({pct:.2f}%) | Downloader PID: {downloader_pid} | Watchdog PID: {watchdog_pid}")

    if not downloader_pid:
        log("[RECOVERY] Downloader is NOT active! Launching download_safetensors_direct.py in detached process...")
        log_out = open(os.path.join(REPORTS_DIR, "download_recovery.log"), "a", encoding="utf-8")
        p = subprocess.Popen([PYTHON_EXE, "-u", os.path.join(REPO_ROOT, "scripts", "download_safetensors_direct.py")],
                             cwd=REPO_ROOT, stdout=log_out, stderr=log_out,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        log(f"[RECOVERY] Downloader restarted with PID {p.pid}")

    if not watchdog_pid:
        log("[RECOVERY] Watchdog is NOT active! Launching watch_and_handoff.py in detached process...")
        p2 = subprocess.Popen([PYTHON_EXE, "-u", os.path.join(REPO_ROOT, "scripts", "watch_and_handoff.py")],
                              cwd=REPO_ROOT,
                              creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        log(f"[RECOVERY] Watchdog restarted with PID {p2.pid}")

    return False

if __name__ == "__main__":
    check_progress()
