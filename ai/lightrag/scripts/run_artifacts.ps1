param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArtifactArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$targetScript = Join-Path $scriptDir "export_artifacts.py"

$pythonArgs = @($targetScript) + $ArtifactArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
