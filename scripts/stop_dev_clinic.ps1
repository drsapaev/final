param(
    [int] $BackendPort = 18000,
    [int] $FrontendPort = 5173,
    [switch] $ForcePorts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$pidFile = Join-Path $env:TEMP "final-dev-clinic.pids.json"

function Get-PortProcessIds {
    param([Parameter(Mandatory = $true)][int] $Port)

    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ })
}

function Get-ChildProcessIds {
    param([Parameter(Mandatory = $true)][int] $ParentProcessId)

    @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentProcessId" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty ProcessId |
        Where-Object { $_ })
}

function Get-ProcessTreeIds {
    param([Parameter(Mandatory = $true)][int] $RootProcessId)

    $ids = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootProcessId)

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if ($ids.Contains($current)) {
            continue
        }

        $ids.Add($current)
        foreach ($child in Get-ChildProcessIds -ParentProcessId $current) {
            $queue.Enqueue([int] $child)
        }
    }

    return $ids
}

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int] $ProcessId)

    if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        Write-Output "pid $ProcessId is not running"
        return
    }

    $tree = @(Get-ProcessTreeIds -RootProcessId $ProcessId | Sort-Object -Descending)
    foreach ($pid in $tree) {
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }

        Write-Output "stopping pid $pid ($($process.ProcessName))"
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

function Get-StatePropertyValue {
    param(
        [Parameter(Mandatory = $true)] $State,
        [Parameter(Mandatory = $true)][string] $Name
    )

    $property = $State.PSObject.Properties[$Name]
    if ($property) {
        return $property.Value
    }
    return $null
}

function Add-TrackedPids {
    param(
        [Parameter(Mandatory = $true)] [System.Collections.Generic.List[int]] $Target,
        $Value
    )

    if ($null -eq $Value) {
        return
    }

    foreach ($item in @($Value)) {
        if ($null -ne $item -and [int] $item -gt 0) {
            $Target.Add([int] $item)
        }
    }
}

Write-Output "Dev clinic stop"
Write-Output "repo: $repoRoot"
Write-Output "pid file: $pidFile"

$trackedPids = New-Object System.Collections.Generic.List[int]
if (Test-Path -LiteralPath $pidFile) {
    $state = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
    foreach ($name in @("backend_pid", "frontend_pid", "backend_existing_pids", "frontend_existing_pids")) {
        Add-TrackedPids -Target $trackedPids -Value (Get-StatePropertyValue -State $state -Name $name)
    }
}
else {
    Write-Output "pid file not found; no tracked launcher pids available"
}

foreach ($pid in ($trackedPids | Sort-Object -Unique)) {
    Stop-ProcessTree -ProcessId $pid
}

if ($ForcePorts) {
    foreach ($port in @($BackendPort, $FrontendPort)) {
        foreach ($pid in Get-PortProcessIds -Port $port) {
            Write-Output "force stopping process on port $port"
            Stop-ProcessTree -ProcessId ([int] $pid)
        }
    }
}

Start-Sleep -Seconds 1
$backendPids = @(Get-PortProcessIds -Port $BackendPort)
$frontendPids = @(Get-PortProcessIds -Port $FrontendPort)

if ($backendPids.Count -eq 0 -and $frontendPids.Count -eq 0) {
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
    Write-Output "Result: stopped"
    exit 0
}

Write-Output "Result: ports still in use"
Write-Output "backend port $BackendPort pids: $($backendPids -join ', ')"
Write-Output "frontend port $FrontendPort pids: $($frontendPids -join ', ')"
if (-not $ForcePorts) {
    Write-Output "Use .\scripts\stop_dev_clinic.ps1 -ForcePorts only if these are the dev clinic processes."
}
exit 1
