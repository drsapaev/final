#!/usr/bin/env python3
import requests
import json

# Тестируем логин API
url = "http://localhost:8000/api/v1/auth/login"
data = {
    "username": "admin",
    "password": "admin123"
}

print("Тестируем логин API...")
print(f"URL: {url}")
print(f"Data: {data}")

try:
    response = requests.post(url, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Text: {response.text}")
    
    if response.status_code == 200:
        print("✅ Логин успешен!")
        result = response.json()
        print(f"Access Token: {result.get('access_token', 'N/A')[:20]}...")
    else:
        print("❌ Ошибка логина")
        
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")
