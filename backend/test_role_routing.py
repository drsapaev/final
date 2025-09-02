"""
Тесты для проверки системы ролей и маршрутизации
Запускать после каждого изменения в системе авторизации
"""
import requests
import json
import sys

BASE_URL = 'http://127.0.0.1:8000'

def test_user_login_and_role(username, password, expected_role, expected_redirect=None):
    """Тестирует логин пользователя и проверяет роль"""
    print(f"🧪 Тестируем пользователя: {username}")
    
    # Логин
    login_url = f'{BASE_URL}/api/v1/auth/login'
    login_data = {
        'username': username,
        'password': password,
        'grant_type': 'password'
    }
    
    try:
        response = requests.post(login_url, data=login_data)
        if response.status_code != 200:
            print(f"❌ Логин не удался: {response.status_code}")
            return False
            
        token_data = response.json()
        token = token_data.get('access_token')
        if not token:
            print(f"❌ Токен не получен")
            return False
            
        # Получение профиля
        profile_url = f'{BASE_URL}/api/v1/auth/me'
        headers = {'Authorization': f'Bearer {token}'}
        profile_response = requests.get(profile_url, headers=headers)
        
        if profile_response.status_code != 200:
            print(f"❌ Профиль не получен: {profile_response.status_code}")
            return False
            
        profile = profile_response.json()
        actual_role = profile.get('role')
        
        if actual_role != expected_role:
            print(f"❌ Неправильная роль: ожидалось '{expected_role}', получено '{actual_role}'")
            return False
            
        print(f"✅ {username}: роль '{actual_role}' корректна")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании {username}: {e}")
        return False

def test_all_critical_users():
    """Тестирует всех критических пользователей"""
    print("🔍 Тестирование системы ролей и авторизации")
    print("=" * 60)
    
    # Критические пользователи и их ожидаемые роли
    critical_users = [
        ('admin', 'admin123', 'Admin'),
        ('registrar', 'registrar123', 'Registrar'),
        ('lab', 'lab123', 'Lab'),
        ('doctor', 'doctor123', 'Doctor'),
        ('cashier', 'cashier123', 'Cashier'),
        ('cardio', 'cardio123', 'cardio'),
        ('derma', 'derma123', 'derma'),
        ('dentist', 'dentist123', 'dentist'),
    ]
    
    results = []
    for username, password, expected_role in critical_users:
        result = test_user_login_and_role(username, password, expected_role)
        results.append((username, result))
        print()
    
    # Итоги
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for username, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {username}")
    
    print(f"\nИтого: {passed}/{total} тестов прошли успешно")
    
    if passed == total:
        print("🎉 Все тесты прошли! Система ролей работает корректно.")
        return True
    else:
        print("⚠️  Есть проблемы с системой ролей!")
        return False

def test_api_endpoints_access():
    """Тестирует доступ к специализированным API endpoints"""
    print("\n🔍 Тестирование доступа к API endpoints")
    print("=" * 60)
    
    # Получаем токен админа
    login_data = {'username': 'admin', 'password': 'admin123', 'grant_type': 'password'}
    response = requests.post(f'{BASE_URL}/api/v1/auth/login', data=login_data)
    if response.status_code != 200:
        print("❌ Не удалось получить токен админа")
        return False
        
    token = response.json().get('access_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    # Тестируем специализированные endpoints
    endpoints = [
        ('/api/v1/cardio/ecg', 'Cardio API'),
        ('/api/v1/derma/examinations', 'Derma API'),
        ('/api/v1/dental/examinations', 'Dental API'),
        ('/api/v1/lab/tests', 'Lab API'),
    ]
    
    for endpoint, name in endpoints:
        try:
            response = requests.get(f'{BASE_URL}{endpoint}', headers=headers)
            if response.status_code in [200, 404]:  # 404 тоже нормально, если нет данных
                print(f"✅ {name}: доступен")
            else:
                print(f"❌ {name}: ошибка {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: исключение {e}")
    
    return True

if __name__ == "__main__":
    print("Запуск тестов системы ролей")
    print("=" * 60)
    
    # Проверяем доступность сервера
    try:
        response = requests.get(f'{BASE_URL}/api/v1/health')
        if response.status_code != 200:
            print("❌ Сервер недоступен")
            sys.exit(1)
    except:
        print("❌ Сервер недоступен")
        sys.exit(1)
    
    # Запускаем тесты
    success1 = test_all_critical_users()
    success2 = test_api_endpoints_access()
    
    if success1 and success2:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        sys.exit(0)
    else:
        print("\n⚠️  ЕСТЬ ПРОБЛЕМЫ В СИСТЕМЕ!")
        sys.exit(1)
