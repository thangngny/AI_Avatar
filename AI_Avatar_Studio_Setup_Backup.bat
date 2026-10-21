@echo off
setlocal
chcp 65001 >nul
set "STUDIO_PY=D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\runtime\venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
echo === AI Avatar Studio — optional backup scheduler ===
echo   install  : đăng ký backup DB hằng ngày 03:17
echo   verify   : kiểm tra task
echo   remove   : gỡ task
echo.
"%STUDIO_PY%" scripts\setup_backup_schedule.py %*
endlocal