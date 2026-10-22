@echo off
setlocal
title AI Avatar Studio V2 (RTX 5090 Blackwell Edition)

set "REPO_ROOT=%~dp0"
set "PYTHON_EXE=C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
set "STUDIO_PORT=8178"

echo =======================================================
echo   AI AVATAR STUDIO V2 -- PHOTOREALISTIC HUMAN STUDIO
echo   Operating on Port: %STUDIO_PORT%
echo   Runtime: %PYTHON_EXE%
echo =======================================================

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Canonical Python interpreter not found at: %PYTHON_EXE%
    pause
    exit /b 1
)

cd /d "%REPO_ROOT%"
echo Starting Studio V2 server...
start http://127.0.0.1:%STUDIO_PORT%/
"%PYTHON_EXE%" run_studio_v2.py

endlocal
