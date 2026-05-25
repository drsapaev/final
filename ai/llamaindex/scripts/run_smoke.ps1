param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $SmokeArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$targetScript = Join-Path $scriptDir "smoke.py"

$pythonArgs = @($targetScript, "--update-status") + $SmokeArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
