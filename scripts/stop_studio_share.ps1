<#
.SYNOPSIS
  Stop the AI Avatar Studio share session.
.DESCRIPTION
  Reads diagnostics/share_runtime.json for THIS share session only, kills the
  cloudflared child, disables the share gate, and stops the Studio ONLY if the
  launcher itself started it. Never kills unrelated python.exe / cloudflared
  sessions (spec 27/28). Does NOT store/read the access code or API key.

  ASCII-only output on purpose (see start_studio_share.ps1 header).
#>
[CmdletBinding()]
param([int]$Port = 8077)

$ErrorActionPreference = "SilentlyContinue"
$Repo = Split-Path -Parent $PSScriptRoot
$RuntimeFile = Join-Path $Repo "diagnostics\share_runtime.json"
$Base = "http://127.0.0.1:$Port"

function Out([Parameter()]$m){ Write-Host $m }
function Warn([Parameter()]$m){ Write-Host $m -ForegroundColor Yellow }
function Good([Parameter()]$m){ Write-Host $m -ForegroundColor Green }
function Bad([Parameter()]$m){ Write-Host $m -ForegroundColor Red }

if (-not (Test-Path $RuntimeFile)) { Bad "Khong co share_runtime.json - khong co phien chia se nao duoc ghi nhan."; exit 0 }
$st = Get-Content $RuntimeFile -Raw | ConvertFrom-Json

# 1. Stop the cloudflared child for THIS session only.
if ($st.cloudflared_pid) {
  $p = Get-Process -Id $st.cloudflared_pid -ErrorAction SilentlyContinue
  if ($p) { Warn "Dung cloudflared (PID $($st.cloudflared_pid))..."; Stop-Process -Id $st.cloudflared_pid -Force } else { Out "cloudflared PID $($st.cloudflared_pid) khong con chay." }
}

# 2. Disable the share gate (owner-direct only; best-effort).
try { Invoke-RestMethod "$Base/api/share/disable" -Method Post -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null; Good "Share gate da tat." } catch { Out "Studio khong phan hoi /api/share/disable (co the da dung)." }

# 3. Stop Studio ONLY if the launcher started it.
if ($st.studio_started_by_share_launcher -and $st.studio_pid) {
  $p = Get-Process -Id $st.studio_pid -ErrorAction SilentlyContinue
  if ($p) { Warn "Studio do launcher khoi dong -> dung PID $($st.studio_pid)."; Stop-Process -Id $st.studio_pid -Force } else { Out "Studio PID $($st.studio_pid) khong con chay." }
} else {
  Out "Studio da chay tu truoc phien chia se - KHONG dung (spec 27)."
}

# 4. Clear runtime state.
Remove-Item $RuntimeFile -Force -ErrorAction SilentlyContinue
Good "Da ngung chia se. URL trycloudflare cu khong con truy cap duoc."