@echo off
cd /d C:\final\frontend
set "VITE_API_BASE_URL=http://127.0.0.1:18008"
npm run dev -- --host 127.0.0.1 --port 4194
