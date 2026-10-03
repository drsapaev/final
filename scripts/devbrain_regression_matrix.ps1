param(
    [switch] $IncludeRetrieval
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$failCount = 0
$warnCount = 0

function Write-Section {
    param([Parameter(Mandatory = $true)][string] $Title)

    Write-Output ""
    Write-Output "== $Title =="
}

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

function Invoke-MatrixStep {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][scriptblock] $Step,
        [switch] $WarnOnly
    )

    Write-Section $Name
    try {
        & $Step
        Write-Output "PASS: $Name"
    }
    catch {
        if ($WarnOnly) {
            Add-Warn "$Name failed: $($_.Exception.Message)"
        }
        else {
            Add-Fail "$Name failed: $($_.Exception.Message)"
        }
    }
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

function Invoke-Inventory {
    $inventory = Join-Path $repoRoot "scripts\devbrain_inventory.ps1"
    if ($IncludeRetrieval) {
        $result = Invoke-PowerShellChild -ScriptPath $inventory -Arguments @("-IncludeRetrieval")
    }
    else {
        $result = Invoke-PowerShellChild -ScriptPath $inventory
    }
    if ($result.StandardOutput) {
        Write-Output $result.StandardOutput.TrimEnd()
    }
    if ($result.ExitCode -ne 0) {
        throw "inventory command failed"
    }
}

function Invoke-MarkdownCoverage {
    $coverage = Join-Path $repoRoot "scripts\devbrain_markdown_index_coverage.ps1"
    if ($IncludeRetrieval) {
        $result = Invoke-PowerShellChild -ScriptPath $coverage -Arguments @("-IncludeRetrieval")
    }
    else {
        $result = Invoke-PowerShellChild -ScriptPath $coverage
    }
    if ($result.StandardOutput) {
        Write-Output $result.StandardOutput.TrimEnd()
    }
    if ($result.ExitCode -ne 0) {
        throw "markdown indexing coverage command reported issues"
    }
}

function Test-MemoryProbeLedger {
    $ledger = Join-Path $repoRoot ".ai-factory\logs\memory-probes.md"
    $expected = "Memory probe protocol was created after PR #1332 optimized the PR Lifecycle Recommendation workflow."

    if (-not (Test-Path -LiteralPath $ledger)) {
        throw "memory probe ledger not found"
    }

    $text = Get-Content -Raw -LiteralPath $ledger
    if ($text -notmatch [regex]::Escape($expected)) {
        throw "active memory probe control fact not found in ledger"
    }

    Write-Output "Active memory probe control fact is present"
}

function Test-LlamaIndexAvailable {
    $query = Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1"
    $index = Join-Path $repoRoot "ai\llamaindex\storage\devbrain_index.json"
    return (Test-Path -LiteralPath $query) -and (Test-Path -LiteralPath $index)
}

function Test-LightRagAvailable {
    $query = Join-Path $repoRoot "ai\lightrag\scripts\run_query.ps1"
    $graph = Join-Path $repoRoot "ai\lightrag\indexes\lightrag_graph\graph.json"
    return (Test-Path -LiteralPath $query) -and (Test-Path -LiteralPath $graph)
}

function Invoke-QueryProbe {
    param(
        [Parameter(Mandatory = $true)][string] $Layer,
        [Parameter(Mandatory = $true)][string] $ScriptPath,
        [Parameter(Mandatory = $true)][string] $Query,
        [Parameter(Mandatory = $true)][string[]] $ExpectedPatterns
    )

    $result = Invoke-PowerShellChild -ScriptPath $ScriptPath -Arguments @($Query)
    if ($result.ExitCode -ne 0) {
        throw "$Layer query failed"
    }

    foreach ($pattern in $ExpectedPatterns) {
        if ($result.StandardOutput -notmatch $pattern) {
            Add-Warn "$Layer query did not show expected anchor pattern: $pattern"
        }
    }
}

function Test-ArtifactFreshness {
    param(
        [Parameter(Mandatory = $true)][string] $Layer,
        [Parameter(Mandatory = $true)][string] $MetadataPath,
        [Parameter(Mandatory = $true)][string] $Head
    )

    if (-not (Test-Path -LiteralPath $MetadataPath)) {
        Add-Warn "$Layer artifact metadata is missing; no freshness claim made"
        return
    }

    try {
        $metadata = Get-Content -Raw -LiteralPath $MetadataPath | ConvertFrom-Json
    }
    catch {
        Add-Warn "$Layer artifact metadata is invalid; no freshness claim made"
        return
    }

    $commit = if ($metadata.PSObject.Properties.Name -contains "commit") { [string] $metadata.commit } else { "" }
    if (-not $commit) {
        Add-Warn "$Layer artifact metadata has no commit; no freshness claim made"
    }
    elseif ($commit -eq $Head) {
        Write-Output "PASS: $Layer artifact metadata is fresh at HEAD"
    }
    else {
        Add-Warn "STALE / NEEDS REFRESH: $Layer artifact commit $commit differs from HEAD $Head"
    }
}

function Test-IndexedArtifactFreshness {
    Push-Location $repoRoot
    try {
        $head = (git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "git rev-parse HEAD failed"
        }

        Write-Output "HEAD: $head"
        Test-ArtifactFreshness `
            -Layer "LlamaIndex" `
            -MetadataPath (Join-Path $repoRoot "ai\llamaindex\storage\devbrain_index.json") `
            -Head $head
        Test-ArtifactFreshness `
            -Layer "LightRAG" `
            -MetadataPath (Join-Path $repoRoot "ai\lightrag\indexes\lightrag_graph\artifacts\metadata.json") `
            -Head $head
    }
    finally {
        Pop-Location
    }
}

Write-Output "DevBrain Regression Matrix"
Write-Output ""
Write-Output "Default checks cover portable memory and guardrails. Legacy retrieval is dormant and skipped unless -IncludeRetrieval is supplied."

Invoke-MatrixStep "Inventory" { Invoke-Inventory }

Invoke-MatrixStep "Guardrail acceptance" {
    $acceptance = Join-Path $repoRoot "scripts\devbrain_acceptance.ps1"
    $result = Invoke-PowerShellChild -ScriptPath $acceptance
    if ($result.StandardOutput) {
        Write-Output $result.StandardOutput.TrimEnd()
    }
    if ($result.ExitCode -ne 0) {
        throw "acceptance command failed"
    }
}

Invoke-MatrixStep "Memory probe ledger direct read" {
    Test-MemoryProbeLedger
}

Invoke-MatrixStep "Markdown indexing coverage" { Invoke-MarkdownCoverage } -WarnOnly

if (-not $IncludeRetrieval) {
    Write-Section "Legacy retrieval probes"
    Write-Output "SKIP: intentional; pass -IncludeRetrieval to run read-only queries against existing artifacts"

    Write-Section "Retrieval freshness"
    Write-Output "SKIP: intentional; freshness is not checked for dormant legacy indexes by default"
}
else {
    if (Test-LlamaIndexAvailable) {
        Invoke-MatrixStep "LlamaIndex simple locate query" {
            Invoke-QueryProbe `
                -Layer "LlamaIndex" `
                -ScriptPath (Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1") `
                -Query "Where is runtime API/WS origin resolution implemented on the frontend?" `
                -ExpectedPatterns @("frontend/src/api/runtime\.js", "frontend/src/api/ws\.js")
        } -WarnOnly
    }
    else {
        Write-Section "LlamaIndex simple locate query"
        Add-Warn "LlamaIndex artifacts are missing; query was not run or created"
    }

    if (Test-LightRagAvailable) {
        $lightRagQuery = Join-Path $repoRoot "ai\lightrag\scripts\run_query.ps1"
        $lightRagProbes = @(
            @("LightRAG local dev runtime query", "run project locally with clinic_dev PostgreSQL dev database backend 18000 frontend 5173", @("local_dev_runtime_contour", "scripts/start_dev_clinic\.ps1", "docs/runbooks/LOCAL_DEV_ONBOARDING\.md")),
            @("LightRAG memory probe query", "active memory probe control fact memory-probes", @("memory_probe_protocol", "\.ai-factory/logs/memory-probes\.md")),
            @("LightRAG registrar ownership query", "fix registrar payment status persistence ownership", @("registrar_payment_status", "backend/app/services/billing_service\.py", "backend/app/models/payment\.py")),
            @("LightRAG Alembic ownership query", "add Alembic revision for existing TelegramStaffLinkToken model table telegram_staff_link_tokens", @("alembic_migration_ownership", "backend/alembic/versions", "backend/app/models")),
            @("LightRAG notification anti-noise query", "implement notification preferences mute snooze DND runtime policy", @("notification_catalog_anti_noise", "backend/app/services/notifications\.py", "backend/app/schemas/notification\.py")),
            @("LightRAG queue identity query", "fix queue specialist id Doctor.id canonical ownership", @("queue_identity_fairness", "backend/app/services/queue_service\.py", "backend/app/models/online_queue\.py"))
        )

        foreach ($probe in $lightRagProbes) {
            $probeName = [string] $probe[0]
            $probeQuery = [string] $probe[1]
            $expected = [string[]] $probe[2]
            Invoke-MatrixStep $probeName {
                Invoke-QueryProbe -Layer "LightRAG" -ScriptPath $lightRagQuery -Query $probeQuery -ExpectedPatterns $expected
            } -WarnOnly
        }
    }
    else {
        Write-Section "LightRAG relationship queries"
        Add-Warn "LightRAG graph is missing; queries were not run or created"
    }

    Invoke-MatrixStep "Retrieval freshness" {
        Test-IndexedArtifactFreshness
    } -WarnOnly
}

Write-Output ""
Write-Output "Summary:"
Write-Output "- failures: $failCount"
Write-Output "- warnings: $warnCount"

if ($failCount -gt 0) {
    exit 1
}

exit 0
