@echo off
cd /d C:\final\backend
set "BACKEND_PORT=18006"
set "BACKEND_RELOAD=0"
set "CORS_ALLOW_ALL=1"
C:\final\backend\.venv\Scripts\python.exe start_server.py
