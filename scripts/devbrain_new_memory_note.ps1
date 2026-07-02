param(
    [ValidateSet("logs", "dossiers", "patches")]
    [string] $Target = "logs",

    [Parameter(Mandatory = $true)]
    [string] $Title,

    [string] $Date,

    [switch] $Force,

    [switch] $Preview
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$templatePath = Join-Path $repoRoot "docs\devbrain\MEMORY_CAPTURE_TEMPLATE.md"

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Memory capture template not found: $templatePath"
}

function Convert-ToSlug {
    param([Parameter(Mandatory = $true)][string] $Value)

    $normalized = $Value.ToLowerInvariant()
    $slug = [regex]::Replace($normalized, "[^a-z0-9]+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return "memory-note"
    }
    if ($slug.Length -gt 80) {
        return $slug.Substring(0, 80).Trim("-")
    }
    return $slug
}

if ([string]::IsNullOrWhiteSpace($Date)) {
    $Date = Get-Date -Format "yyyy-MM-dd"
}
elseif ($Date -notmatch "^\d{4}-\d{2}-\d{2}$") {
    throw "Date must use YYYY-MM-DD format."
}

$slug = Convert-ToSlug -Value $Title
$targetDir = Join-Path $repoRoot (Join-Path ".ai-factory" $Target)
$outputPath = Join-Path $targetDir "$Date-$slug.md"
$relativeOutput = Resolve-Path -LiteralPath $repoRoot -Relative
$relativeOutput = Join-Path ".ai-factory\$Target" "$Date-$slug.md"

$template = Get-Content -LiteralPath $templatePath -Raw
$createdAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
$content = @"
# $Title

Generated from `docs/devbrain/MEMORY_CAPTURE_TEMPLATE.md`.

- Target: `.ai-factory/$Target`
- Created: $createdAt
- Promotion rule: keep this as a note unless it becomes a repeated ownership, routing, validation, or safety fact.

"@ + $template

Write-Output "DevBrain New Memory Note"
Write-Output ""
Write-Output "Target: .ai-factory/$Target"
Write-Output "Title: $Title"
Write-Output "Output: $relativeOutput"

if ($Preview) {
    Write-Output "Mode: preview"
    Write-Output ""
    Write-Output "No file written."
    exit 0
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

if ((Test-Path -LiteralPath $outputPath) -and -not $Force) {
    throw "Output already exists: $relativeOutput. Re-run with -Force to overwrite."
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($outputPath, $content, $utf8NoBom)

Write-Output "Mode: write"
Write-Output "Result: created"
exit 0
