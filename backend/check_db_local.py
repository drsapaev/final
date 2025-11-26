#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print("🔍 Проверяем таблицы:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%queue%'")
tables = cursor.fetchall()
for table in tables:
    print(f"   ✅ Таблица: {table[0]}")

print("\n🔍 Проверяем визит ID 76:")
cursor.execute('SELECT id, patient_id, department, visit_date, status, created_at FROM visits WHERE id = 76')
visit = cursor.fetchone()
if visit:
    print(f'✅ Визит ID 76 найден в базе!')
    print(f'   Patient: {visit[1]}, Dept: {visit[2]}, Date: {visit[3]}, Status: {visit[4]}, Created: {visit[5]}')
else:
    print('❌ Визит ID 76 НЕ найден в базе!')

print('\n📋 Последние 3 визита:')
cursor.execute('SELECT id, patient_id, department, visit_date, status FROM visits ORDER BY id DESC LIMIT 3')
for v in cursor.fetchall():
    print(f'   ID: {v[0]}, Patient: {v[1]}, Dept: {v[2]}, Date: {v[3]}, Status: {v[4]}')

print('\n🎯 Записи в очередях на сегодня:')
try:
    cursor.execute("""
    SELECT oqe.id, oqe.patient_id, oqe.number, oqe.status, oqe.source, dq.queue_tag 
    FROM online_queue_entries oqe 
    JOIN daily_queues dq ON oqe.queue_id = dq.id 
    WHERE dq.day = '2025-10-01' 
    ORDER BY oqe.id DESC LIMIT 5
    """)
    for q in cursor.fetchall():
        print(f'   Entry ID: {q[0]}, Patient: {q[1]}, Number: {q[2]}, Status: {q[3]}, Source: {q[4]}, Tag: {q[5]}')
except Exception as e:
    print(f'❌ Ошибка: {e}')

conn.close()
