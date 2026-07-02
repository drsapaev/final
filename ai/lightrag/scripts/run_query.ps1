param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Query,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $QueryArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$targetScript = Join-Path $scriptDir "query.py"

$pythonArgs = @($targetScript, $Query) + $QueryArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
