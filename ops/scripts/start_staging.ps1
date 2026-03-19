param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$composeFile = Join-Path $projectRoot "ops\\compose.staging.yml"
$envFile = Join-Path $projectRoot "ops\\staging.env"

if (-not (Test-Path $envFile)) {
    throw "Missing $envFile. Copy ops/staging.env.sample to ops/staging.env first."
}

$upArgs = @("compose", "--env-file", $envFile, "-f", $composeFile, "up", "-d")
if (-not $NoBuild) {
    $upArgs += "--build"
}

Push-Location $projectRoot
try {
    & docker @upArgs
    docker compose --env-file $envFile -f $composeFile ps
}
finally {
    Pop-Location
}
