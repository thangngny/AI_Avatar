@echo off
setlocal
chcp 65001 >nul
set "STUDIO_PY=C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
"%STUDIO_PY%" scripts\maintenance.py
endlocal