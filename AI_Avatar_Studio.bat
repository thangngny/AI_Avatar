@echo off
REM =====================================================================
REM  AI Avatar Studio — local launcher (V1.6.0 hardened)
REM  Starts the Flask controller + opens the browser. The controller drives
REM  the EXISTING MuseTalk v1.5 production renderer (generate_video_from_script.py).
REM  LatentSync is NOT integrated (experimental only).
REM
REM  Operator workflow: Avatar -> Script -> Voice ID -> TEST 10s -> RENDER
REM
REM  Hardening (V1.6.0):
REM    * Launches ONLY the canonical torch-capable runtime. There is NO
REM      fallback to system Python / PATH / py launcher — if the canonical
REM      interpreter is missing, the launcher STOPS (no silent wrong runtime).
REM    * Single-instance is enforced inside run_studio.py: a verified Studio
REM      already owning port 8077 is reused (no duplicate server). An unknown
REM      port owner is reported and never killed.
REM =====================================================================
setlocal

set "STUDIO_PY=D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
set "PORT=8077"
set "HOST=127.0.0.1"

cd /d "%~dp0"

if not exist "%STUDIO_PY%" (
  echo =====================================================================
  echo CANONICAL_RUNTIME_MISSING
  echo   Expected: %STUDIO_PY%
  echo   The canonical torch-capable runtime was not found.
  echo   Refusing to start. No fallback to system Python.
  echo =====================================================================
  exit /b 1
)

echo Starting AI Avatar Studio at http://%HOST%:%PORT% ...
"%STUDIO_PY%" run_studio.py --host %HOST% --port %PORT%

endlocal