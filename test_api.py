import os
import sys

import requests
token = os.environ.get("REGISTRAR_API_TOKEN")
if not token:
    print("Set REGISTRAR_API_TOKEN to a locally generated bearer token before running this smoke script.")
    sys.exit(2)

try:
    response = requests.get(
        'http://localhost:18000/api/v1/registrar/queues/today',
        headers={'Authorization': f'Bearer {token}'}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ API вернул данные: {response.status_code}")
        print(f"📊 Очередей: {len(data.get('queues', []))}")

        total_entries = 0
        for queue in data.get('queues', []):
            entries = len(queue.get('entries', []))
            total_entries += entries
            print(f"  {queue['specialty']}: {entries} записей")

        print(f"📋 Всего записей: {total_entries}")

        if total_entries > 6:
            print("✅ НОВАЯ ЗАПИСЬ ОБНАРУЖЕНА!")
        else:
            print("❌ Новая запись НЕ найдена")

    else:
        print(f"❌ Ошибка API: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Ошибка запроса: {e}")

