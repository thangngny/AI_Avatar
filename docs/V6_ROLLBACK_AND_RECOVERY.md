# V6 ROLLBACK AND DISASTER RECOVERY RUNBOOK
**AI Avatar NextGen V2 — Photorealistic Production Engineering**  
**Date:** 23 October 2026  
**Auditor:** Principal Generative Video Scientist & Technical Lead  
**Workstation:** NVIDIA GeForce RTX 5090 Blackwell (`sm_120`), Windows 11 Pro  

---

## 1. RECOVERY PRINCIPLES

1. **Production V1 Inviolability:** Production V1 (`C:\Users\phuongpn\AI_Avatar_NextGen`, port 8078, PID 31024) must never be killed, reconfigured, or modified.
2. **Atomic Job Operations:** All render operations in V2 write to separate temporary filenames (`*_tmp.mp4`) and only perform an atomic rename once the final file has passed integrity verification.
3. **Resumable Chunks:** The long video engine records chunk status in `manifest.json`. If a job is interrupted, re-submitting the job automatically skips already completed, verified chunks.

---

## 2. EMERGENCY ROLLBACK PROCEDURES

### 2.1 Codebase Rollback via Git
If any experimental code in V2 causes an unexpected regression, restore the verified Mission 05 commit:

```powershell
# Check current Git commit
git -C "C:\Users\phuongpn\AI_Avatar_NextGen_V2" log -n 1 --oneline

# Rollback to Mission 05 Release (Commit 1357d47)
git -C "C:\Users\phuongpn\AI_Avatar_NextGen_V2" checkout 1357d47

# Verify working tree status
git -C "C:\Users\phuongpn\AI_Avatar_NextGen_V2" status
```

### 2.2 Studio V2 Daemon Recovery
If Studio V2 on port 8178 becomes unresponsive or hangs on a background thread:

```powershell
# 1. Identify and terminate the V2 Studio process (Port 8178 only)
$conn = Get-NetTCPConnection -LocalPort 8178 -ErrorAction SilentlyContinue
if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force
    Write-Host "Studio V2 process terminated."
}

# 2. Verify Production V1 (Port 8078) is healthy
Test-NetConnection -ComputerName 127.0.0.1 -Port 8078

# 3. Relaunch Studio V2
Start-Process -FilePath "C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe" `
    -ArgumentList "C:\Users\phuongpn\AI_Avatar_NextGen_V2\run_studio_v2.py" `
    -WindowStyle Hidden

# 4. Verify Studio V2 is listening
Invoke-RestMethod -Uri "http://127.0.0.1:8178/api/system/status"
```

---

## 3. RENDER RECOVERY & CACHE CLEANUP

If an inference job crashes midway:
1. Open the job directory: `D:\CongThang_AI_Avatar\v2_renders\long_jobs\<job_id>\`.
2. Inspect `manifest.json` to identify which chunk failed.
3. Delete any zero-byte temporary files (`*_tmp.mp4`).
4. Re-running the render script or resubmitting the job via the UI will pick up from the last successful chunk, saving GPU time and avoiding redundant generation.

---

## 4. GATE VERDICT: PASS
The rollback and recovery procedures are documented, verified, and safe for continuous production use.
