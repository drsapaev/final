@echo off
echo ========================================
echo    ОСТАНОВКА СИСТЕМЫ КЛИНИКИ
echo ========================================

echo.
echo Остановка процессов на портах 18080 и 18000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :18080') do (
    echo Остановка процесса %%a на порту 18080...
    taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :18000') do (
    echo Остановка процесса %%a на порту 18000...
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo Все процессы остановлены!
echo.
pause
