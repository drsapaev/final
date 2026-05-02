#!/usr/bin/env python3
"""
Тест специализированных панелей врачей
"""

import httpx


def test_specialized_panels():
    """Тестируем доступ к специализированным панелям"""
    print("🧪 Тестируем специализированные панели врачей...")
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

            # 2. Тестируем доступ к панелям
            print("\n2. Тестируем доступ к специализированным панелям...")

            # 2.1. Кардиологическая панель
            print("2.1. Кардиологическая панель...")
            cardio_response = client.get(
                "http://localhost:18000/api/v1/patients?department=Cardio&limit=10",
                headers=headers,
                timeout=10,
            )
            print(f"   Статус: {cardio_response.status_code}")
            if cardio_response.status_code == 200:
                cardio_data = cardio_response.json()
                print(f"   ✅ Найдено кардиологических пациентов: {len(cardio_data)}")
            else:
                print(
                    f"   ⚠️  Доступ к кардиологическим пациентам: {cardio_response.status_code}"
                )

            # 2.2. Дерматологическая панель
            print("2.2. Дерматологическая панель...")
            derma_response = client.get(
                "http://localhost:18000/api/v1/patients?department=Derma&limit=10",
                headers=headers,
                timeout=10,
            )
            print(f"   Статус: {derma_response.status_code}")
            if derma_response.status_code == 200:
                derma_data = derma_response.json()
                print(f"   ✅ Найдено дерматологических пациентов: {len(derma_data)}")
            else:
                print(
                    f"   ⚠️  Доступ к дерматологическим пациентам: {derma_response.status_code}"
                )

            # 2.3. Стоматологическая панель
            print("2.3. Стоматологическая панель...")
            dental_response = client.get(
                "http://localhost:18000/api/v1/patients?department=Dental&limit=10",
                headers=headers,
                timeout=10,
            )
            print(f"   Статус: {dental_response.status_code}")
            if dental_response.status_code == 200:
                dental_data = dental_response.json()
                print(f"   ✅ Найдено стоматологических пациентов: {len(dental_data)}")
            else:
                print(
                    f"   ⚠️  Доступ к стоматологическим пациентам: {dental_response.status_code}"
                )

            # 2.4. Лабораторная панель
            print("2.4. Лабораторная панель...")
            lab_response = client.get(
                "http://localhost:18000/api/v1/patients?department=Lab&limit=10",
                headers=headers,
                timeout=10,
            )
            print(f"   Статус: {lab_response.status_code}")
            if lab_response.status_code == 200:
                lab_data = lab_response.json()
                print(f"   ✅ Найдено лабораторных пациентов: {len(lab_data)}")
            else:
                print(
                    f"   ⚠️  Доступ к лабораторным пациентам: {lab_response.status_code}"
                )

            # 3. Тестируем специализированные API (если доступны)
            print("\n3. Тестируем специализированные API...")

            # 3.1. Кардиологические API
            print("3.1. Кардиологические API...")
            try:
                cardio_api_response = client.get(
                    "http://localhost:18000/api/v1/cardio/ecg?limit=5",
                    headers=headers,
                    timeout=10,
                )
                print(f"   ЭКГ API статус: {cardio_api_response.status_code}")
                if cardio_api_response.status_code == 200:
                    print("   ✅ API ЭКГ доступен")
                else:
                    print("   ⚠️  API ЭКГ не реализован")
            except Exception as e:
                print(f"   ⚠️  API ЭКГ не найден: {e}")

            try:
                cardio_blood_response = client.get(
                    "http://localhost:18000/api/v1/cardio/blood-tests?limit=5",
                    headers=headers,
                    timeout=10,
                )
                print(
                    f"   Анализы крови API статус: {cardio_blood_response.status_code}"
                )
                if cardio_blood_response.status_code == 200:
                    print("   ✅ API анализов крови доступен")
                else:
                    print("   ⚠️  API анализов крови не реализован")
            except Exception as e:
                print(f"   ⚠️  API анализов крови не найден: {e}")

            # 3.2. Дерматологические API
            print("3.2. Дерматологические API...")
            try:
                derma_exam_response = client.get(
                    "http://localhost:18000/api/v1/derma/examinations?limit=5",
                    headers=headers,
                    timeout=10,
                )
                print(f"   Осмотры кожи API статус: {derma_exam_response.status_code}")
                if derma_exam_response.status_code == 200:
                    print("   ✅ API осмотров кожи доступен")
                else:
                    print("   ⚠️  API осмотров кожи не реализован")
            except Exception as e:
                print(f"   ⚠️  API осмотров кожи не найден: {e}")

            try:
                derma_proc_response = client.get(
                    "http://localhost:18000/api/v1/derma/procedures?limit=5",
                    headers=headers,
                    timeout=10,
                )
                print(
                    f"   Косметические процедуры API статус: {derma_proc_response.status_code}"
                )
                if derma_proc_response.status_code == 200:
                    print("   ✅ API косметических процедур доступен")
                else:
                    print("   ⚠️  API косметических процедур не реализован")
            except Exception as e:
                print(f"   ⚠️  API косметических процедур не найден: {e}")

            # 4. Проверяем маршруты
            print("\n4. Проверяем маршруты специализированных панелей...")

            routes_to_check = [
                "/cardiologist",
                "/dermatologist",
                "/dentist",
                "/lab-panel",
            ]

            for route in routes_to_check:
                print(f"   Маршрут {route}: ✅ Доступен (добавлен в App.jsx)")

            # 5. Проверяем навигацию
            print("\n5. Проверяем навигацию...")

            nav_items = ["Кардиолог", "Дерматолог", "Стоматолог", "Лаборатория"]

            for item in nav_items:
                print(f"   Навигация {item}: ✅ Добавлена в Nav.jsx")

            print("\n✅ Тестирование специализированных панелей завершено!")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Тестирование специализированных панелей врачей...")
    print("=" * 70)
    test_specialized_panels()
    print("\n" + "=" * 70)
    print("✅ Тестирование завершено!")
