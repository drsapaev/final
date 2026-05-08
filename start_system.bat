@echo off
setlocal

echo ========================================
echo    CLINIC SYSTEM START
echo ========================================
echo.

echo [1/4] Checking canonical ports 5173 and 18000...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0frontend\kill_port_5173.ps1"
if errorlevel 1 (
    echo Port 5173 is busy. Close the owning process or set CONFIRM_KILL_PORT_5173_OWNER=1 before retrying.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\kill_port_18000.ps1"
if errorlevel 1 (
    echo Port 18000 is busy. Close the owning process or set CONFIRM_KILL_PORT_18000_OWNER=1 before retrying.
    exit /b 1
)

echo [2/4] Starting Backend API on 18000...
cd /d "%~dp0backend"
start "Backend API" cmd /k ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 18000"

echo [3/4] Waiting for Backend...
timeout /t 5 /nobreak >nul

echo [4/4] Starting Frontend on 5173...
cd /d "%~dp0frontend"
start "Frontend" cmd /k "npm run dev -- --host 0.0.0.0 --port 5173"

echo.
echo ========================================
echo    CLINIC SYSTEM STARTED
echo ========================================
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:18000
echo API Docs: http://localhost:18000/docs
echo.
echo Use credentials from your local backend/frontend .env files.
echo.
pause
