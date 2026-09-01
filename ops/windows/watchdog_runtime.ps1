#requires -Version 5.1
<#
.SYNOPSIS
    Local runtime watchdog (second level of monitoring - NEVER deploys).

.DESCRIPTION
    Checks ONLY localhost runtime health of uvicorn (:18000) and the
    cloudflared tunnel process. Performs NO git operations of any kind
    (no fetch, no pull, no deploy - deploy is a human/CI decision).

    After <FailureThreshold> consecutive health failures it restarts the
    CURRENTLY DEPLOYED runtime by invoking scripts\deploy_restart.ps1
    -RestartRuntime, which acquires the same
    Global\FinalClinicProductionRestart mutex as every deploy - so a
    watchdog restart can never race a human/CI deploy.

    cloudflared is checked separately: if the process is missing it is
    restarted with the documented command line (tunnel clinic-api).

    Designed to run under Task Scheduler (every minute). All activity is
    appended to C:\final\output\windows\watchdog.log.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\windows\watchdog_runtime.ps1
#>
[CmdletBinding()]
param(
    [int]$FailureThreshold = 3,
    [int]$PollSeconds = 60,
    [int]$HealthTimeoutSec = 5
)

$ErrorActionPreference = 'Continue'

$MainTree = 'C:\final'
$Port = 18000
$StateFile = Join-Path $MainTree 'output\windows\watchdog_failures.txt'
$LogFile = Join-Path $MainTree 'output\windows\watchdog.log'
$CloudflaredExe = Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe'

function Write-WatchdogLog {
    param([string] $Message)
    $line = '{0} watchdog: {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    try {
        $dir = Split-Path -Parent $LogFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $LogFile -Value $line
    } catch { }
}

function Test-UvicornHealthy {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec $HealthTimeoutSec
        return [bool]$health.ok
    } catch {
        return $false
    }
}

function Get-ConsecutiveFailures {
    if (Test-Path $StateFile) {
        $raw = Get-Content $StateFile -ErrorAction SilentlyContinue
        $n = 0
        [int]::TryParse($raw, [ref]$n) | Out-Null
        return $n
    }
    return 0
}

function Set-ConsecutiveFailures {
    param([int] $Count)
    $dir = Split-Path -Parent $StateFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Set-Content -Path $StateFile -Value $Count
}

# --- 1. uvicorn runtime --------------------------------------------------------
if (Test-UvicornHealthy) {
    $failures = Get-ConsecutiveFailures
    if ($failures -gt 0) {
        Write-WatchdogLog "uvicorn healthy again after $failure(s); counter reset."
    }
    Set-ConsecutiveFailures 0
} else {
    $failures = Get-ConsecutiveFailures + 1
    Set-ConsecutiveFailures $failures
    Write-WatchdogLog "uvicorn unhealthy (consecutive failure #$failures)."

    if ($failures -ge $FailureThreshold) {
        Write-WatchdogLog "threshold reached - restarting CURRENT runtime via deploy_restart.ps1 -RestartRuntime (same mutex as deploy; no git operations)."
        & powershell -NoProfile -ExecutionPolicy Bypass `
            -File (Join-Path $MainTree 'scripts\deploy_restart.ps1') -RestartRuntime 2>&1 |
            ForEach-Object { Write-WatchdogLog "deploy_restart: $_" }

        if (Test-UvicornHealthy) {
            Write-WatchdogLog 'runtime restarted and healthy.'
            Set-ConsecutiveFailures 0
        } else {
            Write-WatchdogLog 'runtime STILL unhealthy after restart - leaving it to the next cycle / operator.'
        }
    }
}

# --- 2. cloudflared tunnel process (checked separately, no git involvement) ----
$cloudflared = Get-Process -Name 'cloudflared' -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-WatchdogLog 'cloudflared process not found - restarting tunnel (documented command line).'
    if (Test-Path $CloudflaredExe) {
        Start-Process -FilePath $CloudflaredExe `
            -ArgumentList '--logfile', 'C:\final\tools\cloudflared.log', 'tunnel', 'run', 'clinic-api' `
            -WindowStyle Hidden
        Write-WatchdogLog 'cloudflared start issued.'
    } else {
        Write-WatchdogLog "cloudflared executable not found at $CloudflaredExe - cannot restart."
    }
}
