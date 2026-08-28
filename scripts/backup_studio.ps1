@echo off
REM =====================================================================
REM  AI Avatar Studio — safe SQLite + critical-state backup
REM  Uses the SQLite online backup API (transaction-safe on live WAL DB).
REM  Default destination: D:\CongThang_AI_Avatar\backups
REM  Usage: scripts\backup_studio.ps1 [DEST_DIR]
REM =====================================================================
setlocal
chcp 65001 >nul
set "STUDIO_PY=C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=python"
cd /d "%~dp0.."
set "PYTHONIOENCODING=utf-8"
"%STUDIO_PY%" scripts\backup_studio.py %*
endlocal & exit /b %ERRORLEVEL%