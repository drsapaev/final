param(
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
        [pscustomobject] $Candidate
    )

    try {
        $probe = "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)"
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
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$candidates = [System.Collections.Generic.List[object]]::new()

Add-FileCandidate $candidates "REPO_PYTHON" $env:REPO_PYTHON
Add-FileCandidate $candidates "AGENT_GATE_PYTHON" $env:AGENT_GATE_PYTHON
Add-FileCandidate $candidates "repo .venv" (Join-Path $repoRoot ".venv\Scripts\python.exe")
Add-CommandCandidate $candidates "py -3.11 launcher" "py.exe" @("-3.11")
Add-CommandCandidate $candidates "py -3 launcher" "py.exe" @("-3")
Add-CommandCandidate $candidates "PATH python.exe" "python.exe"

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

$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$uniqueCandidates = foreach ($candidate in $candidates) {
    $key = "$($candidate.Command)|$($candidate.PrefixArgs -join ' ')"
    if ($seen.Add($key)) {
        $candidate
    }
}

foreach ($candidate in $uniqueCandidates) {
    if (Test-PythonCandidate $candidate) {
        Write-Host "[repo-python] Using Python: $($candidate.Label) ($($candidate.Command) $($candidate.PrefixArgs -join ' '))"
        & $candidate.Command @($candidate.PrefixArgs) @PythonArgs
        exit $LASTEXITCODE
    }
}

$attempted = $uniqueCandidates | ForEach-Object {
    "- $($_.Label): $($_.Command) $($_.PrefixArgs -join ' ')"
}

Write-Error @"
No working Python 3.11+ interpreter was found.

Tried:
$($attempted -join [Environment]::NewLine)

Set REPO_PYTHON to a valid python.exe, set AGENT_GATE_PYTHON for gate-only runs,
or recreate .venv with Python 3.11+.
"@
