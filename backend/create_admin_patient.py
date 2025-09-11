#!/usr/bin/env python3
"""
Создание профиля пациента для пользователя admin
"""
import sqlite3
import os

def create_admin_patient():
    db_path = 'clinic.db'
    
    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Получаем ID пользователя admin
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        
        if not admin_user:
            print("❌ Пользователь admin не найден")
            return
        
        admin_user_id = admin_user[0]
        print(f"✅ Найден пользователь admin с ID: {admin_user_id}")
        
        # Проверяем, есть ли уже профиль пациента для admin
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (admin_user_id,))
        existing_patient = cursor.fetchone()
        
        if existing_patient:
            print("✅ Профиль пациента для admin уже существует")
        else:
            # Создаем профиль пациента для admin
            print("➕ Создаем профиль пациента для admin...")
            cursor.execute("""
                INSERT INTO patients (user_id, first_name, last_name, middle_name, birth_date, gender, phone, doc_type, doc_number, address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                admin_user_id,
                "Admin",
                "User", 
                "System",
                "1990-01-01",
                "M",
                "+7-999-000-0000",
                "passport",
                "1234567890",
                "System Address",
            ))
            
            patient_id = cursor.lastrowid
            print(f"✅ Профиль пациента создан с ID: {patient_id}")
        
        # Проверяем результат
        cursor.execute("SELECT id, user_id, first_name, last_name FROM patients WHERE user_id = ?", (admin_user_id,))
        patient = cursor.fetchone()
        
        if patient:
            print(f"✅ Профиль пациента: ID={patient[0]}, User ID={patient[1]}, Name={patient[2]} {patient[3]}")
        else:
            print("❌ Профиль пациента не найден")
        
        conn.commit()
        print("\n✅ Операция завершена успешно")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_admin_patient()
