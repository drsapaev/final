"""Exercise the actual deploy script with every host mutation replaced.

No real git sync, process kill/start, network call or migration is possible:
all commands are mocked inside a disposable PowerShell child. Only the
hard-coded root, mutex name and alembic executable are redirected; the
script's control flow is executed unchanged.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts" / "deploy_restart.ps1"

HARNESS = r"""
$ErrorActionPreference = 'Stop'
$script:Revision = 'a' * 40
$script:OtherRevision = 'b' * 40
$script:RemoteRevision = $script:Revision
$script:LocalRevision = $script:Revision
$script:Started = $false
$script:Listener = 12001
$script:Now = [datetime]'2026-01-01T00:00:00Z'
if ($env:PROBE_SCENARIO -eq 'no-listener') { $script:Listener = $null }
if ($env:PROBE_SCENARIO -eq 'pinned-deploy') { $script:LocalRevision = $script:OtherRevision }
if ($env:PROBE_SCENARIO -eq 'pin-mismatch') { $script:RemoteRevision = $script:OtherRevision }
if ($env:PROBE_SCENARIO -eq 'invalid-origin-revision') { $script:RemoteRevision = 'not-a-commit' }
function Record-Probe([string]$Event) {
    [IO.File]::AppendAllText($env:PROBE_LOG, ($Event + [Environment]::NewLine))
}
function git {
    $global:LASTEXITCODE = 0
    switch ($args[0]) {
        'branch' { return 'main' }
        'status' { return }
        'rev-parse' {
            if ($args -match '^origin/main(?:\^\{commit\})?$') { return $script:RemoteRevision }
            if ($args -match '^HEAD(?:\^\{commit\})?$') { return $script:LocalRevision }
        }
        'fetch' { Record-Probe 'fetch'; return }
        'merge' {
            if ($args[1] -ne '--ff-only' -or $args[2] -cne $script:Revision) {
                throw 'The merge must use the selected commit, not a moving ref'
            }
            Record-Probe 'merge'
            $script:LocalRevision = $args[2]
            $script:RemoteRevision = $script:OtherRevision
            return
        }
    }
    throw "Unexpected mocked git command: $args"
}
function Set-Location { param($LiteralPath) }
function Push-Location { param($Path) }
function Pop-Location { }
function Test-Path { param($Path, $LiteralPath) return $true }
function New-ProbeListener([int]$ProcessId, [string]$Address = '127.0.0.1') {
    return [pscustomobject]@{ OwningProcess = $ProcessId; LocalAddress = $Address; LocalPort = 18000 }
}
function Get-NetTCPConnection {
    param($LocalPort, $State, $ErrorAction, $LocalAddress)
    if ($LocalPort -ne 18000 -or $State -ne 'Listen') { throw 'Unexpected mocked listener query' }
    if ($script:Started) {
        switch ($env:PROBE_SCENARIO) {
            'listener-missing' { return }
            'listener-old' { New-ProbeListener 12001; return }
            'listener-ambiguous' { New-ProbeListener 12002; New-ProbeListener 12003; return }
            'listener-wildcard' {
                if (-not $LocalAddress) { New-ProbeListener 12002 '0.0.0.0' }
                return
            }
            'listener-unknown-pid' { New-ProbeListener 0; return }
        }
    }
    if ($script:Listener) { New-ProbeListener $script:Listener }
}
function taskkill {
    Record-Probe 'stop'
    $global:LASTEXITCODE = 0
    if ($env:PROBE_SCENARIO -ne 'stop-failure') { $script:Listener = $null }
}
function Start-Sleep { param($Seconds) }
function Get-Date {
    $script:Now = $script:Now.AddSeconds(35)
    return $script:Now
}
function Invoke-MigrationProbe {
    Record-Probe 'migrate'
    $global:LASTEXITCODE = 0
    if ($env:PROBE_SCENARIO -eq 'migration-failure') { $global:LASTEXITCODE = 1 }
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle)
    Record-Probe 'start'
    $script:Started = $true
    $script:Listener = 12002
}
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($Uri -ne 'http://127.0.0.1:18000/api/v1/health') { throw 'Unexpected mocked HTTP request' }
    switch ($env:PROBE_SCENARIO) {
        'revision-missing' { return [pscustomobject]@{ ok = $true; db = 'ok' } }
        'revision-wrong' {
            return [pscustomobject]@{ ok = $true; db = 'ok'; revision = $script:OtherRevision }
        }
        'database-unavailable' {
            return [pscustomobject]@{ ok = $true; db = 'error: OperationalError'; revision = $script:Revision }
        }
        'listener-replaced-during-health' {
            if ($script:Listener -eq 12002) { Record-Probe 'replace-listener' }
            $script:Listener += 1
        }
        'restart' { return [pscustomobject]@{ ok = $true; db = 'error: OperationalError' } }
    }
    return [pscustomobject]@{ ok = $true; db = 'ok'; revision = $script:Revision }
}
$text = [IO.File]::ReadAllText($env:PROBE_SOURCE)
$rootAssignment = "`$MainTree = 'C:\final'"
$mutexAssignment = "`$MutexName = 'Global\FinalClinicProductionRestart'"
$alembicAssignment = "`$alembic = Join-Path (Join-Path `$backendDir '.venv\Scripts') 'alembic.exe'"
foreach ($anchor in @($rootAssignment, $mutexAssignment, $alembicAssignment)) {
    if (-not $text.Contains($anchor)) { throw "Test anchor missing; refuse execution" }
}
$text = $text.Replace($rootAssignment, ("`$MainTree = '" + $env:PROBE_ROOT + "'"))
$text = $text.Replace($mutexAssignment, ("`$MutexName = 'review-test-" + [guid]::NewGuid().ToString('N') + "'"))
$text = $text.Replace($alembicAssignment, "`$alembic = 'Invoke-MigrationProbe'")
$block = [scriptblock]::Create($text)
switch ($env:PROBE_SCENARIO) {
    'restart' { & $block -RestartRuntime }
    'check-only' { & $block -CheckOnly }
    'skip-migrations' { & $block -Deploy -SkipMigrations }
    'pinned-deploy' { & $block -Deploy -ExpectedRevision $script:Revision }
    'pin-mismatch' { & $block -Deploy -ExpectedRevision $script:Revision }
    default { & $block -Deploy }
}
"""


@pytest.mark.parametrize(
    ('scenario', 'expected_exit', 'expected_events'),
    [
        ('deploy', 0, ['fetch', 'stop', 'migrate', 'start']),
        ('pinned-deploy', 0, ['fetch', 'merge', 'stop', 'migrate', 'start']),
        ('pin-mismatch', 1, ['fetch']),
        ('invalid-origin-revision', 1, ['fetch']),
        ('stop-failure', 1, ['fetch', 'stop']),
        ('migration-failure', 1, ['fetch', 'stop', 'migrate']),
        ('restart', 0, ['stop', 'start']),
        ('check-only', 0, ['fetch']),
        ('skip-migrations', 0, ['fetch', 'stop', 'start']),
        ('no-listener', 0, ['fetch', 'migrate', 'start']),
        ('database-unavailable', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('revision-missing', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('revision-wrong', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('listener-missing', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('listener-old', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('listener-ambiguous', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('listener-wildcard', 1, ['fetch', 'stop', 'migrate', 'start']),
        ('listener-unknown-pid', 1, ['fetch', 'stop', 'migrate', 'start']),
        (
            'listener-replaced-during-health',
            1,
            ['fetch', 'stop', 'migrate', 'start', 'replace-listener'],
        ),
    ],
)
def test_deploy_migration_order(tmp_path, scenario, expected_exit, expected_events):
    pwsh = shutil.which('pwsh')
    if not pwsh:
        pytest.skip('PowerShell is required for the host-command mock harness')
    harness = tmp_path / 'harness.ps1'
    harness.write_text(HARNESS)
    log = tmp_path / 'events.log'
    env = dict(os.environ, PROBE_SCENARIO=scenario, PROBE_SOURCE=str(SOURCE),
               PROBE_ROOT=str(tmp_path), PROBE_LOG=str(log))
    result = subprocess.run(
        [pwsh, '-NoProfile', '-File', str(harness)],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )
    events = log.read_text().splitlines() if log.exists() else []
    evidence = json.dumps({'scenario': scenario, 'exit': result.returncode, 'events': events})
    output = result.stdout + result.stderr
    assert result.returncode == expected_exit, evidence + output
    assert events == expected_events, evidence
    if expected_exit == 0 and 'start' in expected_events:
        assert 'deploy_restart: healthy' in output
        assert ('deploy_restart: verified revision ' in output) == (scenario != 'restart')
    elif expected_exit != 0:
        assert 'deploy_restart: healthy' not in output
    if scenario == 'listener-replaced-during-health':
        assert 'health check did not turn OK within' in output
