Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$statusFile = Join-Path $repoRoot "docs\devbrain\DEVBRAIN_STATUS.md"

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
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Step,
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

function Test-StatusActive {
    param([Parameter(Mandatory = $true)][string] $Pattern)

    if (-not (Test-Path -LiteralPath $statusFile)) {
        return $false
    }

    return Select-String -LiteralPath $statusFile -Pattern $Pattern -Quiet
}

function Test-LlamaIndexActive {
    $root = Join-Path $repoRoot "ai\llamaindex"
    $query = Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1"
    $index = Join-Path $repoRoot "ai\llamaindex\storage\devbrain_index.json"
    return (
        (Test-Path -LiteralPath $root) -and
        (Test-Path -LiteralPath $query) -and
        (Test-Path -LiteralPath $index) -and
        (Test-StatusActive "Current status: ``active local fallback``")
    )
}

function Test-LightRagActive {
    $root = Join-Path $repoRoot "ai\lightrag"
    $query = Join-Path $repoRoot "ai\lightrag\scripts\run_query.ps1"
    $graph = Join-Path $repoRoot "ai\lightrag\indexes\lightrag_graph\graph.json"
    return (
        (Test-Path -LiteralPath $root) -and
        (Test-Path -LiteralPath $query) -and
        (Test-Path -LiteralPath $graph) -and
        (Test-StatusActive "Current status: ``active relationship fallback``")
    )
}

function Invoke-QueryProbe {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Layer,
        [Parameter(Mandatory = $true)]
        [string] $ScriptPath,
        [Parameter(Mandatory = $true)]
        [string] $Query,
        [Parameter(Mandatory = $true)]
        [string[]] $ExpectedPatterns
    )

    Write-Output "Query: $Query"
    $outputLines = & $ScriptPath $Query
    $exitCode = $LASTEXITCODE
    $output = ($outputLines | ForEach-Object { $_.ToString() }) -join "`n"
    Write-Output $output

    if ($exitCode -ne 0) {
        throw "$Layer query exited with code $exitCode"
    }

    foreach ($pattern in $ExpectedPatterns) {
        if ($output -notmatch $pattern) {
            Add-Warn "$Layer query did not show expected anchor pattern: $pattern"
        }
    }
}

function Test-MemoryProbeLedger {
    $ledger = Join-Path $repoRoot ".ai-factory\logs\memory-probes.md"
    $expected = "Memory probe protocol was created after PR #1332 optimized the PR Lifecycle Recommendation workflow."

    if (-not (Test-Path -LiteralPath $ledger)) {
        throw "memory probe ledger not found: $ledger"
    }

    $text = Get-Content -Raw -LiteralPath $ledger
    if ($text -notmatch [regex]::Escape($expected)) {
        throw "active memory probe control fact not found in ledger"
    }

    Write-Output "Active memory probe: `"$expected`""
    Write-Output "Stored in: .ai-factory/logs/memory-probes.md"
}

function Get-RecordedIndexedCommits {
    if (-not (Test-Path -LiteralPath $statusFile)) {
        throw "DevBrain status file not found: $statusFile"
    }

    $text = Get-Content -Raw -LiteralPath $statusFile
    $sectionMatches = [regex]::Matches(
        $text,
        "(?s)## (?<name>LlamaIndex|LightRAG) Status.*?- Last indexed commit: ``(?<commit>[0-9a-f]{40})``"
    )

    $commits = @{}
    foreach ($match in $sectionMatches) {
        $commits[$match.Groups["name"].Value] = $match.Groups["commit"].Value
    }
    return $commits
}

function Test-DevBrainBookkeepingOnlySince {
    param([Parameter(Mandatory = $true)][string] $RecordedCommit)

    $changedFiles = @(
        git diff --name-only $RecordedCommit HEAD |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )

    if ($changedFiles.Count -eq 0) {
        return $true
    }

    $allowedPatterns = @(
        "^docs/devbrain/DEVBRAIN_STATUS\.md$",
        "^ai/llamaindex/scripts/update_status\.py$",
        "^ai/lightrag/scripts/update_status\.py$",
        "^scripts/devbrain_regression_matrix\.ps1$"
    )

    foreach ($file in $changedFiles) {
        $allowed = $false
        foreach ($pattern in $allowedPatterns) {
            if ($file -match $pattern) {
                $allowed = $true
                break
            }
        }

        if (-not $allowed) {
            Write-Output "Freshness-relevant changed file since indexed commit: $file"
            return $false
        }
    }

    Write-Output "Only DevBrain status/freshness bookkeeping changed since indexed commit:"
    foreach ($file in $changedFiles) {
        Write-Output "- $file"
    }
    return $true
}

function Test-IndexedCommitFreshness {
    Push-Location $repoRoot
    try {
        $head = (git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "git rev-parse HEAD failed"
        }

        Write-Output "HEAD: $head"
        $commits = Get-RecordedIndexedCommits
        foreach ($layer in @("LlamaIndex", "LightRAG")) {
            if (-not $commits.ContainsKey($layer)) {
                Add-Warn "$layer indexed commit is not recorded"
                continue
            }

            $recorded = [string] $commits[$layer]
            Write-Output "$layer recorded indexed commit: $recorded"
            if ($recorded -eq $head) {
                Write-Output "PASS: $layer index is fresh at HEAD"
                continue
            }

            git merge-base --is-ancestor $recorded $head 2>$null
            $isAncestor = $LASTEXITCODE -eq 0
            if ($isAncestor) {
                if (Test-DevBrainBookkeepingOnlySince -RecordedCommit $recorded) {
                    Write-Output "PASS: $layer index is acceptable; only DevBrain bookkeeping changed after indexing"
                    continue
                }

                Add-Warn "STALE / NEEDS REINDEX: $layer indexed commit $recorded is behind HEAD $head"
            }
            else {
                Add-Warn "STALE / NEEDS REINDEX: $layer indexed commit $recorded differs from HEAD $head"
            }
        }
    }
    finally {
        Pop-Location
    }
}

Write-Output "DevBrain Regression Matrix"
Write-Output ""
Write-Output "This checker is read-only. It does not run ingest, does not require API keys, and does not update status files."

Invoke-MatrixStep "Inventory" {
    & (Join-Path $repoRoot "scripts\devbrain_inventory.ps1")
    if (-not $?) {
        throw "inventory command failed"
    }
}

Invoke-MatrixStep "Guardrail acceptance" {
    & (Join-Path $repoRoot "scripts\devbrain_acceptance.ps1")
    if (-not $?) {
        throw "acceptance command failed"
    }
}

Invoke-MatrixStep "Memory probe ledger direct read" {
    Test-MemoryProbeLedger
}

Invoke-MatrixStep "Markdown indexing coverage" {
    & (Join-Path $repoRoot "scripts\devbrain_markdown_index_coverage.ps1")
    if (-not $?) {
        throw "markdown indexing coverage command reported issues"
    }
} -WarnOnly

$llamaIndexActive = Test-LlamaIndexActive
$lightRagActive = Test-LightRagActive

if ($llamaIndexActive) {
    Invoke-MatrixStep "LlamaIndex simple locate query" {
        Invoke-QueryProbe `
            -Layer "LlamaIndex" `
            -ScriptPath (Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1") `
            -Query "Where is runtime API/WS origin resolution implemented on the frontend?" `
            -ExpectedPatterns @("frontend/src/api/runtime\.js", "frontend/src/api/ws\.js")
    } -WarnOnly

    Invoke-MatrixStep "LlamaIndex local dev runtime query" {
        Invoke-QueryProbe `
            -Layer "LlamaIndex" `
            -ScriptPath (Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1") `
            -Query "How do I run the project locally with the clinic_dev PostgreSQL database?" `
            -ExpectedPatterns @("docs/runbooks/LOCAL_DEV_ONBOARDING\.md", "clinic_dev")
    } -WarnOnly

    Invoke-MatrixStep "LlamaIndex dev clinic launcher query" {
        Invoke-QueryProbe `
            -Layer "LlamaIndex" `
            -ScriptPath (Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1") `
            -Query "start_dev_clinic check_dev_clinic stop_dev_clinic local dev launcher scripts" `
            -ExpectedPatterns @("scripts/start_dev_clinic\.ps1", "scripts/check_dev_clinic\.ps1", "scripts/stop_dev_clinic\.ps1")
    } -WarnOnly

    Invoke-MatrixStep "LlamaIndex memory probe query" {
        Invoke-QueryProbe `
            -Layer "LlamaIndex" `
            -ScriptPath (Join-Path $repoRoot "ai\llamaindex\scripts\run_query.ps1") `
            -Query "What is the active memory probe control fact?" `
            -ExpectedPatterns @("docs/devbrain/MEMORY_PROBE_PROTOCOL\.md", "\.ai-factory/logs/memory-probes\.md")
    } -WarnOnly
}
else {
    Write-Section "LlamaIndex simple locate query"
    Add-Warn "LlamaIndex is not active in this checkout; skipping query probe"
}

if ($lightRagActive) {
    $lightRagQuery = Join-Path $repoRoot "ai\lightrag\scripts\run_query.ps1"
    $lightRagArtifactCheck = Join-Path $repoRoot "ai\lightrag\scripts\run_artifact_check.ps1"

    Invoke-MatrixStep "LightRAG artifact integrity" {
        & $lightRagArtifactCheck --warn-stale
        if (-not $?) {
            throw "LightRAG artifact check command failed"
        }
    } -WarnOnly

    Invoke-MatrixStep "LightRAG local dev runtime query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "run project locally with clinic_dev PostgreSQL dev database backend 18000 frontend 5173" `
            -ExpectedPatterns @("local_dev_runtime_contour", "scripts/start_dev_clinic\.ps1", "docs/runbooks/LOCAL_DEV_ONBOARDING\.md")
    } -WarnOnly

    Invoke-MatrixStep "LightRAG memory probe query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "active memory probe control fact memory-probes" `
            -ExpectedPatterns @("memory_probe_protocol", "\.ai-factory/logs/memory-probes\.md")
    } -WarnOnly

    Invoke-MatrixStep "LightRAG registrar ownership query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "fix registrar payment status persistence ownership" `
            -ExpectedPatterns @("registrar_payment_status", "backend/app/services/billing_service\.py", "backend/app/models/payment\.py")
    } -WarnOnly

    Invoke-MatrixStep "LightRAG Alembic ownership query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "add Alembic revision for existing TelegramStaffLinkToken model table telegram_staff_link_tokens" `
            -ExpectedPatterns @("alembic_migration_ownership", "backend/alembic/versions", "backend/app/models")
    } -WarnOnly

    Invoke-MatrixStep "LightRAG notification anti-noise query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "implement notification preferences mute snooze DND runtime policy" `
            -ExpectedPatterns @("notification_catalog_anti_noise", "backend/app/services/notifications\.py", "backend/app/schemas/notification\.py")
    } -WarnOnly

    Invoke-MatrixStep "LightRAG queue identity query" {
        Invoke-QueryProbe `
            -Layer "LightRAG" `
            -ScriptPath $lightRagQuery `
            -Query "fix queue specialist id Doctor.id canonical ownership" `
            -ExpectedPatterns @("queue_identity_fairness", "backend/app/services/queue_service\.py", "backend/app/models/online_queue\.py")
    } -WarnOnly
}
else {
    Write-Section "LightRAG relationship queries"
    Add-Warn "LightRAG is not active in this checkout; skipping relationship probes"
}

Invoke-MatrixStep "Retrieval freshness" {
    Test-IndexedCommitFreshness
} -WarnOnly

Write-Output ""
Write-Output "Summary:"
Write-Output "- failures: $failCount"
Write-Output "- warnings: $warnCount"

if ($failCount -gt 0) {
    exit 1
}

exit 0
