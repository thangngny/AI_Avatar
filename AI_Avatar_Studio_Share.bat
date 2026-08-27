@echo off
REM =====================================================================
REM  AI Avatar Studio — Trusted-Collaborator Share launcher (one-click).
REM  Calls scripts/start_studio_share.ps1. Authentic default: AUTH ON.
REM
REM  Usage:
REM    AI_Avatar_Studio_Share.bat            (auth ON — recommended)
REM    AI_Avatar_Studio_Share.bat --no-auth  (auth OFF — public link)
REM =====================================================================
setlocal
cd /d "%~dp0"

set "PSARGS="
if /i "%~1"=="--no-auth" set "PSARGS=-NoAuth"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_studio_share.ps1" %PSARGS%

endlocal