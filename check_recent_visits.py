import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Ищем записи созданные после 09:18:00
cursor.execute('SELECT COUNT(*) FROM visits WHERE created_at > "2025-10-01 09:18:00"')
recent_count = cursor.fetchone()[0]
print(f'Записей созданных после 09:18:00: {recent_count}')

if recent_count > 0:
    cursor.execute('''
        SELECT v.id,
               (p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.middle_name, '')) as fio,
               v.visit_date,
               v.created_at,
               v.department,
               v.status
        FROM visits v
        JOIN patients p ON v.patient_id = p.id
        WHERE v.created_at > "2025-10-01 09:18:00"
        ORDER BY v.created_at DESC
    ''')

    rows = cursor.fetchall()
    print('Новые записи:')
    for row in rows:
        print(f'ID: {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}')

conn.close()

