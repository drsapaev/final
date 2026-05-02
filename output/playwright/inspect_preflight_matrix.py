import json
import httpx

origins = [
    'http://localhost:5173',
    'http://localhost:4173',
    'http://localhost:4174',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]
rows = []
for origin in origins:
    response = httpx.request(
        'OPTIONS',
        'http://localhost:18002/api/v1/registrar/queues/today',
        headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'authorization,content-type',
        },
    )
    rows.append({
        'origin': origin,
        'status': response.status_code,
        'allow_origin': response.headers.get('access-control-allow-origin'),
        'allow_headers': response.headers.get('access-control-allow-headers'),
    })
print(json.dumps(rows, ensure_ascii=False, indent=2))
