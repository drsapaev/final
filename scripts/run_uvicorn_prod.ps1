#requires -Version 5.1
<#
.SYNOPSIS
    Single launch point for the production uvicorn (port 18000) with
    persistent output logging.

.DESCRIPTION
    Both the logon autostart (Startup folder .cmd) and
    scripts/deploy_restart.ps1 start the backend through this script, so
    the uvicorn command line lives in exactly one place.

    stdout+stderr are APPENDED to C:\final\tools\uvicorn_backend.log via
    cmd redirection (Start-Process cannot append and cannot merge both
    streams into one file). The backend runs with --log-level warning,
    so the file carries warnings and errors only — including the
    request.slow entries (#2996) that name slow endpoints during SLA
    spikes; before this, uvicorn logged into a minimized console window
    that vanished on logoff, leaving spikes undiagnosable.

    Volume is low (warnings only); trim the file manually if it ever
    grows past a few MB.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Repo   = 'C:\final'
$Python = Join-Path $Repo 'backend\.venv\Scripts\python.exe'
$Log    = Join-Path $Repo 'tools\uvicorn_backend.log'

Set-Location (Join-Path $Repo 'backend')

& "$env:ComSpec" /c "`"$Python`" -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --log-level warning >> `"$Log`" 2>&1"
exit $LASTEXITCODE
