import sqlite3
import json

conn = sqlite3.connect('clinic.db')
c = conn.cursor()

print('=== QueueProfiles ===')
for row in c.execute('SELECT key, queue_tags, is_active, show_on_qr_page FROM queue_profiles ORDER BY display_order'):
    key, tags_json, is_active, show_on_qr = row
    tags = json.loads(tags_json) if tags_json else []
    print(f'{key}: tags={tags}, active={is_active}, qr={show_on_qr}')

# Collect all valid tags
all_tags = set()
for row in c.execute('SELECT queue_tags FROM queue_profiles'):
    tags = json.loads(row[0]) if row[0] else []
    all_tags.update(tags)

print(f'\nВсе допустимые queue_tags: {sorted(all_tags)}')

print('\n=== Services with queue_tag ===')
services_with_tag = list(c.execute('SELECT id, name, queue_tag FROM services WHERE queue_tag IS NOT NULL AND queue_tag != ""'))
print(f'Всего: {len(services_with_tag)}')

orphans = []
for sid, name, tag in services_with_tag:
    if tag not in all_tags:
        orphans.append((sid, name, tag))
        print(f'  ⚠️ ORPHAN: "{name}" (id={sid}) -> queue_tag="{tag}" НЕ в профилях!')

if not orphans:
    print('  ✅ Все queue_tag услуг соответствуют профилям')

print('\n=== Services WITHOUT queue_tag ===')
count = c.execute('SELECT COUNT(*) FROM services WHERE queue_tag IS NULL OR queue_tag = ""').fetchone()[0]
print(f'Всего без queue_tag: {count}')

if count > 0:
    print('Примеры:')
    for row in c.execute('SELECT id, name FROM services WHERE queue_tag IS NULL OR queue_tag = "" LIMIT 10'):
        print(f'  - {row[1]} (id={row[0]})')

conn.close()
