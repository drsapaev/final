#!/usr/bin/env python3
"""
Проверка записей пациентов и их кодов услуг
"""

import sqlite3

def check_patient_appointments():
    """Проверяем записи пациентов и их коды услуг"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("🔍 ПРОВЕРКА ЗАПИСЕЙ ПАЦИЕНТОВ")
    print("=" * 50)
    
    # Проверяем таблицы с записями
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%appointment%'")
    appointment_tables = cursor.fetchall()
    print(f"📋 Таблицы записей: {[t[0] for t in appointment_tables]}")
    
    # Проверяем таблицу appointments
    try:
        cursor.execute("SELECT id, patient_id, service_codes, created_at FROM appointments ORDER BY created_at DESC LIMIT 10")
        appointments = cursor.fetchall()
        print(f"\n📅 ПОСЛЕДНИЕ ЗАПИСИ ({len(appointments)} найдено):")
        for appt in appointments:
            print(f"  ID: {appt[0]}, Пациент: {appt[1]}, Коды услуг: {appt[2]}, Дата: {appt[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении записей: {e}")
    
    # Проверяем таблицу patient_appointments
    try:
        cursor.execute("SELECT id, patient_id, service_codes, created_at FROM patient_appointments ORDER BY created_at DESC LIMIT 10")
        patient_appointments = cursor.fetchall()
        print(f"\n👤 ЗАПИСИ ПАЦИЕНТОВ ({len(patient_appointments)} найдено):")
        for appt in patient_appointments:
            print(f"  ID: {appt[0]}, Пациент: {appt[1]}, Коды услуг: {appt[2]}, Дата: {appt[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении записей пациентов: {e}")
    
    # Проверяем таблицу queue_appointments
    try:
        cursor.execute("SELECT id, patient_id, service_codes, created_at FROM queue_appointments ORDER BY created_at DESC LIMIT 10")
        queue_appointments = cursor.fetchall()
        print(f"\n⏰ ЗАПИСИ В ОЧЕРЕДИ ({len(queue_appointments)} найдено):")
        for appt in queue_appointments:
            print(f"  ID: {appt[0]}, Пациент: {appt[1]}, Коды услуг: {appt[2]}, Дата: {appt[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении записей очереди: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_patient_appointments()
