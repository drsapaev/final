param(
    [switch]$NoBuild,
    [string]$EnvFile = 'ops/staging.env',
    [string]$Distribution = 'Ubuntu-24.04',
    [ValidateRange(30, 900)][int]$TimeoutSec = 180
)

& (Join-Path $PSScriptRoot 'wsl_staging.ps1') -Action Start -EnvFile $EnvFile `
    -Distribution $Distribution -NoBuild:$NoBuild -TimeoutSec $TimeoutSec
exit $LASTEXITCODE
