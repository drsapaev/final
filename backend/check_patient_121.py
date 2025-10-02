import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print('=== ПРОВЕРКА ПАЦИЕНТА ID 121 ===')

# Проверяем пациента
cursor.execute('SELECT id, first_name, last_name, phone, created_at FROM patients WHERE id = 121')
patient = cursor.fetchone()

if patient:
    print(f'\nПациент найден:')
    print(f'  ID: {patient[0]}')
    print(f'  Имя: {patient[1]} {patient[2]}')
    print(f'  Телефон: {patient[3]}')
    print(f'  Создан: {patient[4]}')
    
    # Проверяем визиты
    cursor.execute('SELECT id, department, visit_date, visit_time, status, created_at FROM visits WHERE patient_id = 121')
    visits = cursor.fetchall()
    
    print(f'\nВизиты для пациента 121: {len(visits)}')
    if visits:
        for v in visits:
            print(f'  Visit ID: {v[0]}, Dept: {v[1]}, Date: {v[2]}, Time: {v[3]}, Status: {v[4]}, Created: {v[5]}')
    else:
        print('  ❌ ВИЗИТЫ НЕ НАЙДЕНЫ!')
else:
    print('\n❌ Пациент ID 121 НЕ НАЙДЕН!')

# Проверяем последних пациентов
print('\n=== ПОСЛЕДНИЕ 5 ПАЦИЕНТОВ ===')
cursor.execute('SELECT id, first_name, last_name, phone, created_at FROM patients ORDER BY id DESC LIMIT 5')
for p in cursor.fetchall():
    print(f'  ID: {p[0]}, {p[1]} {p[2]}, Tel: {p[3]}, Created: {p[4]}')

conn.close()

