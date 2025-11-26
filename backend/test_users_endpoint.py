#!/usr/bin/env python3
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
import requests

# Создаем токен с правильным sub (username)
payload = {'sub': 'admin@example.com', 'user_id': 19, 'username': 'admin@example.com'}
token = jwt.encode({**payload, 'exp': datetime.utcnow() + timedelta(hours=1)}, settings.SECRET_KEY, algorithm=getattr(settings, 'ALGORITHM', 'HS256'))
print(f'Токен: {token[:50]}...')

headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8000/api/v1/users/users', headers=headers)
print(f'Статус: {response.status_code}')
if response.status_code == 200:
    print('✅ Успешно!')
    data = response.json()
    print(f'Пользователей: {len(data.get("users", []))}')
else:
    print(response.text)
