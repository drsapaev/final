from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def _to_dict(u: User) -> Dict:
    return {
        "id": getattr(u, "id", None),
        "username": getattr(u, "username", None),
        "full_name": getattr(u, "full_name", None),
        "email": getattr(u, "email", None),
        "is_active": getattr(u, "is_active", True),
        "is_superuser": getattr(u, "is_superuser", False),
        "hashed_password": getattr(u, "hashed_password", None),
    }


# === СИНХРОННЫЕ ВАРИАНТЫ (если где-то используются) ===
def get_user_by_username(db: Session, username: str) -> Optional[Dict]:
    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None


def get_user_by_id(db: Session, user_id: int) -> Optional[Dict]:
    stmt = select(User).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None


# === АСИНХРОННЫЕ ВАРИАНТЫ (для AsyncSession) ===
async def a_get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalars().first()


async def a_get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    res = await db.execute(select(User).where(User.id == user_id))
    return res.scalars().first()


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """Получить пользователя по номеру телефона"""
    stmt = select(User).where(User.phone == phone)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_telegram_id(db: Session, telegram_id: str) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    stmt = select(User).where(User.telegram_id == telegram_id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_data: dict) -> User:
    """Создать нового пользователя"""
    # Хешируем пароль если он есть
    if "password" in user_data:
        user_data["hashed_password"] = pwd_context.hash(user_data.pop("password"))

    # Устанавливаем значения по умолчанию
    user_data.setdefault("is_active", True)
    user_data.setdefault("is_superuser", False)
    user_data.setdefault("created_at", datetime.utcnow())

    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(password, hashed_password)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Аутентификация пользователя"""
    user = get_user_by_username(db, username)
    if not user:
        return None

    # Если user - это словарь, получаем объект User
    if isinstance(user, dict):
        user_obj = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if not user_obj or not verify_password(password, user_obj.hashed_password):
            return None
        return user_obj

    if not verify_password(password, user.hashed_password):
        return None

    return user


def get_user_permissions(user: User) -> List[str]:
    """Получить разрешения пользователя"""
    permissions = []

    # Базовые разрешения для всех пользователей
    permissions.extend(["read:profile", "update:profile"])

    # Разрешения в зависимости от роли
    if user.role == "Admin":
        permissions.extend(
            [
                "read:all",
                "create:all",
                "update:all",
                "delete:all",
                "manage:users",
                "manage:appointments",
                "manage:patients",
                "view:analytics",
                "manage:settings",
            ]
        )
    elif user.role == "Doctor":
        permissions.extend(
            [
                "read:patients",
                "create:appointments",
                "update:appointments",
                "read:medical_records",
                "create:medical_records",
                "update:medical_records",
                "read:lab_results",
                "create:prescriptions",
            ]
        )
    elif user.role == "Patient":
        permissions.extend(
            [
                "read:own_appointments",
                "create:appointments",
                "read:own_medical_records",
                "read:own_lab_results",
                "read:own_payments",
            ]
        )
    elif user.role == "Registrar":
        permissions.extend(
            [
                "read:patients",
                "create:appointments",
                "update:appointments",
                "read:appointments",
                "manage:queue",
            ]
        )
    elif user.role == "Cashier":
        permissions.extend(
            [
                "read:appointments",
                "update:payments",
                "read:payments",
                "create:payments",
                "read:patients",
            ]
        )
    elif user.role == "Lab":
        permissions.extend(
            [
                "read:lab_tests",
                "create:lab_tests",
                "update:lab_tests",
                "read:lab_results",
                "create:lab_results",
                "update:lab_results",
            ]
        )

    return permissions


def create_access_token(data: dict) -> str:
    """Создать токен доступа"""
    from jose import jwt

    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.AUTH_SECRET, algorithm=settings.AUTH_ALGORITHM
    )
    return encoded_jwt


def search_users(db: Session, query: str, limit: int = 10) -> List[User]:
    """
    Поиск пользователей по имени, телефону или email
    """
    search_pattern = f"%{query}%"

    stmt = (
        select(User)
        .where(
            or_(
                User.full_name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.phone.ilike(search_pattern),
            )
        )
        .limit(limit)
    )

    result = db.execute(stmt)
    return result.scalars().all()


def get(db: Session, id: int) -> Optional[User]:
    """Получить пользователя по ID"""
    return db.query(User).filter(User.id == id).first()
