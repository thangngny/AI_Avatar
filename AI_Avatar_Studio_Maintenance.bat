@echo off
setlocal
chcp 65001 >nul
set "STUDIO_PY=C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
"%STUDIO_PY%" scripts\maintenance.py
endlocal