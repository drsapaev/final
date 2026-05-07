#!/usr/bin/env python3
"""
РЎРєСЂРёРїС‚ РґР»СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё Р±Р°Р·С‹ РґР°РЅРЅС‹С…
РЎРѕР·РґР°РµС‚ РІСЃРµ РЅРµРѕР±С…РѕРґРёРјС‹Рµ С‚Р°Р±Р»РёС†С‹ Рё РґРѕР±Р°РІР»СЏРµС‚ Р±Р°Р·РѕРІС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№, РѕС‚РґРµР»РµРЅРёРµ Рё РІСЂР°С‡Р°.
"""

import os
import sys
from datetime import time
from pathlib import Path

# Р”РѕР±Р°РІР»СЏРµРј РїСѓС‚СЊ Рє РїСЂРѕРµРєС‚Сѓ
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def require_init_database_confirmation():
    if os.getenv("CONFIRM_INIT_DATABASE") != "1":
        raise RuntimeError(
            "Refusing to initialize database seed data. "
            "Run Alembic migrations first and set CONFIRM_INIT_DATABASE=1 only for an explicit bootstrap run."
        )


require_init_database_confirmation()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.role_permission import Role, Permission, UserGroup
from app.models.authentication import RefreshToken, UserActivity, SecurityEvent, LoginAttempt
from app.models.department import Department
from app.models.clinic import Doctor
from app.core.config import settings
from passlib.context import CryptContext

# РЎРѕР·РґР°РµРј РґРІРёР¶РѕРє Р±Р°Р·С‹ РґР°РЅРЅС‹С…
engine = create_engine(settings.DATABASE_URL, echo=True)

# РЎРѕР·РґР°РµРј РІСЃРµ С‚Р°Р±Р»РёС†С‹
print("рџ—„пёЏ РЎРѕР·РґР°РЅРёРµ С‚Р°Р±Р»РёС† РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…...")
Base.metadata.create_all(bind=engine)

# РЎРѕР·РґР°РµРј РєРѕРЅС‚РµРєСЃС‚ РґР»СЏ С…РµС€РёСЂРѕРІР°РЅРёСЏ РїР°СЂРѕР»РµР№
# РСЃРїРѕР»СЊР·СѓРµРј argon2 РєР°Рє РѕСЃРЅРѕРІРЅРѕР№ (РєР°Рє РЅР°СЃС‚СЂРѕРµРЅРѕ РІ security.py), bcrypt РєР°Рє Р·Р°РїР°СЃРЅРѕР№
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# РЎРѕР·РґР°РµРј СЃРµСЃСЃРёСЋ
print("рџ‘Ґ РЎРѕР·РґР°РЅРёРµ Р±Р°Р·РѕРІС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№...")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё СѓР¶Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»Рё
    existing_users = db.query(User).count()
    if existing_users > 0:
        print(f"вњ… Р’ Р±Р°Р·Рµ СѓР¶Рµ РµСЃС‚СЊ {existing_users} РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№")
    else:
        # РЎРѕР·РґР°РµРј СЂРѕР»Рё (РёСЃРїРѕР»СЊР·СѓРµРј РїСЂР°РІРёР»СЊРЅСѓСЋ РјРѕРґРµР»СЊ Role РёР· role_permission.py)
        admin_role = Role(
            name="Admin",
            display_name="РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ",
            description="РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃРёСЃС‚РµРјС‹",
            level=100,
            is_system=True,
        )
        doctor_role = Role(
            name="Doctor",
            display_name="Р’СЂР°С‡",
            description="Р’СЂР°С‡",
            level=50,
            is_system=True,
        )
        registrar_role = Role(
            name="Registrar",
            display_name="Р РµРіРёСЃС‚СЂР°С‚РѕСЂ",
            description="Р РµРіРёСЃС‚СЂР°С‚РѕСЂ",
            level=30,
            is_system=True,
        )

        db.add_all([admin_role, doctor_role, registrar_role])
        db.flush()  # РџРѕР»СѓС‡Р°РµРј ID СЂРѕР»РµР№

        # РЎРѕР·РґР°РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        admin_user = User(
            username="admin",
            email="admin@clinic.local",
            full_name="РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ",
            hashed_password=get_password_hash("admin123"),
            role="Admin",
            is_active=True,
            is_superuser=True,
        )

        doctor_user = User(
            username="doctor",
            email="doctor@clinic.local",
            full_name="Р”РѕРєС‚РѕСЂ РРІР°РЅРѕРІ",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )

        registrar_user = User(
            username="registrar",
            email="registrar@clinic.local",
            full_name="Р РµРіРёСЃС‚СЂР°С‚РѕСЂ РџРµС‚СЂРѕРІР°",
            hashed_password=get_password_hash("registrar123"),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )

        users = [admin_user, doctor_user, registrar_user]
        db.add_all(users)
        db.flush()  # РџРѕР»СѓС‡Р°РµРј ID РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№

        # РЎРѕР·РґР°РµРј РѕС‚РґРµР»РµРЅРёРµ (РєСЂРёС‚РёС‡РµСЃРєРё РІР°Р¶РЅРѕ РґР»СЏ СЂР°Р±РѕС‚С‹ QR Queue)
        general_dept = Department(
            key="general",
            name_ru="РћР±С‰РµРµ РѕС‚РґРµР»РµРЅРёРµ",
            name_uz="Umumiy bo'lim",
            icon="folder",
            display_order=1,
            active=True,
            description="РћР±С‰РµРµ РѕС‚РґРµР»РµРЅРёРµ РєР»РёРЅРёРєРё",
        )
        db.add(general_dept)
        db.flush()  # РџРѕР»СѓС‡Р°РµРј ID РѕС‚РґРµР»РµРЅРёСЏ

        # РЎРѕР·РґР°РµРј РїСЂРѕС„РёР»СЊ РІСЂР°С‡Р° (Doctor) - СЃРІСЏР·С‹РІР°РµС‚ User СЃ РѕС‚РґРµР»РµРЅРёРµРј
        # Р­С‚Рѕ РєСЂРёС‚РёС‡РµСЃРєРё РІР°Р¶РЅРѕ РґР»СЏ СЂР°Р±РѕС‚С‹ QR Queue СЃРёСЃС‚РµРјС‹!
        doctor = Doctor(
            user_id=doctor_user.id,
            department_id=general_dept.id,
            specialty="general",
            active=True,
            start_number_online=1,
            max_online_per_day=20,
            # РСЃРїРѕР»СЊР·СѓРµРј time() РѕР±СЉРµРєС‚ РІРјРµСЃС‚Рѕ СЃС‚СЂРѕРєРё РґР»СЏ SQLite СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё
            auto_close_time=time(9, 0),
        )
        db.add(doctor)

        db.commit()

        print("вњ… РЎРѕР·РґР°РЅС‹ СЂРѕР»Рё:")
        print("  - Admin (СѓСЂРѕРІРµРЅСЊ 100)")
        print("  - Doctor (СѓСЂРѕРІРµРЅСЊ 50)")
        print("  - Registrar (СѓСЂРѕРІРµРЅСЊ 30)")
        print()
        print("вњ… РЎРѕР·РґР°РЅС‹ РїРѕР»СЊР·РѕРІР°С‚РµР»Рё:")
        print("  - admin / admin123 (РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ)")
        print("  - doctor / doctor123 (Р’СЂР°С‡)")
        print("  - registrar / registrar123 (Р РµРіРёСЃС‚СЂР°С‚РѕСЂ)")
        print()
        print(f"вњ… РЎРѕР·РґР°РЅРѕ РѕС‚РґРµР»РµРЅРёРµ: {general_dept.name_ru} (key={general_dept.key})")
        print(f"вњ… РЎРѕР·РґР°РЅ РїСЂРѕС„РёР»СЊ РІСЂР°С‡Р° РґР»СЏ {doctor_user.full_name} (Doctor.id={doctor.id})")
        print()
        print("рџ’Ў РўРµРїРµСЂСЊ QR Queue СЃРёСЃС‚РµРјР° СЃРјРѕР¶РµС‚ РЅР°С…РѕРґРёС‚СЊ РѕС‡РµСЂРµРґРё РїРѕ doctor.id")

except Exception as e:
    print(f"вќЊ РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

print()
print("рџЋ‰ РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С… Р·Р°РІРµСЂС€РµРЅР°!")
