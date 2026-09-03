"""Launch persistent GCP tunnel daemon as a fully detached Windows process.
"""
import os
import sys
import subprocess
import time

sys.stdout.reconfigure(encoding="utf-8")

PYTHON_EXE = r"D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
DAEMON_SCRIPT = os.path.join(os.path.dirname(__file__), "gcp_tunnel_daemon.py")
PID_FILE = os.path.join(os.path.dirname(__file__), "..", "diagnostics", "gcp_tunnel.pid")

def is_pid_running(pid: int) -> bool:
    try:
        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"], capture_output=True, text=True)
        return str(pid) in res.stdout
    except Exception:
        return False

def stop_existing():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if is_pid_running(pid):
                print(f"Stopping existing daemon PID {pid}...")
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        except Exception as e:
            print("Error stopping existing PID:", e)
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

def main():
    stop_existing()
    # Stop lingering ssh
    subprocess.run(["powershell", "-Command", "Get-Process *ssh* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"], capture_output=True)
    time.sleep(2)
    
    # Flags for completely detached independent Windows process
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    
    print("Launching independent detached GCP tunnel daemon...")
    proc = subprocess.Popen(
        [PYTHON_EXE, DAEMON_SCRIPT],
        creationflags=flags,
        close_fds=True
    )
    
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
        
    print(f"Detached GCP Tunnel Daemon launched with PID: {proc.pid}")
    print("Saved PID to diagnostics/gcp_tunnel.pid")
    
    # Wait 8s for tunnel to establish
    time.sleep(8)
    if is_pid_running(proc.pid):
        print(f"Verified PID {proc.pid} is ALIVE and RUNNING independently!")
    else:
        print(f"WARNING: PID {proc.pid} is not running!")

if __name__ == "__main__":
    main()
