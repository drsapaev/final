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

function Get-StartupGitRevision {
    # An inherited Git repository or index would make the cleanliness check
    # describe a different checkout or snapshot.
    foreach ($name in @('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')) {
        if (Test-Path "Env:$name") { return }
    }

    try {
        $git = (Get-Command -Name git.exe -CommandType Application -ErrorAction Stop |
            Select-Object -First 1).Source
        $options = @('--no-optional-locks', '-C', $Repo)
        $root = & $git @options rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($root) -ne [IO.Path]::GetFullPath($Repo)) { return }

        $revision = & $git @options rev-parse --verify 'HEAD^{commit}' 2>$null
        if ($LASTEXITCODE -ne 0 -or $revision -cnotmatch '^[0-9a-f]{40}$') { return }

        $changes = & $git @options status --porcelain=v1 --untracked-files=normal 2>$null
        if ($LASTEXITCODE -ne 0 -or $changes) { return }

        $branch = & $git @options symbolic-ref --quiet HEAD 2>$null
        if ($LASTEXITCODE -ne 0 -or $branch -cne 'refs/heads/main') { return }

        $currentRevision = & $git @options rev-parse --verify 'HEAD^{commit}' 2>$null
        if ($LASTEXITCODE -eq 0 -and $currentRevision -ceq $revision) { return $revision }
    } catch {
        # The service can still boot when Git is unavailable or rejects the repo.
        return
    }
}

# Always override any inherited stamp. An explicit value also takes precedence
# over dotenv when Git cannot verify the startup checkout.
$env:APP_GIT_REVISION = 'unverified'
$startupRevision = Get-StartupGitRevision
if ($startupRevision) { $env:APP_GIT_REVISION = $startupRevision }

Set-Location (Join-Path $Repo 'backend')

# The detached process inherits the Windows console code page even though its
# streams are redirected to a file. Force UTF-8 so structured logs containing
# Cyrillic text or symbols do not fail inside logging.StreamHandler.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

& "$env:ComSpec" /c "`"$Python`" -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --log-level warning >> `"$Log`" 2>&1"
exit $LASTEXITCODE
