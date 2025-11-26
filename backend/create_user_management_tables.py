#!/usr/bin/env python3
"""
Создание таблиц для системы управления пользователями
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.db.base_class import Base
from app.db.session import engine
from app.models.user_profile import (
    UserProfile, UserPreferences, UserNotificationSettings, 
    UserRole, UserPermission, RolePermission, UserGroup, 
    UserGroupMember, UserAuditLog
)

def create_user_management_tables():
    """Создает таблицы для системы управления пользователями"""
    print("🔧 СОЗДАНИЕ ТАБЛИЦ ДЛЯ СИСТЕМЫ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ")
    print("=" * 60)
    
    try:
        # Создаем все таблицы
        print("📋 Создание таблиц...")
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы успешно")
        
        # Проверяем созданные таблицы
        print("\n🔍 Проверка созданных таблиц...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'user_%'
                ORDER BY name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"✅ Найдено таблиц: {len(tables)}")
            for table in tables:
                print(f"   - {table}")
        
        # Создаем базовые роли
        print("\n👥 Создание базовых ролей...")
        with engine.connect() as conn:
            # Проверяем, есть ли уже роли
            result = conn.execute(text("SELECT COUNT(*) FROM user_roles"))
            role_count = result.scalar()
            
            if role_count == 0:
                # Создаем базовые роли
                roles = [
                    ("Admin", "Администратор", "Полный доступ к системе", True),
                    ("Doctor", "Врач", "Доступ к пациентам и записям", True),
                    ("Nurse", "Медсестра", "Доступ к записям и расписанию", True),
                    ("Receptionist", "Регистратор", "Доступ к записям и платежам", True),
                    ("Patient", "Пациент", "Доступ к своему профилю", True)
                ]
                
                for name, display_name, description, is_system in roles:
                    conn.execute(text("""
                        INSERT INTO user_roles (name, display_name, description, is_system, is_active)
                        VALUES (:name, :display_name, :description, :is_system, :is_active)
                    """), {
                        "name": name,
                        "display_name": display_name,
                        "description": description,
                        "is_system": is_system,
                        "is_active": True
                    })
                
                conn.commit()
                print("✅ Базовые роли созданы")
            else:
                print(f"✅ Роли уже существуют ({role_count} ролей)")
        
        # Создаем базовые разрешения
        print("\n🔐 Создание базовых разрешений...")
        with engine.connect() as conn:
            # Проверяем, есть ли уже разрешения
            result = conn.execute(text("SELECT COUNT(*) FROM user_permissions"))
            permission_count = result.scalar()
            
            if permission_count == 0:
                # Создаем базовые разрешения
                permissions = [
                    ("users:read", "Просмотр пользователей", "Просмотр списка пользователей", "users"),
                    ("users:write", "Редактирование пользователей", "Создание и редактирование пользователей", "users"),
                    ("users:delete", "Удаление пользователей", "Удаление пользователей", "users"),
                    ("users:bulk_action", "Массовые действия", "Выполнение массовых действий с пользователями", "users"),
                    ("profile:read", "Просмотр профилей", "Просмотр профилей пользователей", "profile"),
                    ("profile:write", "Редактирование профилей", "Редактирование профилей пользователей", "profile"),
                    ("patients:read", "Просмотр пациентов", "Просмотр списка пациентов", "patients"),
                    ("patients:write", "Редактирование пациентов", "Создание и редактирование пациентов", "patients"),
                    ("patients:delete", "Удаление пациентов", "Удаление пациентов", "patients"),
                    ("appointments:read", "Просмотр записей", "Просмотр записей на прием", "appointments"),
                    ("appointments:write", "Редактирование записей", "Создание и редактирование записей", "appointments"),
                    ("appointments:delete", "Удаление записей", "Удаление записей на прием", "appointments"),
                    ("emr:read", "Просмотр медкарт", "Просмотр медицинских карт", "emr"),
                    ("emr:write", "Редактирование медкарт", "Создание и редактирование медкарт", "emr"),
                    ("emr:delete", "Удаление медкарт", "Удаление медицинских карт", "emr"),
                    ("payments:read", "Просмотр платежей", "Просмотр платежей", "payments"),
                    ("payments:write", "Редактирование платежей", "Создание и редактирование платежей", "payments"),
                    ("payments:delete", "Удаление платежей", "Удаление платежей", "payments"),
                    ("analytics:read", "Просмотр аналитики", "Просмотр аналитики и отчетов", "analytics"),
                    ("settings:read", "Просмотр настроек", "Просмотр настроек системы", "settings"),
                    ("settings:write", "Редактирование настроек", "Редактирование настроек системы", "settings"),
                    ("audit:read", "Просмотр аудита", "Просмотр журнала аудита", "audit"),
                    ("export:write", "Экспорт данных", "Экспорт данных системы", "export")
                ]
                
                for name, display_name, description, category in permissions:
                    conn.execute(text("""
                        INSERT INTO user_permissions (name, display_name, description, category, is_system, is_active)
                        VALUES (:name, :display_name, :description, :category, :is_system, :is_active)
                    """), {
                        "name": name,
                        "display_name": display_name,
                        "description": description,
                        "category": category,
                        "is_system": True,
                        "is_active": True
                    })
                
                conn.commit()
                print("✅ Базовые разрешения созданы")
            else:
                print(f"✅ Разрешения уже существуют ({permission_count} разрешений)")
        
        # Создаем связи ролей и разрешений
        print("\n🔗 Создание связей ролей и разрешений...")
        with engine.connect() as conn:
            # Проверяем, есть ли уже связи
            result = conn.execute(text("SELECT COUNT(*) FROM role_permissions"))
            link_count = result.scalar()
            
            if link_count == 0:
                # Получаем ID ролей
                result = conn.execute(text("SELECT id, name FROM user_roles"))
                roles = {name: id for id, name in result.fetchall()}
                
                # Получаем ID разрешений
                result = conn.execute(text("SELECT id, name FROM user_permissions"))
                permissions = {name: id for id, name in result.fetchall()}
                
                # Создаем связи для роли Admin (все разрешения)
                admin_role_id = roles.get("Admin")
                if admin_role_id:
                    for perm_name, perm_id in permissions.items():
                        conn.execute(text("""
                            INSERT INTO role_permissions (role_id, permission_id)
                            VALUES (:role_id, :permission_id)
                        """), {
                            "role_id": admin_role_id,
                            "permission_id": perm_id
                        })
                
                # Создаем связи для роли Doctor
                doctor_role_id = roles.get("Doctor")
                if doctor_role_id:
                    doctor_permissions = [
                        "patients:read", "patients:write",
                        "appointments:read", "appointments:write",
                        "emr:read", "emr:write",
                        "analytics:read", "profile:read", "profile:write"
                    ]
                    for perm_name in doctor_permissions:
                        if perm_name in permissions:
                            conn.execute(text("""
                                INSERT INTO role_permissions (role_id, permission_id)
                                VALUES (:role_id, :permission_id)
                            """), {
                                "role_id": doctor_role_id,
                                "permission_id": permissions[perm_name]
                            })
                
                # Создаем связи для роли Nurse
                nurse_role_id = roles.get("Nurse")
                if nurse_role_id:
                    nurse_permissions = [
                        "patients:read", "appointments:read", "emr:read", "profile:read"
                    ]
                    for perm_name in nurse_permissions:
                        if perm_name in permissions:
                            conn.execute(text("""
                                INSERT INTO role_permissions (role_id, permission_id)
                                VALUES (:role_id, :permission_id)
                            """), {
                                "role_id": nurse_role_id,
                                "permission_id": permissions[perm_name]
                            })
                
                # Создаем связи для роли Receptionist
                receptionist_role_id = roles.get("Receptionist")
                if receptionist_role_id:
                    receptionist_permissions = [
                        "patients:read", "patients:write",
                        "appointments:read", "appointments:write",
                        "payments:read", "payments:write",
                        "profile:read", "profile:write"
                    ]
                    for perm_name in receptionist_permissions:
                        if perm_name in permissions:
                            conn.execute(text("""
                                INSERT INTO role_permissions (role_id, permission_id)
                                VALUES (:role_id, :permission_id)
                            """), {
                                "role_id": receptionist_role_id,
                                "permission_id": permissions[perm_name]
                            })
                
                # Создаем связи для роли Patient
                patient_role_id = roles.get("Patient")
                if patient_role_id:
                    patient_permissions = [
                        "profile:read", "profile:write",
                        "appointments:read", "payments:read"
                    ]
                    for perm_name in patient_permissions:
                        if perm_name in permissions:
                            conn.execute(text("""
                                INSERT INTO role_permissions (role_id, permission_id)
                                VALUES (:role_id, :permission_id)
                            """), {
                                "role_id": patient_role_id,
                                "permission_id": permissions[perm_name]
                            })
                
                conn.commit()
                print("✅ Связи ролей и разрешений созданы")
            else:
                print(f"✅ Связи уже существуют ({link_count} связей)")
        
        print("\n🎉 СИСТЕМА УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        print("✅ Все таблицы созданы")
        print("✅ Базовые роли настроены")
        print("✅ Базовые разрешения настроены")
        print("✅ Связи ролей и разрешений созданы")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА СОЗДАНИЯ ТАБЛИЦ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_user_management_tables()
    sys.exit(0 if success else 1)
