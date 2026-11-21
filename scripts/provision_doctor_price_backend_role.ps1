param(
    [Parameter(Mandatory = $true)] [string] $Schema,
    [Parameter(Mandatory = $true)] [string] $Role
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $env:DATABASE_URL) {
    Write-Error 'DATABASE_URL is required'
    exit 2
}
$pythonScript = Join-Path $PSScriptRoot 'provision_doctor_price_backend_role.py'
$pythonRunner = Join-Path $PSScriptRoot 'run_python.ps1'
& $pythonRunner -RequireModule @('sqlalchemy', 'psycopg') -PythonArgs @($pythonScript, '--schema', $Schema, '--role', $Role)
exit $LASTEXITCODE
