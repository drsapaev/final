import sqlite3
from datetime import datetime
from argon2 import PasswordHasher

# Создаем тестового пользователя
ph = PasswordHasher()
password = "test123"
hashed_password = ph.hash(password)

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Удаляем существующего тестового пользователя если есть
cursor.execute("DELETE FROM users WHERE username='test'")

# Создаем нового тестового пользователя
cursor.execute("""
    INSERT INTO users (username, email, full_name, hashed_password, role, is_active, created_at, email_verified, is_superuser)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    'test',
    'test@example.com', 
    'Test User',
    hashed_password,
    'Admin',
    1,
    datetime.now().isoformat(),
    1,
    0
))

conn.commit()
print(f"Created test user with password: {password}")

# Проверяем что пользователь создан
cursor.execute("SELECT id, username, email, role FROM users WHERE username='test'")
user = cursor.fetchone()
print(f"User created: {user}")

conn.close()

