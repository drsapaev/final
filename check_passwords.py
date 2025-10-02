#!/usr/bin/env python3
"""
Проверка паролей пользователей
"""

import sqlite3
import hashlib

def check_passwords():
    """Проверяем пароли пользователей"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("🔐 ПРОВЕРКА ПАРОЛЕЙ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 50)
    
    # Проверяем пользователя registrar
    cursor.execute("SELECT id, email, username, password_hash FROM users WHERE username = 'registrar'")
    registrar = cursor.fetchone()
    
    if registrar:
        print(f"👤 Пользователь registrar:")
        print(f"  ID: {registrar[0]}")
        print(f"  Email: {registrar[1]}")
        print(f"  Username: {registrar[2]}")
        print(f"  Password hash: {registrar[3][:50]}...")
        
        # Проверяем возможные пароли
        possible_passwords = ['registrar123', 'registrar', 'password', '123456']
        
        print(f"\n🔍 Проверяем возможные пароли:")
        for pwd in possible_passwords:
            # Проверяем разные алгоритмы хеширования
            md5_hash = hashlib.md5(pwd.encode()).hexdigest()
            sha1_hash = hashlib.sha1(pwd.encode()).hexdigest()
            sha256_hash = hashlib.sha256(pwd.encode()).hexdigest()
            
            print(f"  {pwd}:")
            print(f"    MD5: {md5_hash}")
            print(f"    SHA1: {sha1_hash}")
            print(f"    SHA256: {sha256_hash}")
            
            if registrar[3] == md5_hash:
                print(f"    ✅ MD5 совпадает!")
            elif registrar[3] == sha1_hash:
                print(f"    ✅ SHA1 совпадает!")
            elif registrar[3] == sha256_hash:
                print(f"    ✅ SHA256 совпадает!")
    else:
        print("❌ Пользователь registrar не найден")
    
    conn.close()

if __name__ == "__main__":
    check_passwords()
