@echo off
REM =====================================================================
REM  AI Avatar Studio — local launcher
REM  Starts the Flask controller + opens the browser. The controller drives
REM  the EXISTING MuseTalk v1.5 production renderer (generate_video_from_script.py).
REM  LatentSync is NOT integrated (experimental only).
REM
REM  Operator workflow: Avatar -> Script -> Voice ID -> TEST 10s -> RENDER
REM =====================================================================
setlocal

REM --- The torch-capable interpreter (only env on this machine with torch).
set "STUDIO_PY=C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
if not exist "%STUDIO_PY%" (
  REM Fallback: use whatever python is on PATH (works if the env is active).
  set "STUDIO_PY=python"
)

set "PORT=8077"
set "HOST=127.0.0.1"

cd /d "%~dp0"

echo Starting AI Avatar Studio at http://%HOST%:%PORT% ...
"%STUDIO_PY%" run_studio.py --host %HOST% --port %PORT%

endlocal