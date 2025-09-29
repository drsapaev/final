import requests
import json

def test_wizard_settings_access(username, password):
    print(f"\n=== Тестируем доступ для пользователя {username} ===")
    
    # Логин
    login_data = {
        'username': username,
        'password': password,
        'grant_type': 'password'
    }
    
    response = requests.post('http://localhost:8000/api/v1/authentication/login', json=login_data)
    print(f'Статус логина: {response.status_code}')
    
    if response.status_code != 200:
        print(f'Ошибка логина: {response.text}')
        return False
    
    data = response.json()
    token = data.get('access_token') or (data.get('tokens', {}).get('access_token'))
    
    if not token:
        print('Токен не получен')
        return False
    
    # Проверяем профиль
    headers = {'Authorization': f'Bearer {token}'}
    profile_response = requests.get('http://localhost:8000/api/v1/authentication/profile', headers=headers)
    
    if profile_response.status_code == 200:
        profile = profile_response.json()
        print(f'Роль: {profile.get("role")}')
        print(f'is_superuser: {profile.get("is_superuser")}')
    else:
        print(f'Ошибка получения профиля: {profile_response.status_code}')
    
    # Тестируем wizard-settings
    settings_response = requests.get('http://localhost:8000/api/v1/admin/wizard-settings', headers=headers)
    print(f'Статус wizard-settings: {settings_response.status_code}')
    
    if settings_response.status_code == 200:
        print('✅ Доступ разрешен')
        return True
    else:
        print(f'❌ Доступ запрещен: {settings_response.text}')
        return False

# Тестируем разных пользователей
test_wizard_settings_access('admin', 'admin123')
test_wizard_settings_access('registrar', 'registrar123')
test_wizard_settings_access('doctor', 'doctor123')
