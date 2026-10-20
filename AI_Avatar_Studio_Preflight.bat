@echo off
REM =====================================================================
REM  AI Avatar Studio — PRE-FLIGHT CHECK (read-only readiness, no render)
REM  Exit codes: 0 READY · 1 READY_WITH_WARNINGS · 2 BLOCKED
REM =====================================================================
setlocal
chcp 65001 >nul
set "STUDIO_PY=D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
"%STUDIO_PY%" scripts/preflight.py %*
set "RC=%ERRORLEVEL%"
echo.
echo (Exit code: %RC% — 0=Sẵn sàng, 1=Cảnh báo, 2=Chặn)
endlocal & exit /b %RC%