param(
    [switch] $IncludeRetrieval
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$active = [System.Collections.Generic.List[string]]::new()
$dormant = [System.Collections.Generic.List[string]]::new()
$missing = [System.Collections.Generic.List[string]]::new()
$stale = [System.Collections.Generic.List[string]]::new()

function Add-ExistingPath {
    param(
        [Parameter(Mandatory = $true)][string] $Label,
        [Parameter(Mandatory = $true)][string] $RelativePath
    )

    if (Test-Path -LiteralPath (Join-Path $repoRoot $RelativePath)) {
        $active.Add("$Label ($RelativePath)") | Out-Null
        return $true
    }

    $missing.Add("$Label ($RelativePath)") | Out-Null
    return $false
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

function Get-LocalMemoryStatus {
    $memoryLauncher = Join-Path $repoRoot "scripts\run_devbrain_memory.ps1"
    if (-not (Test-Path -LiteralPath $memoryLauncher)) {
        return $null
    }

    try {
        $result = Invoke-PowerShellChild -ScriptPath $memoryLauncher -Arguments @("-Action", "status")
        if ($result.ExitCode -ne 0) {
            return $null
        }
        return ($result.StandardOutput | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Get-ArtifactCommit {
    param([Parameter(Mandatory = $true)][string] $RelativePath)

    $path = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        return "missing"
    }

    try {
        $metadata = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
        if (-not ($metadata.PSObject.Properties.Name -contains "commit") -or -not $metadata.commit) {
            return "commit missing"
        }
        return [string] $metadata.commit
    }
    catch {
        return "metadata invalid"
    }
}

$agents = Add-ExistingPath "AGENTS rules" "AGENTS.md"
$projectMemory = Add-ExistingPath "Project memory anchor" "docs/devbrain/PROJECT_MEMORY.md"
$devbrainStatus = Add-ExistingPath "DevBrain status file" "docs/devbrain/DEVBRAIN_STATUS.md"
$cyclicWorkflow = Add-ExistingPath "Cyclic workflow runbook" "docs/runbooks/AGENT_CYCLIC_WORKFLOW.md"
$superpowersGuard = Add-ExistingPath "Superpowers guard runbook" "docs/runbooks/CODEX_SUPERPOWERS_GUARD.md"
$gateLauncher = Add-ExistingPath "LangGraph gate launcher" "ai/langgraph/scripts/run_agent_gate.ps1"
$gateScript = Add-ExistingPath "LangGraph agent gate" "ai/langgraph/scripts/agent_gate.py"
$aiFactory = Add-ExistingPath "AI Factory file memory" ".ai-factory"
$skills = Add-ExistingPath "Repo/user skills directory" ".agents/skills"
$memoryLauncherExists = Add-ExistingPath "Local memory helper" "scripts/run_devbrain_memory.ps1"

if ($memoryLauncherExists) {
    $memoryStatus = Get-LocalMemoryStatus
    if ($null -eq $memoryStatus) {
        $stale.Add("Local memory status could not be read") | Out-Null
    }
    elseif ($memoryStatus.status -eq "OK") {
        $active.Add("Shared local filesystem memory ($($memoryStatus.event_count) events)") | Out-Null
    }
    else {
        $stale.Add("Local memory is $($memoryStatus.status); inspect status errors") | Out-Null
    }
}

$dormant.Add("LlamaIndex legacy retrieval (dormant by ADR-0007; opt-in only)") | Out-Null
$dormant.Add("LightRAG legacy retrieval (dormant by ADR-0007; opt-in only)") | Out-Null

$historicalWorkflowScripts = @(
    "scripts/dev_brain.py",
    "scripts/planner_smoke.py",
    "scripts/dossier_smoke.py",
    "scripts/handoff_smoke.py"
)
foreach ($relativePath in $historicalWorkflowScripts) {
    if (Test-Path -LiteralPath (Join-Path $repoRoot $relativePath)) {
        $dormant.Add("Historical DevBrain workflow script present; not verified as active ($relativePath)") | Out-Null
    }
}

$retrievalStatus = "legacy retrieval checks intentionally skipped"
if ($IncludeRetrieval) {
    $retrievalStatus = "legacy retrieval artifacts inspected (read-only)"
    $llamaCommit = Get-ArtifactCommit "ai/llamaindex/storage/devbrain_index.json"
    $lightRagCommit = Get-ArtifactCommit "ai/lightrag/indexes/lightrag_graph/artifacts/metadata.json"
    $stale.Add("LlamaIndex artifact commit: $llamaCommit") | Out-Null
    $stale.Add("LightRAG artifact commit: $lightRagCommit") | Out-Null
}

$portableActive = @(
    $agents, $projectMemory, $devbrainStatus, $cyclicWorkflow,
    $superpowersGuard, $gateLauncher, $gateScript, $aiFactory,
    $skills, $memoryLauncherExists
) | Where-Object { $_ } | Measure-Object | Select-Object -ExpandProperty Count

Write-Output "DevBrain Inventory"
Write-Output ""

Write-Output "ACTIVE"
if ($active.Count -eq 0) {
    Write-Output "- none"
}
else {
    $active | Sort-Object | ForEach-Object { Write-Output "- $_" }
}
Write-Output ""

Write-Output "DORMANT"
if ($dormant.Count -eq 0) {
    Write-Output "- none detected"
}
else {
    $dormant | Sort-Object | ForEach-Object { Write-Output "- $_" }
}
Write-Output ""

Write-Output "MISSING"
if ($missing.Count -eq 0) {
    Write-Output "- none detected"
}
else {
    $missing | Sort-Object | ForEach-Object { Write-Output "- $_" }
}
Write-Output ""

Write-Output "STALE / NEEDS VERIFICATION"
if ($stale.Count -eq 0) {
    Write-Output "- none detected"
}
else {
    $stale | Sort-Object | ForEach-Object { Write-Output "- $_" }
}
Write-Output ""

Write-Output "Summary:"
Write-Output "- portable guardrails and memory helper: $portableActive expected components present"
Write-Output "- retrieval: $retrievalStatus"
Write-Output "- task memory is local to this clone's Git common directory; it is not a production brain"
