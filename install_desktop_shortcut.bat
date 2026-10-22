@echo off
REM =====================================================================
REM  Install Desktop Shortcut for AI Avatar Studio NextGen
REM =====================================================================
setlocal

set "TARGET_BAT=%~dp0AI_Avatar_Studio.bat"
set "ICON_FILE=%~dp0assets\app_icon.ico"
set "SCRIPT_DIR=%~dp0"

echo Creating desktop shortcut for AI Avatar Studio NextGen...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desktop = $ws.SpecialFolders('Desktop'); " ^
  "$s = $ws.CreateShortcut(\"$desktop\AI Avatar Studio NextGen.lnk\"); " ^
  "$s.TargetPath = '%TARGET_BAT%'; " ^
  "$s.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$s.Description = 'AI Avatar Studio NextGen (RTX 5090 Blackwell Edition)'; " ^
  "if (Test-Path '%ICON_FILE%') { $s.IconLocation = '%ICON_FILE%,0' }; " ^
  "$s.Save(); " ^
  "Write-Host '[OK] Shortcut created successfully on Desktop!'"

pause
endlocal
