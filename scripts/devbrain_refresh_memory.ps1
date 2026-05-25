Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$results = [ordered]@{
    "LlamaIndex refresh" = "skip"
    "LightRAG acceptance" = "skip"
    "LightRAG artifacts" = "skip"
    "Artifact check" = "skip"
    "Regression matrix" = "skip"
}
$warnCount = 0
$failCount = 0

function Add-Warn {
    param([Parameter(Mandatory = $true)][string] $Message)

    $script:warnCount += 1
    Write-Output "WARN: $Message"
}

function Add-Fail {
    param([Parameter(Mandatory = $true)][string] $Message)

    $script:failCount += 1
    Write-Output "FAIL: $Message"
}

function Invoke-MemoryStep {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [string] $RelativeScript,
        [switch] $Core
    )

    $scriptPath = Join-Path $repoRoot $RelativeScript
    Write-Output ""
    Write-Output "== $Name =="

    if (-not (Test-Path -LiteralPath $scriptPath)) {
        $script:results[$Name] = "skip"
        $message = "$RelativeScript not found; skipped"
        if ($Core) {
            Add-Fail $message
        }
        else {
            Add-Warn $message
        }
        return
    }

    & $scriptPath
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        $script:results[$Name] = "pass"
        Write-Output "PASS: $Name"
        return
    }

    if ($Core) {
        $script:results[$Name] = "fail"
        Add-Fail "$Name exited with code $exitCode"
    }
    else {
        $script:results[$Name] = "warn"
        Add-Warn "$Name exited with code $exitCode"
    }
}

Write-Output "DevBrain Memory Refresh"
Write-Output ""
Write-Output "This wrapper refreshes local DevBrain retrieval/status evidence only."
Write-Output "It does not run product tests, require API keys, or commit generated indexes/artifacts."

Push-Location $repoRoot
try {
    Invoke-MemoryStep -Name "LlamaIndex refresh" -RelativeScript "ai\llamaindex\scripts\run_smoke.ps1"
    Invoke-MemoryStep -Name "LightRAG acceptance" -RelativeScript "ai\lightrag\scripts\run_acceptance.ps1"
    Invoke-MemoryStep -Name "LightRAG artifacts" -RelativeScript "ai\lightrag\scripts\run_artifacts.ps1"
    Invoke-MemoryStep -Name "Artifact check" -RelativeScript "ai\lightrag\scripts\run_artifact_check.ps1"
    Invoke-MemoryStep -Name "Regression matrix" -RelativeScript "scripts\devbrain_regression_matrix.ps1" -Core
}
finally {
    Pop-Location
}

Write-Output ""
Write-Output "Summary:"
foreach ($key in $results.Keys) {
    Write-Output "- ${key}: $($results[$key])"
}
Write-Output "- warnings: $warnCount"
Write-Output "- failures: $failCount"

if ($failCount -gt 0) {
    Write-Output ""
    Write-Output "Final memory freshness verdict: fail"
    exit 1
}

if ($warnCount -gt 0) {
    Write-Output ""
    Write-Output "Final memory freshness verdict: pass with warnings"
    exit 0
}

Write-Output ""
Write-Output "Final memory freshness verdict: fresh"
exit 0
