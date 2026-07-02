param(
    [switch]$ForcePortOwners
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$runtimeDir = Join-Path $projectRoot "output\\staging"

function Confirm-UnmanagedPortOwnerStop {
    param(
        [int]$Port,
        [int[]]$ProcessIds
    )

    if ($ForcePortOwners -or $env:CONFIRM_STOP_STAGING_PORT_OWNERS -eq "1") {
        return
    }

    throw "Refusing to stop unmanaged listener(s) on port ${Port}: $($ProcessIds -join ', '). Pass -ForcePortOwners or set CONFIRM_STOP_STAGING_PORT_OWNERS=1 for an intentional cleanup."
}

function Stop-ListenerByPort {
    param([int]$Port)

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if ($listeners) {
        Confirm-UnmanagedPortOwnerStop -Port $Port -ProcessIds @($listeners)
    }

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
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Stop-ListenerByPort -Port 18000
Stop-ListenerByPort -Port 18080
