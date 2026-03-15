[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ContractPath,
    [string]$OutputPath = ""
)

$ErrorActionPreference = 'Stop'

$resolvedContract = (Resolve-Path $ContractPath).Path
$contract = Get-Content -Path $resolvedContract -Raw | ConvertFrom-Json

$requiredTopLevel = @(
    'task_type',
    'repo',
    'scope',
    'goals',
    'constraints',
    'must_run',
    'must_not_touch',
    'required_artifacts',
    'stop_conditions',
    'review_notes'
)

foreach ($name in $requiredTopLevel) {
    if ($null -eq $contract.$name) {
        throw "Contract is missing required field: $name"
    }
}

if ($null -eq $contract.scope.include -or $null -eq $contract.scope.exclude) {
    throw 'Contract scope must include both include and exclude arrays.'
}

if ($null -eq $contract.constraints.max_files_changed -or $null -eq $contract.constraints.max_diff_lines) {
    throw 'Contract constraints must include max_files_changed and max_diff_lines.'
}

if (-not $OutputPath) {
    $directory = Split-Path -Parent $resolvedContract
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedContract)
    $OutputPath = Join-Path $directory "$baseName.handoff.md"
}

function Format-Bullets {
    param([object[]]$Items)

    if (-not $Items -or $Items.Count -eq 0) {
        return '- (none specified)'
    }

    return ($Items | ForEach-Object { "- $_" }) -join "`n"
}

$lines = @(
    "# OpenHands Handoff: $($contract.task_type)",
    "",
    ('Source contract: `' + $resolvedContract + '`'),
    ('Repo: `' + $contract.repo + '`'),
    "",
    "## Non-negotiable rules",
    "- Operate in PR-only mode.",
    "- Do not push directly to `main`.",
    "- Stop immediately if you need to touch a protected path not already allowed by the contract.",
    "- Report anything partial or blocked instead of calling it done.",
    "",
    "## Scope include",
    (Format-Bullets -Items $contract.scope.include),
    "",
    "## Scope exclude",
    (Format-Bullets -Items $contract.scope.exclude),
    "",
    "## Goals",
    (Format-Bullets -Items $contract.goals),
    "",
    "## Constraints",
    "- max_files_changed: $($contract.constraints.max_files_changed)",
    "- max_diff_lines: $($contract.constraints.max_diff_lines)",
    "- must_run_tests: $($contract.constraints.must_run_tests)",
    "- mandatory_human_review: $($contract.constraints.mandatory_human_review)",
    "",
    "Protected paths:",
    (Format-Bullets -Items $contract.constraints.protected_paths),
    "",
    "## Must run",
    (Format-Bullets -Items $contract.must_run),
    "",
    "## Must not touch",
    (Format-Bullets -Items $contract.must_not_touch),
    "",
    "## Required artifacts",
    (Format-Bullets -Items $contract.required_artifacts),
    "",
    "## Stop conditions",
    (Format-Bullets -Items $contract.stop_conditions),
    "",
    "## Review notes",
    (Format-Bullets -Items $contract.review_notes),
    "",
    "## Output expectation",
    "- Return a concise summary of changes.",
    "- Return exact tests run and outcomes.",
    "- Return any follow-up risks or blocked items.",
    "- If the work drifts outside this contract, stop and say so."
)

Set-Content -Path $OutputPath -Value ($lines -join "`n")

Write-Output "Rendered handoff prompt: $OutputPath"
