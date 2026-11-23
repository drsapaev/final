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

    The managed uvicorn listener is stopped and verified absent BEFORE any
    migration runs. A failed stop prevents migrations; a failed migration
    leaves the listener stopped and does not launch the new runtime.
    Independently managed queue-writing workers must also be quiesced by
    the operator before Deploy; this script owns only the listener below.

    Modes (mutually exclusive, Deploy is the default):
      -Deploy          sync main with origin/main (ff-only), apply pending
                       database migrations (alembic upgrade head), restart
                       runtime. -SkipMigrations skips the alembic step for
                       a deliberate code-only deploy. -ExpectedRevision
                       requires the fetched main to match a tested Git SHA.
      -RestartRuntime  restart the CURRENTLY DEPLOYED runtime only — no git
                       fetch/pull/mutation, no migrations. This is the only
                       mode a watchdog may call (it must never deploy).
      -CheckOnly       fetch origin and run the checkout guards only.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -CheckOnly
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -Deploy
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_restart.ps1 -RestartRuntime
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$RestartRuntime,
    [switch]$Deploy,
    [switch]$SkipMigrations,
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedRevision
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

function Get-LoopbackListenerPid {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 1 -and $listeners[0].LocalAddress -eq '127.0.0.1' -and $listeners[0].OwningProcess -gt 0) {
        return $listeners[0].OwningProcess
    }
}

# --- Mode resolution ----------------------------------------------------------
$modeCount = @($CheckOnly, $RestartRuntime, $Deploy | Where-Object { $_ }).Count
if ($modeCount -gt 1) {
    Fail "-CheckOnly, -RestartRuntime and -Deploy are mutually exclusive."
}
if (-not $CheckOnly -and -not $RestartRuntime -and -not $Deploy) {
    $Deploy = $true  # backward-compatible default
}
if ($ExpectedRevision -and -not $Deploy) {
    Fail '-ExpectedRevision applies only to -Deploy.'
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

    # --- Guard 1: main tree is on main (ENFORCED FOR EVERY MODE) -------------
    # The runtime is launched from C:\final\backend, so a watchdog restart
    # while the tree sits on a feature branch would deploy unreviewed code.
    # Only the clean-tree and sync checks are relaxed for -RestartRuntime.
    $branch = (& git branch --show-current)
    if ($LASTEXITCODE -ne 0) { Fail "git branch failed in $MainTree." }
    if ($branch -ne 'main') {
        Fail "main tree is on branch '$branch' - production restarts and deploys only run from 'main'. Switch the tree to main, then retry."
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
    $deployRevision = $null
    if ($Deploy) {
        & git fetch origin --quiet
        if ($LASTEXITCODE -ne 0) { Fail "git fetch origin failed (network?). Transient failures must be retried explicitly - this script never loops." }

        $local = (& git rev-parse --verify HEAD)
        if ($LASTEXITCODE -ne 0 -or $local -cnotmatch '^[0-9a-f]{40}$') { Fail 'Cannot resolve the local Git revision.' }
        $deployRevision = (& git rev-parse --verify origin/main)
        if ($LASTEXITCODE -ne 0 -or $deployRevision -cnotmatch '^[0-9a-f]{40}$') { Fail 'Cannot resolve the fetched main Git revision.' }
        if ($ExpectedRevision -and $ExpectedRevision -ine $deployRevision) {
            Fail "fetched main is $deployRevision, expected $ExpectedRevision. No fast-forward or restart performed."
        }
        if ($local -cne $deployRevision) {
            # EAP=Continue around native 2>&1: with EAP='Stop' the first
            # stderr line of git becomes a terminating NativeCommandError.
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            & git merge --ff-only $deployRevision 2>&1 | Out-Null
            $ErrorActionPreference = $prevEap
            if ($LASTEXITCODE -ne 0) { Fail "fast-forward to origin/main failed - resolve (untracked collisions, divergence) manually. This script never loops." }
            $local = (& git rev-parse --verify HEAD)
            if ($LASTEXITCODE -ne 0 -or $local -cne $deployRevision) { Fail 'fast-forward did not reach the selected revision.' }
            Write-Host "deploy_restart: main fast-forwarded to $deployRevision."
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

    $backendDir = Join-Path $MainTree 'backend'
    $python = Join-Path $backendDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { Fail "backend venv python not found at $python." }
    $launcher = Join-Path $MainTree 'scripts\run_uvicorn_prod.ps1'
    if (-not (Test-Path $launcher)) { Fail "launcher script not found at $launcher." }

    # --- Stop current uvicorn -------------------------------------------------
    # Remember the OLD listener pid: if the kill fails (e.g. an elevated
    # process vs a non-elevated shell) and the same pid still answers the
    # health poll afterwards, the deploy DID NOT take effect — fail loudly
    # instead of reporting "healthy" against the previous process
    # (observed 2026-09-06: access-denied taskkill, health passed on the
    # old process, deploy silently skipped).
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $oldPid = $null
    if ($conn) {
        $oldPid = $conn.OwningProcess
        Write-Host "deploy_restart: stopping uvicorn pid=$oldPid."
        taskkill /PID $oldPid /T /F | Out-Null
        Start-Sleep -Seconds 3
        $stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($stillListening) {
            Fail "old uvicorn pid=$oldPid could not be stopped (access denied?) - run this script from an elevated shell or stop the process manually; aborting instead of reporting a false deploy."
        }
    }
    else {
        Write-Host 'deploy_restart: no listener on port; starting fresh.'
    }

    # --- Database migrations: Deploy only --------------------------------------
    # Applied while the OLD runtime is stopped and the NEW one has not
    # started: production code and schema never disagree in service. A
    # failed migration rolls back (transactional DDL) and the Fail path
    # leaves prod down-but-consistent for manual resolution - never
    # half-deployed. Missed on 2026-09-05: code shipped referencing
    # queue_entries.called_by_user_id before 0054 ran, and
    # /registrar/queues/today 500-ed for every registrar until the
    # migration was applied by hand.
    if ($Deploy -and -not $SkipMigrations) {
        Write-Host 'deploy_restart: applying database migrations (alembic upgrade head)...'
        $alembic = Join-Path (Join-Path $backendDir '.venv\Scripts') 'alembic.exe'
        Push-Location $backendDir
        try {
            # EAP=Continue around native 2>&1: alembic writes its INFO logs to
            # stderr, and with EAP='Stop' the first one would be a terminating
            # NativeCommandError before any migration output is visible.
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            & $alembic upgrade head 2>&1 | ForEach-Object { Write-Host "alembic: $_" }
            $alembicExit = $LASTEXITCODE
            $ErrorActionPreference = $prevEap
            if ($alembicExit -ne 0) {
                Fail 'alembic upgrade head failed - resolve manually, then re-run deploy. The runtime was not restarted.'
            }
        } finally {
            Pop-Location
        }
    }

    # --- Start detached uvicorn (survives the calling session) ----------------
    # Single launch point with persistent logging (tools\uvicorn_backend.log):
    # the same script the logon autostart uses, so the command line and the
    # log destination live in exactly one place.
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $launcher `
        -WorkingDirectory $MainTree `
        -WindowStyle Hidden

    # --- Health poll -----------------------------------------------------------
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
    $healthFailure = 'no healthy HTTP response'
    do {
        Start-Sleep -Seconds 3
        $listenerPid = Get-LoopbackListenerPid
        if (-not $listenerPid) {
            $healthFailure = 'could not verify a single IPv4 loopback listener'
            continue
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 5
        } catch {
            $healthFailure = 'no healthy HTTP response'
            continue
        }
        if (-not $health.ok) {
            $healthFailure = 'no healthy HTTP response'
            continue
        }
        if ($listenerPid -ne (Get-LoopbackListenerPid)) {
            $healthFailure = 'loopback listener changed during the health check'
            continue
        }
        if ($oldPid -and $listenerPid -eq $oldPid) {
            Fail "old process pid=$oldPid is still answering after the restart attempt - the new backend did not take over."
        }
        if ($Deploy) {
            if ($health.revision -cne $deployRevision) {
                Fail "runtime response did not prove the selected Git revision $deployRevision."
            }
            if ($health.db -cne 'ok') {
                $healthFailure = 'database check did not report ok'
                continue
            }
            Write-Host "deploy_restart: verified revision $deployRevision."
        }
        Write-Host "deploy_restart: healthy (db=$($health.db)) on port $Port (listener pid=$listenerPid)."
        exit 0
    } while ((Get-Date) -lt $deadline)

    Fail "health check did not turn OK within ${HealthTimeoutSec}s ($healthFailure) - inspect tools\uvicorn_backend.log."
}
finally {
    Release-DeployMutex
}
