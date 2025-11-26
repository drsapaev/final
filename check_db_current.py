import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Проверим количество записей на сегодня
cursor.execute('SELECT COUNT(*) FROM visits WHERE visit_date = "2025-10-01"')
today_count = cursor.fetchone()[0]
print(f'Визитов на сегодня в базе: {today_count}')

# Последние 5 записей на сегодня
cursor.execute('''
    SELECT v.id,
           (p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.middle_name, '')) as fio,
           v.created_at,
           v.department
    FROM visits v
    JOIN patients p ON v.patient_id = p.id
    WHERE v.visit_date = "2025-10-01"
    ORDER BY v.created_at DESC
    LIMIT 5
''')

rows = cursor.fetchall()
print('Последние записи на сегодня:')
for row in rows:
    print(f'ID: {row[0]} | {row[1]} | {row[2]} | {row[3]}')

conn.close()

