@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================================
echo     AI AVATAR STUDIO - TỰ ĐỘNG TẢI MODELS & AVATARS TỪ CLOUD
echo ====================================================================

set "PY=python"
if exist "..\runtime\venv\Scripts\python.exe" set "PY=..\runtime\venv\Scripts\python.exe"

%PY% tools\download_cloud_assets.py %*
pause
