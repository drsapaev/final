param(
    [Parameter(Mandatory = $true)][string] $Executable,
    [Parameter(Mandatory = $true)][string] $ArgumentsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$arguments = @($ArgumentsJson | ConvertFrom-Json)
& $Executable @arguments
exit $LASTEXITCODE
