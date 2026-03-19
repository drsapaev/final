#!/usr/bin/env python3
"""
Тест панели регистратора - управление пациентами и записями
"""
from datetime import datetime, timedelta

import httpx


def test_registrar_panel():
    """Тестируем панель регистратора"""
    print("🧪 Тестируем панель регистратора...")
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
                "http://localhost:18000/api/v1/auth/login", data=login_data, timeout=10
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

            # 2. Создаем тестового пациента
            print("\n2. Создаем тестового пациента...")
            test_patient = {
                "first_name": "Иван",
                "last_name": "Иванов",
                "middle_name": "Иванович",
                "birth_date": "1990-01-01",
                "gender": "male",
                "phone": "+998901234567",
                "doc_type": "passport",
                "doc_number": "AA1234567",
                "address": "г. Ташкент, ул. Тестовая, д. 1",
            }

            create_patient_response = client.post(
                "http://localhost:18000/api/v1/patients",
                headers={**headers, "Content-Type": "application/json"},
                json=test_patient,
                timeout=10,
            )

            if create_patient_response.status_code == 200:
                created_patient = create_patient_response.json()
                patient_id = created_patient.get("id")
                print(f"✅ Пациент создан с ID: {patient_id}")
                print(
                    f"   ФИО: {created_patient.get('last_name')} {created_patient.get('first_name')}"
                )
                print(f"   Телефон: {created_patient.get('phone')}")
            else:
                print(
                    f"❌ Ошибка создания пациента: {create_patient_response.status_code}"
                )
                print(f"   Ответ: {create_patient_response.text}")
                return

            # 3. Получаем список пациентов
            print("\n3. Получаем список пациентов...")
            patients_response = client.get(
                "http://localhost:18000/api/v1/patients", headers=headers, timeout=10
            )
            print(f"Статус: {patients_response.status_code}")
            if patients_response.status_code == 200:
                patients = patients_response.json()
                print(f"✅ Найдено пациентов: {len(patients)}")
                for patient in patients[:3]:  # Показываем первые 3
                    print(
                        f"   - {patient.get('last_name')} {patient.get('first_name')} (ID: {patient.get('id')})"
                    )
            else:
                print(f"❌ Ошибка получения пациентов: {patients_response.text}")

            # 4. Создаем тестовую запись на прием
            print(f"\n4. Создаем тестовую запись для пациента {patient_id}...")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            test_appointment = {
                "patient_id": patient_id,
                "doctor_id": 1,  # Предполагаем, что врач с ID 1 существует
                "department": "ENT",
                "appointment_date": tomorrow,
                "appointment_time": "09:00",
                "reason": "Консультация",
                "notes": "Тестовая запись",
            }

            create_appointment_response = client.post(
                "http://localhost:18000/api/v1/appointments",
                headers={**headers, "Content-Type": "application/json"},
                json=test_appointment,
                timeout=10,
            )

            if create_appointment_response.status_code == 200:
                created_appointment = create_appointment_response.json()
                appointment_id = created_appointment.get("id")
                print(f"✅ Запись создана с ID: {appointment_id}")
                print(f"   Дата: {created_appointment.get('appointment_date')}")
                print(f"   Время: {created_appointment.get('appointment_time')}")
                print(f"   Отделение: {created_appointment.get('department')}")
            else:
                print(
                    f"❌ Ошибка создания записи: {create_appointment_response.status_code}"
                )
                print(f"   Ответ: {create_appointment_response.text}")
                return

            # 5. Получаем список записей
            print("\n5. Получаем список записей...")
            appointments_response = client.get(
                "http://localhost:18000/api/v1/appointments", headers=headers, timeout=10
            )
            print(f"Статус: {appointments_response.status_code}")
            if appointments_response.status_code == 200:
                appointments = appointments_response.json()
                print(f"✅ Найдено записей: {len(appointments)}")
                for appointment in appointments[:3]:  # Показываем первые 3
                    print(
                        f"   - Запись #{appointment.get('id')} (Пациент ID: {appointment.get('patient_id')})"
                    )
            else:
                print(f"❌ Ошибка получения записей: {appointments_response.text}")

            # 6. Тестируем поиск пациентов
            print("\n6. Тестируем поиск пациентов...")
            search_response = client.get(
                "http://localhost:18000/api/v1/patients?q=Иванов",
                headers=headers,
                timeout=10,
            )
            if search_response.status_code == 200:
                search_results = search_response.json()
                print(f"✅ Поиск по 'Иванов' вернул: {len(search_results)} результатов")
            else:
                print(f"⚠️  Поиск пациентов: {search_response.status_code}")

            # 7. Получаем записи пациента
            print(f"\n7. Получаем записи пациента {patient_id}...")
            patient_appointments_response = client.get(
                f"http://localhost:18000/api/v1/patients/{patient_id}/appointments",
                headers=headers,
                timeout=10,
            )
            if patient_appointments_response.status_code == 200:
                patient_appointments = patient_appointments_response.json()
                print(
                    f"✅ У пациента {patient_id} найдено записей: {len(patient_appointments)}"
                )
            else:
                print(
                    f"⚠️  Получение записей пациента: {patient_appointments_response.status_code}"
                )

            # 8. Удаляем тестовую запись
            print(f"\n8. Удаляем тестовую запись {appointment_id}...")
            delete_appointment_response = client.delete(
                f"http://localhost:18000/api/v1/appointments/{appointment_id}",
                headers=headers,
                timeout=10,
            )
            if delete_appointment_response.status_code == 200:
                print("✅ Тестовая запись удалена")
            else:
                print(
                    f"⚠️  Ошибка удаления записи: {delete_appointment_response.status_code}"
                )

            # 9. Удаляем тестового пациента
            print(f"\n9. Удаляем тестового пациента {patient_id}...")
            delete_patient_response = client.delete(
                f"http://localhost:18000/api/v1/patients/{patient_id}",
                headers=headers,
                timeout=10,
            )
            if delete_patient_response.status_code == 200:
                print("✅ Тестовый пациент удален")
            else:
                print(
                    f"⚠️  Ошибка удаления пациента: {delete_patient_response.status_code}"
                )

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Тестирование панели регистратора...")
    print("=" * 60)
    test_registrar_panel()
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
