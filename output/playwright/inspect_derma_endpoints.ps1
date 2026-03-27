$ErrorActionPreference = 'Stop'
$dermaToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyNSIsInVzZXJuYW1lIjoiZGVybWFAZXhhbXBsZS5jb20iLCJyb2xlIjoiZGVybWEiLCJpc19hY3RpdmUiOnRydWUsImlzX3N1cGVydXNlciI6ZmFsc2UsImV4cCI6MTc3NDEwMTY2MSwidHlwZSI6ImFjY2VzcyJ9.XiYK7NlbdkXYx_Vw_T75AcvZXS-eGfU4E6rKIzYx5rM'
$today = Get-Date -Format 'yyyy-MM-dd'
$headers = @{ Authorization = "Bearer $dermaToken" }
$queues = Invoke-RestMethod -Uri 'http://127.0.0.1:18002/api/v1/registrar/queues/today' -Headers $headers
$apts = Invoke-RestMethod -Uri "http://127.0.0.1:18002/api/v1/registrar/all-appointments?date_from=$today&date_to=$today&limit=500" -Headers $headers
$result = [ordered]@{
  queue_count = @($queues.queues).Count
  dermatology_queues = @($queues.queues | Where-Object { $_.specialty -eq 'dermatology' -or $_.specialty -eq 'derma' })
  all_appointments_count = @($apts.data).Count
  dermatology_appointments = @($apts.data | Where-Object { $_.department -eq 'dermatology' -or $_.specialty -eq 'dermatology' -or $_.specialty -eq 'derma' -or $_.service_codes -contains 'D01' } | Select-Object -First 10)
}
$result | ConvertTo-Json -Depth 8
