param(
    [ValidateSet('Preflight', 'Check', 'Start', 'Stop', 'Session')][string]$Action = 'Check',
    [string]$EnvFile = 'ops/staging.env',
    [string]$Distribution = 'Ubuntu-24.04',
    [switch]$NoBuild,
    [ValidateRange(30, 900)][int]$TimeoutSec = 180,
    [string]$PgAdminEnv,
    [string]$Junit,
    [string[]]$CommandArgs = @()
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonArgs = @((Join-Path $repoRoot 'scripts/wsl_staging.py'), '--action',
    $Action.ToLowerInvariant(), '--env-file', $EnvFile, '--distribution',
    $Distribution, '--timeout', "$TimeoutSec")
if ($NoBuild) { $pythonArgs += '--no-build' }
if ($PgAdminEnv) { $pythonArgs += @('--pg-admin-env', $PgAdminEnv) }
if ($Junit) { $pythonArgs += @('--junit', $Junit) }
if ($CommandArgs.Count) { $pythonArgs += @('--') + $CommandArgs }

Push-Location $repoRoot
try {
    # Named PythonArgs avoids accidentally binding the script path to RequireModule.
    & (Join-Path $repoRoot 'scripts/run_python.ps1') -PythonArgs $pythonArgs
    exit $LASTEXITCODE
}
finally { Pop-Location }
