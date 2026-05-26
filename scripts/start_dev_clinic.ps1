param(
    [int] $BackendPort = 18000,
    [int] $FrontendPort = 5173,
    [string] $DatabaseName = "clinic_dev",
    [int] $WaitSeconds = 90
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$backendEnvPath = Join-Path $backendDir ".env"
$pidFile = Join-Path $env:TEMP "final-dev-clinic.pids.json"
$backendOut = Join-Path $env:TEMP "final-backend-dev.out.log"
$backendErr = Join-Path $env:TEMP "final-backend-dev.err.log"
$frontendOut = Join-Path $env:TEMP "final-frontend-dev.out.log"
$frontendErr = Join-Path $env:TEMP "final-frontend-dev.err.log"

function Write-Info {
    param([string] $Message)
    Write-Output $Message
}

function Get-DatabaseUrlFromBackendEnv {
    if (-not (Test-Path -LiteralPath $backendEnvPath)) {
        throw "backend .env not found: $backendEnvPath"
    }

    $line = Get-Content -LiteralPath $backendEnvPath |
        Where-Object { $_ -match "^\s*DATABASE_URL\s*=" } |
        Select-Object -First 1

    if (-not $line) {
        throw "DATABASE_URL not found in backend .env"
    }

    return $line.Split("=", 2)[1].Trim().Trim('"').Trim("'")
}

function Convert-ToDevDatabaseUrl {
    param(
        [Parameter(Mandatory = $true)][string] $DatabaseUrl,
        [Parameter(Mandatory = $true)][string] $TargetDatabaseName
    )

    if ($TargetDatabaseName -notmatch "^[A-Za-z0-9_]+$") {
        throw "unsafe database name: $TargetDatabaseName"
    }

    $match = [regex]::Match($DatabaseUrl, "^(?<prefix>.+/)(?<database>[^/?#]+)(?<suffix>[?#].*)?$")
    if (-not $match.Success) {
        throw "cannot derive dev database URL from backend DATABASE_URL"
    }

    $prefix = $match.Groups["prefix"].Value
    $suffix = $match.Groups["suffix"].Value
    return "$prefix$TargetDatabaseName$suffix"
}

function Get-PortProcessIds {
    param([Parameter(Mandatory = $true)][int] $Port)

    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ })
}

function Test-PortOpen {
    param([Parameter(Mandatory = $true)][int] $Port)
    return @(Get-PortProcessIds -Port $Port).Count -gt 0
}

function Wait-Port {
    param(
        [Parameter(Mandatory = $true)][int] $Port,
        [Parameter(Mandatory = $true)][int] $TimeoutSeconds,
        [Parameter(Mandatory = $true)][string] $Name
    )

    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-PortOpen -Port $Port) {
            return
        }
        Start-Sleep -Seconds 1
    }

    throw "$Name did not open port $Port within $TimeoutSeconds seconds"
}

function Invoke-HealthJson {
    param([Parameter(Mandatory = $true)][string] $Url)

    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
    return @{
        StatusCode = [int] $response.StatusCode
        Content = [string] $response.Content
    }
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string] $Url,
        [Parameter(Mandatory = $true)][int] $TimeoutSeconds,
        [Parameter(Mandatory = $true)][string] $Name
    )

    $lastError = $null
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        try {
            $result = Invoke-HealthJson -Url $Url
            if ($result.StatusCode -ge 200 -and $result.StatusCode -lt 300) {
                return $result
            }
        }
        catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }

    throw "$Name did not return HTTP 2xx from $Url. Last error: $lastError"
}

function Write-LogTail {
    param(
        [Parameter(Mandatory = $true)][string] $Label,
        [Parameter(Mandatory = $true)][string] $Path
    )

    if (Test-Path -LiteralPath $Path) {
        Write-Output ""
        Write-Output "== ${Label}: $Path =="
        Get-Content -LiteralPath $Path -Tail 80
    }
}

function Set-ProcessEnvironment {
    param([Parameter(Mandatory = $true)][hashtable] $Values)

    $previous = @{}
    foreach ($key in $Values.Keys) {
        $previous[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
        [Environment]::SetEnvironmentVariable($key, [string] $Values[$key], "Process")
    }
    return $previous
}

function Restore-ProcessEnvironment {
    param([Parameter(Mandatory = $true)][hashtable] $Previous)

    foreach ($key in $Previous.Keys) {
        [Environment]::SetEnvironmentVariable($key, $Previous[$key], "Process")
    }
}

function Start-Backend {
    param([Parameter(Mandatory = $true)][string] $DevDatabaseUrl)

    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $pythonCommand = Get-Command python -ErrorAction Stop
        $python = $pythonCommand.Source
    }

    Remove-Item -LiteralPath $backendOut, $backendErr -ErrorAction SilentlyContinue
    $previous = Set-ProcessEnvironment @{
        ENV = "dev"
        APP_ENV = "dev"
        DATABASE_URL = $DevDatabaseUrl
        DISABLE_2FA_REQUIREMENT = "1"
        BACKEND_HOST = "0.0.0.0"
        BACKEND_PORT = [string] $BackendPort
    }

    try {
        return Start-Process `
            -FilePath $python `
            -ArgumentList @("run_server.py") `
            -WorkingDirectory $backendDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $backendOut `
            -RedirectStandardError $backendErr `
            -PassThru
    }
    finally {
        Restore-ProcessEnvironment -Previous $previous
    }
}

function Start-Frontend {
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
    if (-not $npm) {
        $npm = Get-Command npm -ErrorAction Stop
    }

    Remove-Item -LiteralPath $frontendOut, $frontendErr -ErrorAction SilentlyContinue
    $previous = Set-ProcessEnvironment @{
        VITE_PROXY_TARGET = "http://localhost:$BackendPort"
        VITE_WS_PROXY_TARGET = "ws://localhost:$BackendPort"
    }

    try {
        return Start-Process `
            -FilePath $npm.Source `
            -ArgumentList @("run", "dev", "--", "--host", "0.0.0.0", "--port", [string] $FrontendPort) `
            -WorkingDirectory $frontendDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $frontendOut `
            -RedirectStandardError $frontendErr `
            -PassThru
    }
    finally {
        Restore-ProcessEnvironment -Previous $previous
    }
}

Write-Info "Dev clinic launcher"
Write-Info "repo: $repoRoot"
Write-Info "backend port: $BackendPort"
Write-Info "frontend port: $FrontendPort"
Write-Info "database: $DatabaseName"
Write-Info "logs:"
Write-Info "- backend stdout: $backendOut"
Write-Info "- backend stderr: $backendErr"
Write-Info "- frontend stdout: $frontendOut"
Write-Info "- frontend stderr: $frontendErr"
Write-Info ""
Write-Info "Safety: this script does not edit backend/.env, reset databases, seed data, or run migrations."

$sourceDatabaseUrl = Get-DatabaseUrlFromBackendEnv
$devDatabaseUrl = Convert-ToDevDatabaseUrl -DatabaseUrl $sourceDatabaseUrl -TargetDatabaseName $DatabaseName

$backendProcess = $null
$frontendProcess = $null
$backendExistingPids = @(Get-PortProcessIds -Port $BackendPort)
if ($backendExistingPids.Count -gt 0) {
    Write-Info "backend port $BackendPort already listening; reusing existing process(es): $($backendExistingPids -join ', ')"
}
else {
    try {
        $backendProcess = Start-Backend -DevDatabaseUrl $devDatabaseUrl
        Write-Info "backend pid: $($backendProcess.Id)"
        Wait-Port -Port $BackendPort -TimeoutSeconds $WaitSeconds -Name "backend"
    }
    catch {
        Write-LogTail -Label "backend stderr" -Path $backendErr
        Write-LogTail -Label "backend stdout" -Path $backendOut
        throw
    }
}

$backendHealth = Wait-HttpOk -Url "http://localhost:$BackendPort/api/v1/health" -TimeoutSeconds $WaitSeconds -Name "backend health"
Write-Info "backend health: $($backendHealth.StatusCode) $($backendHealth.Content)"

$frontendExistingPids = @(Get-PortProcessIds -Port $FrontendPort)
if ($frontendExistingPids.Count -gt 0) {
    Write-Info "frontend port $FrontendPort already listening; reusing existing process(es): $($frontendExistingPids -join ', ')"
}
else {
    try {
        $frontendProcess = Start-Frontend
        Write-Info "frontend pid: $($frontendProcess.Id)"
        Wait-Port -Port $FrontendPort -TimeoutSeconds $WaitSeconds -Name "frontend"
    }
    catch {
        Write-LogTail -Label "frontend stderr" -Path $frontendErr
        Write-LogTail -Label "frontend stdout" -Path $frontendOut
        throw
    }
}

$frontendRoot = Wait-HttpOk -Url "http://localhost:$FrontendPort/" -TimeoutSeconds $WaitSeconds -Name "frontend root"
Write-Info "frontend root: $($frontendRoot.StatusCode)"

$proxyHealth = Wait-HttpOk -Url "http://localhost:$FrontendPort/api/v1/health" -TimeoutSeconds $WaitSeconds -Name "frontend proxy health"
Write-Info "frontend proxy health: $($proxyHealth.StatusCode) $($proxyHealth.Content)"

$state = [ordered] @{
    repo = [string] $repoRoot
    database = $DatabaseName
    backend_port = $BackendPort
    frontend_port = $FrontendPort
    backend_pid = if ($backendProcess) { $backendProcess.Id } elseif ($backendExistingPids.Count -gt 0) { [int] $backendExistingPids[0] } else { $null }
    frontend_pid = if ($frontendProcess) { $frontendProcess.Id } elseif ($frontendExistingPids.Count -gt 0) { [int] $frontendExistingPids[0] } else { $null }
    backend_existing_pids = $backendExistingPids
    frontend_existing_pids = $frontendExistingPids
    backend_stdout = $backendOut
    backend_stderr = $backendErr
    frontend_stdout = $frontendOut
    frontend_stderr = $frontendErr
    started_at = (Get-Date).ToString("o")
}

$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pidFile -Encoding UTF8

Write-Info ""
Write-Info "Started/validated dev clinic runtime."
Write-Info "Backend: http://localhost:$BackendPort"
Write-Info "Frontend: http://localhost:$FrontendPort"
Write-Info "PID file: $pidFile"
Write-Info "Stop with: .\scripts\stop_dev_clinic.ps1"
