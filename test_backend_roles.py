import requests
import sqlite3

# 1. Проверяем роли в базе данных
print("=== Роли пользователей в БД ===")
conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()
cursor.execute('SELECT id, username, email, role FROM users WHERE username IN ("cardio", "derma", "dentist", "lab")')
for row in cursor.fetchall():
    print(f'ID: {row[0]}, User: {row[1]}, Email: {row[2]}, Role: {row[3]}')
conn.close()

# 2. Пытаемся аутентифицироваться как cardio
print("\n=== Тест аутентификации cardio ===")
login_response = requests.post(
    'http://localhost:8000/api/v1/auth/minimal-login',
    json={'username': 'cardio@example.com', 'password': 'cardio123'}
)
print(f'Login status: {login_response.status_code}')

if login_response.status_code == 200:
    data = login_response.json()
    token = data['access_token']
    user = data['user']
    print(f'User ID: {user["id"]}, Role: {user["role"]}')
    
    # 3. Пытаемся получить доступ к эндпоинту
    print("\n=== Тест доступа к /api/v1/registrar/queues/today ===")
    queues_response = requests.get(
        'http://localhost:8000/api/v1/registrar/queues/today',
        headers={'Authorization': f'Bearer {token}'}
    )
    print(f'Queues status: {queues_response.status_code}')
    if queues_response.status_code != 200:
        print(f'Error: {queues_response.text}')
    else:
        print(f'Success! Received data: {queues_response.json()}')
else:
    print(f'Login failed: {login_response.text}')

