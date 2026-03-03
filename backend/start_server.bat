@echo off
cd /d "C:\final\backend"
call "C:\final\.venv\Scripts\activate.bat"
set WS_DEV_ALLOW=1
if not defined CORS_DISABLE set CORS_DISABLE=0
set REQUIRE_LICENSE=0
python run_server.py
pause
