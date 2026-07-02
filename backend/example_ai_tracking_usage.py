#!/usr/bin/env python3
"""
Пример использования трекинга AI моделей в авто режиме
"""
import asyncio
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.ai_service_enhanced import get_enhanced_ai_service


async def example_ai_tracking():
    """Пример использования трекинга AI моделей"""
    
    # Создаем сессию базы данных
    db = SessionLocal()
    
    try:
        # Получаем улучшенный AI сервис
        async with get_enhanced_ai_service(db) as ai_service:
            
            print("🤖 Пример трекинга AI моделей в авто режиме")
            print("=" * 60)
            
            # Пример 1: Анализ жалоб с трекингом
            print("\n📋 Пример 1: Анализ жалоб пациента")
            print("-" * 40)
            
            complaints = "Пациент жалуется на боль в груди, одышку при физической нагрузке"
            
            result = await ai_service.analyze_complaints_with_tracking(
                complaints_text=complaints,
                specialty="cardio",
                language="ru",
                user_id=1
            )
            
            # Выводим информацию о модели
            tracking = result.tracking
            model_info = tracking.model_info
            
            print(f"✅ Запрос выполнен успешно!")
            print(f"🤖 AI Модель: {model_info.provider_name} - {model_info.model_name}")
            print(f"⚙️ Настройки: температура={model_info.temperature}, max_tokens={model_info.max_tokens}")
            print(f"⏱️ Время ответа: {tracking.response_time_ms}мс")
            print(f"🔢 Токены: {tracking.tokens_used}")
            print(f"✅ Успешность: {tracking.success}")
            print(f"📊 Результат: {result.data}")
            
            # Пример 2: Генерация рецепта с трекингом
            print("\n💊 Пример 2: Генерация рецепта")
            print("-" * 40)
            
            patient_data = {
                "name": "Иван Петров",
                "age": 45,
                "gender": "male"
            }
            
            diagnosis = "Ишемическая болезнь сердца, стенокардия напряжения"
            
            result = await ai_service.generate_prescription_with_tracking(
                patient_data=patient_data,
                diagnosis=diagnosis,
                specialty="cardio",
                user_id=1
            )
            
            # Выводим информацию о модели
            tracking = result.tracking
            model_info = tracking.model_info
            
            print(f"✅ Рецепт сгенерирован успешно!")
            print(f"🤖 AI Модель: {model_info.provider_name} - {model_info.model_name}")
            print(f"⚙️ Настройки: температура={model_info.temperature}, max_tokens={model_info.max_tokens}")
            print(f"⏱️ Время ответа: {tracking.response_time_ms}мс")
            print(f"🔢 Токены: {tracking.tokens_used}")
            print(f"✅ Успешность: {tracking.success}")
            print(f"💊 Рецепт: {result.data}")
            
            # Пример 3: Получение статистики по моделям
            print("\n📊 Пример 3: Статистика AI моделей")
            print("-" * 40)
            
            model_stats = ai_service.get_model_stats(days_back=7)
            
            print(f"📈 Статистика за последние 7 дней:")
            for stat in model_stats:
                print(f"   🤖 {stat.provider_name} - {stat.model_name}")
                print(f"      📊 Запросов: {stat.total_requests}")
                print(f"      ✅ Успешных: {stat.successful_requests}")
                print(f"      ⏱️ Среднее время: {stat.average_response_time_ms:.2f}мс")
                print(f"      🔢 Токенов: {stat.total_tokens_used}")
                print(f"      💾 Кэш: {stat.cache_hit_rate:.1%}")
                print()
            
            # Пример 4: Получение статистики по провайдерам
            print("\n🏢 Пример 4: Статистика провайдеров")
            print("-" * 40)
            
            provider_stats = ai_service.get_provider_stats(days_back=7)
            
            print(f"🏢 Статистика провайдеров за последние 7 дней:")
            for stat in provider_stats:
                print(f"   🏢 {stat.display_name} ({stat.provider_name})")
                print(f"      📊 Всего запросов: {stat.total_requests}")
                print(f"      ✅ Успешность: {stat.success_rate:.1f}%")
                print(f"      ⏱️ Среднее время: {stat.average_response_time_ms:.2f}мс")
                print(f"      🔧 Активен: {'Да' if stat.is_active else 'Нет'}")
                print(f"      ⭐ По умолчанию: {'Да' if stat.is_default else 'Нет'}")
                print(f"      🤖 Моделей: {len(stat.models)}")
                print()
            
            print("🎉 Все примеры выполнены успешно!")
            print("\n💡 Теперь вы можете:")
            print("   • Отслеживать, какая AI модель выполнила каждый запрос")
            print("   • Анализировать производительность моделей")
            print("   • Сравнивать разные провайдеры")
            print("   • Оптимизировать использование AI ресурсов")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(example_ai_tracking())
