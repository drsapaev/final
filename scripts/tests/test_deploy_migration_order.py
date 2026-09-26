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
$script:Listener = 12001
if ($env:PROBE_SCENARIO -eq 'no-listener') { $script:Listener = $null }
function Record-Probe([string]$Event) {
    [IO.File]::AppendAllText($env:PROBE_LOG, ($Event + [Environment]::NewLine))
}
function git {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'branch') { return 'main' }
    if ($args[0] -eq 'rev-parse') { return 'verified-main-sha' }
    if ($args[0] -eq 'fetch') { Record-Probe 'fetch' }
}
function Set-Location { param($LiteralPath) }
function Push-Location { param($Path) }
function Pop-Location { }
function Test-Path { param($Path, $LiteralPath) return $true }
function Get-NetTCPConnection {
    param($LocalPort, $State, $ErrorAction)
    if ($script:Listener) { return [pscustomobject]@{ OwningProcess = $script:Listener } }
}
function taskkill {
    Record-Probe 'stop'
    $global:LASTEXITCODE = 0
    if ($env:PROBE_SCENARIO -ne 'stop-failure') { $script:Listener = $null }
}
function Start-Sleep { param($Seconds) }
function Invoke-MigrationProbe {
    Record-Probe 'migrate'
    $global:LASTEXITCODE = 0
    if ($env:PROBE_SCENARIO -eq 'migration-failure') { $global:LASTEXITCODE = 1 }
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle)
    Record-Probe 'start'
    $script:Listener = 12002
}
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    return [pscustomobject]@{ ok = $true; db = 'synthetic' }
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
    default { & $block -Deploy }
}
"""


@pytest.mark.parametrize(
    ('scenario', 'expected_exit', 'expected_events'),
    [
        ('deploy', 0, ['stop', 'migrate', 'start']),
        ('stop-failure', 1, ['stop']),
        ('migration-failure', 1, ['stop', 'migrate']),
        ('restart', 0, ['stop', 'start']),
        ('check-only', 0, []),
        ('skip-migrations', 0, ['stop', 'start']),
        ('no-listener', 0, ['migrate', 'start']),
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
    critical = [e for e in events if e != 'fetch']
    evidence = json.dumps({'scenario': scenario, 'exit': result.returncode, 'events': events})
    assert result.returncode == expected_exit, evidence + result.stdout + result.stderr
    assert critical == expected_events, evidence
    if scenario == 'restart':
        assert 'fetch' not in events, 'RestartRuntime must not deploy new code'
