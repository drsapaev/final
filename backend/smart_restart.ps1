param(
    [switch]$ForcePortOwners
)

Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "CLINIC MANAGEMENT SYSTEM - SMART BACKEND RESTART" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: stopping project Python processes..." -ForegroundColor Yellow
if ($ForcePortOwners) {
    & "$PSScriptRoot\stop_all_python.ps1" -ForcePortOwners
}
else {
    & "$PSScriptRoot\stop_all_python.ps1"
}

Write-Host ""
Write-Host "Step 2: checking port 18000..." -ForegroundColor Yellow

$maxAttempts = 5
$attempt = 0
$portFree = $false

while ($attempt -lt $maxAttempts -and -not $portFree) {
    $attempt++
    $check = netstat -ano | Select-String ":18000.*LISTENING"

    if (-not $check) {
        $portFree = $true
        Write-Host "[OK] Port 18000 is free." -ForegroundColor Green
    }
    else {
        Write-Host "Attempt $attempt/${maxAttempts}: port 18000 is still busy." -ForegroundColor Yellow

        if (-not $ForcePortOwners -and $env:CONFIRM_STOP_ALL_PYTHON_PORT_OWNERS -ne "1") {
            Write-Host "Refusing unmanaged port-owner kill without -ForcePortOwners or CONFIRM_STOP_ALL_PYTHON_PORT_OWNERS=1." -ForegroundColor Red
        }
        else {
            $check | ForEach-Object {
                $line = $_.Line
                $processId = ($line -split '\s+')[-1]
                Write-Host "Killing unmanaged port owner PID: $processId"
                taskkill /PID $processId /F 2>$null
            }
        }

        Start-Sleep -Seconds 2
    }
}

Write-Host ""
if ($portFree) {
    Write-Host "Step 3: starting backend on port 18000..." -ForegroundColor Yellow
    Write-Host ""
    & "c:\final\.venv\Scripts\python.exe" "$PSScriptRoot\start_server.py"
}
else {
    Write-Host ("=" * 80) -ForegroundColor Red
    Write-Host "[WARN] Could not free port 18000." -ForegroundColor Red
    Write-Host ("=" * 80) -ForegroundColor Red
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "1. Close the owning process manually." -ForegroundColor Cyan
    Write-Host "2. Rerun with -ForcePortOwners or CONFIRM_STOP_ALL_PYTHON_PORT_OWNERS=1." -ForegroundColor Cyan
    Write-Host "3. Start on alternate port 8001." -ForegroundColor Cyan
    Write-Host ""

    $response = Read-Host "Start on port 8001? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host ""
        Write-Host "Starting on port 8001..." -ForegroundColor Green
        & "c:\final\.venv\Scripts\python.exe" "$PSScriptRoot\start_server_port8001.py"
    }
}
