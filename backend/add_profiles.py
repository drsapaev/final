"""
Добавление новых QueueProfiles для orphan queue_tags
"""
import sqlite3
import json

conn = sqlite3.connect('clinic.db')
c = conn.cursor()

# Получаем максимальный display_order
max_order = c.execute('SELECT MAX(display_order) FROM queue_profiles').fetchone()[0] or 0

# Новые профили
new_profiles = [
    {
        'key': 'ultrasound',
        'title': 'Ultrasound',
        'title_ru': 'УЗИ',
        'queue_tags': json.dumps(['ultrason', 'ultrasound', 'uzi']),
        'department_key': None,
        'display_order': max_order + 1,
        'is_active': True,
        'show_on_qr_page': True,
        'icon': 'Activity',
        'color': '#6366F1'  # Indigo
    },
    {
        'key': 'neurology',
        'title': 'Neurology',
        'title_ru': 'Неврология',
        'queue_tags': json.dumps(['neurology', 'neuro', 'neurologist']),
        'department_key': None,
        'display_order': max_order + 2,
        'is_active': True,
        'show_on_qr_page': True,
        'icon': 'Stethoscope',
        'color': '#8B5CF6'  # Violet
    }
]

for profile in new_profiles:
    # Проверяем, существует ли уже
    existing = c.execute('SELECT key FROM queue_profiles WHERE key = ?', (profile['key'],)).fetchone()
    if existing:
        print(f"⚠️ Профиль '{profile['key']}' уже существует, пропускаем")
        continue
    
    c.execute('''
        INSERT INTO queue_profiles (key, title, title_ru, queue_tags, department_key, display_order, is_active, show_on_qr_page, icon, color)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        profile['key'],
        profile['title'],
        profile['title_ru'],
        profile['queue_tags'],
        profile['department_key'],
        profile['display_order'],
        profile['is_active'],
        profile['show_on_qr_page'],
        profile['icon'],
        profile['color']
    ))
    print(f"✅ Создан профиль: {profile['title_ru']} (key={profile['key']})")

conn.commit()

# Проверяем результат
print("\n=== Обновлённый список профилей ===")
for row in c.execute('SELECT key, title_ru, queue_tags, is_active, show_on_qr_page FROM queue_profiles ORDER BY display_order'):
    key, title, tags_json, active, qr = row
    tags = json.loads(tags_json) if tags_json else []
    status = "✅" if active else "❌"
    print(f"{status} {title} ({key}): {tags}")

conn.close()
print("\n✅ Готово!")
