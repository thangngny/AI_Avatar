@echo off
REM =====================================================================
REM  AI Avatar Studio — Trusted-Collaborator Share launcher (one-click).
REM
REM  DEFAULT (LINK ONLY): no access code, no login. The URL itself is the
REM  temporary access mechanism. Anyone with the active link gets FULL Studio.
REM
REM  Usage:
REM    AI_Avatar_Studio_Share.bat          (link-only — recommended)
REM    AI_Avatar_Studio_Share.bat --auth   (optional legacy access-code gate)
REM =====================================================================
setlocal
cd /d "%~dp0"

set "PSARGS="
if /i "%~1"=="--auth" set "PSARGS=-Auth"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_studio_share.ps1" %PSARGS%

endlocal