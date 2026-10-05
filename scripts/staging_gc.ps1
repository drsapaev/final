# Targeted GC for forgotten ephemeral staging resources.
#
# Removes ONLY Docker resources labeled `clinic.lifecycle=ephemeral` whose
# `clinic.expires_at` has passed (or all ephemeral ones with -IncludeUnexpired).
# Resources without the label are NEVER touched, and there is intentionally no
# `docker system prune` here: parallel agent sessions share this daemon, so a
# global prune could destroy another working process's cache, volumes, or
# images.
#
# Usage:
#   powershell -File scripts/staging_gc.ps1 -DryRun        # list only
#   powershell -File scripts/staging_gc.ps1                # remove expired
#   powershell -File scripts/staging_gc.ps1 -IncludeUnexpired
#
# Docker runs inside WSL (Ubuntu-24.04) on this host; the script wraps it.
# Labels are read via full `docker inspect` JSON (no --format templates:
# their quote escaping differs between the Windows/WSL invocation paths and
# silently produces empty matches).
param(
    [switch] $IncludeUnexpired,
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$nativeDocker = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($nativeDocker) {
    function D { docker @args }
} else {
    function D { wsl -d Ubuntu-24.04 -- docker @args }
}

function Get-LabelsFor([string] $kind, [string] $id) {
    $raw = (D $kind "inspect" $id) | Out-String
    $obj = $raw | ConvertFrom-Json
    if ($kind -eq "container") { return $obj[0].Config.Labels }
    return $obj[0].Labels
}

function Get-LabeledEphemeral {
    # kind = docker object noun used by the CLI (container/volume/network)
    $out = @()
    foreach ($kind in @("container", "volume", "network")) {
        # containers MUST use -a: forgotten leftovers are usually EXITED,
        # and `docker container ls -q` (running only) silently misses them.
        if ($kind -eq "container") {
            $ids = (D $kind "ls" "-aq") | Where-Object { $_ -ne "" }
        } else {
            $ids = (D $kind "ls" "-q") | Where-Object { $_ -ne "" }
        }
        foreach ($id in $ids) {
            $labels = Get-LabelsFor $kind $id
            if (-not $labels -or $labels."clinic.lifecycle" -ne "ephemeral") { continue }
            $out += [PSCustomObject]@{
                Kind    = $kind
                Id      = $id
                Project = $labels."com.docker.compose.project"
                Expires = $labels."clinic.expires_at"
            }
        }
    }
    return $out
}

function Test-Expired([string] $expiresRaw) {
    if ($IncludeUnexpired) { return $true }
    if ([string]::IsNullOrWhiteSpace($expiresRaw)) { return $false }  # no expiry stamp: report-only, never auto-removed
    try {
        $parsed = [datetime]::Parse($expiresRaw, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal)
        return ($parsed -lt [datetime]::UtcNow)
    } catch {
        Write-Warning "Unparseable clinic.expires_at '$expiresRaw' - treating as NOT expired."
        return $false
    }
}

$found = Get-LabeledEphemeral
$expired = $found | Where-Object { Test-Expired $_.Expires }
$kept = $found | Where-Object { -not (Test-Expired $_.Expires) }

if (-not $expired) {
    Write-Host "No expired ephemeral resources found."
}
foreach ($item in $expired) {
    Write-Host ("REMOVE {0} {1} (project={2}, expires={3})" -f $item.Kind, $item.Id, $item.Project, $item.Expires)
}
foreach ($item in $kept) {
    Write-Host ("KEEP   {0} {1} (project={2}, expires={3})" -f $item.Kind, $item.Id, $item.Project, $item.Expires)
}

if ($DryRun) {
    Write-Host "DryRun: nothing removed."
    exit 0
}

$hadError = $false
foreach ($item in $expired) {
    switch ($item.Kind) {
        "container" { D container rm -f $item.Id | Out-Null }
        "volume"    { D volume rm $item.Id | Out-Null }
        "network"   { D network rm $item.Id | Out-Null }
    }
    if ($LASTEXITCODE -ne 0) { $hadError = $true }
}

# Images are not labeled individually; remove the built images of expired
# projects (the compose-created, project-tagged ones) — mirrors what
# `compose down --rmi local` would have done.
$projects = $expired | Where-Object { $_.Kind -eq "container" -and $_.Project } | Select-Object -ExpandProperty Project -Unique
foreach ($project in $projects) {
    $imageIds = (D images "--filter" "label=com.docker.compose.project=$project" "-q") | Where-Object { $_ -ne "" }
    foreach ($img in $imageIds) {
        Write-Host "REMOVE image $img (project=$project)"
        D rmi $img | Out-Null
        if ($LASTEXITCODE -ne 0) { $hadError = $true }
    }
}

if ($hadError) { exit 1 }
Write-Host "GC complete."
