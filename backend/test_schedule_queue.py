#!/usr/bin/env python3
"""
Тест новых API для расписания и очереди
"""
from datetime import date, timedelta

import httpx


def test_schedule_queue_apis():
    """Тестируем новые API для расписания и очереди"""
    print("🧪 Тестируем API расписания и очереди...")
    try:
        with httpx.Client() as client:
            # 1. Логинимся как админ
            print("1. Логинимся как админ...")
            login_data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            }
            login_response = client.post(
                "http://localhost:8000/api/v1/auth/login", data=login_data, timeout=10
            )
            if login_response.status_code != 200:
                print(f"❌ Ошибка логина: {login_response.status_code}")
                print(f"   Ответ: {login_response.text}")
                return
            token_data = login_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                print("❌ В ответе нет access_token")
                return
            print(f"✅ Логин успешен, токен: {access_token[:20]}...")

            headers = {"Authorization": f"Bearer {access_token}"}

            # 2. Тестируем API расписания
            print("\n2. Тестируем API расписания...")

            # 2.1. Получаем расписание на неделю
            print("2.1. Получаем расписание на неделю...")
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_start_str = week_start.strftime("%Y-%m-%d")

            weekly_response = client.get(
                f"http://localhost:8000/api/v1/schedule/weekly?week_start={week_start_str}",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {weekly_response.status_code}")
            if weekly_response.status_code == 200:
                weekly_data = weekly_response.json()
                print(f"✅ Получено дней: {len(weekly_data)}")
                for day in weekly_data[:2]:  # Показываем первые 2 дня
                    print(
                        f"   - {day.get('weekday_name')} {day.get('date')}: {len(day.get('templates', []))} шаблонов"
                    )
            else:
                print(
                    f"❌ Ошибка получения недельного расписания: {weekly_response.text}"
                )

            # 2.2. Получаем расписание на день
            print("\n2.2. Получаем расписание на день...")
            today_str = today.strftime("%Y-%m-%d")
            daily_response = client.get(
                f"http://localhost:8000/api/v1/schedule/daily?date_str={today_str}",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {daily_response.status_code}")
            if daily_response.status_code == 200:
                daily_data = daily_response.json()
                print(f"✅ Получено расписание на {daily_data.get('date')}")
                print(f"   Шаблонов: {len(daily_data.get('templates', []))}")
                print(f"   Записей: {len(daily_data.get('appointments', []))}")
            else:
                print(f"❌ Ошибка получения дневного расписания: {daily_response.text}")

            # 2.3. Получаем доступные слоты
            print("\n2.3. Получаем доступные слоты...")
            slots_response = client.get(
                f"http://localhost:8000/api/v1/schedule/available-slots?date_str={today_str}&department=ENT",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {slots_response.status_code}")
            if slots_response.status_code == 200:
                slots_data = slots_response.json()
                print(f"✅ Найдено доступных слотов: {len(slots_data)}")
                for slot in slots_data[:3]:  # Показываем первые 3 слота
                    print(
                        f"   - {slot.get('time')}: {slot.get('available_capacity')}/{slot.get('total_capacity')} мест"
                    )
            else:
                print(f"⚠️  Получение слотов: {slots_response.status_code}")

            # 2.4. Получаем отделения
            print("\n2.4. Получаем список отделений...")
            dept_response = client.get(
                "http://localhost:8000/api/v1/schedule/departments",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {dept_response.status_code}")
            if dept_response.status_code == 200:
                dept_data = dept_response.json()
                print(f"✅ Найдено отделений: {len(dept_data)}")
                for dept in dept_data:
                    print(
                        f"   - {dept.get('department')}: {dept.get('template_count')} шаблонов"
                    )
            else:
                print(f"⚠️  Получение отделений: {dept_response.status_code}")

            # 3. Тестируем API очереди
            print("\n3. Тестируем API очереди...")

            # 3.1. Получаем статус очереди
            print("3.1. Получаем статус очереди...")
            queue_response = client.get(
                f"http://localhost:8000/api/v1/queue/status?department=ENT&date_str={today_str}",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {queue_response.status_code}")
            if queue_response.status_code == 200:
                queue_data = queue_response.json()
                print("✅ Статус очереди получен:")
                print(f"   Отделение: {queue_data.get('department')}")
                print(f"   Дата: {queue_data.get('date')}")
                print(f"   Открыта: {queue_data.get('is_open')}")
                print(f"   Ожидают: {queue_data.get('waiting')}")
                print(f"   На приеме: {queue_data.get('serving')}")
                print(f"   Завершено: {queue_data.get('done')}")
            else:
                print(f"⚠️  Получение статуса очереди: {queue_response.status_code}")

            # 3.2. Открываем очередь
            print("\n3.2. Открываем очередь...")
            open_response = client.post(
                "http://localhost:8000/api/v1/queue/open",
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"department": "ENT", "date_str": today_str, "start_number": "1"},
                timeout=10,
            )
            print(f"Статус: {open_response.status_code}")
            if open_response.status_code == 200:
                open_data = open_response.json()
                print(f"✅ Очередь открыта: {open_data.get('message')}")
            else:
                print(f"⚠️  Открытие очереди: {open_response.status_code}")

            # 3.3. Добавляем пациента в очередь
            print("\n3.3. Добавляем пациента в очередь...")
            add_response = client.post(
                "http://localhost:8000/api/v1/queue/add",
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "department": "ENT",
                    "date_str": today_str,
                    "patient_name": "Тестовый Пациент",
                    "priority": "false",
                },
                timeout=10,
            )
            print(f"Статус: {add_response.status_code}")
            if add_response.status_code == 200:
                add_data = add_response.json()
                print(f"✅ Пациент добавлен: талон #{add_data.get('ticket_number')}")
            else:
                print(f"⚠️  Добавление в очередь: {add_response.status_code}")

            # 3.4. Вызываем следующего пациента
            print("\n3.4. Вызываем следующего пациента...")
            next_response = client.post(
                "http://localhost:8000/api/v1/queue/next",
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"department": "ENT", "date_str": today_str},
                timeout=10,
            )
            print(f"Статус: {next_response.status_code}")
            if next_response.status_code == 200:
                next_data = next_response.json()
                print(f"✅ Следующий пациент вызван: {next_data.get('message')}")
            else:
                print(f"⚠️  Вызов пациента: {next_response.status_code}")

            # 3.5. Завершаем прием
            print("\n3.5. Завершаем прием...")
            complete_response = client.post(
                "http://localhost:8000/api/v1/queue/complete",
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"department": "ENT", "date_str": today_str},
                timeout=10,
            )
            print(f"Статус: {complete_response.status_code}")
            if complete_response.status_code == 200:
                complete_data = complete_response.json()
                print(f"✅ Прием завершен: {complete_data.get('message')}")
            else:
                print(f"⚠️  Завершение приема: {complete_response.status_code}")

            # 3.6. Получаем список отделений с очередями
            print("\n3.6. Получаем список отделений с очередями...")
            dept_queue_response = client.get(
                f"http://localhost:8000/api/v1/queue/departments?date_str={today_str}",
                headers=headers,
                timeout=10,
            )
            print(f"Статус: {dept_queue_response.status_code}")
            if dept_queue_response.status_code == 200:
                dept_queue_data = dept_queue_response.json()
                print(f"✅ Найдено отделений с очередями: {len(dept_queue_data)}")
                for dept in dept_queue_data:
                    print(
                        f"   - {dept.get('department')}: ожидают {dept.get('waiting')}"
                    )
            else:
                print(
                    f"⚠️  Получение отделений с очередями: {dept_queue_response.status_code}"
                )

            # 3.7. Закрываем очередь
            print("\n3.7. Закрываем очередь...")
            close_response = client.post(
                "http://localhost:8000/api/v1/queue/close",
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"department": "ENT", "date_str": today_str},
                timeout=10,
            )
            print(f"Статус: {close_response.status_code}")
            if close_response.status_code == 200:
                close_data = close_response.json()
                print(f"✅ Очередь закрыта: {close_data.get('message')}")
            else:
                print(f"⚠️  Закрытие очереди: {close_response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Тестирование API расписания и очереди...")
    print("=" * 60)
    test_schedule_queue_apis()
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
