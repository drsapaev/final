param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CheckArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$targetScript = Join-Path $scriptDir "check_artifacts.py"

$pythonArgs = @($targetScript) + $CheckArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
