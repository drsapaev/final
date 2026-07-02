param(
    [switch]$ForcePortOwners
)

Write-Host ("=" * 60)
Write-Host "Stopping project Python processes..." -ForegroundColor Yellow
Write-Host ("=" * 60)

$stopped = 0
$allowPortOwnerKill = $ForcePortOwners -or ($env:CONFIRM_STOP_ALL_PYTHON_PORT_OWNERS -eq "1")

Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*final*"
} | ForEach-Object {
    Write-Host "Stopping project process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Cyan
    Write-Host "  Path: $($_.Path)"
    Stop-Process -Id $_.Id -Force
    $stopped++
}

if ($stopped -gt 0) {
    Write-Host ""
    Write-Host "[OK] Stopped project Python processes: $stopped" -ForegroundColor Green
    Start-Sleep -Seconds 2
}
else {
    Write-Host "[INFO] No project Python processes found." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Checking port 18000..." -ForegroundColor Yellow
$netstat = netstat -ano | Select-String ":18000.*LISTENING"

if ($netstat) {
    Write-Host "[WARN] Port 18000 is still busy." -ForegroundColor Yellow
    $netstat | ForEach-Object {
        $line = $_.Line
        $processId = ($line -split '\s+')[-1]
        if (-not $allowPortOwnerKill) {
            Write-Host "Refusing to kill unmanaged port owner PID $processId without -ForcePortOwners or CONFIRM_STOP_ALL_PYTHON_PORT_OWNERS=1" -ForegroundColor Red
            return
        }
        Write-Host "Killing unmanaged port owner PID: $processId"
        taskkill /PID $processId /F 2>$null
    }

    Write-Host "Waiting for port release..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3

    $netstat2 = netstat -ano | Select-String ":18000.*LISTENING"
    if ($netstat2) {
        Write-Host "Second port cleanup attempt..." -ForegroundColor Yellow
        $netstat2 | ForEach-Object {
            $line = $_.Line
            $processId = ($line -split '\s+')[-1]
            if (-not $allowPortOwnerKill) {
                Write-Host "Refusing second unmanaged port-owner kill for PID $processId without explicit confirmation" -ForegroundColor Red
                return
            }
            taskkill /PID $processId /F 2>$null
        }
        Start-Sleep -Seconds 2
    }
}

$finalCheck = netstat -ano | Select-String ":18000.*LISTENING"
if (-not $finalCheck) {
    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "[OK] Port 18000 is free and ready." -ForegroundColor Green
    Write-Host ("=" * 60)
}
else {
    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "[WARN] Port 18000 is still busy." -ForegroundColor Red
    Write-Host "Close the owning process manually or rerun with explicit confirmation." -ForegroundColor Yellow
    Write-Host ("=" * 60)
}
