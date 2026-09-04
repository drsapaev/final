#requires -Version 5.1
<#
.SYNOPSIS
    Targeted guard tests for scripts\deploy_restart.ps1 (no Pester dependency).

.DESCRIPTION
    Verifies the P0 contract without deploying anything:
      1. -CheckOnly passes on a clean, synced main tree.
      2. Any untracked file makes -CheckOnly FAIL (the #3005 lesson: an
         untracked leftover blocked a fast-forward).
      3. A held Global\FinalClinicProductionRestart mutex makes the script
         FAIL immediately (no restart attempted - verified by port state).
      4. Mutually exclusive modes are rejected.

    The runtime-restart path is intentionally NOT exercised here; it is
    verified by an actual operator deploy.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test_deploy_restart_guards.ps1
#>

$ErrorActionPreference = 'Continue'
$Repo = 'C:\final'
# The script under test is the WORKTREE copy of this PR (not the deployed
# C:\final\scripts one).
$Script = Join-Path $PSScriptRoot 'deploy_restart.ps1'
$MutexName = 'Global\FinalClinicProductionRestart'
$ProbeFile = Join-Path $Repo 'backend\__guard_probe_untracked.tmp'

$failed = 0

function Assert-ExitCode {
    param([string] $Name, [int] $Expected, [int] $Actual, [string] $Output)
    if ($Actual -eq $Expected) {
        Write-Host "[PASS] $Name"
    } else {
        $script:failed++
        Write-Host "[FAIL] $Name (expected exit $Expected, got $Actual)"
        Write-Host "       output: $($Output -join ' | ')"
    }
}

function Invoke-DeployScript {
    param([string[]] $Arguments)
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $Script @Arguments 2>&1
    return @{ Exit = $LASTEXITCODE; Output = $out }
}

# --- Preconditions ---------------------------------------------------------------
Set-Location $Repo
& git fetch origin --quiet

# Test 1 needs a fully clean, synced tree. Legacy scratch may legitimately be
# present (it becomes ignorable once this PR's .gitignore block is merged), so
# a dirty tree only skips Test 1 - the failure-path tests below are valid
# either way: the new guard must report the dirt it sees.
$cleanTree = ((@(& git status --porcelain)).Count -eq 0) -and
             ((@(& git rev-list --count main..origin/main) | Select-Object -First 1) -eq '0')

# --- Test 1: CheckOnly passes on clean synced tree --------------------------------
if ($cleanTree) {
    $r = Invoke-DeployScript @('-CheckOnly')
    Assert-ExitCode 'CheckOnly passes on clean synced main' 0 $r.Exit ($r.Output | Where-Object { $_ -match 'prechecks passed' })
} else {
    Write-Host '[SKIP] CheckOnly-pass test: main tree is dirty or behind (expected pre-merge; re-run after deploy).'
}

# --- Test 2: untracked file => CheckOnly FAILS ------------------------------------
Set-Content -Path $ProbeFile -Value 'guard probe'
try {
    $r = Invoke-DeployScript @('-CheckOnly')
    $untrackedReported = ($r.Output | Where-Object { $_ -match 'not clean' }).Count -gt 0
    if ($r.Exit -eq 1 -and $untrackedReported) {
        Write-Host '[PASS] untracked file makes CheckOnly FAIL with explicit report'
    } else {
        $script:failed++
        Write-Host "[FAIL] untracked file did not fail CheckOnly (exit=$($r.Exit), reported=$untrackedReported)"
    }
} finally {
    Remove-Item $ProbeFile -Force -ErrorAction SilentlyContinue
}

# --- Test 3: held mutex => immediate FAIL, no restart ------------------------------
$listenerBefore = (Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
$m = New-Object System.Threading.Mutex($false, $MutexName)
$acquired = $false
try { $acquired = $m.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
if ($acquired) {
    try {
        $r = Invoke-DeployScript @('-RestartRuntime')
        $mutexReported = ($r.Output | Where-Object { $_ -match 'mutex' }).Count -gt 0
        $listenerAfter = (Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
        if ($r.Exit -eq 1 -and $mutexReported -and $listenerBefore -eq $listenerAfter) {
            Write-Host '[PASS] held mutex FAILS immediately; uvicorn untouched'
        } else {
            $script:failed++
            Write-Host "[FAIL] held-mutex behavior wrong (exit=$($r.Exit), mutexReported=$mutexReported, pidBefore=$listenerBefore pidAfter=$listenerAfter)"
        }
    } finally {
        try { $m.ReleaseMutex() } catch { }
        $m.Dispose()
    }
} else {
    $script:failed++
    Write-Host '[FAIL] could not acquire mutex for the test (another operation running?)'
    $m.Dispose()
}

# --- Test 4: mutually exclusive modes rejected -------------------------------------
$r = Invoke-DeployScript @('-CheckOnly', '-RestartRuntime')
Assert-ExitCode 'mutually exclusive modes rejected' 1 $r.Exit ($r.Output | Where-Object { $_ -match 'mutually exclusive' })

# --- Summary ------------------------------------------------------------------------
if ($failed -eq 0) {
    Write-Host 'ALL GUARD TESTS PASSED'
    exit 0
}
Write-Host "$failed GUARD TEST(S) FAILED"
exit 1
