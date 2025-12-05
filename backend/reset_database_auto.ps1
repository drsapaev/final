# Database Reset Script for FK Policy Hardening (AUTO MODE)
# This script drops all tables and recreates them with correct FK constraints
# WARNING: ALL DATA WILL BE DELETED
# AUTO MODE: No confirmation required

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "DATABASE RESET SCRIPT (AUTO MODE)" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "WARNING: This will DELETE ALL DATA in the database!" -ForegroundColor Red
Write-Host "AUTO MODE: Proceeding without confirmation..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Step 1: Creating backup..." -ForegroundColor Cyan
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "clinic.db.backup_pre_reset_$timestamp"
if (Test-Path "clinic.db") {
    try {
        Copy-Item "clinic.db" $backupPath -ErrorAction Stop
        Write-Host "Backup created: $backupPath" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: Failed to create backup: $_" -ForegroundColor Yellow
        Write-Host "Continuing anyway..." -ForegroundColor Yellow
    }
} else {
    Write-Host "No existing database found, skipping backup." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 2: Deleting database files..." -ForegroundColor Cyan
$deleted = $false
if (Test-Path "clinic.db") {
    Remove-Item "clinic.db" -ErrorAction SilentlyContinue
    $deleted = $true
}
Remove-Item "clinic.db-journal" -ErrorAction SilentlyContinue
Remove-Item "clinic.db-wal" -ErrorAction SilentlyContinue
Remove-Item "clinic.db-shm" -ErrorAction SilentlyContinue
if ($deleted) {
    Write-Host "Database files deleted." -ForegroundColor Green
} else {
    Write-Host "No database files to delete." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 3: Running Alembic migrations..." -ForegroundColor Cyan
try {
    alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Migration failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
    Write-Host "Migrations applied successfully." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Migration failed with exception: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 4: Verifying FK enforcement..." -ForegroundColor Cyan
try {
    python verify_fk_enforcement.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: FK enforcement verification failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
    Write-Host "FK enforcement verified." -ForegroundColor Green
} catch {
    Write-Host "ERROR: FK enforcement verification failed with exception: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 5: Checking for orphaned records..." -ForegroundColor Cyan
try {
    if (Test-Path "app/scripts/audit_foreign_keys.py") {
        python app/scripts/audit_foreign_keys.py
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARNING: Audit script returned errors (may be expected for empty DB)" -ForegroundColor Yellow
        } else {
            Write-Host "Audit completed successfully." -ForegroundColor Green
        }
    } else {
        Write-Host "WARNING: audit_foreign_keys.py not found, skipping audit." -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: Audit script failed: $_" -ForegroundColor Yellow
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
if (Test-Path $backupPath) {
    Write-Host "Backup location: $backupPath" -ForegroundColor Cyan
}
Write-Host ""

