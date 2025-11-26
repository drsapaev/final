@echo off
cd /d "C:\final\backend"
call "C:\final\.venv\Scripts\activate.bat"
set WS_DEV_ALLOW=1
set CORS_DISABLE=1
set REQUIRE_LICENSE=0
python run_server.py
pause
