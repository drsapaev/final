"""
Тест проверки endpoint /registrar/departments
"""
import requests

BASE_URL = "http://localhost:18000"

# Тест 1: Проверка что бэкенд работает
try:
    response = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"✅ Backend is running: {response.status_code}")
except Exception as e:
    print(f"❌ Backend is NOT running: {e}")
    exit(1)

# Тест 2: Проверка endpoint без авторизации (ожидаем 401 или 403)
try:
    response = requests.get(f"{BASE_URL}/api/v1/registrar/departments")
    print(f"📊 /registrar/departments without auth: {response.status_code}")
    if response.status_code == 404:
        print("❌ ERROR: Endpoint not found! Need to restart backend.")
    elif response.status_code in [401, 403]:
        print("✅ Endpoint exists but requires auth (expected)")
    else:
        print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"❌ Request failed: {e}")

# Тест 3: Проверка других registrar endpoints
try:
    response = requests.get(f"{BASE_URL}/api/v1/registrar/services")
    print(f"📊 /registrar/services without auth: {response.status_code}")
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\n📋 Summary:")
print("If /registrar/departments returns 404 - backend needs restart")
print("If it returns 401/403 - endpoint is registered correctly")
