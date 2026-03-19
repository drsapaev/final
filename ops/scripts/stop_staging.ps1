$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$composeFile = Join-Path $projectRoot "ops\\compose.staging.yml"
$envFile = Join-Path $projectRoot "ops\\staging.env"

Push-Location $projectRoot
try {
    docker compose --env-file $envFile -f $composeFile down
}
finally {
    Pop-Location
}
