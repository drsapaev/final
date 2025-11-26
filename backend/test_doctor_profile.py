import requests
import json

login_data = {
    'username': 'doctor',
    'password': 'doctor123',
    'grant_type': 'password'
}

print('Тестируем логин с doctor...')
response = requests.post('http://localhost:8000/api/v1/authentication/login', json=login_data)
print(f'Статус логина: {response.status_code}')

if response.status_code == 200:
    data = response.json()
    token = data.get('access_token') or (data.get('tokens', {}).get('access_token'))
    
    if token:
        print('Токен получен, проверяем профиль...')
        headers = {'Authorization': f'Bearer {token}'}
        profile_response = requests.get('http://localhost:8000/api/v1/authentication/profile', headers=headers)
        print(f'Статус профиля: {profile_response.status_code}')
        
        if profile_response.status_code == 200:
            profile = profile_response.json()
            print(f'Профиль пользователя: {profile}')
            print(f'Роль: {profile.get("role")}')
            print(f'is_superuser: {profile.get("is_superuser")}')
        else:
            print(f'Ошибка профиля: {profile_response.text}')
    else:
        print('Токен не получен')
else:
    print(f'Ошибка логина: {response.text}')
