# Mandatory teardown for an isolated staging Compose project.
#
# Lifecycle contract (AGENT_SESSION_WORKTREES.md / LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md):
# every synthetic staging run ends with this command unless KEEP_STAGING=1 is
# explicitly set for failure investigation. The command is the contract, not
# documentation: docker compose down -v --remove-orphans --rmi local removes
# the project's containers, networks, named volumes, and locally built images.
#
# Usage:
#   powershell -File scripts/staging_down.ps1 -ProjectName clinic-pr3524-a1
#   powershell -File scripts/staging_down.ps1 -ProjectName clinic-pr3524-a1 -EnvFile ops/.env.staging-pr3524
#
# Docker runs inside WSL (Ubuntu-24.04) on this host; the script wraps it and
# converts Windows paths automatically. If a native docker.exe appears on PATH
# later, it is preferred automatically.
param(
    [Parameter(Mandatory = $true)]
    [string] $ProjectName,

    # Compose file relative to this checkout's root (or absolute).
    [string] $ComposeFile = "ops/compose.staging.yml",

    # Untracked env file used at `up` time; optional for `down`.
    [string] $EnvFile = "",

    # Bypass the KEEP_STAGING=1 guard (e.g. GC operator action).
    [switch] $Force,

    # Print the command without executing it.
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

# KEEP_STAGING=1 is the explicit exception that keeps a failed stack running
# for investigation. A plain re-run with -Force still tears it down.
if (-not $Force -and "$env:KEEP_STAGING" -eq "1") {
    Write-Host "KEEP_STAGING=1 is set - leaving project '$ProjectName' running."
    Write-Host "Investigate, then re-run with -Force (or unset KEEP_STAGING) to tear it down."
    exit 0
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Resolve-RepoPath([string] $p) {
    if ([System.IO.Path]::IsPathRooted($p)) { return (Resolve-Path $p).Path }
    return (Resolve-Path (Join-Path $repoRoot $p)).Path
}

function Convert-ToWslPath([string] $p) {
    # C:\repo\ops\x.yml -> /mnt/c/repo/ops/x.yml
    $full = (Resolve-Path $p).Path
    $slash = $full -replace "\\", "/"
    $drive = $slash.Substring(0, 1).ToLowerInvariant()
    return "/mnt/$drive" + $slash.Substring(2)
}

# Prefer a native docker.exe when one exists; this host currently has none,
# so the WSL wrapper is the default path.
$nativeDocker = Get-Command docker.exe -ErrorAction SilentlyContinue
$composeArgs = @()
if ($nativeDocker) {
    $dockerBase = @("docker")
    $composeFileArg = (Resolve-RepoPath $ComposeFile)
} else {
    $dockerBase = @("wsl", "-d", "Ubuntu-24.04", "--", "docker")
    $composeFileArg = Convert-ToWslPath (Resolve-RepoPath $ComposeFile)
}

$composeArgs += @("compose", "-p", $ProjectName, "-f", $composeFileArg)
if ($EnvFile -ne "") {
    $composeArgs += @("--env-file", (Convert-ToWslPath (Resolve-RepoPath $EnvFile)))
}
$composeArgs += @("down", "-v", "--remove-orphans", "--rmi", "local")

Write-Host "Tearing down Compose project '$ProjectName':"
Write-Host ("  " + ($dockerBase + $composeArgs -join " "))

if ($DryRun) {
    Write-Host "DryRun: nothing executed."
    exit 0
}

& $dockerBase[0] $dockerBase[1..($dockerBase.Length - 1)] $composeArgs
$exit = $LASTEXITCODE
if ($exit -ne 0) {
    Write-Error "docker compose down failed with exit code $exit"
    exit $exit
}
Write-Host "Project '$ProjectName' removed (containers, networks, volumes, local images)."
