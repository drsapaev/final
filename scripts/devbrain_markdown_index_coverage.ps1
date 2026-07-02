Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$durableMarkdownRoots = @(
    "docs/devbrain",
    "docs/runbooks",
    "docs/dev",
    ".ai-factory/logs",
    ".ai-factory/dossiers",
    ".ai-factory/patches"
)

$excludedDirs = @(
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "indexes",
    "node_modules",
    "storage"
)

$lightRagCuratedRequired = @(
    "AGENTS.md",
    "docs/devbrain/PROJECT_MEMORY.md",
    "docs/devbrain/DEVBRAIN_STATUS.md",
    "docs/devbrain/MEMORY_ROUTING.md",
    "docs/devbrain/MEMORY_CAPTURE_TEMPLATE.md",
    "docs/devbrain/MEMORY_PROBE_PROTOCOL.md",
    "docs/devbrain/DEV_BRAIN_ROLE_MAP.md",
    "docs/devbrain/MARKDOWN_INDEXING_POLICY.md",
    ".ai-factory/logs/memory-probes.md",
    "docs/runbooks/AGENT_CYCLIC_WORKFLOW.md",
    "docs/runbooks/CODEX_SUPERPOWERS_GUARD.md",
    "docs/runbooks/LOCAL_DEV_ONBOARDING.md",
    "docs/runbooks/MESSAGING_CONTRACT.md",
    "docs/runbooks/CLINIC_STATE_SEPARATION_AUDIT.md",
    "docs/dev/POSTGRES_DEV_DATABASE.md",
    "docs/dev/DEMO_USERS.md"
)

function ConvertTo-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string] $Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $rootPath = $repoRoot.Path.TrimEnd("\")
    if (-not $resolved.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "path is outside repo root: $resolved"
    }

    $relative = $resolved.Substring($rootPath.Length).TrimStart("\")
    return $relative.Replace("\", "/")
}

function Test-ExcludedPath {
    param([Parameter(Mandatory = $true)][string] $RepoRelativePath)

    $parts = $RepoRelativePath -split "/"
    foreach ($part in $parts) {
        if ($excludedDirs -contains $part) {
            return $true
        }
    }
    return $false
}

function Get-DurableMarkdownFiles {
    $files = New-Object System.Collections.Generic.List[string]

    foreach ($root in $durableMarkdownRoots) {
        $absoluteRoot = Join-Path $repoRoot $root
        if (-not (Test-Path -LiteralPath $absoluteRoot)) {
            continue
        }

        Get-ChildItem -LiteralPath $absoluteRoot -Filter "*.md" -Recurse -File |
            ForEach-Object {
                $relative = ConvertTo-RepoRelativePath -Path $_.FullName
                if (-not (Test-ExcludedPath -RepoRelativePath $relative)) {
                    $files.Add($relative)
                }
            }
    }

    return $files | Sort-Object -Unique
}

function Get-ManifestMarkdownCoverage {
    param([Parameter(Mandatory = $true)][string] $ManifestPath)

    $manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
    $covered = @{}

    foreach ($source in $manifest.sources) {
        $relativeSource = ([string] $source.path).Replace("\", "/")
        $absoluteSource = Join-Path $repoRoot $relativeSource
        $sourceType = if ($source.PSObject.Properties.Name -contains "type") { [string] $source.type } else { "file" }

        if ($sourceType -eq "file") {
            if ((Test-Path -LiteralPath $absoluteSource) -and $relativeSource.EndsWith(".md")) {
                $covered[$relativeSource] = $true
            }
            continue
        }

        if ($sourceType -ne "dir" -or -not (Test-Path -LiteralPath $absoluteSource)) {
            continue
        }

        $extensions = @()
        if ($source.PSObject.Properties.Name -contains "extensions") {
            $extensions = @($source.extensions | ForEach-Object { ([string] $_).ToLowerInvariant() })
        }

        if ($extensions.Count -gt 0 -and ($extensions -notcontains ".md")) {
            continue
        }

        Get-ChildItem -LiteralPath $absoluteSource -Filter "*.md" -Recurse -File |
            ForEach-Object {
                $relative = ConvertTo-RepoRelativePath -Path $_.FullName
                if (-not (Test-ExcludedPath -RepoRelativePath $relative)) {
                    $covered[$relative] = $true
                }
            }
    }

    return $covered
}

Write-Output "DevBrain Markdown Index Coverage"
Write-Output ""

$llamaManifest = Join-Path $repoRoot "ai\llamaindex\data\manifest.json"
$lightManifest = Join-Path $repoRoot "ai\lightrag\data\manifest.json"

if (-not (Test-Path -LiteralPath $llamaManifest)) {
    throw "LlamaIndex manifest not found: $llamaManifest"
}
if (-not (Test-Path -LiteralPath $lightManifest)) {
    throw "LightRAG manifest not found: $lightManifest"
}

$durableFiles = @(Get-DurableMarkdownFiles)
$llamaCoverage = Get-ManifestMarkdownCoverage -ManifestPath $llamaManifest
$lightCoverage = Get-ManifestMarkdownCoverage -ManifestPath $lightManifest

$missingFromLlama = @(
    $durableFiles |
        Where-Object { -not $llamaCoverage.ContainsKey($_) } |
        Sort-Object
)

$missingFromLight = @(
    $lightRagCuratedRequired |
        Where-Object { -not $lightCoverage.ContainsKey($_) } |
        Sort-Object
)

Write-Output "Durable markdown files: $($durableFiles.Count)"
Write-Output "LlamaIndex markdown covered: $($llamaCoverage.Count)"
Write-Output "LightRAG curated markdown covered: $($lightCoverage.Count)"
Write-Output ""

$issueCount = 0

if ($missingFromLlama.Count -gt 0) {
    $issueCount += $missingFromLlama.Count
    Write-Output "WARN: Durable markdown not covered by LlamaIndex:"
    foreach ($item in $missingFromLlama) {
        Write-Output "- $item"
    }
}
else {
    Write-Output "PASS: LlamaIndex covers all durable markdown roots"
}

if ($missingFromLight.Count -gt 0) {
    $issueCount += $missingFromLight.Count
    Write-Output ""
    Write-Output "WARN: Curated LightRAG markdown anchors missing from manifest coverage:"
    foreach ($item in $missingFromLight) {
        Write-Output "- $item"
    }
}
else {
    Write-Output "PASS: LightRAG covers curated markdown anchors"
}

Write-Output ""
Write-Output "Summary:"
Write-Output "- issues: $issueCount"

if ($issueCount -gt 0) {
    exit 1
}

exit 0
