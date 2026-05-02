import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print('=== All users with username "cardio" or ID 24 ===')
cursor.execute('SELECT id, username, email, role FROM users WHERE username="cardio" OR id=24 ORDER BY id')
for row in cursor.fetchall():
    print(f'ID: {row[0]}, User: {row[1]}, Email: {row[2]}, Role: {row[3]}')

print('\n=== Recent users (last 10) ===')
cursor.execute('SELECT id, username, email, role FROM users ORDER BY id DESC LIMIT 10')
for row in cursor.fetchall():
    print(f'ID: {row[0]}, User: {row[1]}, Email: {row[2]}, Role: {row[3]}')

conn.close()

