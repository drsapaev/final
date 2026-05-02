param(
    [string]$PgHost = "localhost",
    [int]$Port = 5432,
    [string]$AppUser = "clinic",
    [string]$AppPassword,
    [string]$AdminUser = "postgres",
    [string]$AdminPassword,
    [string]$Database = "clinicdb",
    [string]$BackupDir = "c:\final\backups\postgres",
    [string]$BackendDir = "c:\final\backend"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-PgTool {
    param([string]$ToolName)

    $cmd = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "C:\Program Files\PostgreSQL\17\bin\$ToolName",
        "C:\Program Files\PostgreSQL\16\bin\$ToolName",
        "C:\Program Files\PostgreSQL\15\bin\$ToolName"
    )

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }

    throw "Cannot find $ToolName in PATH or standard PostgreSQL install paths."
}

if (-not $AppPassword) {
    throw "AppPassword is required."
}
if (-not $AdminPassword) {
    throw "AdminPassword is required."
}

$pgDump = Resolve-PgTool -ToolName "pg_dump.exe"
$psql = Resolve-PgTool -ToolName "psql.exe"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "$Database`_$timestamp.dump"

Write-Host "[1/5] Backup database with pg_dump..."
$env:PGPASSWORD = $AppPassword
& $pgDump -h $PgHost -p $Port -U $AppUser -d $Database -F c -f $backupFile
if (-not (Test-Path $backupFile)) {
    throw "Backup file was not created: $backupFile"
}
Write-Host "Backup created: $backupFile"

Write-Host "[2/5] Terminate active sessions..."
$env:PGPASSWORD = $AdminPassword
& $psql -w -h $PgHost -p $Port -U $AdminUser -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$Database' AND pid<>pg_backend_pid();"

Write-Host "[3/5] Drop database..."
& $psql -w -h $PgHost -p $Port -U $AdminUser -d postgres -c "DROP DATABASE IF EXISTS $Database;"

Write-Host "[4/5] Recreate database..."
& $psql -w -h $PgHost -p $Port -U $AdminUser -d postgres -c "CREATE DATABASE $Database OWNER $AppUser;"

Write-Host "[5/5] Alembic upgrade and verification..."
Push-Location $BackendDir
try {
    $env:DATABASE_URL = "postgresql+psycopg://$AppUser`:$AppPassword@$PgHost`:$Port/$Database"
    alembic upgrade head
    alembic current
}
finally {
    Pop-Location
}

Write-Host "DR test completed successfully."
Write-Host "Backup file: $backupFile"
