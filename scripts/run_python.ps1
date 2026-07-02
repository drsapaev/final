param(
    [string[]] $RequireModule = @(),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PythonArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-Candidate {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string] $Command,
        [string[]] $PrefixArgs = @()
    )

    [pscustomobject]@{
        Label = $Label
        Command = $Command
        PrefixArgs = $PrefixArgs
    }
}

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject] $Candidate,
        [string[]] $RequiredModules = @()
    )

    try {
        $modules = ($RequiredModules -join ",")
        $probe = "import importlib.util, sys; modules = [name for name in r'''$modules'''.split(',') if name]; ok = sys.version_info >= (3, 11) and all(importlib.util.find_spec(name) is not None for name in modules); raise SystemExit(0 if ok else 2)"
        & $Candidate.Command @($Candidate.PrefixArgs) -c $probe *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Add-FileCandidate {
    param(
        [System.Collections.Generic.List[object]] $Candidates,
        [string] $Label,
        [string] $Path
    )

    if ($Path -and (Test-Path -LiteralPath $Path)) {
        $Candidates.Add((New-Candidate -Label $Label -Command $Path)) | Out-Null
    }
}

function Add-CommandCandidate {
    param(
        [System.Collections.Generic.List[object]] $Candidates,
        [string] $Label,
        [string] $Name,
        [string[]] $PrefixArgs = @()
    )

    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        $Candidates.Add((New-Candidate -Label $Label -Command $command.Source -PrefixArgs $PrefixArgs)) | Out-Null
    }
}

if (-not $PythonArgs -or $PythonArgs.Count -eq 0) {
    Write-Error "Usage: .\scripts\run_python.ps1 <python arguments>"
    exit 64
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$candidates = [System.Collections.Generic.List[object]]::new()
$isWindowsPlatform = $env:OS -eq 'Windows_NT'

Add-FileCandidate $candidates "REPO_PYTHON" $env:REPO_PYTHON
Add-FileCandidate $candidates "AGENT_GATE_PYTHON" $env:AGENT_GATE_PYTHON

if ($isWindowsPlatform) {
    Add-FileCandidate $candidates "repo .venv" (Join-Path $repoRoot ".venv\Scripts\python.exe")
    Add-FileCandidate $candidates "backend .venv" (Join-Path $repoRoot "backend\.venv\Scripts\python.exe")
    Add-CommandCandidate $candidates "py -3.11 launcher" "py.exe" @("-3.11")
    Add-CommandCandidate $candidates "py -3 launcher" "py.exe" @("-3")
    Add-CommandCandidate $candidates "PATH python.exe" "python.exe"
    Add-CommandCandidate $candidates "PATH python" "python"
}
else {
    Add-FileCandidate $candidates "repo .venv" (Join-Path $repoRoot ".venv/bin/python3")
    Add-FileCandidate $candidates "repo .venv fallback" (Join-Path $repoRoot ".venv/bin/python")
    Add-FileCandidate $candidates "backend .venv" (Join-Path $repoRoot "backend/.venv/bin/python3")
    Add-FileCandidate $candidates "backend .venv fallback" (Join-Path $repoRoot "backend/.venv/bin/python")
    Add-CommandCandidate $candidates "PATH python3" "python3"
    Add-CommandCandidate $candidates "PATH python" "python"
}

if ($isWindowsPlatform) {
    $programFilesRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $programFilesRoots) {
        $postgresRoot = Join-Path $root "PostgreSQL"
        if (-not (Test-Path -LiteralPath $postgresRoot)) {
            continue
        }

        Get-ChildItem -LiteralPath $postgresRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                Add-FileCandidate $candidates "pgAdmin bundled Python" (Join-Path $_.FullName "pgAdmin 4\python\python.exe")
            }
    }

    foreach ($path in @("C:\Python311\python.exe", "C:\Program Files\Python311\python.exe")) {
        Add-FileCandidate $candidates "common Python 3.11 path" $path
    }
}

$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$uniqueCandidates = foreach ($candidate in $candidates) {
    $key = "$($candidate.Command)|$($candidate.PrefixArgs -join ' ')"
    if ($seen.Add($key)) {
        $candidate
    }
}

foreach ($candidate in $uniqueCandidates) {
    if (Test-PythonCandidate $candidate -RequiredModules $RequireModule) {
        Write-Host "[repo-python] Using Python: $($candidate.Label) ($($candidate.Command) $($candidate.PrefixArgs -join ' '))"
        & $candidate.Command @($candidate.PrefixArgs) @PythonArgs
        exit $LASTEXITCODE
    }
}

$attempted = $uniqueCandidates | ForEach-Object {
    "- $($_.Label): $($_.Command) $($_.PrefixArgs -join ' ')"
}

Write-Error @"
No working Python 3.11+ interpreter was found$(if ($RequireModule.Count -gt 0) { " with required module(s): $($RequireModule -join ', ')" } else { "" }).

Tried:
$($attempted -join [Environment]::NewLine)

Set REPO_PYTHON to a valid Python executable, set AGENT_GATE_PYTHON for gate-only runs,
or recreate the repo/backend virtual environment with Python 3.11+ and the required packages.
"@
