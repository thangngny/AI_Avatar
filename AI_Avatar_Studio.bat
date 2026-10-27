@echo off
REM =====================================================================
REM  AI Avatar Studio NextGen V2 — Local Launcher (RTX 5090 Blackwell sm_120)
REM  Multi-Band Laplacian Pyramid + Dental Enamel SOTA
REM =====================================================================
setlocal

set "STUDIO_PY=C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\runtime_avatar_v2\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=C:\Users\phuongpn\runtime_nextgen\venv\Scripts\python.exe"

set "PORT=8178"
set "HOST=127.0.0.1"

cd /d "%~dp0"

if not exist "%STUDIO_PY%" (
  echo =====================================================================
  echo CANONICAL_RUNTIME_MISSING
  echo   Expected: %STUDIO_PY%
  echo   The canonical torch-capable runtime was not found.
  echo   Refusing to start. No fallback to system Python.
  echo =====================================================================
  pause
  exit /b 1
)

echo =====================================================================
echo  AI AVATAR STUDIO NEXTGEN V2 (RTX 5090 BLACKWELL EDITION)
echo  Photoreal Multi-Band Laplacian Pyramid Blending
echo  URL: http://%HOST%:%PORT%/
echo =====================================================================

start "" http://%HOST%:%PORT%/
"%STUDIO_PY%" run_studio.py --host %HOST% --port %PORT%

endlocal
