$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$composeFile = Join-Path $projectRoot "ops\\compose.staging.yml"
$envFile = Join-Path $projectRoot "ops\\staging.env"

Push-Location $projectRoot
try {
    docker compose --env-file $envFile -f $composeFile exec backend python scripts/run_emr_cutover.py --pretty
}
finally {
    Pop-Location
}
