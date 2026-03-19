$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$runtimeDir = Join-Path $projectRoot "output\\staging"

function Stop-ListenerByPort {
    param([int]$Port)

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($listenerPid in $listeners) {
        if ($listenerPid) {
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
}

foreach ($name in @("backend", "frontend")) {
    $pidFile = Join-Path $runtimeDir "$name.pid"
    if (Test-Path $pidFile) {
        $pidValue = (Get-Content $pidFile | Select-Object -First 1).Trim()
        if ($pidValue) {
            Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Stop-ListenerByPort -Port 18000
Stop-ListenerByPort -Port 18080
