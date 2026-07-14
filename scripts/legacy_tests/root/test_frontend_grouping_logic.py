#!/usr/bin/env python3
"""
Тестирование новой логики группировки визитов в фронтенде
"""

def test_frontend_grouping_logic():
    """Тестируем новую логику группировки визитов"""
    print("🧪 ТЕСТИРОВАНИЕ НОВОЙ ЛОГИКИ ГРУППИРОВКИ ВИЗИТОВ")
    print("=" * 60)

    # Симулируем функцию getDepartmentByService
    def getDepartmentByService(serviceId, servicesData):
        service = next((s for s in servicesData if s['id'] == serviceId), None)

        if not service:
            return 'general'

        # ✅ ИСПРАВЛЕННЫЙ МАППИНГ - соответствует вкладкам RegistrarPanel
        mapping = {
            'K': 'cardiology',    # Кардиология → вкладка cardio
            'D': 'dermatology',   # Дерматология → вкладка derma (только консультации)
            'S': 'dentistry',     # Стоматология → вкладка dental
            'L': 'laboratory',    # Лаборатория → вкладка lab
            'P': 'procedures',    # Физиотерапия → вкладка procedures
            'C': 'procedures',    # Косметология → вкладка procedures
            'D_PROC': 'procedures', # Дерматологические процедуры → вкладка procedures
            'O': 'procedures'     # Прочие процедуры → вкладка procedures
        }

        return mapping.get(service['category_code'], 'general')

    # Симулируем функцию groupCartItemsByVisit
    def groupCartItemsByVisit(cart_items, servicesData):
        visits = {}

        for item in cart_items:
            # Определяем отделение для услуги
            department = getDepartmentByService(item['service_id'], servicesData)

            # ✅ ИСПРАВЛЕНО: Объединяем все процедуры в один визит
            # Все процедуры (P, C, D_PROC) должны быть в одном визите с department = 'procedures'
            finalDepartment = department
            if department == 'procedures':
                finalDepartment = 'procedures' # Все процедуры в одном отделе

            # Группируем по finalDepartment + doctor_id + visit_date + visit_time
            key = f"{finalDepartment}_{item.get('doctor_id', 'no_doctor')}_{item['visit_date']}_{item.get('visit_time', 'no_time')}"

            if key not in visits:
                visits[key] = {
                    'doctor_id': item.get('doctor_id'),
                    'services': [],
                    'visit_date': item['visit_date'],
                    'visit_time': item.get('visit_time'),
                    'department': finalDepartment,
                    'notes': None
                }

            visits[key]['services'].append({
                'service_id': item['service_id'],
                'quantity': item['quantity']
            })

        return list(visits.values())

    # Тестовые данные услуг
    servicesData = [
        {'id': 1, 'name': 'Консультация дерматолога-косметолога', 'category_code': 'D'},
        {'id': 100, 'name': 'Дарсонваль', 'category_code': 'P'},
        {'id': 101, 'name': 'УФО терапия', 'category_code': 'P'},
        {'id': 110, 'name': 'Плазмолифтинг лица', 'category_code': 'C'},
        {'id': 111, 'name': 'Чистка лица', 'category_code': 'C'},
        {'id': 120, 'name': 'Криодеструкция бородавок', 'category_code': 'D_PROC'},
        {'id': 121, 'name': 'Криодеструкция папиллом', 'category_code': 'D_PROC'},
    ]

    # Тестовые данные корзины (пациент выбирает разные типы процедур)
    cart_items = [
        {
            'service_id': 1,  # Консультация дерматолога
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 100,  # Дарсонваль (физиотерапия)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 101,  # УФО терапия (физиотерапия)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 110,  # Плазмолифтинг лица (косметология)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 111,  # Чистка лица (косметология)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 120,  # Криодеструкция бородавок (дерматологические процедуры)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        },
        {
            'service_id': 121,  # Криодеструкция папиллом (дерматологические процедуры)
            'quantity': 1,
            'visit_date': '2025-10-02',
            'visit_time': None,
            'doctor_id': None
        }
    ]

    print("📋 ТЕСТОВЫЕ ДАННЫЕ:")
    print("-" * 30)
    print("Услуги в корзине:")
    for item in cart_items:
        service = next((s for s in servicesData if s['id'] == item['service_id']), None)
        if service:
            department = getDepartmentByService(item['service_id'], servicesData)
            print(f"  - {service['name']} (ID: {item['service_id']}, категория: {service['category_code']}, отдел: {department})")

    print(f"\n🔍 РЕЗУЛЬТАТ ГРУППИРОВКИ:")
    print("-" * 40)

    # Тестируем группировку
    visits = groupCartItemsByVisit(cart_items, servicesData)

    print(f"Создано визитов: {len(visits)}")

    for i, visit in enumerate(visits):
        print(f"\n  Визит {i+1}:")
        print(f"    Отдел: {visit['department']}")
        print(f"    Врач: {visit['doctor_id']}")
        print(f"    Дата: {visit['visit_date']}")
        print(f"    Время: {visit['visit_time']}")
        print(f"    Услуги ({len(visit['services'])}):")

        for service_item in visit['services']:
            service = next((s for s in servicesData if s['id'] == service_item['service_id']), None)
            if service:
                print(f"      - {service['name']} (ID: {service_item['service_id']}, категория: {service['category_code']})")

    # Проверяем результат
    print(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТА:")
    print("-" * 30)

    departments = {}
    for visit in visits:
        dept = visit['department']
        if dept not in departments:
            departments[dept] = 0
        departments[dept] += len(visit['services'])

    for dept, count in departments.items():
        print(f"  {dept}: {count} услуг")

    # Проверяем, что все процедуры в одном визите
    procedures_visits = [v for v in visits if v['department'] == 'procedures']
    if len(procedures_visits) == 1:
        print(f"\n✅ УСПЕХ! Все процедуры объединены в одном визите!")
        print(f"   Процедур в визите: {len(procedures_visits[0]['services'])}")
    else:
        print(f"\n❌ ПРОБЛЕМА! Процедуры разделены на {len(procedures_visits)} визитов")

    # Проверяем, что консультации дерматолога в отдельном визите
    derma_visits = [v for v in visits if v['department'] == 'dermatology']
    if len(derma_visits) == 1:
        print(f"✅ Консультации дерматолога в отдельном визите!")
    else:
        print(f"❌ Проблема с консультациями дерматолога: {len(derma_visits)} визитов")

if __name__ == "__main__":
    test_frontend_grouping_logic()
