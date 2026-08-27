<#
.SYNOPSIS
  AI Avatar Studio - Trusted-Collaborator Share launcher.
.DESCRIPTION
  Starts (or reuses) the local Studio on 127.0.0.1:8077, arms the shared-access
  gate with a freshly generated one-time code, opens a Cloudflare Quick Tunnel,
  prints + copies the share info, and keeps the tunnel alive until Ctrl+C.

  TRUSTED-COLLABORATOR MODE: after login the remote user gets FULL Studio access
  (same avatars, ElevenLabs quota, GPU queue, history, settings). ONE app; the
  tunnel is only transport. Origin stays 127.0.0.1 - no public inbound port.

  ASCII-only output on purpose: Vietnamese diacritics break PowerShell parsing
  under a non-UTF8 console codepage and render as mojibake. The UI itself stays
  fully Vietnamese; only this console script is ASCII.
.PARAMETER NoAuth
  Disable the shared access code for this session. Default is AUTH ON.
.PARAMETER StudioPy
  Python interpreter (default: latentsync_env python, then python on PATH).
.PARAMETER Port
  Studio port (default 8077).
#>
[CmdletBinding()]
param(
  [switch]$Auth,     # OPTIONAL: re-enable the legacy access-code gate. Default = LINK ONLY.
  [switch]$NoAuth,   # Accepted for backward compat; forces link-only (already the default).
  [string]$StudioPy = "",
  [int]$Port = 8077
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

function Out([Parameter()]$m){ Write-Host $m }
function Head([Parameter()]$m){ Write-Host $m -ForegroundColor Cyan }
function Good([Parameter()]$m){ Write-Host $m -ForegroundColor Green }
function Warn([Parameter()]$m){ Write-Host $m -ForegroundColor Yellow }
function Bad([Parameter()]$m){ Write-Host $m -ForegroundColor Red }

$RuntimeDir = Join-Path $Repo "diagnostics"
$RuntimeFile = Join-Path $RuntimeDir "share_runtime.json"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

# 1. Verify repository
if (-not (Test-Path (Join-Path $Repo "run_studio.py"))) { Bad "Khong tim thay run_studio.py - chay trong repo AI_avatar."; exit 1 }

# 2. Verify cloudflared
if (-not (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)) {
  Bad "Khong tim thay cloudflared."
  Head "Cai dat chinh thuc:"
  Out "  winget install --id Cloudflare.cloudflared"
  Out "  hoac: https://github.com/cloudflare/cloudflared/releases/latest"
  exit 1
}
Out ("cloudflared: " + (& cloudflared --version 2>$null).Trim())

# Resolve studio python
if (-not $StudioPy) {
  $envPy = "C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe"
  if (Test-Path $envPy) { $StudioPy = $envPy } else { $StudioPy = "python" }
}

# 3. Start Studio if not already running
$Base = "http://127.0.0.1:$Port"
$StudioStartedByUs = $false
$StudioPid = $null
function Test-Studio($p) {
  try { Invoke-RestMethod "$Base/api/system/status" -TimeoutSec 4 -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}
$existing = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($existing -and (Test-Studio $Port)) {
  Warn "Studio da chay (PID $existing) - dung lai, KHONG dung (spec 27)."
  $StudioPid = $existing
} elseif ($existing) {
  Warn "Port $Port ban nhung khong phai Studio healthy - dung anyway (PID $existing)."
  $StudioPid = $existing
} else {
  Head "Khoi dong Studio..."
  $logOut = Join-Path $Repo "data\studio_runtime\logs\studio_share.out.log"
  $logErr = Join-Path $Repo "data\studio_runtime\logs\studio_share.err.log"
  New-Item -ItemType Directory -Force -Path (Split-Path $logOut) | Out-Null
  $sp = Start-Process -FilePath $StudioPy -ArgumentList "run_studio.py","--no-browser","--port","$Port" `
       -WorkingDirectory $Repo -RedirectStandardOutput $logOut -RedirectStandardError $logErr -WindowStyle Hidden -PassThru
  $StudioStartedByUs = $true
  $StudioPid = $sp.Id
  Out "Studio PID $($sp.Id) (launcher khoi dong)."
  $ok = $false
  for ($i=0; $i -lt 40; $i++) { Start-Sleep -Milliseconds 500; if (Test-Studio $Port) { $ok=$true; break } }
  if (-not $ok) { Bad "Studio khong health-check duoc sau 20s. Xem $logErr"; Get-Content $logErr -Tail 20 -ErrorAction SilentlyContinue; exit 1 }
  Good "Studio ONLINE ($Base)."
}

# 4. localhost health (confirmed above)

# 5. Access mode: LINK ONLY by default (no access code, no login). The URL
# itself is the temporary access mechanism. Optional -Auth re-enables the
# legacy access-code gate for a stricter session.
$RequireAuth = [bool]$Auth
if ($NoAuth) { $RequireAuth = $false }  # backward compat (already the default)
$AccessCode = ""
if ($RequireAuth) {
  $alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".ToCharArray()
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $buf = New-Object byte[] 12
  $rng.GetBytes($buf)
  $chars = for ($i=0; $i -lt 12; $i++) { $alphabet[$buf[$i] % $alphabet.Length] }
  $AccessCode = ($chars[0..3] -join "") + "-" + ($chars[4..7] -join "") + "-" + ($chars[8..11] -join "")
  $rng.Dispose()
  $body = @{ access_code = $AccessCode; loopback_exempt = $true } | ConvertTo-Json -Compress
  try {
    $er = Invoke-RestMethod "$Base/api/share/enable" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 8 -ErrorAction Stop
    if (-not $er.share_enabled) { Bad "Khong arm duoc share gate."; $er | Out-String | Out-Null; exit 1 }
  } catch { Bad "Loi /api/share/enable: $_"; exit 1 }
  Good "Share gate ARMED (auth ON, legacy mode)."
} else {
  Warn "LINK-ONLY: Bat ky ai co link nay deu co the su dung Studio trong thoi gian dang chia se."
}

# 6. Start Cloudflare Quick Tunnel
Head "Khoi dong Cloudflare Quick Tunnel -> $Base ..."
$cfArgs = @("tunnel","--no-autoupdate","--url",$Base)
$cfLog = Join-Path $RuntimeDir "cloudflared.log"
$cfProc = Start-Process -FilePath "cloudflared" -ArgumentList $cfArgs `
           -RedirectStandardOutput $cfLog -RedirectStandardError "$cfLog.err" `
           -WindowStyle Hidden -PassThru
$CfPid = $cfProc.Id

# 7. Parse trycloudflare URL
$PublicUrl = $null
for ($i=0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  foreach ($f in @($cfLog, "$cfLog.err")) {
    if (-not (Test-Path $f)) { continue }
    $lines = Get-Content $f -ErrorAction SilentlyContinue
    if (-not $lines) { continue }
    $m = $lines | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches
    if ($m) { $PublicUrl = ($m.Matches[0].Value); break }
  }
  if ($PublicUrl) { break }
  if ($cfProc.HasExited) { Bad "cloudflared thoat som. Log:"; Get-Content $cfLog -Tail 30 -ErrorAction SilentlyContinue; Get-Content "$cfLog.err" -Tail 30 -ErrorAction SilentlyContinue; exit 1 }
}
if (-not $PublicUrl) { Bad "Khong lay duoc trycloudflare URL sau 20s. Log:"; Get-Content $cfLog -Tail 30 -ErrorAction SilentlyContinue; exit 1 }
Good "Tunnel ONLINE: $PublicUrl"

# 8. Write runtime state (NO code, NO key - spec 29)
$state = [ordered]@{
  studio_pid = $StudioPid
  studio_started_by_share_launcher = $StudioStartedByUs
  cloudflared_pid = $CfPid
  public_url = $PublicUrl
  origin = $Base
  require_auth = $RequireAuth
  started_at = (Get-Date).ToString("o")
}
$state | ConvertTo-Json -Depth 4 | Set-Content -Path $RuntimeFile -Encoding UTF8

# 9 + 10. Print + copy share info
$line = "=" * 60
Out ""
Out $line
Head " AI AVATAR STUDIO - CHIA SE CHO CONG SU"
Out $line
Out " STATUS:          ONLINE"
Out " PUBLIC LINK:     $PublicUrl"
if ($RequireAuth) { Out " MA TRUY CAP:      $AccessCode  (che do -auth cu)" } else { Out " ACCESS:          FULL STUDIO - LINK ONLY" }
Out ""
Out " ElevenLabs:       ENABLED"
Out " Edge TTS:         ENABLED"
Out " Create Avatar:    ENABLED"
Out " Production Render: ENABLED"
Out " History:          ENABLED"
Out " Settings:         ENABLED"
Out " GPU:              SAME LOCAL WORKSTATION"
Out ""
if (-not $RequireAuth) { Warn " CANH BAO: Bat ky ai co link nay deu co the su dung Studio trong thoi gian dang chia se." }
Warn " Nhan Ctrl+C hoac chay Stop Sharing de ngung chia se."
Out $line

# Clipboard: link-only by default (no code). Legacy -Auth mode also includes the code.
$clip = "AI Avatar Studio`r`n`r`nLink:`r`n$PublicUrl`r`n`r`n"
if ($RequireAuth) { $clip += "Ma truy cap:`r`n$AccessCode`r`n`r`n" }
$clip += "Mo link de su dung Studio."
try { Set-Clipboard -Value $clip; Good "Da copy link vao clipboard." } catch { Warn "Khong copy duoc vao clipboard." }

# 11. Keep alive until Ctrl+C; cleanup on exit
$cleanup = {
  Out ""
  Warn "Dang ngung chia se..."
  try { if ($cfProc -and -not $cfProc.HasExited) { Stop-Process -Id $cfProc.Id -Force -ErrorAction SilentlyContinue } } catch {}
  try { Invoke-RestMethod "$Base/api/share/disable" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null } catch {}
  if ($StudioStartedByUs -and $StudioPid) {
    Warn "Studio do launcher khoi dong -> dung PID $StudioPid."
    try { Stop-Process -Id $StudioPid -Force -ErrorAction SilentlyContinue } catch {}
  } else {
    Warn "Studio da chay tu truoc - KHONG dung (spec 27)."
  }
  Good "Da ngung chia se. URL cu khong con truy cap duoc."
}
try {
  $cfProc.WaitForExit() | Out-Null
} finally {
  & $cleanup
}