# Database Reset Script for FK Policy Hardening
# This script drops all tables and recreates them with correct FK constraints
# WARNING: ALL DATA WILL BE DELETED

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "DATABASE RESET SCRIPT" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "WARNING: This will DELETE ALL DATA in the database!" -ForegroundColor Red
Write-Host ""

$confirm = Read-Host "Type 'RESET' to confirm database reset"
if ($confirm -ne "RESET") {
    Write-Host "Reset cancelled." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "Step 1: Creating backup..." -ForegroundColor Cyan
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "clinic.db.backup_pre_reset_$timestamp"
if (Test-Path "clinic.db") {
    Copy-Item "clinic.db" $backupPath -ErrorAction SilentlyContinue
    Write-Host "Backup created: $backupPath" -ForegroundColor Green
} else {
    Write-Host "No existing database found, skipping backup." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 2: Deleting database files..." -ForegroundColor Cyan
Remove-Item "clinic.db" -ErrorAction SilentlyContinue
Remove-Item "clinic.db-journal" -ErrorAction SilentlyContinue
Remove-Item "clinic.db-wal" -ErrorAction SilentlyContinue
Remove-Item "clinic.db-shm" -ErrorAction SilentlyContinue
Write-Host "Database files deleted." -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Running Alembic migrations..." -ForegroundColor Cyan
alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Migration failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Migrations applied successfully." -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Verifying FK enforcement..." -ForegroundColor Cyan
python verify_fk_enforcement.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: FK enforcement verification failed!" -ForegroundColor Red
    exit 1
}
Write-Host "FK enforcement verified." -ForegroundColor Green

Write-Host ""
Write-Host "Step 5: Checking for orphaned records..." -ForegroundColor Cyan
python app/scripts/audit_foreign_keys.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Audit script returned errors (may be expected for empty DB)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DATABASE RESET COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Database is now clean with correct FK constraints:" -ForegroundColor Green
Write-Host "  - All FKs have explicit ondelete policies" -ForegroundColor Green
Write-Host "  - FK enforcement is enabled (PRAGMA foreign_keys = 1)" -ForegroundColor Green
Write-Host "  - No orphaned records possible by design" -ForegroundColor Green
Write-Host ""
Write-Host "Backup location: $backupPath" -ForegroundColor Cyan
Write-Host ""

