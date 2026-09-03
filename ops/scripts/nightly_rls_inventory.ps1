#requires -Version 5.1
<#
.SYNOPSIS
    Nightly live RLS inventory for the production database.

.DESCRIPTION
    Closes the detection gap left by the CI RLS guard (#3009): CI asserts
    RLS on a FRESH alembic chain, but tables created out-of-band on the
    live database (the 2026-09-02 incident class — salary tables, then
    medical_specialties the same day) are invisible to it. This script
    runs ops/scripts/check_public_rls.py against the LIVE production
    DATABASE_URL (read-only query on pg_class) and raises a Sentry event
    when any public table has RLS disabled.

    Registered on the prod host as a daily scheduled task (see
    docs/incidents/2026-09-02-supabase-rls-disabled-in-public.md).
    Log: C:\final\tools\rls_inventory.log (append-only; trim manually).

.NOTES
    Read-only against the database. No mutations; the fix for a failure
    is a human/agent action (ENABLE ROW LEVEL SECURITY + adoption PR).
#>
[CmdletBinding()]
param(
    # Optional override for testing (e.g. a local empty database) —
    # skips loading DATABASE_URL/SENTRY_DSN from backend\.env.
    [string]$DatabaseUrl,
    # Skip the Sentry alert even on failure (tests).
    [switch]$NoAlert
)

$ErrorActionPreference = 'Stop'

$Repo   = 'C:\final'
$Python = Join-Path $Repo 'backend\.venv\Scripts\python.exe'
$Checker = Join-Path $Repo 'ops\scripts\check_public_rls.py'
$EnvFile = Join-Path $Repo 'backend\.env'
$Log     = Join-Path $Repo 'tools\rls_inventory.log'

foreach ($p in @($Python, $Checker, $EnvFile)) {
    if (-not (Test-Path $p)) {
        Add-Content $Log "$(Get-Date -Format s) FATAL missing=$p"
        exit 3
    }
}

if ($DatabaseUrl) {
    $env:DATABASE_URL = $DatabaseUrl
}
else {
    # Load DATABASE_URL / SENTRY_DSN from backend\.env (same file the app uses).
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^(DATABASE_URL|SENTRY_DSN)=(.+)$') {
            Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2].Trim().Trim('"')
        }
    }
}

# Native stderr would become ErrorRecords and trip $ErrorActionPreference
# 'Stop' before the log line — capture as plain strings instead.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$output = @(& $Python $Checker 2>&1 | ForEach-Object { $_.ToString() })
$ErrorActionPreference = $prevEap
$code = $LASTEXITCODE
$stamp = Get-Date -Format s
Add-Content $Log "$stamp exit=$code $($output -join ' | ')"

if ($code -ne 0 -and -not $NoAlert -and $env:SENTRY_DSN) {
    $env:RLS_FAIL_OUTPUT = ($output -join ' | ')
    & $Python -c @'
import os
import sentry_sdk
sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], environment="production")
sentry_sdk.capture_message(
    "RLS nightly inventory FAILED: " + os.environ.get("RLS_FAIL_OUTPUT", "")[:800],
    level="error",
)
sentry_sdk.flush()
'@ | Out-Null
}

exit $code
