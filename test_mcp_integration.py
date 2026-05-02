"""
Тестирование MCP интеграции
"""
import asyncio
import json
import sys
import os
from datetime import datetime

# Добавляем путь к backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.mcp.mcp_manager import get_mcp_manager
from backend.app.services.mcp.mcp_client import get_mcp_client


async def test_mcp_health():
    """Тест здоровья MCP системы"""
    print("\n🔍 Тестирование здоровья MCP системы...")
    
    try:
        # Получаем MCP клиент
        client = await get_mcp_client()
        
        # Проверяем здоровье
        health = await client.health_check()
        
        print(f"✅ Общее состояние: {health.get('overall', 'unknown')}")
        
        # Проверяем каждый сервер
        for server_name, status in health.get('servers', {}).items():
            status_icon = "✅" if status['status'] == 'healthy' else "❌"
            print(f"  {status_icon} {server_name}: {status['status']}")
            if 'tools_count' in status:
                print(f"      Инструментов: {status['tools_count']}")
            if 'resources_count' in status:
                print(f"      Ресурсов: {status['resources_count']}")
        
        return health.get('overall') == 'healthy'
        
    except Exception as e:
        print(f"❌ Ошибка проверки здоровья: {str(e)}")
        return False


async def test_complaint_analysis():
    """Тест анализа жалоб через MCP"""
    print("\n🔍 Тестирование анализа жалоб через MCP...")
    
    test_complaints = [
        {
            "complaint": "Болит голова уже 3 дня, особенно в области висков. Усиливается при наклоне.",
            "patient_info": {"age": 35, "gender": "female"}
        },
        {
            "complaint": "Одышка при подъеме по лестнице на 2 этаж, сердцебиение, отеки ног к вечеру.",
            "patient_info": {"age": 65, "gender": "male"}
        },
        {
            "complaint": "Высыпания на коже лица, зуд, покраснение. Появились после смены косметики.",
            "patient_info": {"age": 25, "gender": "female"}
        }
    ]
    
    try:
        client = await get_mcp_client()
        results = []
        
        for i, test_case in enumerate(test_complaints, 1):
            print(f"\n  Тест {i}: {test_case['complaint'][:50]}...")
            
            # Валидация жалобы
            validation = await client.validate_complaint(test_case['complaint'])
            print(f"    Валидация: {'✅' if validation.get('valid') else '❌'} (уверенность: {validation.get('confidence', 0)})")
            
            # Анализ жалобы
            analysis = await client.analyze_complaint(
                complaint=test_case['complaint'],
                patient_info=test_case['patient_info'],
                urgency_assessment=True
            )
            
            if analysis.get('status') == 'success':
                data = analysis.get('data', {})
                print(f"    ✅ Анализ выполнен успешно")
                
                # Проверяем результаты
                if 'data' in data:
                    result_data = data['data']
                    if 'preliminary_diagnosis' in result_data:
                        print(f"    Предварительные диагнозы: {len(result_data['preliminary_diagnosis'])}")
                    if 'urgency' in result_data:
                        print(f"    Срочность: {result_data['urgency']}")
                    if 'examinations' in result_data:
                        print(f"    Рекомендовано обследований: {len(result_data['examinations'])}")
                
                results.append({
                    'test': i,
                    'success': True,
                    'data': data
                })
            else:
                print(f"    ❌ Ошибка анализа: {analysis.get('error', 'unknown')}")
                results.append({
                    'test': i,
                    'success': False,
                    'error': analysis.get('error')
                })
        
        # Сохраняем результаты
        with open('mcp_test_results_complaint.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 Результат: {success_count}/{len(results)} тестов успешно")
        
        return success_count == len(results)
        
    except Exception as e:
        print(f"❌ Ошибка тестирования жалоб: {str(e)}")
        return False


async def test_icd10_suggestions():
    """Тест подсказок МКБ-10 через MCP"""
    print("\n🔍 Тестирование подсказок МКБ-10 через MCP...")
    
    test_cases = [
        {
            "symptoms": ["головная боль", "тошнота", "светобоязнь"],
            "diagnosis": "Мигрень"
        },
        {
            "symptoms": ["кашель", "температура", "боль в груди"],
            "diagnosis": "Пневмония"
        },
        {
            "symptoms": ["боль в животе", "изжога", "тошнота"],
            "diagnosis": "Гастрит"
        }
    ]
    
    try:
        client = await get_mcp_client()
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n  Тест {i}: {test_case['diagnosis']}")
            print(f"    Симптомы: {', '.join(test_case['symptoms'])}")
            
            # Получаем подсказки
            result = await client.suggest_icd10(
                symptoms=test_case['symptoms'],
                diagnosis=test_case['diagnosis'],
                max_suggestions=5
            )
            
            if result.get('status') == 'success':
                suggestions = result.get('data', {}).get('suggestions', [])
                print(f"    ✅ Получено подсказок: {len(suggestions)}")
                
                for j, suggestion in enumerate(suggestions[:3], 1):
                    print(f"      {j}. {suggestion.get('code', 'N/A')}: {suggestion.get('description', 'N/A')}")
            else:
                print(f"    ❌ Ошибка: {result.get('error', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования МКБ-10: {str(e)}")
        return False


async def test_lab_interpretation():
    """Тест интерпретации лабораторных анализов через MCP"""
    print("\n🔍 Тестирование интерпретации лабораторных анализов через MCP...")
    
    test_results = [
        {"test_name": "glucose", "value": 7.2, "unit": "ммоль/л"},
        {"test_name": "hemoglobin", "value": 110, "unit": "г/л"},
        {"test_name": "alt", "value": 65, "unit": "Ед/л"},
        {"test_name": "creatinine", "value": 150, "unit": "мкмоль/л"}
    ]
    
    try:
        client = await get_mcp_client()
        
        # Проверяем критические значения
        print("\n  Проверка критических значений...")
        critical_check = await client.check_critical_lab_values(test_results)
        
        if critical_check.get('status') == 'success':
            data = critical_check.get('data', {})
            has_critical = data.get('has_critical', False)
            print(f"    {'⚠️' if has_critical else '✅'} Критические значения: {'Обнаружены' if has_critical else 'Не обнаружены'}")
            
            if has_critical:
                for critical in data.get('critical_values', []):
                    print(f"      ❗ {critical['test']}: {critical['value']} {critical['unit']} ({critical['type']})")
        
        # Интерпретируем результаты
        print("\n  Интерпретация результатов...")
        interpretation = await client.interpret_lab_results(
            results=test_results,
            patient_info={"age": 45, "gender": "male"},
            include_recommendations=True
        )
        
        if interpretation.get('status') == 'success':
            data = interpretation.get('data', {})
            summary = data.get('summary', {})
            
            print(f"    ✅ Интерпретация выполнена")
            print(f"    Всего тестов: {summary.get('total_tests', 0)}")
            print(f"    Отклонений: {summary.get('abnormal_count', 0)}")
            print(f"    Критических: {summary.get('critical_count', 0)}")
            print(f"    Оценка: {summary.get('overall_assessment', 'N/A')}")
            
            # Показываем рекомендации
            recommendations = data.get('recommendations', [])
            if recommendations:
                print("    Рекомендации:")
                for rec in recommendations[:3]:
                    print(f"      • {rec}")
        else:
            print(f"    ❌ Ошибка интерпретации: {interpretation.get('error', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования лабораторных анализов: {str(e)}")
        return False


async def test_mcp_metrics():
    """Тест метрик MCP"""
    print("\n🔍 Тестирование метрик MCP...")
    
    try:
        manager = await get_mcp_manager()
        
        # Получаем метрики
        metrics = manager.get_metrics()
        
        print(f"✅ Метрики MCP:")
        print(f"  Всего запросов: {metrics['requests_total']}")
        print(f"  Успешных: {metrics['requests_success']}")
        print(f"  Ошибок: {metrics['requests_failed']}")
        
        # Метрики по серверам
        if metrics['server_stats']:
            print("\n  Статистика по серверам:")
            for server, stats in metrics['server_stats'].items():
                print(f"    {server}:")
                print(f"      Запросов: {stats.get('requests', 0)}")
                print(f"      Ошибок: {stats.get('errors', 0)}")
                print(f"      Ср. время: {stats.get('avg_response_time', 0):.3f}с")
        
        # Конфигурация
        if metrics['config']:
            print("\n  Конфигурация:")
            print(f"    MCP включен: {metrics['config'].get('enabled', False)}")
            print(f"    Fallback: {metrics['config'].get('fallback_to_direct', False)}")
            print(f"    Таймаут: {metrics['config'].get('request_timeout', 0)}с")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка получения метрик: {str(e)}")
        return False


async def test_batch_processing():
    """Тест пакетной обработки через MCP"""
    print("\n🔍 Тестирование пакетной обработки через MCP...")
    
    try:
        manager = await get_mcp_manager()
        
        # Создаем пакет запросов
        batch_requests = [
            {
                "server": "complaint",
                "method": "tool/validate_complaint",
                "params": {"complaint": "Головная боль"}
            },
            {
                "server": "icd10",
                "method": "resource/common_icd10_codes",
                "params": {"category": "neurological"}
            },
            {
                "server": "lab",
                "method": "resource/normal_ranges",
                "params": {"test_name": "glucose"}
            }
        ]
        
        print(f"  Отправка {len(batch_requests)} запросов...")
        
        # Выполняем пакетную обработку
        results = await manager.batch_execute(batch_requests, parallel=True)
        
        success_count = sum(1 for r in results if r.get('status') == 'success')
        print(f"  ✅ Успешно выполнено: {success_count}/{len(results)}")
        
        for i, result in enumerate(results):
            status_icon = "✅" if result.get('status') == 'success' else "❌"
            print(f"    {status_icon} Запрос {i+1}: {result.get('status', 'unknown')}")
        
        return success_count == len(results)
        
    except Exception as e:
        print(f"❌ Ошибка пакетной обработки: {str(e)}")
        return False


async def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ MCP ИНТЕГРАЦИИ")
    print("=" * 60)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Запускаем тесты
    tests = [
        ("Здоровье системы", test_mcp_health),
        ("Анализ жалоб", test_complaint_analysis),
        ("Подсказки МКБ-10", test_icd10_suggestions),
        ("Лабораторные анализы", test_lab_interpretation),
        ("Метрики MCP", test_mcp_metrics),
        ("Пакетная обработка", test_batch_processing)
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте '{test_name}': {str(e)}")
            results[test_name] = False
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    for test_name, success in results.items():
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {'Успешно' if success else 'Ошибка'}")
    
    print("\n" + "-" * 60)
    print(f"Результат: {success_count}/{total_count} тестов пройдено успешно")
    
    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"⚠️ {total_count - success_count} тестов завершились с ошибками")
    
    print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Сохраняем результаты
    with open('mcp_test_report.json', 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'total': total_count,
                'success': success_count,
                'failed': total_count - success_count,
                'success_rate': f"{(success_count/total_count)*100:.1f}%"
            }
        }, f, ensure_ascii=False, indent=2)
    
    print("\n📄 Отчет сохранен в mcp_test_report.json")


if __name__ == "__main__":
    asyncio.run(main())
