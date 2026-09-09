# S4b post-reboot verification (issue #2774) — run as SYSTEM/ScheduledTask at boot
$out = "C:\final\output\s4_reboot_verification.txt"
"=== S4b reboot verification === " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") | Out-File $out -Encoding utf8
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
"boot time: $boot" | Out-File $out -Append -Encoding utf8

# 1) cloudflared service: Running + process alive
$svc = Get-Service cloudflared -ErrorAction SilentlyContinue
"cloudflared service: $($svc.Status)" | Out-File $out -Append -Encoding utf8
$proc = Get-Process cloudflared -ErrorAction SilentlyContinue
"cloudflared process: $(if ($proc) { 'PID=' + $proc.Id } else { 'MISSING' })" | Out-File $out -Append -Encoding utf8

# 2) uvicorn: port 18000 listening
$listen = Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue
"uvicorn port 18000 listen: $(if ($listen) { 'YES pid=' + ($listen.OwningProcess | Select-Object -First 1) } else { 'NO' })" | Out-File $out -Append -Encoding utf8

# 3) local API health (retry up to 5 min — autostart chain needs time)
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    $r = Invoke-WebRequest "http://127.0.0.1:18000/api/v1/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { }
  Start-Sleep -Seconds 5
}
"local /api/v1/health 200: $ok (after $($i*5)s)" | Out-File $out -Append -Encoding utf8

# 4) public API via tunnel (api.finalclinic.fyi)
$pubOk = $false
for ($i = 0; $i -lt 24; $i++) {
  try {
    $body = Invoke-WebRequest "https://api.finalclinic.fyi/api/v1/health" -UseBasicParsing -TimeoutSec 10
    if ($body.Content -match '"ok"') { $pubOk = $true; break }
  } catch { }
  Start-Sleep -Seconds 5
}
"public api.finalclinic.fyi JSON ok: $pubOk" | Out-File $out -Append -Encoding utf8

$verdict = if ($ok -and $pubOk -and ($null -ne $listen) -and ($svc.Status -eq 'Running')) { "S4b PASS" } else { "S4b FAIL — inspect above" }
"VERDICT: $verdict" | Out-File $out -Append -Encoding utf8
