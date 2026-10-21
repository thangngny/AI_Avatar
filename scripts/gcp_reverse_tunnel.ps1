# NcThang AI Avatar Studio - Google Cloud IAP Reverse Tunnel Runner
param(
    [string]$Zone = "us-central1-a",
    [string]$Project = "project-d112b92d-7a5c-401f-8ec",
    [string]$Instance = "ncthang-ai-avatar-gateway",
    [int]$RemotePort = 18077,
    [int]$LocalPort = 8077
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

Write-Output "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Starting IAP reverse tunnel: VM 127.0.0.1:$RemotePort -> Local 127.0.0.1:$LocalPort" | Tee-Object -FilePath $logFile -Append

$sshArgs = @(
    "compute", "ssh", $Instance,
    "--zone=$Zone",
    "--project=$Project",
    "--tunnel-through-iap",
    "--quiet",
    "--",
    "-N",
    "-R", "127.0.0.1:${RemotePort}:127.0.0.1:${LocalPort}",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "ExitOnForwardFailure=yes"
)

& $gcloud @sshArgs 2>&1 | Tee-Object -FilePath $logFile -Append
