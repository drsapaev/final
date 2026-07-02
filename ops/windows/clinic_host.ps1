[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        'start',
        'stop',
        'restart',
        'status',
        'backup',
        'import-release',
        'migrate',
        'smoke-fresh-install',
        'smoke-post-update',
        'restore-rehearsal',
        'update',
        'rollback'
    )]
    [string]$Action = 'status',

    [string]$AppRoot = '',
    [string]$ArtifactFile = '',
    [string]$ReleaseRef = '',
    [string]$RollbackRef = '',

    [switch]$RunRollbackMigrations,
    [switch]$SkipMigrations
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = if ($AppRoot) {
    (Resolve-Path $AppRoot).Path
} else {
    (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
}
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$OpsScripts = Join-Path $RepoRoot 'ops\vps\scripts'
$LifecycleEnv = Join-Path $RepoRoot '.env.clinic-lifecycle'
$BackendEnv = Join-Path $BackendDir '.env.production'
$FrontendEnv = Join-Path $FrontendDir '.env.production'
$OutputDir = Join-Path $RepoRoot 'output'
$StateDir = Join-Path $OutputDir 'windows'
$BackendPidFile = Join-Path $StateDir 'backend.pid'
$FrontendPidFile = Join-Path $StateDir 'frontend.pid'
$BackendOutLog = Join-Path $StateDir 'backend.out.log'
$BackendErrLog = Join-Path $StateDir 'backend.err.log'
$FrontendOutLog = Join-Path $StateDir 'frontend.out.log'
$FrontendErrLog = Join-Path $StateDir 'frontend.err.log'
$DefaultBackendPort = 18000
$DefaultFrontendPort = 18080
$RestoreBackendPort = 18001
$RestoreFrontendPort = 18081
$RestorePostgresPort = 55433
$RestoreDatabaseName = 'clinicdb_restore'
$RestorePostgresDataDir = Join-Path $StateDir 'restore-postgres'
$RestorePostgresLog = Join-Path $StateDir 'restore-postgres.log'
$RestoreBackendPidFile = Join-Path $StateDir 'restore-backend.pid'
$RestoreFrontendPidFile = Join-Path $StateDir 'restore-frontend.pid'
$RestoreBackendOutLog = Join-Path $StateDir 'restore-backend.out.log'
$RestoreBackendErrLog = Join-Path $StateDir 'restore-backend.err.log'
$RestoreFrontendOutLog = Join-Path $StateDir 'restore-frontend.out.log'
$RestoreFrontendErrLog = Join-Path $StateDir 'restore-frontend.err.log'

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Ok {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    throw $Message
}

function Import-EnvFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$Override
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#') -or $line -notmatch '=') {
            return
        }

        $parts = $line.Split('=', 2)
        if ($parts.Count -ne 2) {
            return
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if (-not $key) {
            return
        }

        if ($Override -or -not [System.Environment]::GetEnvironmentVariable($key)) {
            [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
}

function Get-CurrentLanAddress {
    $preferred = @()

    try {
        $configs = Get-NetIPConfiguration -ErrorAction Stop | Where-Object {
            $_.NetAdapter -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4Address
        }

        foreach ($config in $configs) {
            $hasGateway = [bool]$config.IPv4DefaultGateway
            $metric = if ($null -ne $config.InterfaceMetric) { [int]$config.InterfaceMetric } else { 9999 }

            foreach ($address in @($config.IPv4Address)) {
                $ip = $address.IPAddress
                if (-not $ip) {
                    continue
                }

                if ($ip -eq '127.0.0.1' -or $ip -like '169.254*') {
                    continue
                }

                $preferred += [pscustomobject]@{
                    Ip = $ip
                    HasGateway = $hasGateway
                    Metric = $metric
                }
            }
        }
    } catch {
        # Fall through to socket-based detection.
    }

    if ($preferred.Count -gt 0) {
        $best = $preferred | Sort-Object @{ Expression = 'HasGateway'; Descending = $true }, @{ Expression = 'Metric'; Ascending = $true } | Select-Object -First 1
        if ($best -and $best.Ip) {
            return $best.Ip
        }
    }

    try {
        $socket = [System.Net.Sockets.Socket]::new(
            [System.Net.Sockets.AddressFamily]::InterNetwork,
            [System.Net.Sockets.SocketType]::Dgram,
            [System.Net.Sockets.ProtocolType]::Udp
        )
        try {
            $socket.Connect('1.1.1.1', 80)
            $endpoint = $socket.LocalEndPoint
            if ($endpoint -and $endpoint.Address) {
                $ip = $endpoint.Address.IPAddressToString
                if ($ip -and $ip -ne '127.0.0.1') {
                    return $ip
                }
            }
        } finally {
            $socket.Close()
        }
    } catch {
        # No-op; final fallback below.
    }

    return '127.0.0.1'
}

function Set-DynamicRuntimeOrigins {
    $lanAddress = Get-CurrentLanAddress
    $publicUrl = "http://${lanAddress}:$DefaultFrontendPort"
    $corsOrigins = @(
        $publicUrl,
        "http://$($env:COMPUTERNAME):$DefaultFrontendPort"
    ) -join ','

    [System.Environment]::SetEnvironmentVariable('APP_HOST', $lanAddress, 'Process')
    [System.Environment]::SetEnvironmentVariable('PUBLIC_URL', $publicUrl, 'Process')
    [System.Environment]::SetEnvironmentVariable('CORS_ORIGINS', $corsOrigins, 'Process')
    [System.Environment]::SetEnvironmentVariable('CLINIC_AUTO_DETECT_PUBLIC_URL', '1', 'Process')
}

function Initialize-ClinicEnv {
    [System.Environment]::SetEnvironmentVariable('APP_ROOT', $RepoRoot, 'Process')
    [System.Environment]::SetEnvironmentVariable('LIFECYCLE_ENV_FILE', $LifecycleEnv, 'Process')
    [System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Process')
    [System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
    Import-EnvFile -Path $LifecycleEnv -Override
    Import-EnvFile -Path $BackendEnv -Override
    Import-EnvFile -Path $FrontendEnv -Override
    Set-DynamicRuntimeOrigins
    [System.Environment]::SetEnvironmentVariable('APP_ROOT', $RepoRoot, 'Process')
}

function Invoke-WithEnvOverrides {
    param(
        [hashtable]$Overrides = @{},
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock
    )

    $original = @{}
    foreach ($key in $Overrides.Keys) {
        $original[$key] = [System.Environment]::GetEnvironmentVariable($key, 'Process')
        [System.Environment]::SetEnvironmentVariable($key, [string]$Overrides[$key], 'Process')
    }

    try {
        & $ScriptBlock
    } finally {
        foreach ($key in $Overrides.Keys) {
            [System.Environment]::SetEnvironmentVariable($key, $original[$key], 'Process')
        }
    }
}

function Get-PythonExe {
    $venvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    Write-Fail 'Python is required but was not found on PATH.'
}

function Get-NpmExe {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    Write-Fail 'npm is required but was not found on PATH.'
}

function Get-PostgresTool {
    param([Parameter(Mandatory = $true)][string]$ToolName)

    $configuredBin = [System.Environment]::GetEnvironmentVariable('POSTGRES_BIN_DIR', 'Process')
    $candidates = @()

    if ($configuredBin) {
        $candidates += Join-Path $configuredBin $ToolName
        if (-not $ToolName.EndsWith('.exe')) {
            $candidates += Join-Path $configuredBin "$ToolName.exe"
        }
    }

    $candidates += @(
        "C:\Program Files\PostgreSQL\17\bin\$ToolName",
        "C:\Program Files\PostgreSQL\16\bin\$ToolName",
        "C:\Program Files\PostgreSQL\15\bin\$ToolName"
    )
    if (-not $ToolName.EndsWith('.exe')) {
        $candidates += @(
            "C:\Program Files\PostgreSQL\17\bin\$ToolName.exe",
            "C:\Program Files\PostgreSQL\16\bin\$ToolName.exe",
            "C:\Program Files\PostgreSQL\15\bin\$ToolName.exe"
        )
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    if (-not $ToolName.EndsWith('.exe')) {
        $command = Get-Command "$ToolName.exe" -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    Write-Fail "Missing PostgreSQL tool: $ToolName"
}

function Get-LifecycleScript {
    param([Parameter(Mandatory = $true)][string]$Name)
    $script = Join-Path $OpsScripts $Name
    if (-not (Test-Path -LiteralPath $script)) {
        Write-Fail "Missing lifecycle script: $script"
    }
    return $script
}

function Invoke-PythonScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptName,
        [string[]]$Arguments = @(),
        [hashtable]$EnvOverrides = @{}
    )

    $python = Get-PythonExe
    $script = Get-LifecycleScript $ScriptName
    $output = Invoke-WithEnvOverrides -Overrides $EnvOverrides -ScriptBlock {
        & $python $script @Arguments 2>&1
    }
    if ($output) {
        $output | ForEach-Object { Write-Host $_ }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Command failed: $python $script $($Arguments -join ' ')"
    }

    return @($output)
}

function Get-ListeningPids {
    param([Parameter(Mandatory = $true)][int]$Port)

    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        if ($connections) {
            return $connections | Select-Object -ExpandProperty OwningProcess -Unique
        }
    } catch {
        # Fall back to netstat on hosts where the NetTCPIP module is unavailable.
    }

    $lines = netstat -ano | Select-String "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+\d+\s*$"
    if (-not $lines) {
        return @()
    }

    $pids = @()
    foreach ($line in $lines) {
        if ($line.Line -match '(\d+)\s*$') {
            $pids += [int]$Matches[1]
        }
    }

    return $pids | Sort-Object -Unique
}

function Wait-For-PortFree {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-ListeningPids -Port $Port)) {
            return
        }
        Start-Sleep -Seconds 1
    }

    $processIds = Get-ListeningPids -Port $Port
    if ($processIds) {
        Write-Fail "Port $Port is still in use after waiting $TimeoutSeconds seconds: $($processIds -join ', ')"
    }
}

function Wait-For-PortListening {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $processIds = Get-ListeningPids -Port $Port
        if ($processIds) {
            return $processIds
        }
        Start-Sleep -Seconds 1
    }

    Write-Fail "Port $Port did not start listening within $TimeoutSeconds seconds."
}

function Stop-Port {
    param([Parameter(Mandatory = $true)][int]$Port)

    $processIds = Get-ListeningPids -Port $Port
    if ($processIds -and $env:CONFIRM_CLINIC_HOST_STOP_PORT_OWNERS -ne '1') {
        Write-Step "Refusing to stop unmanaged owners of port $Port without CONFIRM_CLINIC_HOST_STOP_PORT_OWNERS=1: $($processIds -join ', ')"
        return
    }

    foreach ($processId in $processIds) {
        try {
            taskkill /PID $processId /T /F | Out-Null
        } catch {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    Wait-For-PortFree -Port $Port
}

function Write-PidFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][int]$ProcessId
    )

    Set-Content -LiteralPath $Path -Value $ProcessId -Encoding ascii
}

function Read-PidFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    try {
        return [int](Get-Content -LiteralPath $Path -ErrorAction Stop | Select-Object -First 1)
    } catch {
        return $null
    }
}

function Stop-ManagedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $processId = Read-PidFile -Path $PidFile
    if ($processId) {
        try {
            taskkill /PID $processId /T /F | Out-Null
        } catch {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    Stop-Port -Port $Port
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Start-Backend {
    Start-BackendInstance -Port $DefaultBackendPort -PidFile $BackendPidFile -StdoutLog $BackendOutLog -StderrLog $BackendErrLog
}

function Start-Frontend {
    Start-FrontendInstance -Port $DefaultFrontendPort -PidFile $FrontendPidFile -StdoutLog $FrontendOutLog -StderrLog $FrontendErrLog -HostAddress '0.0.0.0'
}

function Start-BackendInstance {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog,
        [hashtable]$EnvOverrides = @{}
    )

    Initialize-ClinicEnv
    $python = Get-PythonExe
    $runServer = Join-Path $BackendDir 'run_server.py'
    if (-not (Test-Path -LiteralPath $runServer)) {
        Write-Fail "Missing backend entry point: $runServer"
    }

    Stop-ManagedProcess -PidFile $PidFile -Port $Port

    Invoke-WithEnvOverrides -Overrides $EnvOverrides -ScriptBlock {
        $process = Start-Process `
            -FilePath $python `
            -ArgumentList @($runServer) `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $StdoutLog `
            -RedirectStandardError $StderrLog `
            -PassThru

        Write-PidFile -Path $PidFile -ProcessId $process.Id
    }

    Wait-For-PortListening -Port $Port
}

function Start-FrontendInstance {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog,
        [string]$HostAddress = '0.0.0.0',
        [hashtable]$EnvOverrides = @{}
    )

    Initialize-ClinicEnv
    $npm = Get-NpmExe

    Stop-ManagedProcess -PidFile $PidFile -Port $Port

    Invoke-WithEnvOverrides -Overrides $EnvOverrides -ScriptBlock {
        $process = Start-Process `
            -FilePath $npm `
            -ArgumentList @('run', 'dev', '--', '--host', $HostAddress, '--port', $Port.ToString(), '--strictPort') `
            -WorkingDirectory $FrontendDir `
            -RedirectStandardOutput $StdoutLog `
            -RedirectStandardError $StderrLog `
            -PassThru

        Write-PidFile -Path $PidFile -ProcessId $process.Id
    }

    Wait-For-PortListening -Port $Port
}

function Wait-For-Health {
    Initialize-ClinicEnv
    Invoke-PythonScript -ScriptName 'health_check.py'
}

function Import-Artifact {
    param([Parameter(Mandatory = $true)][string]$Path)

    Initialize-ClinicEnv
    $output = Invoke-PythonScript -ScriptName 'import_release_artifact.py' -Arguments @('--artifact-file', $Path)
    $importedRef = ($output | Select-String '^IMPORTED_RELEASE_REF=' | ForEach-Object {
        $_.Line.Split('=', 2)[1].Trim()
    } | Select-Object -First 1)

    if (-not $importedRef) {
        Write-Fail 'Import did not report IMPORTED_RELEASE_REF.'
    }

    return $importedRef
}

function Run-Backup {
    Initialize-ClinicEnv
    Invoke-PythonScript -ScriptName 'backup_db.py'
}

function Run-Migrations {
    Initialize-ClinicEnv
    Invoke-PythonScript -ScriptName 'run_migrations.py'
}

function Run-SmokeFreshInstall {
    Initialize-ClinicEnv
    Invoke-PythonScript -ScriptName 'smoke_fresh_install.py'
}

function Run-SmokePostUpdate {
    Initialize-ClinicEnv
    Invoke-PythonScript -ScriptName 'smoke_post_update.py'
}

function Invoke-BackendUtilityScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [hashtable]$EnvOverrides = @{}
    )

    $python = Get-PythonExe
    $output = Invoke-WithEnvOverrides -Overrides $EnvOverrides -ScriptBlock {
        & $python $ScriptPath 2>&1
    }
    if ($output) {
        $output | ForEach-Object { Write-Host $_ }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Command failed: $python $ScriptPath"
    }

    return @($output)
}

function Get-DatabaseConfig {
    param([Parameter(Mandatory = $true)][string]$DatabaseUrl)

    $normalized = $DatabaseUrl -replace '^postgresql\+psycopg2://', 'postgresql://' -replace '^postgresql\+psycopg://', 'postgresql://'
    $uri = [System.Uri]$normalized
    $username = ''
    $password = ''
    if ($uri.UserInfo) {
        $parts = $uri.UserInfo.Split(':', 2)
        $username = [System.Uri]::UnescapeDataString($parts[0])
        if ($parts.Count -gt 1) {
            $password = [System.Uri]::UnescapeDataString($parts[1])
        }
    }

    [PSCustomObject]@{
        Username = $username
        Password = $password
        Database = $uri.AbsolutePath.TrimStart('/')
        Host = $uri.Host
        Port = $uri.Port
    }
}

function ConvertTo-DatabaseUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Username,
        [Parameter(Mandatory = $true)][string]$Password,
        [Parameter(Mandatory = $true)][string]$DbHost,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Database
    )

    return "postgresql+psycopg://$Username`:$Password@$DbHost`:$Port/$Database"
}

function Redact-DatabaseUrl {
    param([Parameter(Mandatory = $true)][string]$DatabaseUrl)

    $normalized = $DatabaseUrl -replace '^postgresql\+psycopg2://', 'postgresql://' -replace '^postgresql\+psycopg://', 'postgresql://'
    try {
        $uri = [System.Uri]$normalized
    } catch {
        return '<invalid-url>'
    }

    if (-not $uri.UserInfo -or $uri.UserInfo -notmatch ':') {
        return $DatabaseUrl
    }

    $username = [System.Uri]::UnescapeDataString($uri.UserInfo.Split(':', 2)[0])
    $builder = [System.UriBuilder]::new($uri)
    $builder.UserName = $username
    $builder.Password = '***'
    $builder.Host = $uri.Host
    if ($uri.Port -gt 0) {
        $builder.Port = $uri.Port
    }

    $redacted = $builder.Uri.AbsoluteUri
    if ($DatabaseUrl -match '^postgresql\+psycopg2://') {
        return $redacted -replace '^postgresql://', 'postgresql+psycopg2://'
    }
    if ($DatabaseUrl -match '^postgresql\+psycopg://') {
        return $redacted -replace '^postgresql://', 'postgresql+psycopg://'
    }
    return $redacted
}

function Escape-SqlLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return $Value.Replace("'", "''")
}

function Wait-For-PostgresInstance {
    param([Parameter(Mandatory = $true)][int]$Port)

    $psql = Get-PostgresTool -ToolName 'psql.exe'
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        & $psql -h 127.0.0.1 -p $Port -U postgres -d postgres -Atqc 'SELECT 1' *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    }

    Write-Fail "Restore PostgreSQL instance on port $Port did not become ready."
}

function Initialize-RestorePostgres {
    Initialize-ClinicEnv

    $initdb = Get-PostgresTool -ToolName 'initdb.exe'
    $pgCtl = Get-PostgresTool -ToolName 'pg_ctl.exe'
    $psql = Get-PostgresTool -ToolName 'psql.exe'
    $createdb = Get-PostgresTool -ToolName 'createdb.exe'
    $sourceDb = Get-DatabaseConfig -DatabaseUrl $env:DATABASE_URL

    New-Item -ItemType Directory -Force -Path $RestorePostgresDataDir | Out-Null

    $pgVersionFile = Join-Path $RestorePostgresDataDir 'PG_VERSION'
    if (-not (Test-Path -LiteralPath $pgVersionFile)) {
        Write-Step "Initializing isolated restore PostgreSQL cluster..."
        & $initdb -D $RestorePostgresDataDir -A trust --username=postgres --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) {
            Write-Fail 'initdb failed for isolated restore PostgreSQL cluster.'
        }
    }

    & $pgCtl -D $RestorePostgresDataDir -l $RestorePostgresLog -o "-p $RestorePostgresPort -h 127.0.0.1" -w start
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to start isolated restore PostgreSQL cluster.'
    }

    Wait-For-PostgresInstance -Port $RestorePostgresPort

    $roleName = Escape-SqlLiteral -Value $sourceDb.Username
    $rolePassword = Escape-SqlLiteral -Value $sourceDb.Password
    $restoreDbName = Escape-SqlLiteral -Value $RestoreDatabaseName

    & $psql -h 127.0.0.1 -p $RestorePostgresPort -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$roleName') THEN EXECUTE 'CREATE ROLE ""$roleName"" LOGIN PASSWORD ''$rolePassword'''; ELSE EXECUTE 'ALTER ROLE ""$roleName"" LOGIN PASSWORD ''$rolePassword'''; END IF; END `$`$;"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to ensure restore app role.'
    }

    & $psql -h 127.0.0.1 -p $RestorePostgresPort -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$restoreDbName' AND pid <> pg_backend_pid();"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to terminate active sessions on restore database.'
    }

    & $psql -h 127.0.0.1 -p $RestorePostgresPort -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ""$RestoreDatabaseName"";"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to drop existing restore database.'
    }

    & $createdb -h 127.0.0.1 -p $RestorePostgresPort -U postgres -O $sourceDb.Username $RestoreDatabaseName
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to create restore database.'
    }
}

function Stop-RestorePostgres {
    if (-not (Test-Path -LiteralPath (Join-Path $RestorePostgresDataDir 'PG_VERSION'))) {
        return
    }

    $pgCtl = Get-PostgresTool -ToolName 'pg_ctl.exe'
    & $pgCtl -D $RestorePostgresDataDir -m fast stop *> $null
}

function Start-RestoreHost {
    param([Parameter(Mandatory = $true)][string]$RestoreDatabaseUrl)

    $restoreBackendUrl = "http://127.0.0.1:$RestoreBackendPort"
    $restorePublicUrl = "http://127.0.0.1:$RestoreFrontendPort"
    $restoreWsTarget = "ws://127.0.0.1:$RestoreBackendPort"

    Start-BackendInstance `
        -Port $RestoreBackendPort `
        -PidFile $RestoreBackendPidFile `
        -StdoutLog $RestoreBackendOutLog `
        -StderrLog $RestoreBackendErrLog `
        -EnvOverrides @{
            DATABASE_URL = $RestoreDatabaseUrl
            BACKEND_PORT = $RestoreBackendPort.ToString()
            BACKEND_URL = $restoreBackendUrl
        }

    Start-FrontendInstance `
        -Port $RestoreFrontendPort `
        -PidFile $RestoreFrontendPidFile `
        -StdoutLog $RestoreFrontendOutLog `
        -StderrLog $RestoreFrontendErrLog `
        -HostAddress '127.0.0.1' `
        -EnvOverrides @{
            VITE_API_BASE_URL = $restorePublicUrl
            VITE_PROXY_TARGET = $restoreBackendUrl
            VITE_WS_PROXY_TARGET = $restoreWsTarget
        }
}

function Ensure-RestoreSmokeAdmin {
    param(
        [Parameter(Mandatory = $true)][string]$RestoreDatabaseUrl,
        [Parameter(Mandatory = $true)][string]$Username,
        [Parameter(Mandatory = $true)][string]$Password
    )

    $script = Join-Path $BackendDir 'ensure_admin_auto.py'
    if (-not (Test-Path -LiteralPath $script)) {
        Write-Fail "Missing restore smoke admin helper: $script"
    }

    Invoke-BackendUtilityScript `
        -ScriptPath $script `
        -EnvOverrides @{
            DATABASE_URL = $RestoreDatabaseUrl
            ADMIN_USERNAME = $Username
            ADMIN_PASSWORD = $Password
            ADMIN_EMAIL = 'admin@example.com'
            ADMIN_RESET_PASSWORD = '1'
            ENSURE_ADMIN_ALLOW_INITIALIZED = '1'
        }
}

function Stop-RestoreHost {
    Stop-ManagedProcess -PidFile $RestoreFrontendPidFile -Port $RestoreFrontendPort
    Stop-ManagedProcess -PidFile $RestoreBackendPidFile -Port $RestoreBackendPort
}

function Invoke-RestoreRehearsal {
    Initialize-ClinicEnv

    $sourceDb = Get-DatabaseConfig -DatabaseUrl $env:DATABASE_URL
    $restoreDatabaseUrl = ConvertTo-DatabaseUrl `
        -Username $sourceDb.Username `
        -Password $sourceDb.Password `
        -DbHost '127.0.0.1' `
        -Port $RestorePostgresPort `
        -Database $RestoreDatabaseName
    $restoreBackendUrl = "http://127.0.0.1:$RestoreBackendPort"
    $restorePublicUrl = "http://127.0.0.1:$RestoreFrontendPort"
    $smokeLoginUsername = if ($env:SMOKE_LOGIN_USERNAME) { $env:SMOKE_LOGIN_USERNAME } elseif ($env:SETUP_ADMIN_USERNAME) { $env:SETUP_ADMIN_USERNAME } else { $null }
    $smokeLoginPassword = if ($env:SMOKE_LOGIN_PASSWORD) { $env:SMOKE_LOGIN_PASSWORD } elseif ($env:SETUP_ADMIN_PASSWORD) { $env:SETUP_ADMIN_PASSWORD } else { $null }
    if (-not $smokeLoginUsername) {
        Write-Fail 'Set SMOKE_LOGIN_USERNAME or SETUP_ADMIN_USERNAME before restore smoke admin seeding.'
    }
    if (-not $smokeLoginPassword) {
        Write-Fail 'Set SMOKE_LOGIN_PASSWORD or SETUP_ADMIN_PASSWORD before restore smoke admin seeding.'
    }

    Write-Step 'Preparing isolated restore target...'
    Initialize-RestorePostgres

    $backupOutput = Invoke-PythonScript -ScriptName 'backup_db.py'
    $backupFile = ($backupOutput | Select-String '^BACKUP_FILE=' | ForEach-Object {
        $_.Line.Split('=', 2)[1].Trim()
    } | Select-Object -First 1)
    if (-not $backupFile) {
        Write-Fail 'backup_db.py did not report BACKUP_FILE.'
    }

    Write-Step 'Restoring backup into isolated restore target...'
    Invoke-PythonScript `
        -ScriptName 'restore_db.py' `
        -EnvOverrides @{
            BACKUP_FILE = $backupFile
            RESTORE_DATABASE_URL = $restoreDatabaseUrl
        }

    Write-Step 'Seeding restore login for isolated smoke...'
    Ensure-RestoreSmokeAdmin `
        -RestoreDatabaseUrl $restoreDatabaseUrl `
        -Username $smokeLoginUsername `
        -Password $smokeLoginPassword

    Write-Step 'Starting isolated restore contour...'
    Start-RestoreHost -RestoreDatabaseUrl $restoreDatabaseUrl

    try {
        Invoke-PythonScript `
            -ScriptName 'health_check.py' `
            -EnvOverrides @{
                BACKEND_URL = $restoreBackendUrl
                PUBLIC_URL = $restorePublicUrl
                CLINIC_AUTO_DETECT_PUBLIC_URL = '0'
                EXPECTED_SETUP_INITIALIZED = '1'
            }

        Invoke-PythonScript `
            -ScriptName 'smoke_post_update.py' `
            -EnvOverrides @{
                BACKEND_URL = $restoreBackendUrl
                PUBLIC_URL = $restorePublicUrl
                CLINIC_AUTO_DETECT_PUBLIC_URL = '0'
                EXPECTED_SETUP_INITIALIZED = '1'
                SMOKE_REQUIRE_LOGIN = '1'
                SMOKE_LOGIN_USERNAME = $smokeLoginUsername
                SMOKE_LOGIN_PASSWORD = $smokeLoginPassword
                FRONTEND_RUNTIME_PROBE_GOTO_TIMEOUT_MS = '90000'
                FRONTEND_RUNTIME_PROBE_READY_TIMEOUT_MS = '30000'
            }
    } finally {
        Stop-RestoreHost
        Stop-RestorePostgres
    }

    Write-Host "RESTORE_BACKUP_FILE=$backupFile"
    Write-Host "RESTORE_DATABASE_URL=$(Redact-DatabaseUrl -DatabaseUrl $restoreDatabaseUrl)"
    Write-Host "RESTORE_BACKEND_URL=$restoreBackendUrl"
    Write-Host "RESTORE_PUBLIC_URL=$restorePublicUrl"
    Write-Ok 'PASS: restore_rehearsal completed successfully'
}

function Get-GitHead {
    $head = git -C $RepoRoot rev-parse HEAD
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Failed to resolve git HEAD.'
    }
    return $head.Trim()
}

function Test-GitTrackedChanges {
    git -C $RepoRoot diff --quiet *> $null
    $worktreeDirty = $LASTEXITCODE -ne 0
    git -C $RepoRoot diff --cached --quiet *> $null
    $indexDirty = $LASTEXITCODE -ne 0
    return ($worktreeDirty -or $indexDirty)
}

function Assert-SafeForceCheckout {
    param([Parameter(Mandatory = $true)][string]$Ref)

    if ([string]::IsNullOrWhiteSpace($Ref) -or $Ref -match '\s') {
        Write-Fail 'Refusing forced release checkout with an empty or whitespace-containing ref.'
    }

    git -C $RepoRoot rev-parse --verify --quiet "$Ref^{commit}" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Refusing forced release checkout because ref does not resolve to a commit: $Ref"
    }

    if ($env:CONFIRM_FORCE_RELEASE_CHECKOUT -eq '1') {
        return
    }

    if (Test-GitTrackedChanges) {
        Write-Fail 'Refusing forced release checkout with tracked local changes. Commit/stash the changes, or set CONFIRM_FORCE_RELEASE_CHECKOUT=1 for an intentional release operation.'
    }
}

function Switch-Release {
    param([Parameter(Mandatory = $true)][string]$Ref)

    Initialize-ClinicEnv
    Assert-SafeForceCheckout -Ref $Ref
    git -C $RepoRoot checkout --force $Ref
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to checkout $Ref"
    }
}

function Start-ClinicHost {
    Start-Backend
    Start-Frontend
    Wait-For-HostReady
}

function Wait-For-HostReady {
    param(
        [int]$TimeoutSeconds = 120,
        [int]$PollSeconds = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null

    while ((Get-Date) -lt $deadline) {
        try {
            Wait-For-Health
            return
        } catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Seconds $PollSeconds
        }
    }

    Write-Fail "Host did not become ready within $TimeoutSeconds seconds. Last error: $lastError"
}

function Stop-ClinicHost {
    Stop-ManagedProcess -PidFile $FrontendPidFile -Port $DefaultFrontendPort
    Stop-ManagedProcess -PidFile $BackendPidFile -Port $DefaultBackendPort
}

function Show-Status {
    Initialize-ClinicEnv
    Write-Info "Repo root: $RepoRoot"
    Write-Info "Backend PID: $(Read-PidFile $BackendPidFile)"
    Write-Info "Frontend PID: $(Read-PidFile $FrontendPidFile)"
    Invoke-PythonScript -ScriptName 'health_check.py'
}

function Invoke-Update {
    $baselineRef = Get-GitHead
    $rollbackTarget = if ($RollbackRef) { $RollbackRef } else { $baselineRef }
    $targetRef = $ReleaseRef

    Run-Backup

    if ($ArtifactFile) {
        $targetRef = Import-Artifact -Path $ArtifactFile
    }

    if (-not $targetRef) {
        Write-Fail 'Provide either -ArtifactFile or -ReleaseRef for update.'
    }

    Stop-ClinicHost

    try {
        Switch-Release -Ref $targetRef
        Start-ClinicHost

        if (-not $SkipMigrations) {
            Run-Migrations
        }

        Wait-For-Health
        Run-SmokePostUpdate

        Write-Ok "Update completed successfully at $targetRef"
    } catch {
        Write-Host $_ -ForegroundColor Red
        Write-Step "Rolling back to $rollbackTarget..."
        try {
            Switch-Release -Ref $rollbackTarget
            Start-ClinicHost
            if ($RunRollbackMigrations) {
                Run-Migrations
            }
        } catch {
            Write-Fail "Update failed and rollback also failed: $($_.Exception.Message)"
        }
        Write-Fail "Update failed and was rolled back to $rollbackTarget"
    }
}

Initialize-ClinicEnv

switch ($Action) {
    'start' { Start-ClinicHost }
    'stop' { Stop-ClinicHost }
    'restart' { Stop-ClinicHost; Start-ClinicHost }
    'status' { Show-Status }
    'backup' { Run-Backup }
    'import-release' {
        if (-not $ArtifactFile) {
            Write-Fail '-ArtifactFile is required for import-release.'
        }
        Import-Artifact -Path $ArtifactFile
    }
    'migrate' { Run-Migrations }
    'smoke-fresh-install' { Run-SmokeFreshInstall }
    'smoke-post-update' { Run-SmokePostUpdate }
    'restore-rehearsal' { Invoke-RestoreRehearsal }
    'update' { Invoke-Update }
    'rollback' {
        if (-not $ReleaseRef -and -not $RollbackRef) {
            Write-Fail 'Provide -ReleaseRef or -RollbackRef for rollback.'
        }
        $target = if ($RollbackRef) { $RollbackRef } else { $ReleaseRef }
        Stop-ClinicHost
        Switch-Release -Ref $target
        Start-ClinicHost
        if ($RunRollbackMigrations) {
            Run-Migrations
        }
        Wait-For-Health
        Run-SmokePostUpdate
    }
}
