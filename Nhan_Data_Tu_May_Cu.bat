@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================================
echo     AI AVATAR STUDIO - ĐỒNG BỘ DỮ LIỆU TỪ MÁY CŨ SANG MÁY NÀY (LAN)
echo ====================================================================

REM Prefer the venv python if present, else fallback to system python
set "PY=python"
if exist "..\runtime\venv\Scripts\python.exe" set "PY=..\runtime\venv\Scripts\python.exe"

%PY% tools\sync_from_old_machine.py %*
pause
