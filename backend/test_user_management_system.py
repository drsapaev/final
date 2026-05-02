#!/usr/bin/env python3
"""
Тестирование системы управления пользователями
"""
import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_profile import UserProfile, UserPreferences, UserNotificationSettings, UserStatus
from app.services.user_management_service import get_user_management_service
from app.crud.user_management import user_profile, user_preferences, user_notification_settings
from app.core.security import get_password_hash

def test_user_management_system():
    """Тестирование системы управления пользователями"""
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ")
    print("=" * 60)
    
    db = SessionLocal()
    service = get_user_management_service()
    
    try:
        # Тест 1: Создание пользователя
        print("\n1️⃣ Тест создания пользователя...")
        from app.schemas.user_management import UserCreateRequest
        
        import time
        timestamp = int(time.time())
        
        user_data = UserCreateRequest(
            username=f"test_doctor_{timestamp}",
            email=f"test_doctor_{timestamp}@clinic.com",
            password="TestPass123",
            role="Doctor",
            is_active=True,
            is_superuser=False,
            full_name="Тест Врач",
            first_name="Тест",
            last_name="Врач",
            phone="+7-999-123-45-67"
        )
        
        success, message, user = service.create_user(db, user_data, 1)  # 1 - ID создателя
        
        if success:
            print(f"✅ Пользователь создан: {user.username} (ID: {user.id})")
            user_id = user.id
        else:
            print(f"❌ Ошибка создания пользователя: {message}")
            return False
        
        # Тест 2: Получение профиля пользователя
        print("\n2️⃣ Тест получения профиля пользователя...")
        profile_data = service.get_user_profile(db, user_id)
        
        if profile_data:
            print(f"✅ Профиль получен: {profile_data['full_name']}")
            print(f"   - Email: {profile_data['email']}")
            print(f"   - Роль: {profile_data['role']}")
            print(f"   - Телефон: {profile_data.get('phone', 'Не указан')}")
        else:
            print("❌ Ошибка получения профиля")
            return False
        
        # Тест 3: Обновление профиля
        print("\n3️⃣ Тест обновления профиля...")
        from app.schemas.user_management import UserUpdateRequest
        
        update_data = UserUpdateRequest(
            full_name="Тест Врач Обновленный",
            phone="+7-999-123-45-68"
        )
        
        success, message = service.update_user(db, user_id, update_data, 1)
        
        if success:
            print("✅ Профиль обновлен успешно")
        else:
            print(f"❌ Ошибка обновления профиля: {message}")
            return False
        
        # Тест 4: Обновление настроек пользователя
        print("\n4️⃣ Тест обновления настроек пользователя...")
        from app.schemas.user_management import UserPreferencesUpdate
        
        preferences_data = UserPreferencesUpdate(
            theme="dark",
            language="en",
            timezone="Europe/London",
            working_hours_start="08:00",
            working_hours_end="17:00",
            working_days=[1, 2, 3, 4, 5],  # Понедельник-пятница
            break_duration=60
        )
        
        success, message = service.update_user_preferences(db, user_id, preferences_data)
        
        if success:
            print("✅ Настройки пользователя обновлены успешно")
        else:
            print(f"❌ Ошибка обновления настроек: {message}")
            return False
        
        # Тест 5: Обновление настроек уведомлений
        print("\n5️⃣ Тест обновления настроек уведомлений...")
        from app.schemas.user_management import UserNotificationSettingsUpdate
        
        notification_data = UserNotificationSettingsUpdate(
            email_appointment_reminder=True,
            email_appointment_cancellation=True,
            sms_appointment_reminder=False,
            push_appointment_reminder=True,
            reminder_time_before=120,  # 2 часа
            quiet_hours_start="22:00",
            quiet_hours_end="08:00"
        )
        
        success, message = service.update_notification_settings(db, user_id, notification_data)
        
        if success:
            print("✅ Настройки уведомлений обновлены успешно")
        else:
            print(f"❌ Ошибка обновления настроек уведомлений: {message}")
            return False
        
        # Тест 6: Поиск пользователей
        print("\n6️⃣ Тест поиска пользователей...")
        from app.schemas.user_management import UserSearchRequest
        
        search_params = UserSearchRequest(
            query="Тест",
            role="Doctor",
            page=1,
            per_page=10
        )
        
        users_data, total = service.search_users(db, search_params)
        
        if users_data:
            print(f"✅ Найдено пользователей: {total}")
            for user_data in users_data:
                full_name = user_data.get('full_name', 'Не указано')
                print(f"   - {user_data['username']} ({full_name})")
        else:
            print("❌ Ошибка поиска пользователей")
            return False
        
        # Тест 7: Статистика пользователей
        print("\n7️⃣ Тест статистики пользователей...")
        stats = service.get_user_stats(db)
        
        if stats:
            print("✅ Статистика получена:")
            print(f"   - Всего пользователей: {stats['total_users']}")
            print(f"   - Активных: {stats['active_users']}")
            print(f"   - По ролям: {stats['users_by_role']}")
        else:
            print("❌ Ошибка получения статистики")
            return False
        
        # Тест 8: Массовые действия
        print("\n8️⃣ Тест массовых действий...")
        from app.schemas.user_management import UserBulkActionRequest
        
        bulk_action_data = UserBulkActionRequest(
            user_ids=[user_id],
            action="activate",
            reason="Тестовое действие"
        )
        
        success, message, result = service.bulk_action_users(db, bulk_action_data, 1)
        
        if success:
            print(f"✅ Массовое действие выполнено: {message}")
            print(f"   - Обработано: {result['processed_count']}")
            print(f"   - Ошибок: {result['failed_count']}")
        else:
            print(f"❌ Ошибка массового действия: {message}")
            return False
        
        # Тест 9: Проверка CRUD операций
        print("\n9️⃣ Тест CRUD операций...")
        
        # Получение профиля через CRUD
        profile = user_profile.get_by_user_id(db, user_id)
        if profile:
            print(f"✅ Профиль получен через CRUD: {profile.full_name}")
        else:
            print("❌ Ошибка получения профиля через CRUD")
            return False
        
        # Получение настроек через CRUD
        preferences = user_preferences.get_by_user_id(db, user_id)
        if preferences:
            print(f"✅ Настройки получены через CRUD: тема {preferences.theme}")
        else:
            print("❌ Ошибка получения настроек через CRUD")
            return False
        
        # Получение настроек уведомлений через CRUD
        notifications = user_notification_settings.get_by_user_id(db, user_id)
        if notifications:
            print(f"✅ Настройки уведомлений получены через CRUD: email напоминания {notifications.email_appointment_reminder}")
        else:
            print("❌ Ошибка получения настроек уведомлений через CRUD")
            return False
        
        # Тест 10: Очистка тестовых данных
        print("\n🔟 Очистка тестовых данных...")
        
        # Удаляем тестового пользователя
        success, message = service.delete_user(db, user_id, 1)
        
        if success:
            print("✅ Тестовый пользователь удален")
        else:
            print(f"❌ Ошибка удаления тестового пользователя: {message}")
            return False
        
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        return True
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()

def test_api_endpoints():
    """Тестирование API endpoints"""
    print("\n🌐 ТЕСТИРОВАНИЕ API ENDPOINTS")
    print("=" * 40)
    
    try:
        # Проверяем, что API endpoints импортируются
        from app.api.v1.endpoints import user_management
        print("✅ API endpoints user_management импортированы")
        
        # Проверяем, что роутер создан
        if hasattr(user_management, 'router'):
            print("✅ Роутер создан")
            print(f"   - Количество маршрутов: {len(user_management.router.routes)}")
        else:
            print("❌ Роутер не найден")
            return False
        
        # Проверяем основные маршруты
        routes = [route.path for route in user_management.router.routes]
        expected_routes = [
            "/users",
            "/users/{user_id}",
            "/users/{user_id}/profile",
            "/users/{user_id}/preferences",
            "/users/{user_id}/notifications",
            "/users/{user_id}/activity",
            "/users/stats",
            "/users/bulk-action",
            "/users/export",
            "/users/health"
        ]
        
        for expected_route in expected_routes:
            if any(expected_route in route for route in routes):
                print(f"✅ Маршрут {expected_route} найден")
            else:
                print(f"❌ Маршрут {expected_route} не найден")
                return False
        
        print("✅ Все API endpoints готовы к использованию")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования API: {str(e)}")
        return False

def test_middleware():
    """Тестирование middleware"""
    print("\n🛡️ ТЕСТИРОВАНИЕ MIDDLEWARE")
    print("=" * 30)
    
    try:
        from app.middleware.user_permissions import (
            user_permissions_middleware,
            user_activity_middleware,
            user_rate_limit_middleware
        )
        print("✅ Middleware импортированы")
        
        # Проверяем настройки middleware
        print(f"✅ UserPermissionsMiddleware: {len(user_permissions_middleware.role_permissions)} ролей")
        print(f"✅ UserActivityMiddleware: готов к использованию")
        print(f"✅ UserRateLimitMiddleware: {len(user_rate_limit_middleware.rate_limits)} лимитов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования middleware: {str(e)}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ СИСТЕМЫ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ")
    print("=" * 70)
    
    # Тестируем основные компоненты
    tests_passed = 0
    total_tests = 3
    
    # Тест 1: Основная функциональность
    if test_user_management_system():
        tests_passed += 1
        print("\n✅ Тест 1/3: Основная функциональность - ПРОЙДЕН")
    else:
        print("\n❌ Тест 1/3: Основная функциональность - ПРОВАЛЕН")
    
    # Тест 2: API endpoints
    if test_api_endpoints():
        tests_passed += 1
        print("\n✅ Тест 2/3: API endpoints - ПРОЙДЕН")
    else:
        print("\n❌ Тест 2/3: API endpoints - ПРОВАЛЕН")
    
    # Тест 3: Middleware
    if test_middleware():
        tests_passed += 1
        print("\n✅ Тест 3/3: Middleware - ПРОЙДЕН")
    else:
        print("\n❌ Тест 3/3: Middleware - ПРОВАЛЕН")
    
    # Итоговый результат
    print("\n" + "=" * 70)
    print(f"📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {tests_passed}/{total_tests} тестов пройдено")
    
    if tests_passed == total_tests:
        print("🎉 СИСТЕМА УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        print("✅ Все компоненты работают корректно")
        print("✅ API endpoints готовы")
        print("✅ Middleware настроен")
        print("✅ База данных функционирует")
        return True
    else:
        print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ В СИСТЕМЕ")
        print("⚠️ Требуется исправление ошибок перед использованием")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
