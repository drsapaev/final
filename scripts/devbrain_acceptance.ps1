param(
    [switch] $ShowGateOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$gateLauncher = Join-Path $repoRoot "ai\langgraph\scripts\run_agent_gate.ps1"

if (-not (Test-Path -LiteralPath $gateLauncher)) {
    throw "DevBrain gate launcher not found: $gateLauncher"
}

$regexOptions = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor
    [System.Text.RegularExpressions.RegexOptions]::Multiline

function Test-Text {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Text,
        [Parameter(Mandatory = $true)]
        [string] $Pattern
    )

    return [regex]::IsMatch($Text, $Pattern, $regexOptions)
}

function Get-GateSection {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Text,
        [Parameter(Mandatory = $true)]
        [string] $Header
    )

    $escaped = [regex]::Escape($Header)
    $match = [regex]::Match(
        $Text,
        "(?s)(?:^|\r?\n)$escaped`:\s*\r?\n(?<body>.*?)(?:\r?\n\r?\n|\z)"
    )
    if ($match.Success) {
        return $match.Groups["body"].Value.Trim()
    }

    return ""
}

function Invoke-GateScenario {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Task
    )

    Push-Location $repoRoot
    try {
        $outputLines = & $gateLauncher $Task 6>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $output = ($outputLines |
        ForEach-Object { $_.ToString().TrimEnd("`r", "`n") }) -join "`n"
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
        FirstTouch = Get-GateSection -Text $output -Header "First-touch files"
        Stops = Get-GateSection -Text $output -Header "Stop conditions"
    }
}

$scenarios = @(
    [pscustomobject]@{
        Id = "migration"
        Name = "Alembic / SQLAlchemy migration"
        Task = "add Alembic revision for existing TelegramStaffLinkToken model table telegram_staff_link_tokens"
    },
    [pscustomobject]@{
        Id = "registrar-payment"
        Name = "Registrar payment/status"
        Task = "fix registrar payment status persistence ownership"
    },
    [pscustomobject]@{
        Id = "queue-identity"
        Name = "Queue identity"
        Task = "fix queue specialist id Doctor.id canonical ownership"
    },
    [pscustomobject]@{
        Id = "telegram-mixed"
        Name = "Telegram mixed contract"
        Task = "align Telegram frontend manager with backend contract"
    },
    [pscustomobject]@{
        Id = "notification-catalog"
        Name = "Notification catalog / anti-noise"
        Task = "implement notification preferences mute snooze DND runtime policy"
    }
)

function Test-ScenarioExpectations {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject] $Scenario,
        [Parameter(Mandatory = $true)]
        [pscustomobject] $Run
    )

    $fail = [System.Collections.Generic.List[string]]::new()
    $warn = [System.Collections.Generic.List[string]]::new()

    if ($Run.ExitCode -ne 0) {
        $fail.Add("gate exited with code $($Run.ExitCode)") | Out-Null
    }

    switch ($Scenario.Id) {
        "migration" {
            if (-not (Test-Text $Run.Output "Mode:\s*migration")) {
                $fail.Add("missing migration mode") | Out-Null
            }
            if (-not (Test-Text $Run.Output "DB migration ownership|SQLAlchemy model/table storage gap|storage gap")) {
                $fail.Add("missing DB/storage ownership reason") | Out-Null
            }
            if (-not (Test-Text $Run.FirstTouch "backend/alembic/versions/.*\*\.py")) {
                $fail.Add("first-touch does not allow a new Alembic revision") | Out-Null
            }
            if (Test-Text $Run.FirstTouch "TelegramManager|telegram_webhook|admin_telegram|status") {
                $fail.Add("migration first-touch appears routed to Telegram UI/status/webhook files") | Out-Null
            }
        }
        "registrar-payment" {
            if (-not (Test-Text $Run.Output "registrar")) {
                $fail.Add("missing registrar ownership signal") | Out-Null
            }
            if (-not (Test-Text $Run.Output "backend|service|persistence|billing|payment")) {
                $fail.Add("missing backend/payment persistence ownership signal") | Out-Null
            }
            if ((Test-Text $Run.Output "queue fairness|queue-time|QR") -and -not (Test-Text $Run.Output "payment|billing|registrar")) {
                $fail.Add("appears routed to queue/QR ownership without registrar payment context") | Out-Null
            }
        }
        "queue-identity" {
            if (-not (Test-Text $Run.Output "queue")) {
                $fail.Add("missing queue ownership signal") | Out-Null
            }
            if (-not (Test-Text $Run.Output "backend/app/services/queue_service\.py|backend queue|queue service")) {
                $fail.Add("missing backend queue/service ownership") | Out-Null
            }
            if (-not (Test-Text $Run.Stops "identity|specialist|doctor|canonical owner")) {
                $warn.Add("stop conditions do not explicitly name queue identity beyond generic canonical ownership") | Out-Null
            }
        }
        "telegram-mixed" {
            if (-not (Test-Text $Run.Output "Telegram mixed frontend/backend ownership|frontend/backend")) {
                $fail.Add("missing mixed frontend/backend ownership signal") | Out-Null
            }
            if (-not (Test-Text $Run.FirstTouch "frontend/src/components/TelegramManager\.jsx")) {
                $fail.Add("missing Telegram frontend manager first-touch") | Out-Null
            }
            if (-not (Test-Text $Run.FirstTouch "backend/app/api/v1/endpoints/(admin_telegram|telegram_webhook)\.py")) {
                $fail.Add("missing Telegram backend endpoint first-touch") | Out-Null
            }
            if (Test-Text $Run.Output "Mode:\s*migration") {
                $fail.Add("non-storage Telegram contract task was incorrectly routed to migration mode") | Out-Null
            }
        }
        "notification-catalog" {
            if (-not (Test-Text $Run.Output "notification|preferences|mute|snooze|DND")) {
                $fail.Add("missing notification/preferences ownership signal") | Out-Null
            }
            if (-not (Test-Text $Run.Output "platform|settings|catalog|policy|backend|service|runtime")) {
                $fail.Add("missing notification platform/settings/runtime ownership signal") | Out-Null
            }
            if ((Test-Text $Run.Output "queue|status") -and -not (Test-Text $Run.Output "notification|preferences")) {
                $fail.Add("appears routed to unrelated queue/status ownership only") | Out-Null
            }
        }
        default {
            $fail.Add("unknown scenario id: $($Scenario.Id)") | Out-Null
        }
    }

    return [pscustomobject]@{
        Fail = @($fail)
        Warn = @($warn)
    }
}

Write-Output "DevBrain Guardrail Acceptance"
Write-Output ""

$passCount = 0
$warnCount = 0
$failCount = 0

foreach ($scenario in $scenarios) {
    $run = Invoke-GateScenario -Task $scenario.Task
    $check = Test-ScenarioExpectations -Scenario $scenario -Run $run

    if ($check.Fail.Count -gt 0) {
        $status = "FAIL"
        $failCount += 1
    }
    elseif ($check.Warn.Count -gt 0) {
        $status = "WARN"
        $warnCount += 1
    }
    else {
        $status = "PASS"
        $passCount += 1
    }

    Write-Output "[$status] $($scenario.Name)"
    Write-Output "  task: $($scenario.Task)"
    Write-Output "  exit: $($run.ExitCode)"
    foreach ($reason in $check.Fail) {
        Write-Output "  fail: $reason"
    }
    foreach ($reason in $check.Warn) {
        Write-Output "  warn: $reason"
    }
    if ($ShowGateOutput) {
        Write-Output "  gate output:"
        $run.Output -split "\r?\n" | ForEach-Object { Write-Output "    $_" }
    }
    Write-Output ""
}

Write-Output "Summary:"
Write-Output "- pass: $passCount"
Write-Output "- warn: $warnCount"
Write-Output "- fail: $failCount"

if ($failCount -gt 0) {
    exit 1
}

exit 0
