param(
    [switch]$ForcePortOwner
)

$port = 5173
$allowKill = $ForcePortOwner -or ($env:CONFIRM_KILL_PORT_5173_OWNER -eq "1")

Write-Host "[*] Searching for listeners on port $port..." -ForegroundColor Cyan

$connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "[OK] Port $port is free." -ForegroundColor Green
    exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $pids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }

    Write-Host "[WARN] Port owner: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
    if (-not $allowKill) {
        Write-Host "Refusing to stop PID $processId without -ForcePortOwner or CONFIRM_KILL_PORT_5173_OWNER=1" -ForegroundColor Red
        continue
    }

    try {
        Stop-Process -Id $processId -Force
        Write-Host "[OK] Stopped PID $processId." -ForegroundColor Green
    }
    catch {
        Write-Host "[ERROR] Failed to stop PID $processId." -ForegroundColor Red
    }
}

Start-Sleep -Seconds 1
$remaining = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "[WARN] Port $port is still busy." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Port $port is free." -ForegroundColor Green
