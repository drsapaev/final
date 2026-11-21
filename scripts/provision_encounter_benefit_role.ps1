param(
    [Parameter(Mandatory=$true)][string] $Schema,
    [Parameter(Mandatory=$true)][string] $BackendRole,
    [Parameter(Mandatory=$true)][string] $CapabilityRole,
    [Parameter(Mandatory=$true)][string] $SchemaOwner,
    [string[]] $TrustedOwnerMembers = @()
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$pythonArgs = @(
    (Join-Path $root 'scripts/provision_encounter_benefit_role.py'),
    '--schema', $Schema, '--backend-role', $BackendRole, '--capability-role', $CapabilityRole, '--schema-owner', $SchemaOwner
)
foreach ($member in $TrustedOwnerMembers) { $pythonArgs += @('--trusted-owner-member', $member) }
& (Join-Path $root 'scripts/run_python.ps1') -PythonArgs $pythonArgs
exit $LASTEXITCODE
