import sqlite3
from datetime import datetime

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

today = datetime.now().date().isoformat()

# Последние 10 записей
cursor.execute('''
    SELECT v.id,
           (p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.middle_name, '')) as fio,
           v.visit_date,
           v.created_at,
           v.department,
           v.status
    FROM visits v
    JOIN patients p ON v.patient_id = p.id
    ORDER BY v.created_at DESC
    LIMIT 10
''')

rows = cursor.fetchall()
print('Последние 10 записей в базе:')
for i, row in enumerate(rows, 1):
    print(f'{i:2d}. ID: {row[0]:3d} | {row[1]:30s} | {row[2]} | {row[3]} | {row[4]} | {row[5]}')

# Количество на сегодня
cursor.execute('SELECT COUNT(*) FROM visits WHERE visit_date = ?', (today,))
today_count = cursor.fetchone()[0]
print(f'\nВсего записей на сегодня ({today}): {today_count}')

# Поиск недавних записей (после 08:52)
recent_time = '2025-10-01 08:52:00'
cursor.execute('SELECT COUNT(*) FROM visits WHERE created_at > ?', (recent_time,))
recent_count = cursor.fetchone()[0]
print(f'Записей созданных после 08:52: {recent_count}')

conn.close()

