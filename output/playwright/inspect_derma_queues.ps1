$ErrorActionPreference = 'Stop'
$dermaToken = 'REDACTED_JWT'
$headers = @{ Authorization = "Bearer $dermaToken" }
$queues = Invoke-RestMethod -Uri 'http://127.0.0.1:18002/api/v1/registrar/queues/today' -Headers $headers
$result = [ordered]@{
  queue_count = @($queues.queues).Count
  dermatology_queues = @($queues.queues | Where-Object { $_.specialty -eq 'dermatology' -or $_.specialty -eq 'derma' })
}
$result | ConvertTo-Json -Depth 10
