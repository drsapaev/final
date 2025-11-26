#!/usr/bin/env python3
import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyZWdpc3RyYXJAZXhhbXBsZS5jb20iLCJleHAiOjE3NTkzMTg3MjV9.8UwEEuHt2Ku4YW_657xgE9yuPDe0NyKRu1Q25Epqffs"
headers = {"Authorization": f"Bearer {token}"}

print("Получаю список услуг...")
response = requests.get("http://localhost:8000/api/v1/services", headers=headers)

if response.status_code == 200:
    services = response.json()
    print(f"Всего услуг: {len(services)}")
    print("Первые 10 услуг:")
    for i, service in enumerate(services[:10]):
        service_id = service.get("id")
        code = service.get("code")
        name = service.get("name")
        print(f"{i+1}. ID: {service_id}, Code: {code}, Name: {name}")
    
    # Найдем K01
    k01_service = next((s for s in services if s.get("code") == "K01"), None)
    if k01_service:
        print(f"\nНайдена услуга K01: ID = {k01_service['id']}")
    else:
        print("\nУслуга K01 не найдена")
else:
    print(f"Ошибка получения услуг: {response.status_code} - {response.text}")
