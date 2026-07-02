$ErrorActionPreference = "Stop"

function Import-EnvFile {
    param([string]$Path)

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $pair = $trimmed -split "=", 2
        [System.Environment]::SetEnvironmentVariable($pair[0], $pair[1], "Process")
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$backendDir = Join-Path $projectRoot "backend"
$envFile = Join-Path $backendDir ".env.staging"
$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"

Import-EnvFile -Path $envFile
Push-Location $backendDir
try {
    & $backendPython scripts/run_emr_cutover.py --pretty
}
finally {
    Pop-Location
}
