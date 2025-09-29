import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()
cursor.execute('SELECT username, role, is_superuser FROM users WHERE username = "doctor"')
user = cursor.fetchone()
if user:
    print(f'Пользователь: {user[0]}')
    print(f'Роль: {user[1]}')
    print(f'is_superuser: {user[2]}')
else:
    print('Пользователь doctor не найден')
conn.close()
