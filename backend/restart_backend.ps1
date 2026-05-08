param(
    [switch]$ForceUvicornProcesses
)

$backendRoot = "C:\final\backend"
$allowUnownedStop = $ForceUvicornProcesses -or ($env:CONFIRM_RESTART_BACKEND_STOP_UNOWNED_UVICORN -eq "1")

Write-Host "Restarting backend server..." -ForegroundColor Yellow
Write-Host "Stopping existing project backend processes..." -ForegroundColor Yellow

$uvicornProcesses = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*"
}

foreach ($proc in $uvicornProcesses) {
    $commandLine = [string]$proc.CommandLine
    $executablePath = [string]$proc.ExecutablePath
    $ownedByProject = $commandLine -like "*$backendRoot*" -or $executablePath -like "C:\final*"

    if (-not $ownedByProject -and -not $allowUnownedStop) {
        Write-Host "Refusing to stop unowned uvicorn process PID $($proc.ProcessId). Use -ForceUvicornProcesses or CONFIRM_RESTART_BACKEND_STOP_UNOWNED_UVICORN=1." -ForegroundColor Red
        continue
    }

    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped uvicorn process PID $($proc.ProcessId)." -ForegroundColor Green
}

Start-Sleep -Seconds 2

Write-Host "Starting backend server..." -ForegroundColor Green
Set-Location $backendRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\final\backend; uvicorn app.main:app --reload --host 0.0.0.0 --port 18000"

Write-Host "Backend server started in a new PowerShell window." -ForegroundColor Green
Write-Host "Waiting 5 seconds for server to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "Verifying backend..." -ForegroundColor Yellow
python verify_fix.py

Write-Host ""
Write-Host "Done. Check the new PowerShell window for backend logs." -ForegroundColor Green
