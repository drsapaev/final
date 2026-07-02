[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $repoRoot 'frontend'
$backendRoot = Join-Path $repoRoot 'backend'
$docsRoot = Join-Path (Join-Path $repoRoot 'docs') 'release_gates'
$artifactRoot = Join-Path (Join-Path (Join-Path $repoRoot 'output') 'playwright') 'telegram-miniapp-release-gate'
$jsonReportPath = Join-Path $docsRoot 'telegram_mini_app_release_gate_score.json'
$backendPytestLauncher = Join-Path (Join-Path $repoRoot 'scripts') 'run_backend_pytest.ps1'
$pythonLauncher = Join-Path (Join-Path $repoRoot 'scripts') 'run_python.ps1'

$checks = New-Object System.Collections.Generic.List[object]
$p0 = New-Object System.Collections.Generic.List[string]
$p1 = New-Object System.Collections.Generic.List[string]
$p2 = New-Object System.Collections.Generic.List[string]

function Add-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Severity = 'P1',
        [string]$Detail = ''
    )

    $checks.Add([pscustomobject]@{
        name = $Name
        passed = $Passed
        severity = $Severity
        detail = $Detail
    }) | Out-Null

    if ($Passed) {
        return
    }

    switch ($Severity) {
        'P0' { $p0.Add("${Name}: $Detail") | Out-Null }
        'P1' { $p1.Add("${Name}: $Detail") | Out-Null }
        default { $p2.Add("${Name}: $Detail") | Out-Null }
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Command,
        [string]$WorkingDirectory,
        [string]$Severity = 'P1'
    )

    Push-Location $WorkingDirectory
    try {
        Write-Host "==> $Name"
        Invoke-Expression $Command
        if (-not $?) {
            throw "Command reported failure."
        }
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Command exited with code $LASTEXITCODE."
        }
        Add-CheckResult -Name $Name -Passed $true -Severity $Severity -Detail 'passed'
    }
    catch {
        Add-CheckResult -Name $Name -Passed $false -Severity $Severity -Detail $_.Exception.Message
    }
    finally {
        Pop-Location
    }
}

function Test-PathContains {
    param(
        [string]$Path,
        [string]$Pattern
    )

    if (-not (Test-Path $Path)) {
        return $false
    }

    $content = Get-Content $Path -Raw -ErrorAction SilentlyContinue
    return [bool]($content -match $Pattern)
}

Invoke-Step `
    -Name 'Backend onboarding/privacy tests' `
    -Command "& '$backendPytestLauncher' tests/unit/test_patient_onboarding_request_policy.py tests/unit/test_telemetry_onboarding_privacy.py" `
    -WorkingDirectory $repoRoot `
    -Severity 'P0'

Invoke-Step `
    -Name 'Backend OpenAPI contract test' `
    -Command "& '$backendPytestLauncher' tests/test_openapi_contract.py" `
    -WorkingDirectory $repoRoot `
    -Severity 'P0'

Invoke-Step `
    -Name 'Frontend Telegram tests' `
    -Command 'npm run test:run -- telegramManagerOnboardingRequests telegramMiniApp' `
    -WorkingDirectory $frontendRoot `
    -Severity 'P0'

Invoke-Step `
    -Name 'Frontend build' `
    -Command 'npm run build' `
    -WorkingDirectory $frontendRoot `
    -Severity 'P0'

Invoke-Step `
    -Name 'Alembic heads' `
    -Command "& '$pythonLauncher' -RequireModule alembic -m alembic heads" `
    -WorkingDirectory $backendRoot `
    -Severity 'P0'

Invoke-Step `
    -Name 'Alembic history' `
    -Command "& '$pythonLauncher' -RequireModule alembic -m alembic history" `
    -WorkingDirectory $backendRoot `
    -Severity 'P1'

if ($env:DATABASE_URL_TEST) {
    $originalDatabaseUrl = $env:DATABASE_URL
    try {
        $env:DATABASE_URL = $env:DATABASE_URL_TEST
        Invoke-Step `
            -Name 'Disposable DB alembic upgrade head' `
            -Command "& '$pythonLauncher' -RequireModule alembic -m alembic upgrade head" `
            -WorkingDirectory $backendRoot `
            -Severity 'P0'
    }
    finally {
        $env:DATABASE_URL = $originalDatabaseUrl
    }
}
else {
    Add-CheckResult -Name 'Disposable DB alembic upgrade head' -Passed $true -Severity 'P2' -Detail 'skipped: DATABASE_URL_TEST not set'
}

$requiredViewports = @(375, 768, 1280, 1920)
foreach ($viewport in $requiredViewports) {
    $files = @()
    if (Test-Path $artifactRoot) {
        $files = @(
            Get-ChildItem $artifactRoot -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match "(^|[-_])$viewport([-.]|$)" }
        )
    }
    Add-CheckResult `
        -Name "Browser QA artifacts $viewport" `
        -Passed ($files.Count -gt 0) `
        -Severity 'P1' `
        -Detail $(if ($files.Count -gt 0) { "$($files.Count) artifact(s)" } else { "missing artifacts under $artifactRoot" })
}

$telemetryFile = Join-Path (Join-Path (Join-Path (Join-Path $backendRoot 'app') 'api') 'v1') 'endpoints/telemetry.py'
$requiredEvents = @(
    'patient_onboarding_started',
    'patient_onboarding_opened',
    'patient_onboarding_submitted',
    'patient_onboarding_pending_review',
    'patient_onboarding_needs_more_info',
    'registrar_onboarding_reviewed',
    'patient_onboarding_linked_existing',
    'patient_onboarding_created_patient',
    'patient_onboarding_rejected',
    'patient_onboarding_expired'
)
$telemetryContent = if (Test-Path $telemetryFile) { Get-Content $telemetryFile -Raw } else { '' }
$missingEvents = @($requiredEvents | Where-Object { $telemetryContent -notmatch [regex]::Escape($_) })
Add-CheckResult `
    -Name 'Telemetry whitelist includes onboarding events' `
    -Passed ($missingEvents.Count -eq 0) `
    -Severity 'P0' `
    -Detail $(if ($missingEvents.Count -eq 0) { 'all required events present' } else { "missing: $($missingEvents -join ', ')" })

$privacyTargets = @((Join-Path $docsRoot 'telegram_mini_app_score_100_evidence.md'))
if (Test-Path $artifactRoot) {
    $privacyTargets += @(Get-ChildItem $artifactRoot -Recurse -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
}
$privacyLeakPatterns = @(
    'entryToken=pma_',
    'entryToken=pmo_',
    'pma_[a-z0-9_]{20,}',
    'pmo_[a-z0-9_]{20,}',
    'Traceback \(most recent call last\)',
    'AxiosError',
    'stack trace',
    '"paymentId"\s*:\s*"[0-9]+',
    '"invoiceId"\s*:\s*"[0-9]+'
)
$privacyLeaks = New-Object System.Collections.Generic.List[string]
foreach ($target in $privacyTargets) {
    if (-not (Test-Path $target)) {
        continue
    }
    $content = Get-Content $target -Raw -ErrorAction SilentlyContinue
    foreach ($pattern in $privacyLeakPatterns) {
        if ($content -match $pattern) {
            $privacyLeaks.Add("$([System.IO.Path]::GetFileName($target)) matched [$pattern]") | Out-Null
        }
    }
}
Add-CheckResult `
    -Name 'Privacy grep' `
    -Passed ($privacyLeaks.Count -eq 0) `
    -Severity 'P0' `
    -Detail $(if ($privacyLeaks.Count -eq 0) { 'no raw token or medical leakage patterns found in checked evidence files' } else { $privacyLeaks -join '; ' })

$requiredDocs = @(
    (Join-Path $docsRoot 'telegram_mini_app_operational_ux.md'),
    (Join-Path $docsRoot 'telegram_mini_app_score_100_evidence.md')
)
foreach ($doc in $requiredDocs) {
    Add-CheckResult `
        -Name "Release gate doc $(Split-Path $doc -Leaf)" `
        -Passed (Test-Path $doc) `
        -Severity 'P1' `
        -Detail $(if (Test-Path $doc) { 'present' } else { 'missing' })
}

$statementPattern = [regex]::Escape('Unknown patients can request booking, but cannot become Patients or confirmed Visits until Registrar/Admin review.')
$statementPresent = Test-PathContains -Path (Join-Path $docsRoot 'telegram_mini_app_score_100_evidence.md') -Pattern $statementPattern
Add-CheckResult `
    -Name 'Canonical unknown-patient statement' `
    -Passed $statementPresent `
    -Severity 'P1' `
    -Detail $(if ($statementPresent) { 'present' } else { 'missing from evidence doc' })

$categoryChecks = @{
    'Telegram informativity' = @('Frontend Telegram tests', 'Privacy grep', 'Release gate doc telegram_mini_app_operational_ux.md')
    'Mini App informativity' = @('Frontend Telegram tests', 'Frontend build', 'Release gate doc telegram_mini_app_score_100_evidence.md')
    'Telegram usability' = @('Backend onboarding/privacy tests', 'Frontend Telegram tests')
    'Mini App usability' = @('Frontend build', 'Browser QA artifacts 375', 'Browser QA artifacts 768', 'Browser QA artifacts 1280', 'Browser QA artifacts 1920')
    'Patient utility' = @('Backend onboarding/privacy tests', 'Telemetry whitelist includes onboarding events')
    'Staff utility' = @('Backend onboarding/privacy tests', 'Frontend Telegram tests', 'Backend OpenAPI contract test')
    'Business utility' = @('Backend onboarding/privacy tests', 'Release gate doc telegram_mini_app_score_100_evidence.md', 'Canonical unknown-patient statement')
}

$scorecard = [ordered]@{}
foreach ($category in $categoryChecks.Keys) {
    $required = $categoryChecks[$category]
    $passed = $true
    foreach ($name in $required) {
        $check = $checks | Where-Object { $_.name -eq $name } | Select-Object -First 1
        if (-not $check -or -not $check.passed) {
            $passed = $false
            break
        }
    }
    $scorecard[$category] = if ($passed) { '5/5' } else { '0/5' }
}

$allCategoriesPass = (@($scorecard.Values | Where-Object { $_ -ne '5/5' })).Count -eq 0
$finalScore = if ($allCategoriesPass -and $p0.Count -eq 0 -and $p1.Count -eq 0) { 100 } else {
    [int]((@($scorecard.Values | Where-Object { $_ -eq '5/5' })).Count / [double]$scorecard.Count * 100)
}

$report = [ordered]@{
    generatedAt = (Get-Date).ToString('o')
    scorecard = $scorecard
    finalScore = $finalScore
    privacyGate = if ((@($checks | Where-Object { $_.name -eq 'Privacy grep' -and $_.passed })).Count -gt 0) { 'Pass' } else { 'Fail' }
    p0 = @($p0)
    p1 = @($p1)
    p2 = @($p2)
    checks = $checks
}

if (-not (Test-Path $docsRoot)) {
    New-Item -ItemType Directory -Path $docsRoot -Force | Out-Null
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonReportPath

Write-Host ''
Write-Host 'Telegram + Mini App Release Gate'
Write-Host '--------------------------------'
foreach ($item in $scorecard.GetEnumerator()) {
    Write-Host ("{0}: {1}" -f $item.Key, $item.Value)
}
Write-Host ("Final score: {0}/100" -f $finalScore)
Write-Host ("Privacy Gate: {0}" -f $report.privacyGate)
Write-Host ("P0: {0}" -f $p0.Count)
Write-Host ("P1: {0}" -f $p1.Count)
Write-Host ("P2: {0}" -f $p2.Count)
Write-Host ("JSON report: {0}" -f $jsonReportPath)

if ($p0.Count -gt 0 -or $p1.Count -gt 0) {
    exit 1
}
