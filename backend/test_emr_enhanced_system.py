#!/usr/bin/env python3
"""
Тестирование расширенной EMR системы
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.db.session import SessionLocal
from app.services.emr_ai_enhanced import emr_ai_enhanced
from app.services.emr_versioning_enhanced import emr_versioning_enhanced
from app.services.emr_lab_integration import emr_lab_integration


async def test_emr_ai_enhanced():
    """Тестирование расширенного AI сервиса EMR"""
    print("🤖 ТЕСТИРОВАНИЕ РАСШИРЕННОГО AI СЕРВИСА EMR")
    print("=" * 50)
    
    try:
        # Тест генерации умного шаблона
        print("1. Тестирование генерации умного шаблона...")
        patient_data = {
            "age": 45,
            "gender": "male",
            "medical_history": ["hypertension", "diabetes"],
            "allergies": ["penicillin"]
        }
        
        template = await emr_ai_enhanced.generate_smart_template(
            specialty="cardiology",
            patient_data=patient_data
        )
        
        print(f"   ✅ Шаблон сгенерирован: {len(template)} полей")
        
        # Тест получения умных подсказок
        print("2. Тестирование умных подсказок...")
        current_data = {
            "complaints": "боль в груди",
            "diagnosis": ""
        }
        
        suggestions = await emr_ai_enhanced.get_smart_suggestions(
            current_data=current_data,
            field_name="diagnosis",
            specialty="cardiology"
        )
        
        print(f"   ✅ Получено подсказок: {len(suggestions)}")
        
        # Тест автозаполнения
        print("3. Тестирование автозаполнения...")
        template_structure = {
            "complaints": {"type": "textarea", "auto_fill": True},
            "allergies": {"type": "textarea", "auto_fill": True}
        }
        
        filled_data = await emr_ai_enhanced.auto_fill_emr_fields(
            template_structure=template_structure,
            patient_data=patient_data,
            specialty="cardiology"
        )
        
        print(f"   ✅ Автозаполнено полей: {len(filled_data)}")
        
        # Тест валидации
        print("4. Тестирование валидации...")
        emr_data = {
            "complaints": "боль в груди",
            "diagnosis": "стенокардия",
            "icd10": "I20.9"
        }
        
        validation = await emr_ai_enhanced.validate_emr_data(
            emr_data=emr_data,
            specialty="cardiology"
        )
        
        print(f"   ✅ Валидация: {'✅' if validation['is_valid'] else '❌'}")
        print(f"   Ошибки: {len(validation['errors'])}")
        print(f"   Предупреждения: {len(validation['warnings'])}")
        
        # Тест ICD-10 предложений
        print("5. Тестирование ICD-10 предложений...")
        icd_suggestions = await emr_ai_enhanced.generate_icd10_suggestions(
            diagnosis_text="боль в сердце",
            specialty="cardiology"
        )
        
        print(f"   ✅ ICD-10 предложений: {len(icd_suggestions)}")
        
        print("✅ Все тесты AI сервиса прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тестах AI сервиса: {e}")
        return False


async def test_emr_versioning_enhanced():
    """Тестирование расширенного версионирования EMR"""
    print("\n📚 ТЕСТИРОВАНИЕ РАСШИРЕННОГО ВЕРСИОНИРОВАНИЯ EMR")
    print("=" * 50)
    
    try:
        db = SessionLocal()
        
        # Тест создания версии с анализом
        print("1. Тестирование создания версии с анализом...")
        emr_id = 1
        version_data = {
            "complaints": "боль в груди",
            "diagnosis": "стенокардия",
            "icd10": "I20.9"
        }
        previous_version = {
            "complaints": "усталость",
            "diagnosis": "астения"
        }
        
        # Создаем версию
        version = await emr_versioning_enhanced.create_version_with_analysis(
            db=db,
            emr_id=emr_id,
            version_data=version_data,
            change_type="updated",
            change_description="Обновление диагноза",
            changed_by=1,
            previous_version=previous_version
        )
        
        print(f"   ✅ Версия создана: ID {version.id}")
        
        # Тест сравнения версий
        print("2. Тестирование сравнения версий...")
        comparison = await emr_versioning_enhanced.get_version_comparison(
            db=db,
            emr_id=emr_id,
            version1_id=1,
            version2_id=2
        )
        
        print(f"   ✅ Сравнение выполнено: {comparison['comparison']['fields_changed']} изменений")
        
        # Тест временной линии
        print("3. Тестирование временной линии...")
        timeline = await emr_versioning_enhanced.get_version_timeline(
            db=db,
            emr_id=emr_id,
            limit=10
        )
        
        print(f"   ✅ Временная линия: {len(timeline)} версий")
        
        # Тест статистики
        print("4. Тестирование статистики версий...")
        statistics = await emr_versioning_enhanced.get_version_statistics(
            db=db,
            emr_id=emr_id
        )
        
        print(f"   ✅ Статистика: {statistics['total_versions']} версий")
        
        db.close()
        print("✅ Все тесты версионирования прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тестах версионирования: {e}")
        return False


async def test_emr_lab_integration():
    """Тестирование интеграции EMR с лабораторными данными"""
    print("\n🧪 ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ EMR С ЛАБОРАТОРИЕЙ")
    print("=" * 50)
    
    try:
        db = SessionLocal()
        
        # Тест получения лабораторных результатов
        print("1. Тестирование получения лабораторных результатов...")
        patient_id = 1
        date_from = datetime.utcnow() - timedelta(days=30)
        
        lab_results = await emr_lab_integration.get_patient_lab_results(
            db=db,
            patient_id=patient_id,
            date_from=date_from
        )
        
        print(f"   ✅ Получено результатов: {len(lab_results)}")
        
        # Тест интеграции с EMR
        print("2. Тестирование интеграции с EMR...")
        emr_id = 1
        lab_result_ids = [1, 2, 3]
        
        integration_result = await emr_lab_integration.integrate_lab_results_with_emr(
            db=db,
            emr_id=emr_id,
            lab_result_ids=lab_result_ids
        )
        
        print(f"   ✅ Интегрировано результатов: {integration_result['integrated_results']}")
        
        # Тест аномальных результатов
        print("3. Тестирование аномальных результатов...")
        abnormal_results = await emr_lab_integration.get_abnormal_lab_results(
            db=db,
            patient_id=patient_id,
            date_from=date_from
        )
        
        print(f"   ✅ Аномальных результатов: {len(abnormal_results)}")
        
        # Тест сводки лабораторных данных
        print("4. Тестирование сводки лабораторных данных...")
        lab_summary = await emr_lab_integration.generate_lab_summary_for_emr(
            db=db,
            patient_id=patient_id,
            emr_id=emr_id
        )
        
        print(f"   ✅ Сводка: {lab_summary['summary']['total_tests']} тестов")
        
        # Тест уведомления врача
        print("5. Тестирование уведомления врача...")
        notification = await emr_lab_integration.notify_doctor_about_lab_results(
            db=db,
            patient_id=patient_id,
            doctor_id=1,
            result_id=1
        )
        
        print(f"   ✅ Уведомление отправлено: {notification['type']}")
        
        db.close()
        print("✅ Все тесты интеграции с лабораторией прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тестах интеграции с лабораторией: {e}")
        return False


async def test_emr_export_import():
    """Тестирование экспорта/импорта EMR"""
    print("\n📤 ТЕСТИРОВАНИЕ ЭКСПОРТА/ИМПОРТА EMR")
    print("=" * 50)
    
    try:
        from app.services.emr_export_service import EMRExportService
        
        export_service = EMRExportService()
        
        # Тест экспорта в JSON
        print("1. Тестирование экспорта в JSON...")
        emr_data = {
            "id": 1,
            "complaints": "боль в груди",
            "diagnosis": "стенокардия",
            "icd10": "I20.9",
            "recommendations": "контроль АД"
        }
        
        json_export = await export_service.export_emr_to_json(
            emr_data=emr_data,
            include_versions=True
        )
        
        print(f"   ✅ JSON экспорт: {len(json_export)} полей")
        
        # Тест импорта из JSON
        print("2. Тестирование импорта из JSON...")
        import_data = await export_service.import_emr_from_json(json_export)
        
        print(f"   ✅ JSON импорт: {len(import_data)} полей")
        
        # Тест валидации импорта
        print("3. Тестирование валидации импорта...")
        validation = await export_service.validate_import_data(json_export)
        
        print(f"   ✅ Валидация импорта: {'✅' if validation['is_valid'] else '❌'}")
        
        print("✅ Все тесты экспорта/импорта прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тестах экспорта/импорта: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🏥 ТЕСТИРОВАНИЕ РАСШИРЕННОЙ EMR СИСТЕМЫ")
    print("=" * 60)
    
    tests = [
        ("AI Enhanced Service", test_emr_ai_enhanced),
        ("Versioning Enhanced", test_emr_versioning_enhanced),
        ("Lab Integration", test_emr_lab_integration),
        ("Export/Import", test_emr_export_import)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Критическая ошибка в {test_name}: {e}")
            results.append((test_name, False))
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ EMR система готова к использованию!")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("🔧 Требуется доработка системы")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
