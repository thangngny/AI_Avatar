"""NcThang AI Avatar Studio - Persistent GCP IAP Reverse SSH Tunnel Daemon.
Bridges GCE Gateway 127.0.0.1:18077 -> Local Windows Studio 127.0.0.1:8077 via Google Cloud IAP.
"""
import os
import sys
import time
import signal
import subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ID = "project-d112b92d-7a5c-401f-8ec"
ZONE = "us-central1-a"
INSTANCE = "ncthang-ai-avatar-gateway"
REMOTE_PORT = 18077
LOCAL_PORT = 8077

GCLOUD_BIN = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")
SSH_BIN = r"C:\Windows\System32\OpenSSH\ssh.exe"
KEY_FILE = os.path.expanduser(r"~/.ssh/google_compute_engine")
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "diagnostics", "gcp_tunnel.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

running = True

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def handle_sig(sig, frame):
    global running
    log(f"Received signal {sig}, stopping tunnel daemon...")
    running = False

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

def run_tunnel_cycle():
    proxy_cmd = f'"{GCLOUD_BIN}" compute start-iap-tunnel {INSTANCE} %p --listen-on-stdin --project={PROJECT_ID} --zone={ZONE} --verbosity=warning'
    args = [
        SSH_BIN,
        "-N",
        "-R", f"127.0.0.1:{REMOTE_PORT}:127.0.0.1:{LOCAL_PORT}",
        "-i", KEY_FILE,
        "-o", f"ProxyCommand={proxy_cmd}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "thawsng04_gmail_com@compute.instance"
    ]
    log(f"Spawning OpenSSH tunnel: GCE 127.0.0.1:{REMOTE_PORT} -> Local 127.0.0.1:{LOCAL_PORT}")
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc

def main():
    log("=== NcThang GCP IAP Reverse Tunnel Daemon Initialized ===")
    log(f"Target: {INSTANCE} ({ZONE}, Project: {PROJECT_ID})")
    
    while running:
        proc = run_tunnel_cycle()
        log(f"Tunnel process running with PID {proc.pid}")
        
        while running:
            poll = proc.poll()
            if poll is not None:
                out, err = proc.communicate()
                log(f"Tunnel process PID {proc.pid} exited with return code {poll}.")
                if err and err.strip():
                    log(f"Tunnel stderr: {err.strip()}")
                break
            time.sleep(2)
            
        if not running:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            break
            
        log("Re-establishing tunnel in 5 seconds...")
        time.sleep(5)

    log("=== NcThang GCP IAP Reverse Tunnel Daemon Stopped ===")

if __name__ == "__main__":
    main()
