@echo off
echo ========================================
echo    ОСТАНОВКА СИСТЕМЫ КЛИНИКИ
echo ========================================

echo.
echo Остановка процессов на портах 5173 и 8000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    echo Остановка процесса %%a на порту 5173...
    taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Остановка процесса %%a на порту 8000...
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo Все процессы остановлены!
echo.
pause
