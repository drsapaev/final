# Restart backend server
Write-Host "🔄 Restarting backend server..." -ForegroundColor Yellow

# Kill existing python processes running uvicorn
Write-Host "🛑 Stopping existing backend processes..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -eq "python" -and $_.CommandLine -like "*uvicorn*"} | Stop-Process -Force -ErrorAction SilentlyContinue

# Wait a moment
Start-Sleep -Seconds 2

# Start new backend process
Write-Host "🚀 Starting backend server..." -ForegroundColor Green
Set-Location "c:\final\backend"

# Start uvicorn in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\final\backend; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

Write-Host "✅ Backend server started in new window!" -ForegroundColor Green
Write-Host "⏳ Waiting 5 seconds for server to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Verify
Write-Host "🔍 Verifying backend..." -ForegroundColor Yellow
python verify_fix.py

Write-Host "`n✅ Done! Check the new PowerShell window for backend logs." -ForegroundColor Green
