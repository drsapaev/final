"""
Тест CORS для MCP API
"""
import requests
import json

def test_cors():
    """Тест CORS настроек"""
    print("🔍 Тестирование CORS настроек...")
    
    # Тест OPTIONS запроса (preflight)
    try:
        response = requests.options(
            "http://localhost:8000/api/v1/auth/minimal-login",
            headers={
                'Origin': 'http://localhost:8080',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
        )
        
        print(f"OPTIONS запрос: {response.status_code}")
        print(f"CORS заголовки:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")
        
        if response.status_code == 200:
            print("✅ CORS preflight работает")
        else:
            print(f"❌ CORS preflight ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка CORS теста: {e}")
    
    # Тест обычного запроса
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/auth/minimal-login",
            json={"username": "admin", "password": "admin"},
            headers={
                'Origin': 'http://localhost:8080',
                'Content-Type': 'application/json'
            }
        )
        
        print(f"\nPOST запрос: {response.status_code}")
        print(f"CORS заголовки:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")
        
        if response.status_code in [200, 401]:  # 401 - нормально для неверных данных
            print("✅ CORS запрос работает")
        else:
            print(f"❌ CORS запрос ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка CORS запроса: {e}")

if __name__ == "__main__":
    test_cors()
