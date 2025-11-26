import requests
import json
import base64

def test_user_details(username, password):
    print(f"\n=== Детальная проверка пользователя {username} ===")
    
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
        return
    
    data = response.json()
    print(f'Ответ логина: {json.dumps(data, indent=2)}')
    
    token = data.get('access_token') or (data.get('tokens', {}).get('access_token'))
    
    if not token:
        print('Токен не получен')
        return
    
    # Декодируем токен для проверки содержимого
    
    try:
        # JWT токен состоит из трех частей, разделенных точками
        parts = token.split('.')
        if len(parts) >= 2:
            # Декодируем payload (вторая часть)
            payload = parts[1]
            # Добавляем padding если нужно
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded)
            print(f'Содержимое токена: {json.dumps(payload_data, indent=2)}')
    except Exception as e:
        print(f'Ошибка декодирования токена: {e}')
    
    # Проверяем профиль
    headers = {'Authorization': f'Bearer {token}'}
    profile_response = requests.get('http://localhost:8000/api/v1/authentication/profile', headers=headers)
    
    if profile_response.status_code == 200:
        profile = profile_response.json()
        print(f'Профиль пользователя: {json.dumps(profile, indent=2)}')
    else:
        print(f'Ошибка получения профиля: {profile_response.status_code}')

# Тестируем пользователя doctor
test_user_details('doctor', 'doctor123')
