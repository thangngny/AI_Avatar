# AI Avatar Studio — canonical runtime rebuild (V1.6.0, reproducible).
# Recreates a clean, product-owned, self-contained Python 3.10 venv with the
# EXACT PROVEN_REAL dependency lock (torch 2.5.1+cu121, CUDA 12.1, 2x RTX 3090).
# Does NOT copy any venv. Does NOT modify PATH, .env, registry, or MuseTalk.
# Does NOT delete old environments.
#
# Usage (operator, from an admin PowerShell):
#   .\tools\rebuild_runtime.ps1
#   .\tools\rebuild_runtime.ps1 -Python "C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe"
param(
    [string]$Python = "C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe",
    [string]$Venv   = "D:\CongThang_AI_Avatar\runtime\venv",
    [string]$Repo   = "C:\CongThang_AI_Avatar\AI_avatar"
)

$ErrorActionPreference = "Stop"
$Vpy = Join-Path $Venv "Scripts\python.exe"

Write-Host "=== AI Avatar Studio — canonical runtime rebuild ===" -ForegroundColor Cyan
Write-Host "  base Python : $Python"
Write-Host "  canonical   : $Venv"
Write-Host "  repo        : $Repo"

if (-not (Test-Path $Python)) { throw "Base Python not found: $Python" }

# 1) create a fresh venv (remove an existing half-built one only if you pass -Clean manually)
if (-not (Test-Path (Join-Path $Venv "pyvenv.cfg"))) {
    Write-Host "Creating venv..." -ForegroundColor Yellow
    & $Python -m venv $Venv
}

# 2) upgrade pip tooling
Write-Host "Upgrading pip tooling..." -ForegroundColor Yellow
& $Vpy -m pip install --upgrade pip wheel setuptools

# 3) torch stack from the official cu121 index (EXACT proven versions)
Write-Host "Installing torch 2.5.1+cu121 / torchvision 0.20.1+cu121 (cu121 index)..." -ForegroundColor Yellow
& $Vpy -m pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 4) the rest of the project lock from PyPI (torch/torchvision already satisfied -> skipped)
Write-Host "Installing project lock..." -ForegroundColor Yellow
Push-Location $Repo
& $Vpy -m pip install -r requirements-handover.lock
Pop-Location

# 5) health gate
Write-Host "pip check..." -ForegroundColor Yellow
& $Vpy -m pip check

# 6) verify_runtime
Write-Host "verify_runtime..." -ForegroundColor Yellow
& $Vpy (Join-Path $Repo "tools\verify_runtime.py")

Write-Host "=== rebuild complete ===" -ForegroundColor Cyan
Write-Host "Cutover: set STUDIO_TORCH_PYTHON=$Vpy and update AI_Avatar_Studio.bat STUDIO_PY=$Vpy" -ForegroundColor Green