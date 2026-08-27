@echo off
REM =====================================================================
REM  AI Avatar Studio — Stop sharing.
REM  Reads only diagnostics\share_runtime.json for THIS share session.
REM  Never kills unrelated python.exe / cloudflared sessions (spec §27/§28).
REM =====================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_studio_share.ps1"
endlocal