#!/usr/bin/env python3
"""
Тестирование исправленной логики фронтенда
"""

def test_frontend_logic_fixed():
    """Тестируем исправленную логику фронтенда"""
    print("🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕННОЙ ЛОГИКИ ФРОНТЕНДА")
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
        if serviceCode.startswith('PHYSIO_'):
            return 'P'  # Физиотерапия
        if serviceCode.startswith('DERM_PROC_'):
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

    # Симулируем функцию преобразования ID в коды
    def convertServiceIdsToCodes(serviceIds, services):
        serviceCodesFromIds = []
        for serviceId in serviceIds:
            if isinstance(serviceId, str):
                serviceId = int(serviceId)
            if services and isinstance(services, dict):
                # Ищем услугу по ID во всех группах
                for groupName in services:
                    groupServices = services[groupName]
                    if isinstance(groupServices, list):
                        service = next((s for s in groupServices if s['id'] == serviceId), None)
                        if service and service.get('service_code'):
                            serviceCodesFromIds.append(service['service_code'])
                            break
        return serviceCodesFromIds

    # Тестируем различные сценарии записей
    test_appointments = [
        {
            'id': 1,
            'name': 'Запись с физиотерапией',
            'services': [100, 101],  # P01, P02
            'service_codes': [],
            'department': 'cardiology'
        },
        {
            'id': 2,
            'name': 'Запись с косметологией',
            'services': [110, 111],  # C01, C02
            'service_codes': [],
            'department': 'dermatology'
        },
        {
            'id': 3,
            'name': 'Запись с дерматологическими процедурами',
            'services': [120, 121],  # D_PROC01, D_PROC02
            'service_codes': [],
            'department': 'dermatology'
        },
        {
            'id': 4,
            'name': 'Запись с консультацией дерматолога',
            'services': [1],  # D01
            'service_codes': [],
            'department': 'dermatology'
        },
        {
            'id': 5,
            'name': 'Запись со смешанными услугами',
            'services': [100, 110, 120],  # P01, C01, D_PROC01
            'service_codes': [],
            'department': 'cardiology'
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

    print("🔍 ТЕСТИРОВАНИЕ ЗАПИСЕЙ:")
    print("-" * 40)

    for appointment in test_appointments:
        print(f"\n📋 {appointment['name']}:")
        print(f"  Услуги (ID): {appointment['services']}")

        # Преобразуем ID в коды
        serviceCodesFromIds = convertServiceIdsToCodes(appointment['services'], services_by_group)
        allServiceCodes = appointment['service_codes'] + serviceCodesFromIds

        print(f"  Коды услуг: {allServiceCodes}")

        # Проверяем распределение по вкладкам
        for dept, categories in departmentCategoryMapping.items():
            matches = any(getServiceCategoryByCode(code) in categories for code in allServiceCodes)
            if matches:
                print(f"  ✅ Попадает в вкладку '{dept}'")
            else:
                print(f"  ❌ НЕ попадает в вкладку '{dept}'")

    print(f"\n🎯 ИТОГОВАЯ ПРОВЕРКА:")
    print("-" * 30)

    # Проверяем, что процедуры правильно распределяются
    procedures_codes = ['P01', 'P02', 'P03', 'P04', 'P05', 'C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'D_PROC01', 'D_PROC02', 'D_PROC03']

    print("Процедуры должны попадать в вкладку 'procedures':")
    for code in procedures_codes:
        category = getServiceCategoryByCode(code)
        if category in ['P', 'C', 'D_PROC']:
            print(f"  ✅ {code} → {category} → procedures")
        else:
            print(f"  ❌ {code} → {category} → НЕ procedures")

    print("\nКонсультации дерматолога должны попадать в вкладку 'derma':")
    derma_codes = ['D01']
    for code in derma_codes:
        category = getServiceCategoryByCode(code)
        if category == 'D':
            print(f"  ✅ {code} → {category} → derma")
        else:
            print(f"  ❌ {code} → {category} → НЕ derma")

if __name__ == "__main__":
    test_frontend_logic_fixed()
