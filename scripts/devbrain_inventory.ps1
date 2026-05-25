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
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,
        [System.Collections.Generic.List[string]] $WhenPresent,
        [System.Collections.Generic.List[string]] $WhenMissing
    )

    $fullPath = Join-Path $repoRoot $RelativePath
    if (Test-Path -LiteralPath $fullPath) {
        $WhenPresent.Add("$Label ($RelativePath)") | Out-Null
        return $true
    }

    $WhenMissing.Add("$Label ($RelativePath)") | Out-Null
    return $false
}

function Find-DevBrainScripts {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativeRoot,
        [Parameter(Mandatory = $true)]
        [string[]] $NamePatterns
    )

    $root = Join-Path $repoRoot $RelativeRoot
    if (-not (Test-Path -LiteralPath $root)) {
        return @()
    }

    Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $fileName = $_.Name.ToLowerInvariant()
            foreach ($pattern in $NamePatterns) {
                if ($fileName -like $pattern) {
                    return $true
                }
            }
            return $false
        } |
        ForEach-Object {
            Resolve-Path -LiteralPath $_.FullName -Relative
        }
}

function Add-ScriptProbe {
    param(
        [Parameter(Mandatory = $true)]
        [string] $LayerName,
        [Parameter(Mandatory = $true)]
        [string] $RelativeRoot,
        [Parameter(Mandatory = $true)]
        [string[]] $NamePatterns,
        [Parameter(Mandatory = $true)]
        [bool] $ParentExists
    )

    if (-not $ParentExists) {
        $missing.Add("$LayerName query/ingest scripts ($RelativeRoot)") | Out-Null
        return
    }

    $scripts = @(Find-DevBrainScripts -RelativeRoot $RelativeRoot -NamePatterns $NamePatterns)
    if ($scripts.Count -eq 0) {
        $missing.Add("$LayerName query/ingest scripts ($RelativeRoot)") | Out-Null
        return
    }

    foreach ($script in $scripts) {
        $stale.Add("$LayerName script present; run/contract not verified ($script)") | Out-Null
    }
}

$agents = Add-ExistingPath "AGENTS rules" "AGENTS.md" $active $missing
$projectMemory = Add-ExistingPath "Project memory anchor" "docs/devbrain/PROJECT_MEMORY.md" $active $missing
$devbrainStatus = Add-ExistingPath "DevBrain status file" "docs/devbrain/DEVBRAIN_STATUS.md" $active $missing
$cyclicWorkflow = Add-ExistingPath "Cyclic workflow runbook" "docs/runbooks/AGENT_CYCLIC_WORKFLOW.md" $active $missing
$superpowersGuard = Add-ExistingPath "Superpowers guard runbook" "docs/runbooks/CODEX_SUPERPOWERS_GUARD.md" $active $missing
$gateLauncher = Add-ExistingPath "LangGraph gate launcher" "ai/langgraph/scripts/run_agent_gate.ps1" $active $missing
$gateScript = Add-ExistingPath "LangGraph agent gate" "ai/langgraph/scripts/agent_gate.py" $active $missing
$aiFactory = Add-ExistingPath "AI Factory file memory" ".ai-factory" $active $missing
$skills = Add-ExistingPath "Repo/user skills directory" ".agents/skills" $active $missing

$llamaIndexRoot = Join-Path $repoRoot "ai\llamaindex"
$llamaIndex = Test-Path -LiteralPath $llamaIndexRoot
$llamaIndexRequiredFiles = @(
    "ai/llamaindex/README.md",
    "ai/llamaindex/data/manifest.json",
    "ai/llamaindex/scripts/ingest.py",
    "ai/llamaindex/scripts/query.py",
    "ai/llamaindex/scripts/smoke.py",
    "ai/llamaindex/scripts/run_smoke.ps1"
)
$llamaIndexMissingRequired = @(
    $llamaIndexRequiredFiles |
        Where-Object { -not (Test-Path -LiteralPath (Join-Path $repoRoot $_)) }
)
$llamaIndexIndex = Test-Path -LiteralPath (Join-Path $repoRoot "ai/llamaindex/storage/devbrain_index.json")
$statusFile = Join-Path $repoRoot "docs/devbrain/DEVBRAIN_STATUS.md"
$llamaIndexStatusActive = $false
if (Test-Path -LiteralPath $statusFile) {
    $llamaIndexStatusActive = Select-String -LiteralPath $statusFile -Pattern "Current status: ``active local fallback``" -Quiet
}

if (-not $llamaIndex) {
    $missing.Add("LlamaIndex local layer (ai/llamaindex)") | Out-Null
    $missing.Add("LlamaIndex query/ingest scripts (ai/llamaindex)") | Out-Null
}
elseif ($llamaIndexMissingRequired.Count -gt 0) {
    $stale.Add("LlamaIndex local layer present but required files are missing: $($llamaIndexMissingRequired -join ', ')") | Out-Null
}
elseif ($llamaIndexIndex -and $llamaIndexStatusActive) {
    $active.Add("LlamaIndex local fallback retrieval (ai/llamaindex)") | Out-Null
}
else {
    $stale.Add("LlamaIndex local layer present; run ai/llamaindex/scripts/run_smoke.ps1 to verify and update status") | Out-Null
}

$lightRagRoot = Join-Path $repoRoot "ai\lightrag"
$lightRag = Test-Path -LiteralPath $lightRagRoot
$lightRagRequiredFiles = @(
    "ai/lightrag/README.md",
    "ai/lightrag/data/manifest.json",
    "ai/lightrag/scripts/ingest.py",
    "ai/lightrag/scripts/query.py",
    "ai/lightrag/scripts/acceptance.py",
    "ai/lightrag/scripts/run_acceptance.ps1"
)
$lightRagMissingRequired = @(
    $lightRagRequiredFiles |
        Where-Object { -not (Test-Path -LiteralPath (Join-Path $repoRoot $_)) }
)
$lightRagGraph = Test-Path -LiteralPath (Join-Path $repoRoot "ai/lightrag/indexes/lightrag_graph/graph.json")
$lightRagStatusActive = $false
if (Test-Path -LiteralPath $statusFile) {
    $lightRagStatusActive = Select-String -LiteralPath $statusFile -Pattern "Current status: ``active relationship fallback``" -Quiet
}

if (-not $lightRag) {
    $missing.Add("LightRAG local layer (ai/lightrag)") | Out-Null
    $missing.Add("LightRAG graph storage (ai/lightrag/indexes/lightrag_graph)") | Out-Null
    $missing.Add("LightRAG query/ingest scripts (ai/lightrag)") | Out-Null
}
elseif ($lightRagMissingRequired.Count -gt 0) {
    $stale.Add("LightRAG local layer present but required files are missing: $($lightRagMissingRequired -join ', ')") | Out-Null
}
elseif ($lightRagGraph -and $lightRagStatusActive) {
    $active.Add("LightRAG relationship fallback retrieval (ai/lightrag)") | Out-Null
}
else {
    $stale.Add("LightRAG local layer present; run ai/lightrag/scripts/run_acceptance.ps1 to verify and update status") | Out-Null
}

$historicalWorkflowScripts = @(
    "scripts/dev_brain.py",
    "scripts/planner_smoke.py",
    "scripts/dossier_smoke.py",
    "scripts/handoff_smoke.py"
)

foreach ($relativePath in $historicalWorkflowScripts) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (Test-Path -LiteralPath $fullPath) {
        $dormant.Add("Historical DevBrain workflow script present; not verified as active ($relativePath)") | Out-Null
    }
}

if (Test-Path -LiteralPath (Join-Path $repoRoot "ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md")) {
    $stale.Add("LightRAG readiness evidence exists, but evidence log is not graph storage (ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md)") | Out-Null
}

$portableActive = @($agents, $projectMemory, $devbrainStatus, $cyclicWorkflow, $superpowersGuard, $aiFactory, $skills) |
    Where-Object { $_ } |
    Measure-Object |
    Select-Object -ExpandProperty Count

$retrievalStatus = @()
if ($gateLauncher -and $gateScript) {
    $retrievalStatus += "LangGraph gate active"
}
else {
    $retrievalStatus += "LangGraph gate incomplete"
}

if ($llamaIndex -and $llamaIndexIndex -and $llamaIndexStatusActive) {
    $retrievalStatus += "LlamaIndex active local fallback"
}
elseif ($llamaIndex) {
    $retrievalStatus += "LlamaIndex present, needs verification"
}
else {
    $retrievalStatus += "LlamaIndex missing"
}

if ($lightRag -and $lightRagGraph -and $lightRagStatusActive) {
    $retrievalStatus += "LightRAG active relationship fallback"
}
elseif ($lightRag -and $lightRagGraph) {
    $retrievalStatus += "LightRAG graph present, needs verification"
}
elseif ($lightRag) {
    $retrievalStatus += "LightRAG directory present, graph missing"
}
else {
    $retrievalStatus += "LightRAG missing"
}

$unifiedBrainStatus = "not active"
if ($llamaIndex -and $llamaIndexIndex -and $llamaIndexStatusActive -and $lightRag -and $lightRagGraph -and $lightRagStatusActive) {
    $unifiedBrainStatus = "portable retrieval layers active; still not a production autonomous brain"
}
elseif ($llamaIndex -and $llamaIndexIndex -and $llamaIndexStatusActive -and -not ($lightRag -and $lightRagGraph)) {
    $unifiedBrainStatus = "partial retrieval active; LightRAG missing"
}
elseif ($llamaIndex -or ($lightRag -and $lightRagGraph)) {
    $unifiedBrainStatus = "needs verification"
}

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
Write-Output "- portable guardrails: $portableActive of 7 expected active"
Write-Output "- local retrieval layers: $($retrievalStatus -join '; ')"
Write-Output "- unified brain status: $unifiedBrainStatus"
