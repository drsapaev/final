param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$pythonLauncher = Join-Path (Join-Path $repoRoot "scripts") "run_python.ps1"
$backendRoot = Join-Path $repoRoot "backend"

if (-not (Test-Path -LiteralPath $pythonLauncher)) {
    throw "Python launcher not found: $pythonLauncher"
}

if (-not (Test-Path -LiteralPath $backendRoot)) {
    throw "Backend directory not found: $backendRoot"
}

$previous = Get-Location
try {
    Set-Location -LiteralPath $backendRoot
    $env:PYTHONPATH = $backendRoot
    & $pythonLauncher -RequireModule pytest -m pytest @PytestArgs
    exit $LASTEXITCODE
}
finally {
    Set-Location -LiteralPath $previous
}
