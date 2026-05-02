#!/usr/bin/env python3
"""
Проверка структуры таблицы users
"""

import sqlite3

def check_users_structure():
    """Проверяем структуру таблицы users"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("🔍 СТРУКТУРА ТАБЛИЦЫ USERS")
    print("=" * 50)
    
    # Получаем структуру таблицы
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print("📋 Колонки таблицы users:")
    for col in columns:
        print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
    
    # Проверяем пользователя registrar
    cursor.execute("SELECT * FROM users WHERE username = 'registrar'")
    registrar = cursor.fetchone()
    
    if registrar:
        print(f"\n👤 Данные пользователя registrar:")
        for i, col in enumerate(columns):
            print(f"  {col[1]}: {registrar[i]}")
    
    conn.close()

if __name__ == "__main__":
    check_users_structure()
