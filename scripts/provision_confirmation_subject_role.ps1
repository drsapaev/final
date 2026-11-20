param([Parameter(ValueFromRemainingArguments = $true)][string[]] $ProvisionArgs)
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
& (Join-Path $repoRoot "scripts/run_python.ps1") -PythonArgs (@((Join-Path $PSScriptRoot "scripts/provision_confirmation_subject_role.py")) + $ProvisionArgs)
exit $LASTEXITCODE
