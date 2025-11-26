#!/usr/bin/env python3
"""
Прямое тестирование сервиса аутентификации
"""
import sys
sys.path.append('.')

from app.db.session import get_db
from app.services.authentication_service import get_authentication_service
from sqlalchemy.orm import Session

def test_auth_service_direct():
    """Прямое тестирование сервиса аутентификации"""
    print("🔐 Прямое тестирование сервиса аутентификации...")
    
    try:
        # Получаем сессию базы данных
        db = next(get_db())
        print("✅ Сессия базы данных получена")
        
        # Получаем сервис аутентификации
        service = get_authentication_service()
        print("✅ Сервис аутентификации получен")
        
        # Тестируем аутентификацию
        print("\n🔍 Тестируем аутентификацию admin...")
        result = service.login_user(
            db=db,
            username="admin",
            password="admin123",
            ip_address="127.0.0.1",
            user_agent="test"
        )
        
        print(f"📊 Результат аутентификации:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Message: {result.get('message', 'N/A')}")
        print(f"   User: {result.get('user', 'N/A')}")
        print(f"   Tokens: {result.get('tokens', 'N/A')}")
        
        if result.get('success'):
            print("✅ Аутентификация работает!")
        else:
            print("❌ Аутентификация не работает")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    test_auth_service_direct()
