param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'run_python.ps1') (Join-Path $PSScriptRoot 'provision_reconciliation_fence_role.py') @Arguments
exit $LASTEXITCODE
