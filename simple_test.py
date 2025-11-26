import requests
import json

# Тест вступления в очередь
data = {
    "token": "test-token-123",
    "patient_name": "Тест Тестович", 
    "phone": "+998901234567"
}

try:
    response = requests.post(
        "http://localhost:8000/api/v1/queue/join",
        json=data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
