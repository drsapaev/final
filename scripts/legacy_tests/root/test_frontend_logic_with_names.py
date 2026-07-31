#!/usr/bin/env python3
"""
Тестирование исправленной логики фронтенда с названиями услуг
"""

def test_frontend_logic_with_names():
    """Тестируем исправленную логику фронтенда с названиями услуг"""
    print("🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕННОЙ ЛОГИКИ С НАЗВАНИЯМИ УСЛУГ")
    print("=" * 60)

    # Симулируем функцию getServiceCategoryByCode из фронтенда
    def getServiceCategoryByCode(serviceCode):
        if not serviceCode:
            return None

        # ЭКГ - отдельная категория (только ЭКГ)
        if serviceCode == 'ECG01' or serviceCode == 'CARD_ECG' or 'ECG' in serviceCode or 'ЭКГ' in serviceCode:
            return 'ECG'

        # ЭхоКГ - кардиология (консультации кардиолога и ЭхоКГ)
        if serviceCode == 'K11' or serviceCode == 'CARD_ECHO' or 'ECHO' in serviceCode or 'ЭхоКГ' in serviceCode:
            return 'ECHO'

        # Физиотерапия (дерматологическая) - коды P01-P05
        if serviceCode and serviceCode.startswith('P') and serviceCode[1:].isdigit():
            return 'P'

        # Дерматологические процедуры - коды D_PROC01-D_PROC04
        if serviceCode and serviceCode.startswith('D_PROC') and serviceCode[6:].isdigit():
            return 'D_PROC'

        # Косметологические процедуры - коды C01-C12
        if serviceCode and serviceCode.startswith('C') and serviceCode[1:].isdigit():
            return 'C'

        # Кардиология - коды K01, K11
        if serviceCode and serviceCode.startswith('K') and serviceCode[1:].isdigit():
            return 'K'

        # Стоматология - коды S01, S10
        if serviceCode and serviceCode.startswith('S') and serviceCode[1:].isdigit():
            return 'S'

        # Лаборатория - коды L01-L65
        if serviceCode and serviceCode.startswith('L') and serviceCode[1:].isdigit():
            return 'L'

        # Дерматология - только консультации (D01)
        if serviceCode == 'D01':
            return 'D'

        # Старый формат кодов (префиксы) - обновленный
        if serviceCode.startswith('CONS_CARD'):
            return 'K'  # Консультации кардиолога
        if serviceCode.startswith('CONS_DERM') or serviceCode.startswith('DERMA_'):
            return 'D'  # Дерматология-косметология
        if serviceCode.startswith('CONS_DENT') or serviceCode.startswith('DENT_') or serviceCode.startswith('STOM_'):
            return 'S'  # Стоматология
        if serviceCode.startswith('LAB_'):
            return 'L'  # Лаборатория
        if serviceCode.startswith('COSM_'):
            return 'C'  # Косметология
        if serviceCode.startswith('PHYSIO_') or serviceCode.startswith('PHYS_'):
            return 'P'  # Физиотерапия
        if serviceCode.startswith('DERM_PROC_') or serviceCode.startswith('DERM_'):
            return 'D_PROC'  # Дерматологические процедуры

        # Дополнительные паттерны для кардиологии
        if serviceCode.startswith('CARD_') and 'ECG' not in serviceCode:
            return 'K'

        return None

    # Симулируем данные услуг из API (services_by_group)
    services_by_group = {
        'procedures': [
            {'id': 100, 'name': 'Дарсонваль', 'service_code': 'P01', 'category_code': 'P'},
            {'id': 101, 'name': 'УФО терапия', 'service_code': 'P02', 'category_code': 'P'},
            {'id': 102, 'name': 'Диодная маска лица', 'service_code': 'P03', 'category_code': 'P'},
            {'id': 103, 'name': 'Биоптрон - светотерапия', 'service_code': 'P04', 'category_code': 'P'},
            {'id': 104, 'name': 'Эксимер лазер', 'service_code': 'P05', 'category_code': 'P'},
            {'id': 120, 'name': 'Криодеструкция бородавок', 'service_code': 'D_PROC01', 'category_code': 'D_PROC'},
            {'id': 121, 'name': 'Криодеструкция папиллом', 'service_code': 'D_PROC02', 'category_code': 'D_PROC'},
            {'id': 122, 'name': 'Мезотерапия келлоидных рубцов', 'service_code': 'D_PROC03', 'category_code': 'D_PROC'},
        ],
        'cosmetology': [
            {'id': 110, 'name': 'Плазмолифтинг лица', 'service_code': 'C01', 'category_code': 'C'},
            {'id': 111, 'name': 'Плазмолифтинг волос', 'service_code': 'C02', 'category_code': 'C'},
            {'id': 112, 'name': 'Мезотерапия', 'service_code': 'C03', 'category_code': 'C'},
            {'id': 113, 'name': 'Чистка лица', 'service_code': 'C04', 'category_code': 'C'},
            {'id': 114, 'name': 'Безоперационная блефаропластика', 'service_code': 'C05', 'category_code': 'C'},
            {'id': 115, 'name': 'Удаление жировик', 'service_code': 'C06', 'category_code': 'C'},
            {'id': 116, 'name': 'Лазерное удаление татуаж и татуировок', 'service_code': 'C07', 'category_code': 'C'},
            {'id': 117, 'name': 'Карбоновый пилинг', 'service_code': 'C08', 'category_code': 'C'},
        ],
        'dermatology': [
            {'id': 1, 'name': 'Консультация дерматолога-косметолога', 'service_code': 'D01', 'category_code': 'D'},
        ]
    }

    # Симулируем функцию преобразования услуг в коды
    def convertServicesToCodes(services, service_codes, services_data):
        # Начинаем с кодов из service_codes
        all_codes = list(service_codes) if service_codes else []

        # Преобразуем услуги в коды
        for service in services:
            found_code = None

            # Ищем услугу по ID или названию во всех группах
            for groupName in services_data:
                groupServices = services_data[groupName]
                if isinstance(groupServices, list):
                    # Сначала пробуем найти по ID (если service - число)
                    if isinstance(service, int) or (isinstance(service, str) and service.isdigit()):
                        serviceId = int(service)
                        serviceByID = next((s for s in groupServices if s['id'] == serviceId), None)
                        if serviceByID and serviceByID.get('service_code'):
                            found_code = serviceByID['service_code']
                            break

                    # Затем пробуем найти по названию
                    serviceByName = next((s for s in groupServices if s['name'] == service), None)
                    if serviceByName and serviceByName.get('service_code'):
                        found_code = serviceByName['service_code']
                        break

            if found_code:
                all_codes.append(found_code)

        return all_codes

    # Тестируем реальные данные из API
    test_appointments = [
        {
            'id': 1,
            'name': 'Запись с физиотерапией (из general)',
            'services': ['Дарсонваль', 'Биоптрон - светотерапия', 'Эксимер лазер'],
            'service_codes': ['PHYS_DARSON', 'PHYS_BIOPT', 'PHYS_EXCIM'],
            'department': 'general'
        },
        {
            'id': 2,
            'name': 'Запись с дерматологическими процедурами (из general)',
            'services': ['Криодеструкция бородавок', 'Криодеструкция папиллом', 'Мезотерапия келлоидных рубцов'],
            'service_codes': ['DERM_CRYO_WART', 'DERM_CRYO_PAP', 'DERM_MESO_SCAR'],
            'department': 'general'
        },
        {
            'id': 3,
            'name': 'Запись с косметологией (из procedures)',
            'services': ['Плазмолифтинг лица', 'Чистка лица', 'Лазерное удаление татуаж и татуировок'],
            'service_codes': ['COSM_PLASMA_FACE', 'COSM_CLEAN', 'COSM_LASER_TAT'],
            'department': 'procedures'
        },
        {
            'id': 4,
            'name': 'Запись с консультацией дерматолога (из dermatology)',
            'services': ['Консультация дерматолога-косметолога'],
            'service_codes': ['CONS_DERM'],
            'department': 'dermatology'
        },
        {
            'id': 5,
            'name': 'Запись со смешанными услугами (из dermatology)',
            'services': ['Консультация дерматолога-косметолога', 'Дарсонваль', 'Биоптрон - светотерапия', 'Диодная маска лица', 'Мезотерапия келлоидных рубцов'],
            'service_codes': ['CONS_DERM', 'PHYS_DARSON', 'PHYS_BIOPT', 'PHYS_DIODE', 'DERM_MESO_SCAR'],
            'department': 'dermatology'
        }
    ]

    departmentCategoryMapping = {
        'cardio': ['K', 'ECHO'],
        'echokg': ['ECG'],
        'derma': ['D'],
        'dental': ['S'],
        'lab': ['L'],
        'procedures': ['P', 'C', 'D_PROC']
    }

    print("🔍 ТЕСТИРОВАНИЕ ЗАПИСЕЙ С НАЗВАНИЯМИ УСЛУГ:")
    print("-" * 50)

    for appointment in test_appointments:
        print(f"\n📋 {appointment['name']}:")
        print(f"  Услуги (названия): {appointment['services']}")
        print(f"  Коды услуг (старые): {appointment['service_codes']}")

        # Преобразуем услуги в коды
        allServiceCodes = convertServicesToCodes(
            appointment['services'],
            appointment['service_codes'],
            services_by_group
        )

        print(f"  Все коды услуг: {allServiceCodes}")

        # Проверяем распределение по вкладкам
        for dept, categories in departmentCategoryMapping.items():
            matches = any(getServiceCategoryByCode(code) in categories for code in allServiceCodes)
            if matches:
                print(f"  ✅ Попадает в вкладку '{dept}'")
            else:
                print(f"  ❌ НЕ попадает в вкладку '{dept}'")

    print(f"\n🎯 ПРОВЕРКА СТАРЫХ КОДОВ:")
    print("-" * 30)

    # Проверяем старые коды из API
    old_codes = ['PHYS_DARSON', 'PHYS_BIOPT', 'PHYS_DIODE', 'PHYS_EXCIM', 'DERM_CRYO_WART', 'DERM_CRYO_PAP', 'DERM_MESO_SCAR', 'COSM_PLASMA_FACE', 'COSM_CLEAN', 'COSM_LASER_TAT', 'CONS_DERM']

    for code in old_codes:
        category = getServiceCategoryByCode(code)
        if category in ['P', 'C', 'D_PROC']:
            print(f"  ✅ {code} → {category} → procedures")
        elif category == 'D':
            print(f"  ✅ {code} → {category} → derma")
        else:
            print(f"  ❌ {code} → {category} → НЕ определено")

if __name__ == "__main__":
    test_frontend_logic_with_names()
