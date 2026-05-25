param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $GateArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")
$pythonLauncher = Join-Path $repoRoot "scripts\run_python.ps1"
$gateScript = Join-Path $scriptDir "agent_gate.py"

if (-not (Test-Path -LiteralPath $pythonLauncher)) {
    throw "Python launcher not found: $pythonLauncher"
}

if (-not (Test-Path -LiteralPath $gateScript)) {
    throw "agent_gate.py not found next to this launcher: $gateScript"
}

$pythonArgs = @($gateScript) + $GateArgs
& $pythonLauncher -PythonArgs $pythonArgs
exit $LASTEXITCODE
