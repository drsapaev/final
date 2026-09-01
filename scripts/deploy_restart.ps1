#requires -Version 5.1
<#
.SYNOPSIS
    Guarded production deploy/restart for the clinic backend (uvicorn :18000).

.DESCRIPTION
    Enforces the Multi-Session Worktree & Deploy Convention (AGENTS.md):
    production may run only from the main tree (C:\final), on branch 'main',
    with a clean tracked tree, synced with origin/main. Optionally restarts
    uvicorn (detached, survives the calling session) and polls /api/v1/health.

.PARAMETER CheckOnly
    Run the guards only; do not fetch/pull or restart.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -CheckOnly
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

$MainTree = 'C:\final'
$Port = 18000
$HealthTimeoutSec = 90

function Fail {
    param([string] $Message)
    Write-Error "deploy_restart: $Message"
    exit 1
}

# --- Guard 1: main tree is on main -------------------------------------------
Set-Location -LiteralPath $MainTree
$branch = (& git branch --show-current)
if ($LASTEXITCODE -ne 0) { Fail "git branch failed in $MainTree." }
if ($branch -ne 'main') {
    Fail "main tree is on branch '$branch' - production deploys only from 'main'. Switch the tree to main after your PR merges, then retry."
}

# --- Guard 2: clean tracked tree ---------------------------------------------
$dirty = @(& git status --porcelain) | Where-Object { $_ -notmatch '^\?\?' }
if ($dirty) {
    Fail "main tree has uncommitted tracked changes: $($dirty -join '; ')"
}

# --- Guard 3: synced with origin/main -----------------------------------------
& git fetch origin --quiet
if ($LASTEXITCODE -ne 0) { Fail "git fetch origin failed (network?)." }
$local = (& git rev-parse HEAD)
$remote = (& git rev-parse origin/main)
if ($local -ne $remote) {
    if ($CheckOnly) {
        Fail "main is not synced with origin/main (local=$local remote=$remote)."
    }
    & git pull --ff-only origin main | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "git pull --ff-only failed." }
    $local = (& git rev-parse HEAD)
    $remote = (& git rev-parse origin/main)
    if ($local -ne $remote) { Fail "fast-forward to origin/main failed." }
    Write-Host "deploy_restart: main fast-forwarded to $remote."
}

if ($CheckOnly) {
    Write-Host 'deploy_restart: prechecks passed (CheckOnly - no restart performed).'
    exit 0
}

# --- Stop current uvicorn -----------------------------------------------------
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

# --- Start detached uvicorn (survives the calling session) --------------------
$python = Join-Path $MainTree 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { Fail "backend venv python not found at $python." }
Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port", '--log-level', 'warning' `
    -WorkingDirectory (Join-Path $MainTree 'backend') `
    -WindowStyle Minimized

# --- Health poll ---------------------------------------------------------------
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
