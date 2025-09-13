@echo off
echo ========================================
echo    ЗАПУСК СИСТЕМЫ КЛИНИКИ
echo ========================================

echo.
echo [1/4] Остановка старых процессов...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [2/4] Запуск Backend API...
cd /d C:\final\backend
start "Backend API" cmd /k "python -m uvicorn app.main:app --reload --port 8000"

echo [3/4] Ожидание запуска Backend...
timeout /t 5 /nobreak >nul

echo [4/4] Запуск Frontend...
cd /d C:\final\frontend
start "Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo    СИСТЕМА ЗАПУЩЕНА!
echo ========================================
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Логин: admin
echo Пароль: admin123
echo.
pause
