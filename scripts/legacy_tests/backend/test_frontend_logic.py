#!/usr/bin/env python3
"""
Тестирование логики фронтенда для распределения процедур
"""

def test_frontend_logic():
    """Тестируем логику фронтенда"""
    print("🧪 ТЕСТИРОВАНИЕ ЛОГИКИ ФРОНТЕНДА")
    print("=" * 50)

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

    # Тестируем новые коды
    test_codes = [
        # Физиотерапия
        'P01', 'P02', 'P03', 'P04', 'P05',
        # Косметология
        'C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08',
        # Дерматологические процедуры
        'D_PROC01', 'D_PROC02', 'D_PROC03',
        # Дерматология (только консультации)
        'D01',
        # Старые коды (должны возвращать null или правильную категорию)
        'D10', 'D11', 'D12', 'D13', 'D14', 'D20', 'D21', 'D22'
    ]

    print("\n🔍 ТЕСТИРОВАНИЕ КОДОВ УСЛУГ:")
    print("-" * 40)

    for code in test_codes:
        category = getServiceCategoryByCode(code)
        print(f"  {code:8} → {category if category else 'null':8}")

    # Проверяем распределение по вкладкам
    print(f"\n📋 РАСПРЕДЕЛЕНИЕ ПО ВКЛАДКАМ:")
    print("-" * 40)

    departmentCategoryMapping = {
        'cardio': ['K', 'ECHO'],
        'echokg': ['ECG'],
        'derma': ['D'],
        'dental': ['S'],
        'lab': ['L'],
        'procedures': ['P', 'C', 'D_PROC']
    }

    for dept, categories in departmentCategoryMapping.items():
        print(f"\n🏷️ Вкладка '{dept}':")
        matching_codes = []
        for code in test_codes:
            category = getServiceCategoryByCode(code)
            if category in categories:
                matching_codes.append(code)

        if matching_codes:
            for code in matching_codes:
                print(f"  ✅ {code}")
        else:
            print(f"  (нет услуг)")

    print(f"\n🎯 ИТОГО для вкладки 'Процедуры':")
    procedures_codes = []
    for code in test_codes:
        category = getServiceCategoryByCode(code)
        if category in ['P', 'C', 'D_PROC']:
            procedures_codes.append(code)

    print(f"  📋 Физиотерапия (P): {len([c for c in procedures_codes if getServiceCategoryByCode(c) == 'P'])} услуг")
    print(f"  💄 Косметология (C): {len([c for c in procedures_codes if getServiceCategoryByCode(c) == 'C'])} услуг")
    print(f"  🔬 Дерматологические процедуры (D_PROC): {len([c for c in procedures_codes if getServiceCategoryByCode(c) == 'D_PROC'])} услуг")
    print(f"  🎯 ВСЕГО: {len(procedures_codes)} услуг")

if __name__ == "__main__":
    test_frontend_logic()
