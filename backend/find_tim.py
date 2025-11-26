import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print('=== ПОИСК ПАЦИЕНТА "Тим Галустян" ===')

# Ищем по частичному совпадению
cursor.execute('''
    SELECT id, first_name, last_name, phone, created_at 
    FROM patients 
    WHERE first_name LIKE '%Тим%' OR last_name LIKE '%Галустян%'
       OR first_name LIKE '%Tim%' OR last_name LIKE '%Galust%'
    ORDER BY id DESC
''')
patients = cursor.fetchall()

if patients:
    for p in patients:
        print(f'\nНайден пациент:')
        print(f'  ID: {p[0]}')
        print(f'  Имя: {p[1]} {p[2]}')
        print(f'  Телефон: {p[3]}')
        print(f'  Создан: {p[4]}')
        
        # Проверяем визиты
        cursor.execute('SELECT id, department, visit_date, status FROM visits WHERE patient_id = ?', (p[0],))
        visits = cursor.fetchall()
        if visits:
            print(f'  Визиты: {len(visits)}')
            for v in visits:
                print(f'    - ID: {v[0]}, Dept: {v[1]}, Date: {v[2]}, Status: {v[3]}')
        else:
            print('  Визиты: НЕТ')
else:
    print('\nПациент НЕ НАЙДЕН!')
    print('\nПоследние 10 созданных пациентов:')
    cursor.execute('SELECT id, first_name, last_name, phone, created_at FROM patients ORDER BY id DESC LIMIT 10')
    for p in cursor.fetchall():
        print(f'  ID: {p[0]}, {p[1]} {p[2]}, Tel: {p[3]}, Created: {p[4]}')

conn.close()

