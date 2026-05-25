param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AcceptanceArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$targetScript = Join-Path $scriptDir "acceptance.py"

$pythonArgs = @($targetScript, "--update-status") + $AcceptanceArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
