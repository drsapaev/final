from __future__ import annotations

from typing import AsyncGenerator, Callable, Iterable, Optional
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import SECRET_KEY, ALGORITHM, create_access_token  # create_access_token — переэкспорт
from app.models.user import User

# OAuth2 password bearer с правильным tokenUrl (включая префикс API если у тебя такой)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


async def _get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    Небольшой хелпер: вернуть User объект (или None) по username, используя AsyncSession.
    Если в проекте у тебя CRUD-обёртки — можно заменить вызовом туда.
    """
    res = await db.execute(select(User).where(User.username == username))
    return res.scalars().first()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    Дек dependency: извлекает user из токена (поле sub в payload).
    Бросает 401 если токен недействителен или пользователь не найден.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await _get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Проверка, что пользователь активен (если поле is_active есть).
    """
    if hasattr(current_user, "is_active") and not getattr(current_user, "is_active"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Проверка, что пользователь — суперюзер (если поле is_superuser есть).
    """
    if not (hasattr(current_user, "is_superuser") and getattr(current_user, "is_superuser")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires superuser privileges")
    return current_user


def require_roles(*roles: str) -> Callable[..., User]:
    """
    Фабрика для зависимости: проверяет, что текущий пользователь имеет хотя бы одну из указаных ролей.
    Поддерживает варианты в моделях:
      - поле `role` (строка)
      - поле `roles` (итерируемое / list/tuple)
      - поле `is_superuser` (автоматический пропуск)
    Использование: Depends(require_roles("Reg","Doctor"))
    """
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        # суперюзер пропускается
        if hasattr(current_user, "is_superuser") and getattr(current_user, "is_superuser"):
            return current_user

        # проверка по single role
        user_role = getattr(current_user, "role", None)
        if user_role and user_role in roles:
            return current_user

        # проверка по множественным ролям
        user_roles = getattr(current_user, "roles", None)
        if user_roles:
            try:
                # допускаем list/tuple/set или строку с запятыми
                if isinstance(user_roles, str):
                    user_roles_iter = [r.strip() for r in user_roles.split(",") if r.strip()]
                else:
                    user_roles_iter = list(user_roles)
                for r in user_roles_iter:
                    if r in roles:
                        return current_user
            except Exception:
                pass

        # если не прошёл — 403
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role privileges")
    return _dependency


# Переэкспорт — некоторые модули могли делать "from app.api.deps import create_access_token"
# Мы даём им удобный доступ к функции создания токена (реализована в app.core.security).
create_access_token = create_access_token  # noqa: F401

# Переэкспорт get_db чтобы другие модули могли импортировать напрямую из deps
get_db = get_db  # noqa: F401
