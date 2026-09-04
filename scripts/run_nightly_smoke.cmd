@echo off
rem Nightly functional smoke wrapper (Task Scheduler: ClinicNightlyFunctionalSmoke, daily 02:30)
chcp 65001 >nul
cd /d C:\final
C:\final\.venv\Scripts\python.exe C:\final\scripts\nightly_functional_smoke.py > C:\final\output\nightly_smoke\last_run.log 2>&1
