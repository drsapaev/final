#!/usr/bin/env python3
"""
Быстрая проверка системы управления пользователями
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def quick_user_management_check():
    """Быстрая проверка системы управления пользователями"""
    print("🔍 БЫСТРАЯ ПРОВЕРКА СИСТЕМЫ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ")
    print("=" * 60)
    
    checks_passed = 0
    total_checks = 6
    
    try:
        # Проверка 1: Импорт моделей
        print("\n1️⃣ Проверка импорта моделей...")
        try:
            from app.models.user_profile import (
                UserProfile, UserPreferences, UserNotificationSettings,
                UserRole, UserPermission, UserGroup, UserAuditLog
            )
            print("✅ Модели импортированы успешно")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта моделей: {e}")
        
        # Проверка 2: Импорт схем
        print("\n2️⃣ Проверка импорта схем...")
        try:
            from app.schemas.user_management import (
                UserCreateRequest, UserResponse, UserListResponse,
                UserProfileResponse, UserPreferencesResponse
            )
            print("✅ Схемы импортированы успешно")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта схем: {e}")
        
        # Проверка 3: Импорт сервисов
        print("\n3️⃣ Проверка импорта сервисов...")
        try:
            from app.services.user_management_service import get_user_management_service
            print("✅ Сервисы импортированы успешно")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта сервисов: {e}")
        
        # Проверка 4: Импорт CRUD
        print("\n4️⃣ Проверка импорта CRUD...")
        try:
            from app.crud.user_management import (
                user_profile, user_preferences, user_notification_settings,
                user_role, user_permission, user_group, user_audit_log
            )
            print("✅ CRUD операции импортированы успешно")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта CRUD: {e}")
        
        # Проверка 5: Импорт API endpoints
        print("\n5️⃣ Проверка импорта API endpoints...")
        try:
            from app.api.v1.endpoints.user_management import router
            print("✅ API endpoints импортированы успешно")
            print(f"   - Количество маршрутов: {len(router.routes)}")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта API endpoints: {e}")
        
        # Проверка 6: Импорт middleware
        print("\n6️⃣ Проверка импорта middleware...")
        try:
            from app.middleware.user_permissions import (
                user_permissions_middleware,
                user_activity_middleware,
                user_rate_limit_middleware
            )
            print("✅ Middleware импортированы успешно")
            checks_passed += 1
        except Exception as e:
            print(f"❌ Ошибка импорта middleware: {e}")
        
        # Итоговый результат
        print("\n" + "=" * 60)
        print(f"📊 РЕЗУЛЬТАТ: {checks_passed}/{total_checks} проверок пройдено")
        
        if checks_passed == total_checks:
            print("🎉 СИСТЕМА УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ГОТОВА!")
            print("✅ Все компоненты импортируются корректно")
            print("✅ Можно запускать полные тесты")
            return True
        else:
            print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
            print("⚠️ Требуется исправление перед использованием")
            return False
            
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        return False

if __name__ == "__main__":
    success = quick_user_management_check()
    sys.exit(0 if success else 1)
