#requires -Version 5.1
<#
.SYNOPSIS
    Guarded production deploy/restart for the clinic backend (uvicorn :18000).

.DESCRIPTION
    Enforces the Multi-Session Worktree & Deploy Convention (AGENTS.md, #3001):
    production may run only from the main tree (C:\final), on branch 'main',
    with a fully clean tracked AND untracked tree, synced with origin/main.

    A global named mutex serializes every deploy/restart/watchdog on this
    host: while one operation holds Global\FinalClinicProductionRestart,
    any other deploy/restart attempt FAILS immediately without killing
    processes, restarting, or mutating git state.

    Modes (mutually exclusive, Deploy is the default):
      -Deploy          sync main with origin/main (ff-only) + restart runtime.
      -RestartRuntime  restart the CURRENTLY DEPLOYED runtime only — no git
                       fetch/pull/mutation. This is the only mode a watchdog
                       may call (it must never deploy).
      -CheckOnly       run the guards only; nothing is fetched or restarted.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -CheckOnly
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -Deploy
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -RestartRuntime
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$RestartRuntime,
    [switch]$Deploy
)

$ErrorActionPreference = 'Stop'

$MainTree = 'C:\final'
$Port = 18000
$HealthTimeoutSec = 90
$MutexName = 'Global\FinalClinicProductionRestart'

function Fail {
    param([string] $Message)
    Write-Error "deploy_restart: $Message"
    exit 1
}

# --- Mode resolution ----------------------------------------------------------
$modeCount = @($CheckOnly, $RestartRuntime, $Deploy | Where-Object { $_ }).Count
if ($modeCount -gt 1) {
    Fail "-CheckOnly, -RestartRuntime and -Deploy are mutually exclusive."
}
if (-not $CheckOnly -and -not $RestartRuntime -and -not $Deploy) {
    $Deploy = $true  # backward-compatible default
}

# --- Mutex: serialize deploy/restart/watchdog on this host --------------------
# Held for the whole operation. If it is busy, we FAIL before touching git,
# the port, or any process — no taskkill, no restart, no git mutation.
$script:DeployMutex = $null
function Acquire-DeployMutex {
    $m = New-Object System.Threading.Mutex($false, $MutexName)
    $acquired = $false
    try {
        $acquired = $m.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        # Previous holder died without releasing — the mutex is ours now.
        $acquired = $true
    }
    if (-not $acquired) {
        $m.Dispose()
        Fail ("deployment/restart mutex '$MutexName' is held by another " +
              'process - refusing (no taskkill, no restart, no git mutation). ' +
              'Wait for the other operation to finish and retry.')
    }
    $script:DeployMutex = $m
    Write-Host "deploy_restart: acquired $MutexName."
}

function Release-DeployMutex {
    if ($script:DeployMutex) {
        try { $script:DeployMutex.ReleaseMutex() } catch { }
        $script:DeployMutex.Dispose()
        $script:DeployMutex = $null
    }
}

try {
    Acquire-DeployMutex

    Set-Location -LiteralPath $MainTree

    # --- Guard 1: main tree is on main (skipped for pure runtime restart) ----
    if (-not $RestartRuntime) {
        $branch = (& git branch --show-current)
        if ($LASTEXITCODE -ne 0) { Fail "git branch failed in $MainTree." }
        if ($branch -ne 'main') {
            Fail "main tree is on branch '$branch' - production deploys only from 'main'. Switch the tree to main after your PR merges, then retry."
        }
    }

    # --- Guard 2: fully clean tree (tracked changes AND untracked files) -----
    # Untracked files have already blocked a fast-forward once (#3005's test
    # file collided with an untracked leftover), so ANY porcelain entry is a
    # hard failure. Files covered by .gitignore (venv, worktrees, output,
    # legacy scratch) do not appear in porcelain and do not interfere.
    # We never move or delete foreign files automatically.
    if (-not $RestartRuntime) {
        $dirty = @(& git status --porcelain)
        if ($dirty.Count -gt 0) {
            Fail ("main tree is not clean - refusing to deploy. Entries: " +
                  ($dirty -join '; ') +
                  " . Move session scratch into your worktree or extend " +
                  ".gitignore deliberately; never auto-delete foreign files.")
        }
    }

    # --- Git sync: Deploy only (RestartRuntime must not mutate git) ----------
    if ($Deploy) {
        & git fetch origin --quiet
        if ($LASTEXITCODE -ne 0) { Fail "git fetch origin failed (network?). Transient failures must be retried explicitly - this script never loops." }

        $local = (& git rev-parse HEAD)
        $remote = (& git rev-parse origin/main)
        if ($local -ne $remote) {
            & git merge --ff-only origin/main 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) { Fail "fast-forward to origin/main failed - resolve (untracked collisions, divergence) manually. This script never loops." }
            $local = (& git rev-parse HEAD)
            $remote = (& git rev-parse origin/main)
            if ($local -ne $remote) { Fail "fast-forward to origin/main did not stick." }
            Write-Host "deploy_restart: main fast-forwarded to $remote."
        }
    }
    elseif ($CheckOnly) {
        & git fetch origin --quiet
        if ($LASTEXITCODE -ne 0) { Fail "git fetch origin failed (network?)." }
        $local = (& git rev-parse HEAD)
        $remote = (& git rev-parse origin/main)
        if ($local -ne $remote) {
            Fail "main is not synced with origin/main (local=$local remote=$remote)."
        }
        Write-Host 'deploy_restart: prechecks passed (CheckOnly - no restart performed).'
        exit 0
    }

    # --- Stop current uvicorn -------------------------------------------------
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) {
        Write-Host "deploy_restart: stopping uvicorn pid=$($conn.OwningProcess)."
        taskkill /PID $conn.OwningProcess /T /F | Out-Null
        Start-Sleep -Seconds 3
    }
    else {
        Write-Host 'deploy_restart: no listener on port; starting fresh.'
    }

    # --- Start detached uvicorn (survives the calling session) ----------------
    $python = Join-Path $MainTree 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { Fail "backend venv python not found at $python." }
    Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port", '--log-level', 'warning' `
        -WorkingDirectory (Join-Path $MainTree 'backend') `
        -WindowStyle Minimized

    # --- Health poll -----------------------------------------------------------
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
    do {
        Start-Sleep -Seconds 3
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 5
            if ($health.ok) {
                Write-Host "deploy_restart: healthy (db=$($health.db)) on port $Port."
                exit 0
            }
        }
        catch {
            # not up yet
        }
    } while ((Get-Date) -lt $deadline)

    Fail "health check did not turn OK within ${HealthTimeoutSec}s - inspect the uvicorn window."
}
finally {
    Release-DeployMutex
}
