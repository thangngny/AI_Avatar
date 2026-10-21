@echo off
setlocal
chcp 65001 >nul
set "STUDIO_PY=D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
echo === DRY RUN (không xóa gì) ===
"%STUDIO_PY%" scripts\cleanup.py --dry-run %*
echo.
echo Để xóa thật, chạy: scripts\cleanup.py --yes
echo Hoặc dùng AI_Avatar_Studio_Maintenance.bat (mục 6/7, có xác nhận).
endlocal