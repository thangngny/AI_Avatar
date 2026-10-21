@echo off
REM NcThang AI Avatar Studio - Google Cloud IAP Reverse Tunnel Runner (Self-Healing)
setlocal
set GCLOUD_CMD=%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd
if not exist "%GCLOUD_CMD%" set GCLOUD_CMD=gcloud.cmd

:loop
echo [%date% %time%] Launching resilient Google Cloud IAP reverse tunnel...
"%GCLOUD_CMD%" compute ssh ncthang-ai-avatar-gateway --zone=us-central1-a --tunnel-through-iap --project=project-d112b92d-7a5c-401f-8ec --quiet --ssh-flag="-N" --ssh-flag="-R 127.0.0.1:18077:127.0.0.1:8077" --ssh-flag="-o ServerAliveInterval=15" --ssh-flag="-o ServerAliveCountMax=3" --ssh-flag="-o ExitOnForwardFailure=yes" --ssh-flag="-o TCPKeepAlive=yes"
echo [%date% %time%] Tunnel exited with code %errorlevel%. Auto-recovering in 3 seconds...
timeout /t 3 /nobreak >nul
goto loop
