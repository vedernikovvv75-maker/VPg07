# Start Tor (if needed) and run VPg07 Telegram bot
param(
  [int]$TorPort = 9050,
  [int]$MaxWaitSec = 180
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TorExe = if ($env:TOR_EXE_PATH) { $env:TOR_EXE_PATH } else { "D:\Tor\tor\tor.exe" }
$TorRc = if ($env:TOR_CONFIG_PATH) { $env:TOR_CONFIG_PATH } else { "D:\Tor\data\torrc" }
$TorLog = if ($env:TOR_LOG_PATH) { $env:TOR_LOG_PATH } else { "D:\Tor\data\tor-notices.log" }
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

function Test-TorListening {
  param([int]$Port)
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-TorBootstrap {
  param(
    [string]$LogPath,
    [int]$Port,
    [int]$TimeoutSec
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ((Test-TorListening -Port $Port) -and (Test-Path $LogPath)) {
      $content = Get-Content $LogPath -Raw -ErrorAction SilentlyContinue
      if ($content -match "Bootstrapped 100%") {
        Write-Host "OK: Tor ready at socks5h://127.0.0.1:$Port"
        return
      }
    }
    Write-Host "Waiting for Tor bootstrap on port $Port ..."
    Start-Sleep -Seconds 3
  }
  throw "Tor did not reach Bootstrapped 100% within ${TimeoutSec}s. Check $LogPath or run D:\Tor\start-tor.ps1"
}

Write-Host "VPg07: start bot via Tor"
Write-Host "Tor exe: $TorExe"
Write-Host "Tor rc:  $TorRc"

if (-not (Test-TorListening -Port $TorPort)) {
  if (-not (Test-Path $TorExe)) {
    throw "Tor not found: $TorExe"
  }
  if (-not (Test-Path $TorRc)) {
    throw "torrc not found: $TorRc"
  }
  Write-Host "Starting Tor in background..."
  Start-Process -FilePath $TorExe -ArgumentList "-f", $TorRc -WindowStyle Minimized | Out-Null
  Wait-TorBootstrap -LogPath $TorLog -Port $TorPort -TimeoutSec $MaxWaitSec
} else {
  Write-Host "Tor already listening on port $TorPort"
  if (Test-Path $TorLog) {
    $content = Get-Content $TorLog -Raw -ErrorAction SilentlyContinue
    if ($content -notmatch "Bootstrapped 100%") {
      Write-Host "Port open but bootstrap not confirmed — waiting..."
      Wait-TorBootstrap -LogPath $TorLog -Port $TorPort -TimeoutSec $MaxWaitSec
    }
  }
}

Push-Location $Root
try {
  & $Python main.py
} finally {
  Pop-Location
}
