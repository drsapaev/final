param(
    [Parameter(Mandatory = $true)] [string] $Schema,
    [Parameter(Mandatory = $true)] [string] $Role,
    [Parameter(Mandatory = $true)] [string] $ExpectedOwner,
    [string] $DecisionRole,
    [string] $TrustedOwnerMembers = '[]'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $env:DATABASE_URL) {
    Write-Error 'DATABASE_URL is required'
    exit 2
}
$pythonScript = Join-Path $PSScriptRoot 'provision_all_free_backend_role.py'
$pythonRunner = Join-Path $PSScriptRoot 'run_python.ps1'
$arguments = @($pythonScript, '--schema', $Schema, '--role', $Role, '--expected-owner', $ExpectedOwner, '--trusted-owner-members', $TrustedOwnerMembers)
if ($DecisionRole) { $arguments += @('--decision-role', $DecisionRole) }
& $pythonRunner -RequireModule @('sqlalchemy', 'psycopg') -PythonArgs $arguments
exit $LASTEXITCODE
