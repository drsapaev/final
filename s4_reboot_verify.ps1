# S4b post-reboot verification (issue #2774)
$out = "C:\final\output\s4_reboot_verification.txt"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"=== S4b reboot verification === $stamp" | Out-File $out -Encoding utf8
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
"boot time: $boot" | Out-File $out -Append -Encoding utf8

$svc = Get-Service cloudflared -ErrorAction SilentlyContinue
$svcState = if ($svc) { $svc.Status.ToString() } else { "MISSING" }
"cloudflared service: $svcState" | Out-File $out -Append -Encoding utf8

$cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
$cfProcLine = if ($cfProc) { "PID=" + $cfProc.Id } else { "MISSING" }
"cloudflared process: $cfProcLine" | Out-File $out -Append -Encoding utf8

$listen = Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue
$listenLine = if ($listen) { "YES pid=" + ($listen.OwningProcess | Select-Object -First 1) } else { "NO" }
"uvicorn port 18000 listen: $listenLine" | Out-File $out -Append -Encoding utf8

$ok = $false
$elapsed = -1
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:18000/api/v1/health" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ok = $true; $elapsed = $i * 5; break }
    } catch { }
    Start-Sleep -Seconds 5
}
"local /api/v1/health 200: $ok (after $elapsed s)" | Out-File $out -Append -Encoding utf8

$pubOk = $false
for ($i = 0; $i -lt 24; $i++) {
    try {
        $body = Invoke-WebRequest "https://api.finalclinic.fyi/api/v1/health" -UseBasicParsing -TimeoutSec 10
        if ($body.Content -match '"ok"') { $pubOk = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
"public api.finalclinic.fyi JSON ok: $pubOk" | Out-File $out -Append -Encoding utf8

$verdict = "S4b PASS"
if (-not $ok -or -not $pubOk -or ($null -eq $listen) -or ($svcState -ne "Running")) {
    $verdict = "S4b FAIL - inspect above"
}
"VERDICT: $verdict" | Out-File $out -Append -Encoding utf8
Write-Output "VERDICT: $verdict"
Get-Content $out | Select-Object -Skip 1
