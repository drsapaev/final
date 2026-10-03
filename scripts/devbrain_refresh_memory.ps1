param(
    [switch] $RefreshRetrieval
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$memoryLauncher = Join-Path $repoRoot "scripts\run_devbrain_memory.ps1"
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$results = [ordered]@{
    "Filesystem memory" = "skip"
    "Portable regression" = "skip"
    "LlamaIndex refresh" = "skip"
    "LightRAG acceptance" = "skip"
    "LightRAG artifact export" = "skip"
    "LightRAG artifact check" = "skip"
    "Retrieval regression" = "skip"
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

function Invoke-PowerShellChild {
    param(
        [Parameter(Mandatory = $true)][string] $ScriptPath,
        [string[]] $Arguments = @()
    )

    $powerShellExe = (Get-Process -Id $PID).Path
    $childArguments = @("-NoLogo", "-NoProfile", "-File", $ScriptPath) + $Arguments
    $stdoutLines = & $powerShellExe @childArguments
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        StandardOutput = ($stdoutLines -join [Environment]::NewLine)
        StandardError = ""
    }
}

function Invoke-FileMemoryCheck {
    Write-Output ""
    Write-Output "== Filesystem memory status =="

    if (-not (Test-Path -LiteralPath $memoryLauncher)) {
        $script:results["Filesystem memory"] = "fail"
        Add-Fail "scripts/run_devbrain_memory.ps1 not found"
        return
    }

    try {
        $result = Invoke-PowerShellChild -ScriptPath $memoryLauncher -Arguments @("-Action", "status")
        if ($result.ExitCode -ne 0) {
            throw "memory helper failed"
        }

        $status = $result.StandardOutput | ConvertFrom-Json
        if ($status.status -ne "OK") {
            $script:results["Filesystem memory"] = [string] $status.status
            Add-Fail "filesystem memory reports $($status.status); inspect it with the status command"
            return
        }

        $script:results["Filesystem memory"] = "pass"
        Write-Output "PASS: filesystem memory status is OK ($($status.event_count) events)"
    }
    catch {
        $script:results["Filesystem memory"] = "fail"
        Add-Fail "filesystem memory status could not be read"
    }
}

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][string] $RelativeScript,
        [string[]] $Arguments = @()
    )

    Write-Output ""
    Write-Output "== $Name =="
    $scriptPath = Join-Path $repoRoot $RelativeScript
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        $script:results[$Name] = "skip"
        Add-Warn "$RelativeScript not found; skipped without creating retrieval artifacts"
        return
    }

    if (-not (Test-Path -LiteralPath $pythonLauncher)) {
        $script:results[$Name] = "fail"
        Add-Fail "scripts/run_python.ps1 not found"
        return
    }

    $pythonArgs = @($scriptPath) + $Arguments
    try {
        $childArguments = @("-PythonArgs") + $pythonArgs
        $result = Invoke-PowerShellChild -ScriptPath $pythonLauncher -Arguments $childArguments
        if ($result.StandardOutput) {
            Write-Output $result.StandardOutput.TrimEnd()
        }
        if ($result.StandardError) {
            [Console]::Error.Write($result.StandardError)
        }
        if ($result.ExitCode -eq 0) {
            $script:results[$Name] = "pass"
            Write-Output "PASS: $Name"
        }
        else {
            $script:results[$Name] = "fail"
            Add-Fail "$Name exited with code $($result.ExitCode)"
        }
    }
    catch {
        $script:results[$Name] = "fail"
        Add-Fail "$Name could not run through scripts/run_python.ps1"
    }
}

function Invoke-PortableRegression {
    Write-Output ""
    Write-Output "== Portable regression =="
    $matrix = Join-Path $repoRoot "scripts\devbrain_regression_matrix.ps1"
    if (-not (Test-Path -LiteralPath $matrix)) {
        $script:results["Portable regression"] = "fail"
        Add-Fail "scripts/devbrain_regression_matrix.ps1 not found"
        return
    }

    $result = Invoke-PowerShellChild -ScriptPath $matrix
    if ($result.StandardOutput) {
        Write-Output $result.StandardOutput.TrimEnd()
    }
    if ($result.ExitCode -eq 0) {
        $script:results["Portable regression"] = "pass"
        Write-Output "PASS: portable regression"
    }
    else {
        $script:results["Portable regression"] = "fail"
        Add-Fail "portable regression exited with code $($result.ExitCode)"
    }
}

Write-Output "DevBrain Memory Refresh"
Write-Output ""
Write-Output "Default mode checks filesystem memory and portable guardrails only."
Write-Output "Legacy LlamaIndex/LightRAG work runs only with -RefreshRetrieval and uses the canonical Python launcher."

Push-Location $repoRoot
try {
    Invoke-FileMemoryCheck

    if ($RefreshRetrieval) {
        Invoke-PythonStep -Name "LlamaIndex refresh" -RelativeScript "ai\llamaindex\scripts\smoke.py"

        $lightRagGraph = Join-Path $repoRoot "ai\lightrag\indexes\lightrag_graph\graph.json"
        if (Test-Path -LiteralPath $lightRagGraph) {
            Invoke-PythonStep -Name "LightRAG acceptance" -RelativeScript "ai\lightrag\scripts\acceptance.py"
            Invoke-PythonStep -Name "LightRAG artifact export" -RelativeScript "ai\lightrag\scripts\export_artifacts.py"
            Invoke-PythonStep -Name "LightRAG artifact check" -RelativeScript "ai\lightrag\scripts\check_artifacts.py" -Arguments @("--warn-stale")
        }
        else {
            $results["LightRAG acceptance"] = "skip"
            $results["LightRAG artifact export"] = "skip"
            $results["LightRAG artifact check"] = "skip"
            Add-Warn "LightRAG graph is absent; acceptance/export/check skipped without creating it"
        }

        $matrix = Join-Path $repoRoot "scripts\devbrain_regression_matrix.ps1"
        if (Test-Path -LiteralPath $matrix) {
            $result = Invoke-PowerShellChild -ScriptPath $matrix -Arguments @("-IncludeRetrieval")
            if ($result.StandardOutput) {
                Write-Output $result.StandardOutput.TrimEnd()
            }
            if ($result.ExitCode -eq 0) {
                $results["Retrieval regression"] = "pass"
                Write-Output "PASS: retrieval regression"
            }
            else {
                $results["Retrieval regression"] = "fail"
                Add-Fail "retrieval regression exited with code $($result.ExitCode)"
            }
        }
        else {
            $results["Retrieval regression"] = "skip"
            Add-Warn "scripts/devbrain_regression_matrix.ps1 not found; retrieval regression skipped"
        }
    }
    else {
        Invoke-PortableRegression
    }
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
    Write-Output "Final memory freshness verdict: fail"
    exit 1
}

if ($warnCount -gt 0) {
    Write-Output "Final memory freshness verdict: pass with warnings"
    exit 0
}

Write-Output "Final memory freshness verdict: pass"
exit 0
