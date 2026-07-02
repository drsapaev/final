# Deprecated database reset helper.
# PostgreSQL + Alembic are the database source of truth for this project.

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "DEPRECATED DATABASE RESET SCRIPT" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "This legacy helper no longer deletes local SQLite files." -ForegroundColor Red
Write-Host "Runtime databases must be managed through PostgreSQL procedures and Alembic migrations." -ForegroundColor Yellow
Write-Host ""
Write-Host "For schema updates, run:" -ForegroundColor Cyan
Write-Host "  alembic upgrade head"
Write-Host ""
Write-Host "For destructive PostgreSQL reset or data recovery, use an explicit runbook/backup procedure." -ForegroundColor Cyan
Write-Host "Do not use SQLite file deletion as a runtime reset path." -ForegroundColor Cyan
Write-Host ""
exit 2
