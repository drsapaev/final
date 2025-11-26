#!/usr/bin/env python3
"""Скрипт для исправления проблем с авторизацией"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.role_permission import Role, user_roles_table
from sqlalchemy import select
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

def fix_auth_issues():
    with SessionLocal() as db:
        print("🔧 Проверяем и исправляем проблемы с авторизацией...")

        # 1. Проверяем пользователя admin@example.com
        user = db.query(User).filter(User.username == 'admin@example.com').first()
        if not user:
            print("❌ Пользователь admin@example.com не найден")
            return

        print(f"✅ Пользователь найден: {user.username} (ID: {user.id})")

        # 2. Проверяем роли
        user_roles_query = select(user_roles_table).where(user_roles_table.c.user_id == user.id)
        user_roles = db.execute(user_roles_query).fetchall()

        if not user_roles:
            print("❌ У пользователя нет ролей. Исправляем...")

            # Создаем роль Admin если её нет
            admin_role = db.query(Role).filter(Role.name == "Admin").first()
            if not admin_role:
                admin_role = Role(name="Admin", description="Администратор системы")
                db.add(admin_role)
                db.commit()
                print("✅ Создана роль Admin")

            # Назначаем роль Admin пользователю
            insert_stmt = user_roles_table.insert().values(user_id=user.id, role_id=admin_role.id)
            db.execute(insert_stmt)
            db.commit()
            print(f"✅ Назначена роль Admin пользователю {user.username}")
        else:
            print("✅ У пользователя есть роли:")
            for ur in user_roles:
                role = db.query(Role).filter(Role.id == ur.role_id).first()
                print(f"   - {role.name if role else 'Unknown'}")

        # 3. Тестируем токен
        print("\n🔍 Тестируем токен...")
        payload = {'sub': str(user.id), 'user_id': user.id, 'username': user.username}
        token = jwt.encode({**payload, 'exp': datetime.utcnow() + timedelta(hours=1)},
                          settings.SECRET_KEY,
                          algorithm=getattr(settings, 'ALGORITHM', 'HS256'))
        print(f"✅ Токен создан: {token[:50]}...")

        # 4. Тестируем endpoints
        import requests

        headers = {'Authorization': f'Bearer {token}'}

        # Тест /auth/me
        try:
            response = requests.get('http://localhost:8000/api/v1/auth/me', headers=headers)
            print(f"🔍 /auth/me: {response.status_code}")
            if response.status_code == 200:
                print("✅ /auth/me работает")
            else:
                print(f"❌ /auth/me: {response.text}")
        except Exception as e:
            print(f"❌ /auth/me: {e}")

        # Тест /admin/wizard-settings
        try:
            response = requests.get('http://localhost:8000/api/v1/admin/wizard-settings', headers=headers)
            print(f"🔍 /admin/wizard-settings: {response.status_code}")
            if response.status_code == 200:
                print("✅ /admin/wizard-settings работает")
            elif response.status_code == 401:
                print("❌ /admin/wizard-settings: Нет роли Admin")
            else:
                print(f"❌ /admin/wizard-settings: {response.text}")
        except Exception as e:
            print(f"❌ /admin/wizard-settings: {e}")

        # Тест /users/users
        try:
            response = requests.get('http://localhost:8000/api/v1/users/users', headers=headers)
            print(f"🔍 /users/users: {response.status_code}")
            if response.status_code == 200:
                print("✅ /users/users работает")
            elif response.status_code == 401:
                print("❌ /users/users: Нет роли Admin")
            else:
                print(f"❌ /users/users: {response.text}")
        except Exception as e:
            print(f"❌ /users/users: {e}")

if __name__ == "__main__":
    fix_auth_issues()
