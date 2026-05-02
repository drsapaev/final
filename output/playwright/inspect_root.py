import json
import httpx

response = httpx.get('http://localhost:18002/')
print(response.status_code)
print(response.text)
