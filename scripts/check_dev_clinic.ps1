param(
    [int] $BackendPort = 18000,
    [int] $FrontendPort = 5173,
    [string] $DatabaseName = "clinic_dev"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$pidFile = Join-Path $env:TEMP "final-dev-clinic.pids.json"

function Get-PortProcessIds {
    param([Parameter(Mandatory = $true)][int] $Port)

    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ })
}

function Test-Http {
    param([Parameter(Mandatory = $true)][string] $Url)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
        return @{
            ok = $true
            status = [int] $response.StatusCode
            content = [string] $response.Content
            error = $null
        }
    }
    catch {
        return @{
            ok = $false
            status = $null
            content = $null
            error = $_.Exception.Message
        }
    }
}

Write-Output "Dev clinic runtime check"
Write-Output "repo: $repoRoot"
Write-Output "expected database: $DatabaseName"
Write-Output "backend port: $BackendPort"
Write-Output "frontend port: $FrontendPort"

$state = $null
if (Test-Path -LiteralPath $pidFile) {
    $state = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
    Write-Output "pid file: $pidFile"
    Write-Output "recorded database: $($state.database)"
    Write-Output "recorded backend pid: $($state.backend_pid)"
    Write-Output "recorded frontend pid: $($state.frontend_pid)"
    Write-Output "backend stdout: $($state.backend_stdout)"
    Write-Output "backend stderr: $($state.backend_stderr)"
    Write-Output "frontend stdout: $($state.frontend_stdout)"
    Write-Output "frontend stderr: $($state.frontend_stderr)"
}
else {
    Write-Output "pid file: missing ($pidFile)"
}

$backendPids = @(Get-PortProcessIds -Port $BackendPort)
$frontendPids = @(Get-PortProcessIds -Port $FrontendPort)
Write-Output "backend listening pids: $($backendPids -join ', ')"
Write-Output "frontend listening pids: $($frontendPids -join ', ')"

$backendHealth = Test-Http -Url "http://localhost:$BackendPort/api/v1/health"
$frontendRoot = Test-Http -Url "http://localhost:$FrontendPort/"
$proxyHealth = Test-Http -Url "http://localhost:$FrontendPort/api/v1/health"

Write-Output "backend health: $($backendHealth.status) $($backendHealth.content)"
if (-not $backendHealth.ok) { Write-Output "backend health error: $($backendHealth.error)" }

Write-Output "frontend root: $($frontendRoot.status)"
if (-not $frontendRoot.ok) { Write-Output "frontend root error: $($frontendRoot.error)" }

Write-Output "frontend proxy health: $($proxyHealth.status) $($proxyHealth.content)"
if (-not $proxyHealth.ok) { Write-Output "frontend proxy error: $($proxyHealth.error)" }

$ok = (
    $backendPids.Count -gt 0 -and
    $frontendPids.Count -gt 0 -and
    $backendHealth.ok -and
    $frontendRoot.ok -and
    $proxyHealth.ok
)

if ($ok) {
    Write-Output "Result: PASS"
    exit 0
}

Write-Output "Result: FAIL"
exit 1
