$origins = @('http://localhost:5173', 'http://localhost:4173', 'http://localhost:4174', 'http://localhost:8080', 'http://127.0.0.1:8080')
$result = @()
foreach ($origin in $origins) {
  $headers = @{
    Origin = $origin
    'Access-Control-Request-Method' = 'GET'
    'Access-Control-Request-Headers' = 'authorization,content-type'
  }
  try {
    $response = Invoke-WebRequest -Uri 'http://localhost:18002/api/v1/registrar/queues/today' -Method Options -Headers $headers -MaximumRedirection 0
    $result += [ordered]@{ origin = $origin; status = [int]$response.StatusCode; allow_origin = $response.Headers['Access-Control-Allow-Origin'] }
  } catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $result += [ordered]@{ origin = $origin; status = [int]$resp.StatusCode; allow_origin = $resp.Headers['Access-Control-Allow-Origin'] }
    } else {
      throw
    }
  }
}
$result | ConvertTo-Json -Depth 4
