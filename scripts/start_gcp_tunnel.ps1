# NcThang AI Avatar Studio - Persistent GCP IAP Reverse SSH Tunnel
# Bridges GCE Gateway 127.0.0.1:18077 -> Local Windows Studio 127.0.0.1:8077

param(
    [string]$Zone = "us-central1-a",
    [string]$Project = "project-d112b92d-7a5c-401f-8ec",
    [string]$Instance = "ncthang-ai-avatar-gateway",
    [int]$RemotePort = 18077,
    [int]$LocalPort = 8077,
    [switch]$SingleRun
)

$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
if (-not (Test-Path $gcloud)) {
    $gcloud = "gcloud"
}

$logDir = "$PSScriptRoot\..\diagnostics"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$logFile = "$logDir\gcp_tunnel.log"

function Write-TunnelLog($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

Write-TunnelLog "=== NcThang GCP Reverse Tunnel Service Started ==="
Write-TunnelLog "Target Instance: $Instance ($Zone, Project: $Project)"
Write-TunnelLog "Mapping: GCE 127.0.0.1:$RemotePort -> Local Windows 127.0.0.1:$LocalPort"

$sshArgs = @(
    "compute", "ssh", $Instance,
    "--zone=$Zone",
    "--project=$Project",
    "--tunnel-through-iap",
    "--quiet",
    "--ssh-flag=-N",
    "--ssh-flag=-R 127.0.0.1:${RemotePort}:127.0.0.1:${LocalPort}"
)

do {
    Write-TunnelLog "Launching gcloud IAP reverse tunnel..."
    & $gcloud @sshArgs 2>&1 | ForEach-Object {
        Write-TunnelLog "SSH: $_"
    }
    
    $exitCode = $LASTEXITCODE
    Write-TunnelLog "SSH tunnel exited with code $exitCode."
    
    if ($SingleRun) {
        break
    }
    
    Write-TunnelLog "Waiting 5 seconds before reconnecting..."
    Start-Sleep -Seconds 5
} while ($true)
