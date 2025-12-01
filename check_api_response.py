import requests
import json

def check_api_response():
    # Получаем данные очередей
    url = 'http://localhost:8000/api/v1/registrar/queues/today'
    params = {'target_date': '2025-12-01'}

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()

            print('=== АНАЛИЗ ДАННЫХ ОТ СЕРВЕРА ===')

            if 'queues' in data and isinstance(data['queues'], list):
                print(f'Найдено очередей: {len(data["queues"])}')

                # Ищем записи для пациентки Сапарбаева Золола
                found_entries = []

                for queue in data['queues']:
                    specialty = queue.get('specialty', 'unknown')
                    if queue.get('entries'):
                        for entry in queue['entries']:
                            patient_name = entry.get('patient_name', '')
                            if 'Сапарбаева' in patient_name or 'Золола' in patient_name:
                                found_entries.append({
                                    'specialty': specialty,
                                    'entry_id': entry.get('id'),
                                    'patient_name': patient_name,
                                    'patient_id': entry.get('patient_id'),
                                    'number': entry.get('number'),
                                    'type': entry.get('type')
                                })

                print(f'\nНайдено записей для Сапарбаевой Золола: {len(found_entries)}')

                for entry in found_entries:
                    print(f'  - Специальность: {entry["specialty"]}')
                    print(f'    ID: {entry["entry_id"]}, Patient_ID: {entry["patient_id"]}, Number: {entry["number"]}, Type: {entry["type"]}')

                # Показываем все очереди
                print('\n=== ВСЕ ОЧЕРЕДИ ===')
                for queue in data['queues']:
                    specialty = queue.get('specialty', 'unknown')
                    entries_count = len(queue.get('entries', []))
                    print(f'{specialty}: {entries_count} записей')

                    # Показываем первые записи каждой очереди
                    if queue.get('entries'):
                        for i, entry in enumerate(queue['entries'][:3]):
                            patient_name = entry.get('patient_name', 'N/A')
                            entry_id = entry.get('id')
                            patient_id = entry.get('patient_id')
                            number = entry.get('number')
                            entry_type = entry.get('type')
                            print(f'  {i+1}. {patient_name} (ID:{entry_id}, P_ID:{patient_id}, №{number}, {entry_type})')
            else:
                print('Неверная структура данных')
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        else:
            print(f'Ошибка запроса: {response.status_code}')

    except Exception as e:
        print(f'Ошибка: {e}')

if __name__ == '__main__':
    check_api_response()
