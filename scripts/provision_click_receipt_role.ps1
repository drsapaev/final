param(
    [Parameter(Mandatory=$true)][string] $Schema,
    [Parameter(Mandatory=$true)][string] $Owner,
    [Parameter(Mandatory=$true)][string] $Role,
    [Parameter(Mandatory=$true)][string] $KeyVersion
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
& (Join-Path $repoRoot "scripts/run_python.ps1") -PythonArgs @(
    (Join-Path $repoRoot "scripts/provision_click_receipt_role.py"),
    "--schema", $Schema, "--owner", $Owner, "--role", $Role,
    "--key-version", $KeyVersion
)
exit $LASTEXITCODE
