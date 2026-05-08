$ErrorActionPreference = "Stop"

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing env file: $Path"
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $pair = $trimmed -split "=", 2
        $key = $pair[0].Trim()
        $value = $pair[1].Trim().Trim('"').Trim("'")
        if (-not $key) {
            continue
        }
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$runtimeDir = Join-Path $projectRoot "output\\staging"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

Import-EnvFile -Path (Join-Path $backendDir ".env.staging")

$publicHost = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254*' -and
        $_.InterfaceAlias -notlike 'vEthernet*'
    } |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $publicHost) {
    $publicHost = "127.0.0.1"
}

[System.Environment]::SetEnvironmentVariable(
    "CORS_ORIGINS",
    "http://$publicHost`:18080,http://localhost:18080,http://127.0.0.1:18080",
    "Process"
)
[System.Environment]::SetEnvironmentVariable("VITE_API_BASE_URL", "http://$publicHost`:18000", "Process")

$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
if (-not (Test-Path $backendPython)) {
    throw "Missing backend venv python at $backendPython"
}

$backendLog = Join-Path $runtimeDir "backend.log"
$backendErr = Join-Path $runtimeDir "backend.err.log"
$frontendLog = Join-Path $runtimeDir "frontend.log"
$frontendErr = Join-Path $runtimeDir "frontend.err.log"

$backendProc = Start-Process `
    -FilePath $backendPython `
    -ArgumentList "start_server.py" `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErr `
    -PassThru `
    -WindowStyle Hidden

Set-Content -Path (Join-Path $runtimeDir "backend.pid") -Value $backendProc.Id

Push-Location $frontendDir
try {
    .\node_modules\.bin\vite.cmd build --mode staging
}
finally {
    Pop-Location
}

$frontendCommand = ".\\node_modules\\.bin\\vite.cmd preview --host 0.0.0.0 --port 18080 --strictPort"
$frontendProc = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-Command", $frontendCommand `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErr `
    -PassThru `
    -WindowStyle Hidden

Set-Content -Path (Join-Path $runtimeDir "frontend.pid") -Value $frontendProc.Id

Write-Output "Backend PID: $($backendProc.Id)"
Write-Output "Frontend PID: $($frontendProc.Id)"
Write-Output "Backend URL: http://$publicHost`:18000/docs"
Write-Output "Frontend URL: http://$publicHost`:18080"
Write-Output "Local Frontend URL: http://127.0.0.1:18080"
