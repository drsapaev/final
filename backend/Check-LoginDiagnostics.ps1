Write-Error @'
Check-LoginDiagnostics.ps1 is retired.

This legacy diagnostic used built-in login credentials and inspected a stale
local database file. Use an env-driven smoke check against the current backend
runtime instead:

  $env:SMOKE_LOGIN_USERNAME = '<username>'
  $env:SMOKE_LOGIN_PASSWORD = '<password>'
  powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 restore-rehearsal

Do not print secret-bearing connection strings or rely on legacy local database
artifacts for authentication diagnostics.
'@

exit 2
