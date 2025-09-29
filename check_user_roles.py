#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.role_permission import Role, user_roles_table
from sqlalchemy import select

def check_user_roles():
    with SessionLocal() as db:
        # Проверяем пользователя admin@example.com
        user = db.query(User).filter(User.username == 'admin@example.com').first()
        if not user:
            print("❌ Пользователь admin@example.com не найден")
            return
        
        print(f"✅ Пользователь: {user.username}")
        print(f"   ID: {user.id}")
        print(f"   Активен: {user.is_active}")
        print(f"   Суперпользователь: {getattr(user, 'is_superuser', 'N/A')}")
        
        # Проверяем роли через таблицу связи
        user_roles_query = select(user_roles_table).where(user_roles_table.c.user_id == user.id)
        user_roles = db.execute(user_roles_query).fetchall()
        if not user_roles:
            print("❌ У пользователя нет ролей")
            
            # Проверяем, есть ли роли в системе
            all_roles = db.query(Role).all()
            if not all_roles:
                print("❌ В системе нет ролей")
                print("🔧 Создаем базовые роли...")
                
                # Создаем базовые роли
                admin_role = Role(name="Admin", description="Администратор системы")
                registrar_role = Role(name="Registrar", description="Регистратор")
                doctor_role = Role(name="Doctor", description="Врач")
                
                db.add_all([admin_role, registrar_role, doctor_role])
                db.commit()
                
                # Назначаем роль Admin пользователю admin@example.com
                insert_stmt = user_roles_table.insert().values(user_id=user.id, role_id=admin_role.id)
                db.execute(insert_stmt)
                db.commit()
                
                print(f"✅ Создана роль Admin и назначена пользователю {user.username}")
            else:
                print("✅ Роли в системе есть:")
                for role in all_roles:
                    print(f"   - {role.name}: {role.description}")
                
                # Назначаем роль Admin если она есть
                admin_role = db.query(Role).filter(Role.name == "Admin").first()
                if admin_role:
                    insert_stmt = user_roles_table.insert().values(user_id=user.id, role_id=admin_role.id)
                    db.execute(insert_stmt)
                    db.commit()
                    print(f"✅ Назначена роль Admin пользователю {user.username}")
        else:
            print("✅ Роли пользователя:")
            for ur in user_roles:
                role = db.query(Role).filter(Role.id == ur.role_id).first()
                if role:
                    print(f"   - {role.name}: {role.description}")

if __name__ == "__main__":
    check_user_roles()
