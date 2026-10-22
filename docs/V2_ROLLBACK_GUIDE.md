# V2 ROLLBACK & ISOLATION SAFETY GUIDE

## 1. Zero-Risk Isolation Architecture

V2 has been architected under strict non-destructive isolation:
- **Production (V1) Path:** `C:\Users\phuongpn\AI_Avatar_NextGen`
- **V2 Clone Path:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2`
- **Production Runtime:** `C:\Users\phuongpn\runtime_nextgen\venv`
- **V2 Runtime:** `C:\Users\phuongpn\runtime_avatar_v2`
- **Production Port:** `8078`
- **V2 Port:** `8178`

Because zero production code, environment packages, checkpoints, or configuration files were modified during the creation of V2, **V1 remains 100% operational at all times**.

---

## 2. Emergency Rollback / Purge Procedure

If V2 ever needs to be stopped or completely removed:

### Step 1: Terminate V2 Process
Run in PowerShell:
```powershell
Get-NetTCPConnection -LocalPort 8178 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Step 2: Purge V2 Workspaces (Optional)
To completely delete the V2 instance without affecting production:
```powershell
# 1. Remove NTFS Junctions first
cmd /c "rmdir C:\Users\phuongpn\AI_Avatar_NextGen_V2\models"
cmd /c "rmdir C:\Users\phuongpn\AI_Avatar_NextGen_V2\data\avatars"
cmd /c "rmdir C:\Users\phuongpn\AI_Avatar_NextGen_V2\dist_assets"

# 2. Delete V2 repository & runtime
Remove-Item -Recurse -Force "C:\Users\phuongpn\AI_Avatar_NextGen_V2"
Remove-Item -Recurse -Force "C:\Users\phuongpn\runtime_avatar_v2"
```

Production V1 at `C:\Users\phuongpn\AI_Avatar_NextGen` on port 8078 will continue serving requests without interruption.
