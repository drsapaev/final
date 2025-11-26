import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()
cursor.execute('SELECT username, role, is_superuser FROM users WHERE username LIKE "%doctor%"')
users = cursor.fetchall()
print('Пользователи с doctor в имени:')
for user in users:
    print(f'  {user[0]} - {user[1]} (superuser: {user[2]})')
conn.close()
