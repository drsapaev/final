$headers = @{
  Origin = 'http://localhost:8080'
  'Access-Control-Request-Method' = 'GET'
  'Access-Control-Request-Headers' = 'authorization,content-type'
}
try {
  $response = Invoke-WebRequest -Uri 'http://localhost:18002/api/v1/registrar/queues/today' -Method Options -Headers $headers -MaximumRedirection 0
  [ordered]@{
    status = [int]$response.StatusCode
    headers = $response.Headers
  } | ConvertTo-Json -Depth 6
} catch {
  $resp = $_.Exception.Response
  if ($resp) {
    [ordered]@{
      status = [int]$resp.StatusCode
      headers = $resp.Headers
    } | ConvertTo-Json -Depth 6
  } else {
    throw
  }
}
