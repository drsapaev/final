import requests
import json
from datetime import datetime

def check_queues_data():
    url = 'http://localhost:8000/api/v1/registrar/queues/today'
    params = {'target_date': '2025-12-01'}

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            print('=== СТРУКТУРА ДАННЫХ ОТ СЕРВЕРА ===')
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])

            if 'queues' in data and isinstance(data['queues'], list):
                print(f'\n=== КОЛИЧЕСТВО ОЧЕРЕДЕЙ: {len(data["queues"])} ===')
                for i, queue in enumerate(data['queues']):
                    specialty = queue.get('specialty', 'unknown')
                    entries_count = len(queue.get('entries', []))
                    print(f'Очередь {i+1}: {specialty}, записей: {entries_count}')
                    if queue.get('entries'):
                        for j, entry in enumerate(queue['entries'][:3]):  # Показываем первые 3 записи
                            entry_id = entry.get('id')
                            patient_id = entry.get('patient_id')
                            patient_name = entry.get('patient_name')
                            print(f'  Запись {j+1}: ID={entry_id}, patient_id={patient_id}, name={patient_name}')
        else:
            print(f'Ошибка запроса: {response.status_code}')
            print(response.text)
    except Exception as e:
        print(f'Ошибка: {e}')

if __name__ == '__main__':
    check_queues_data()
