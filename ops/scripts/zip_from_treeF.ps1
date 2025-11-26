# zip_from_treeF.ps1 (ASCII only)
# Build a zip strictly from FILE entries in tree_F.txt, minus junk patterns.
# Works on PowerShell 7+ (Windows 11).

[CmdletBinding()]
param(
  [string]$ProjectPath = "C:\final",
  [string]$TreeFile = "C:\final\tree_F.txt",
  [string]$OutDir = "$ProjectPath\archives",
  [string]$NameSuffix = "",
  [switch]$DryRun
)

# ------------ Exclude patterns (junk) ------------
# Match against POSIX-style relative paths (forward slashes).
$ExcludeGlobs = @(
  ".git/**", ".github/**",
  ".vscode/**", ".idea/**",
  "node_modules/**", "dist/**", "build/**", "coverage/**",
  ".next/**", ".nuxt/**", ".cache/**",
  "**/__pycache__/**", ".mypy_cache/**", ".pytest_cache/**",

  # local env/keys/secrets
  "**/*.env", "**/.env", "**/*.env.*", "**/*.secret.*",
  "**/*.pem", "**/*.key", "**/*.pfx", "**/*.crt",

  # db/logs and archives
  "**/*.db", "**/*.sqlite", "**/*.sqlite3", "**/*.log",
  "archives/**", "**/*.zip", "**/*.7z", "**/*.rar", "**/*.tar", "**/*.gz",

  "Thumbs.db", ".DS_Store",
  ".venv/**", "venv/**", "env/**",

  # common leftovers in your tree
  "**/*.bak",
  "**/scripts/out/**"
)

function Ensure-Dir([string]$p) {
  if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

function RelPosix([string]$base, [string]$full) {
  $uBase = [Uri]("$base" + [IO.Path]::DirectorySeparatorChar)
  $uFull = [Uri]$full
  (($uBase.MakeRelativeUri($uFull)).ToString()) -replace '\\','/'
}

function GlobToRegex([string]$glob) {
  $e = [Regex]::Escape($glob)
  $e = $e -replace '\\\*\\\*','§DS§'
  $e = $e -replace '\\\*','[^/]*'
  $e = $e -replace '§DS§','.*'
  '^' + $e + '$'
}

# ------------ Validate paths ------------
if (-not (Test-Path $ProjectPath)) {
  Write-Error "ProjectPath not found: $ProjectPath"; exit 1
}
if (-not (Test-Path $TreeFile)) {
  Write-Error "TreeFile not found: $TreeFile"; exit 1
}
Ensure-Dir $OutDir

# ------------ Parse tree_F.txt -> file list ------------
# Expected line format like: "FILE /backend/app/main.py  [6110 bytes]"
$lines = Get-Content -LiteralPath $TreeFile -Encoding UTF8
$fileRelPaths = @()

$rx = '^FILE\s+\/(?<path>.+?)\s+\['
foreach ($ln in $lines) {
  $m = [Regex]::Match($ln, $rx)
  if ($m.Success) {
    $fileRelPaths += $m.Groups['path'].Value
  }
}

if ($fileRelPaths.Count -eq 0) {
  Write-Error "No FILE entries parsed from: $TreeFile"; exit 1
}

# Deduplicate and sort
$fileRelPaths = $fileRelPaths | Sort-Object -Unique

# ------------ Exclude filtering ------------
$excRx = $ExcludeGlobs | ForEach-Object { GlobToRegex $_ }

$selected = New-Object System.Collections.Generic.List[string]
$excludedByPattern = New-Object System.Collections.Generic.List[string]
$missingOnDisk = New-Object System.Collections.Generic.List[string]

foreach ($rel in $fileRelPaths) {
  $rel = $rel.Trim()
  if ([string]::IsNullOrWhiteSpace($rel)) { continue }

  # filter by exclude globs
  $isExcluded = $false
  foreach ($rxp in $excRx) {
    if ($rel -match $rxp) { $isExcluded = $true; break }
  }
  if ($isExcluded) { $excludedByPattern.Add($rel) | Out-Null; continue }

  # check existence
  $abs = Join-Path $ProjectPath ($rel -replace '/','\')
  if (Test-Path -LiteralPath $abs) {
    $selected.Add($abs) | Out-Null
  } else {
    $missingOnDisk.Add($rel) | Out-Null
  }
}

if ($selected.Count -eq 0) {
  Write-Error "No files selected (all excluded or missing)."; exit 1
}

# ------------ Name and path for zip ------------
$Date = Get-Date -Format "yyyy-MM-dd"
$ZipName = "clinic_project_$Date"
if ($NameSuffix -ne "") { $ZipName += "_$NameSuffix" }
$ZipName += ".zip"
$ZipPath = Join-Path $OutDir $ZipName
if (Test-Path $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }

# ------------ Dry run or compress ------------
if ($DryRun) {
  Write-Host "DRY-RUN: would zip $($selected.Count) files -> $ZipPath"
  Write-Host "Excluded by pattern: $($excludedByPattern.Count); Missing: $($missingOnDisk.Count)"
  if ($excludedByPattern.Count -gt 0) {
    Write-Host "---- excluded examples ----"
    $excludedByPattern | Select-Object -First 10 | ForEach-Object { Write-Host "  - $_" }
  }
  if ($missingOnDisk.Count -gt 0) {
    Write-Host "---- missing on disk ----"
    $missingOnDisk | Select-Object -First 10 | ForEach-Object { Write-Host "  - $_" }
  }
  exit 0
}

# Compress
Compress-Archive -Path $selected -DestinationPath $ZipPath -Force

# Summary
$sizeBytes = (Get-Item -LiteralPath $ZipPath).Length
Write-Host "OK: zip created -> $ZipPath"
Write-Host "Included: $($selected.Count) files; Excluded: $($excludedByPattern.Count); Missing: $($missingOnDisk.Count)"
Write-Host ("Zip size: {0:N0} bytes" -f $sizeBytes)
