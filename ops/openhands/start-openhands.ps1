[CmdletBinding()]
param(
    [string]$Distro = "",
    [int]$Port = 3000,
    [switch]$PrintOnly
)

$ErrorActionPreference = 'Stop'

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)

    $resolved = (Resolve-Path $WindowsPath).Path
    $normalized = $resolved -replace '\\', '/'

    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        return "/mnt/$($matches[1].ToLower())/$($matches[2])"
    }

    throw "Unsupported Windows path for WSL conversion: $resolved"
}

function Escape-SingleQuotes {
    param([Parameter(Mandatory = $true)][string]$Value)

    return $Value.Replace("'", "'""'""'")
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$composeFile = Join-Path $repoRoot 'ops/openhands/docker-compose.yml'
$stateDir = Join-Path $env:USERPROFILE '.openhands'

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$composeWsl = Convert-ToWslPath -WindowsPath $composeFile
$repoWsl = Convert-ToWslPath -WindowsPath $repoRoot
$stateWsl = Convert-ToWslPath -WindowsPath $stateDir
$workspaceMount = "${repoWsl}:/workspace:rw"

$composeEscaped = Escape-SingleQuotes -Value $composeWsl
$stateEscaped = Escape-SingleQuotes -Value $stateWsl
$workspaceEscaped = Escape-SingleQuotes -Value $workspaceMount

$command = @(
    'set -e'
    'docker info >/dev/null'
    "export OPENHANDS_PORT='$Port'"
    "export OPENHANDS_STATE_DIR='$stateEscaped'"
    "export OPENHANDS_WORKSPACE_MOUNT='$workspaceEscaped'"
    "docker compose -f '$composeEscaped' up -d"
    "docker ps --filter name=openhands-app"
) -join '; '

if ($PrintOnly) {
    Write-Output $command
    exit 0
}

$wslArgs = @()
if ($Distro) {
    $wslArgs += '-d'
    $wslArgs += $Distro
}
$wslArgs += @('bash', '-lc', $command)

& wsl.exe @wslArgs

Write-Output "OpenHands should be available at http://localhost:$Port"
