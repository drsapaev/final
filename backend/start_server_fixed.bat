@echo off
cd /d "C:\final\backend"
call "C:\final\.venv\Scripts\activate.bat"
set WS_DEV_ALLOW=1
set CORS_DISABLE=0
set CORS_ALLOW_ALL=0
set CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174
python run_server.py
pause
