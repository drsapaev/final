import requests
import json

# Тест аутентификации
login_data = {'username': 'cardio@example.com', 'password': 'cardio123'}
response = requests.post('http://localhost:8000/api/v1/auth/minimal-login', json=login_data)

if response.status_code == 200:
    data = response.json()
    token = data['access_token']
    user_role = data['user']['role']
    print(f'Аутентификация успешна. Роль: {user_role}')

    # Тест доступа к очереди
    headers = {'Authorization': f'Bearer {token}'}
    queue_response = requests.get('http://localhost:8000/api/v1/registrar/queues/today', headers=headers)

    if queue_response.status_code == 200:
        print('Доступ к очереди получен! Статус: 200')
        print('Ответ сервера:', json.dumps(queue_response.json(), indent=2, ensure_ascii=False)[:500])
    else:
        print(f'Доступ запрещён. Статус: {queue_response.status_code}')
        print('Ошибка:', queue_response.text)
else:
    print(f'Аутентификация провалилась. Статус: {response.status_code}')
    print('Ответ:', response.text)
