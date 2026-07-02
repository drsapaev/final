@echo off
echo ================================================
echo 🏥 КЛИНИЧЕСКАЯ СИСТЕМА - АВТОМАТИЧЕСКИЙ ЗАПУСК
echo ================================================

cd /d "C:\final\backend"

echo 🔧 Активируем виртуальное окружение...
call "C:\final\.venv\Scripts\activate.bat"
set BACKEND_HOST=0.0.0.0
set BACKEND_PORT=18000

echo 🚀 Запускаем сервер с автоматической проверкой...
python run_server_auto.py

echo.
echo ✅ Работа завершена. Нажмите любую клавишу для выхода...
pause >nul
