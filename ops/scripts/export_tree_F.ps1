# export_tree_F.ps1  (ASCII-only)
# Generates three files under ops/meta:
#  - tree_F.txt       : human-readable project tree (selected files only)
#  - manifest_F.json  : machine-readable manifest with path, size, mtime, sha256
#  - sha256sum.txt    : classic "sha256  path" lines
# Uses include (whitelist) and exclude (blacklist) globs.
# Works on PowerShell 7+ and Windows 11.

[CmdletBinding()]
param(
  [string]$ProjectPath = (Get-Location).Path,
  [string]$OutDir = "ops\meta",
  [string[]]$Include = @(
    "backend/app/**",
    "backend/alembic/**",
    "backend/alembic.ini",
    "backend/requirements*.txt",
    "backend/pyproject.toml",
    "backend/poetry.lock",
    "backend/.env.example",
    "backend/scripts/**",
    "backend/tests/**",
    "backend/static/**",
    "backend/templates/**",

    "backend/bots/**",
    "backend/integrations/**",
    "backend/providers/**",
    "backend/config/**",

    "frontend/src/**",
    "frontend/public/**",
    "frontend/index.html",
    "frontend/package*.json",
    "frontend/yarn.lock",
    "frontend/pnpm-lock.yaml",
    "frontend/vite.config.*",
    "frontend/webpack.config.*",
    "frontend/tsconfig*.json",
    "frontend/.env.example",
    "frontend/README*.md",
    "frontend/src/i18n/**",
    "frontend/src/assets/**",

    "ops/**/Dockerfile*",
    "ops/**.yml",
    "ops/**.yaml",
    "ops/scripts/**",
    "ops/.env.example",
    "ops/README*.md",

    "desktop/electron/**",
    "electron-builder.yml",
    "electron.vite.config.*",

    "README*.md",
    "LICENSE*",
    "SECURITY*.md",
    "docs/**",
    "scripts/**",
    ".editorconfig",
    ".prettierrc*",
    ".eslintrc*",
    ".lintstagedrc*",
    ".commitlintrc*"
  ),
  [string[]]$Exclude = @(
    ".git/**", ".github/**",
    ".vscode/**", ".idea/**",

    "node_modules/**", "dist/**", "build/**", "coverage/**",
    ".next/**", ".nuxt/**", ".cache/**",

    "**/__pycache__/**", ".mypy_cache/**", ".pytest_cache/**",

    "**/*.env", "**/.env", "**/*.env.*", "**/*.secret.*",
    "**/*.pem", "**/*.key", "**/*.pfx", "**/*.crt",

    "**/*.db", "**/*.sqlite", "**/*.sqlite3", "**/*.log",

    "archives/**", "**/*.zip", "**/*.7z", "**/*.rar", "**/*.tar", "**/*.gz",

    "Thumbs.db", ".DS_Store",
    ".venv/**", "venv/**", "env/**"
  )
)

function Resolve-ProjectPath([string]$p) {
  (Resolve-Path $p).Path
}

function Rel([string]$base, [string]$full) {
  $uBase = [Uri]("$base" + [IO.Path]::DirectorySeparatorChar)
  $uFull = [Uri]$full
  (($uBase.MakeRelativeUri($uFull)).ToString()) -replace '\\','/'
}

function GlobToRegex([string]$glob) {
  $e = [Regex]::Escape($glob)
  $e = $e -replace '\\\*\\\*','§DS§'
  $e = $e -replace '\\\*','[^/]*'
  $e = $e -replace '§DS§','.*'
  return '^' + $e + '$'
}

$ProjectPath = Resolve-ProjectPath $ProjectPath
$OutAbs = Join-Path $ProjectPath $OutDir
if (!(Test-Path $OutAbs)) { New-Item -ItemType Directory -Force -Path $OutAbs | Out-Null }

$incRx = $Include | ForEach-Object { GlobToRegex $_ }
$excRx = $Exclude | ForEach-Object { GlobToRegex $_ }

# Enumerate all files once and filter by include/exclude (relative paths)
$all = Get-ChildItem -Path $ProjectPath -Recurse -File -Force

$selected = foreach ($f in $all) {
  $rel = Rel $ProjectPath $f.FullName
  if (!($incRx | Where-Object { $rel -match $_ })) { continue }
  if ( ($excRx | Where-Object { $rel -match $_ }) ) { continue }
  $f
}

# Sort and materialize metadata
$items = $selected | Sort-Object { Rel $ProjectPath $_.FullName } | ForEach-Object {
  [PSCustomObject]@{
    path  = Rel $ProjectPath $_.FullName
    size  = $_.Length
    mtime = $_.LastWriteTimeUtc.ToString("o")
  }
}

function Sha256File([string]$p) {
  $h = Get-FileHash -Algorithm SHA256 -Path $p
  $h.Hash.ToLower()
}

$withHash = foreach ($it in $items) {
  $abs = Join-Path $ProjectPath ($it.path -replace '/','\')
  [PSCustomObject]@{
    path   = $it.path
    size   = $it.size
    mtime  = $it.mtime
    sha256 = Sha256File $abs
  }
}

# Write tree_F.txt
$treeTxt = Join-Path $OutAbs "tree_F.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("TREE/F (project view) - generated $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') UTC")
$lines.Add("ROOT: /")
$seenDirs = @{}

foreach ($it in $withHash) {
  $parts = $it.path.Split('/')
  $acc = ""
  for ($i = 0; $i -lt $parts.Length - 1; $i++) {
    $acc = if ($i -eq 0) { $parts[$i] } else { "$acc/$($parts[$i])" }
    if (-not $seenDirs.ContainsKey($acc)) {
      $lines.Add("DIR  /$acc/")
      $seenDirs[$acc] = $true
    }
  }
  $lines.Add(("FILE /{0}  [{1} bytes]" -f $it.path, $it.size))
}
$lines | Set-Content -Path $treeTxt -Encoding UTF8

# Write manifest_F.json
$manifestJson = Join-Path $OutAbs "manifest_F.json"
$withHash | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestJson -Encoding UTF8

# Write sha256sum.txt
$shaTxt = Join-Path $OutAbs "sha256sum.txt"
$withHash | ForEach-Object { "{0}  {1}" -f $_.sha256, $_.path } | Set-Content -Path $shaTxt -Encoding UTF8

Write-Host "OK: files generated"
Write-Host " - $treeTxt"
Write-Host " - $manifestJson"
Write-Host " - $shaTxt"
