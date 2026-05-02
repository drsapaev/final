$ErrorActionPreference = 'Stop'
$dermaToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyNSIsInVzZXJuYW1lIjoiZGVybWFAZXhhbXBsZS5jb20iLCJyb2xlIjoiZGVybWEiLCJpc19hY3RpdmUiOnRydWUsImlzX3N1cGVydXNlciI6ZmFsc2UsImV4cCI6MTc3NDEwMTY2MSwidHlwZSI6ImFjY2VzcyJ9.XiYK7NlbdkXYx_Vw_T75AcvZXS-eGfU4E6rKIzYx5rM'
$headers = @{ Authorization = "Bearer $dermaToken" }
$queues = Invoke-RestMethod -Uri 'http://127.0.0.1:18002/api/v1/registrar/queues/today' -Headers $headers
$result = [ordered]@{
  queue_count = @($queues.queues).Count
  dermatology_queues = @($queues.queues | Where-Object { $_.specialty -eq 'dermatology' -or $_.specialty -eq 'derma' })
}
$result | ConvertTo-Json -Depth 10
