#!/usr/bin/env python3
"""
Отладка auth endpoint
"""
from fastapi.testclient import TestClient
from app.main import app
import requests

def test_auth_debug():
    """Отладка auth endpoint"""
    print("🔍 ОТЛАДКА AUTH ENDPOINT")
    print("=" * 40)
    
    # Тест 1: TestClient (должен работать)
    print("1. Тестируем через TestClient...")
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        print(f"   TestClient статус: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ TestClient работает")
            data = response.json()
            print(f"   Токен: {data.get('access_token', 'Нет')[:50]}...")
        else:
            print(f"   ❌ TestClient: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка TestClient: {e}")
    
    # Тест 2: HTTP запрос (падает)
    print("\n2. Тестируем через HTTP запрос...")
    try:
        response = requests.post(
            "http://localhost:18000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            timeout=10
        )
        print(f"   HTTP статус: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ HTTP работает")
        else:
            print(f"   ❌ HTTP: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка HTTP: {e}")
    
    # Тест 3: Проверим, что происходит с базой данных
    print("\n3. Проверяем базу данных...")
    try:
        from app.db.session import get_db
        from sqlalchemy import text
        db = next(get_db())
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"   ✅ Пользователей в БД: {count}")
        
        # Проверим admin пользователя
        result = db.execute(text("SELECT username, role FROM users WHERE username='admin'"))
        admin = result.fetchone()
        if admin:
            print(f"   ✅ Admin найден: {admin[0]} (роль: {admin[1]})")
        else:
            print("   ❌ Admin не найден")
        
    except Exception as e:
        print(f"   ❌ Ошибка БД: {e}")

if __name__ == "__main__":
    test_auth_debug()
