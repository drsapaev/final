@echo off
setlocal

echo ========================================
echo    CLINIC SYSTEM STOP
echo ========================================
echo.

echo Stopping canonical ports 5173 and 18000 through guarded helpers...
echo To allow helper scripts to stop port owners automatically, set:
echo   CONFIRM_KILL_PORT_5173_OWNER=1
echo   CONFIRM_KILL_PORT_18000_OWNER=1
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0frontend\kill_port_5173.ps1"
set FRONTEND_STATUS=%ERRORLEVEL%

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\kill_port_18000.ps1"
set BACKEND_STATUS=%ERRORLEVEL%

echo.
if not "%FRONTEND_STATUS%"=="0" (
    echo Frontend port 5173 is still busy or was not stopped.
)
if not "%BACKEND_STATUS%"=="0" (
    echo Backend port 18000 is still busy or was not stopped.
)

if "%FRONTEND_STATUS%"=="0" if "%BACKEND_STATUS%"=="0" (
    echo Clinic ports are free.
    exit /b 0
)

echo Close the owning process manually or rerun with explicit CONFIRM_KILL_PORT_*_OWNER=1.
exit /b 1
