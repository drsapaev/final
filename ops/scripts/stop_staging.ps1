param(
    [string]$EnvFile = 'ops/staging.env',
    [string]$Distribution = 'Ubuntu-24.04'
)

& (Join-Path $PSScriptRoot 'wsl_staging.ps1') -Action Stop -EnvFile $EnvFile `
    -Distribution $Distribution
exit $LASTEXITCODE
