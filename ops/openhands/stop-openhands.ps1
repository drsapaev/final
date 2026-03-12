[CmdletBinding()]
param(
    [string]$Distro = ""
)

$ErrorActionPreference = 'Stop'

$command = 'docker rm -f openhands-app >/dev/null 2>&1 || true'

$wslArgs = @()
if ($Distro) {
    $wslArgs += '-d'
    $wslArgs += $Distro
}
$wslArgs += @('bash', '-lc', $command)

& wsl.exe @wslArgs

Write-Output 'OpenHands container stop request completed.'
