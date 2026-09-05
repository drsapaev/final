# app/api/deps.py
"""
Dependency helpers for the API.

This module provides:
- oauth2_scheme for extracting Bearer token
- create_access_token(...) helper
- get_current_user(...) which works with both async and sync SQLAlchemy sessions
- require_roles(...) dependency factory (алиас для security.require_roles)

It is intentionally defensive: it supports get_db() returning either
an AsyncSession or a regular (sync) Session / sessionmaker instance.
"""
from __future__ import annotations

import inspect
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

# try to import settings (SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)
from app.core.config import settings  # type: ignore
from app.core.roles import is_login_blocked_role  # QD-1.1 sentinel guard

# import authentication service
from app.services.authentication_service import get_authentication_service

# import get_db lazily -- it may return AsyncSession or sync Session
try:
    from app.db.session import get_db  # type: ignore
except Exception:
    # get_db should exist in your project; if not, imports will fail later and you need to provide it.
    get_db = None  # type: ignore

# import User model
try:
    from app.models.user import User  # type: ignore
except Exception:
    # If import fails the project is misconfigured; leave User unresolved to raise early.
    User = None  # type: ignore

# import TokenBlacklist model (blacklist check is fused into the user query)
try:
    from app.models.authentication import TokenBlacklist  # type: ignore
except Exception:
    TokenBlacklist = None  # type: ignore

logger = logging.getLogger(__name__)

# Document the 2FA-aware canonical login endpoint in OpenAPI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/authentication/login")


def _token_subject_kind(value: object) -> str:
    if isinstance(value, int):
        return "numeric"
    if isinstance(value, str):
        return "numeric" if value.isdigit() else "text"
    return "missing"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT token with `sub` claim taken from data (if provided).
    Returns encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(
            minutes=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
        )
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=getattr(settings, "ALGORITHM", "HS256"),
    )
    return encoded_jwt


def _subject_from_payload(payload: dict) -> str | None:
    """
    Extract the lookup subject from an already-decoded JWT payload.

    Prefers the 'username' claim (set by the canonical 2FA login), then
    falls back to 'sub' which may be a username or a numeric user id
    string. Returns None when neither claim is a string.
    """
    username = payload.get("username")
    if isinstance(username, str):
        return username

    sub = payload.get("sub")
    if isinstance(sub, str):
        return sub

    return None


async def _get_user_by_username(db, username: str) -> User | None:
    """
    Universal helper that supports both AsyncSession and sync Session.

    - If db.execute is a coroutine function (AsyncSession) we `await db.execute(...)`
    - Otherwise we call db.execute(...) in a threadpool to avoid blocking event loop.

    Attempts to return a mapped User instance or None.
    """
    logger.debug("_get_user_by_username: looking for text subject")
    if db is None:
        logger.debug("_get_user_by_username: db is None")
        return None

    execute_callable = getattr(db, "execute", None)
    stmt = select(User).where(User.username == username)

    # AsyncSession: await directly; Sync Session: call directly to avoid SQLite thread issues
    if inspect.iscoroutinefunction(execute_callable):
        result = await db.execute(stmt)
    else:
        result = db.execute(stmt)

    # Try common extraction patterns for Result / AsyncResult
    try:
        user = result.scalar_one_or_none()
        return user
    except Exception:
        pass

    try:
        # result.scalars() exists for many versions
        scalars = result.scalars()
        try:
            return scalars.first()
        except Exception:
            # as last resort, convert to list
            items = list(scalars)
            return items[0] if items else None
    except Exception:
        pass

    return None


async def _get_user_by_id(db, user_id: int) -> User | None:
    """
    Получить пользователя по числовому ID, поддерживая как AsyncSession, так и sync Session.
    """
    logger.debug("_get_user_by_id: looking for numeric subject")
    if db is None:
        logger.debug("_get_user_by_id: db is None")
        return None

    execute_callable = getattr(db, "execute", None)
    stmt = select(User).where(User.id == user_id)

    if inspect.iscoroutinefunction(execute_callable):
        logger.debug("_get_user_by_id: using async execute")
        result = await db.execute(stmt)
    else:
        logger.debug("_get_user_by_id: using sync execute")
        result = db.execute(stmt)

    try:
        user = result.scalar_one_or_none()
        logger.debug("_get_user_by_id: found_user=%s", user is not None)
        return user
    except Exception as e:
        logger.debug(
            "_get_user_by_id: scalar_one_or_none error (%s)",
            type(e).__name__,
        )
        try:
            user = result.scalars().first()
            logger.debug("_get_user_by_id: found_with_scalars=%s", user is not None)
            return user
        except Exception as e2:
            logger.debug("_get_user_by_id: scalars error (%s)", type(e2).__name__)
            return None


async def _get_user_with_blacklist(
    db,
    jti: str | None,
    user_id: int | None = None,
    username: str | None = None,
) -> tuple[User | None, bool]:
    """
    Load the user and check the token blacklist in ONE SQL roundtrip.

    Perf (#2772): the previous flow ran up to 3 sequential SELECTs per
    authenticated request (user fetch + blacklist by jti + blacklist
    "all_user_tokens" sentinel) — ~1.2s of RTT against the remote
    Supabase Postgres. Both blacklist checks are now EXISTS columns on
    the same query. The returned User is a fully-loaded session-attached
    ORM instance, so endpoint-side semantics are unchanged.

    Returns (user, blacklisted); user is None when the user is not found.
    """
    if db is None or TokenBlacklist is None:
        return None, False

    if user_id is not None:
        subject_filter = User.id == user_id
    elif username is not None:
        subject_filter = User.username == username
    else:
        return None, False

    jti_bl = select(TokenBlacklist.id).where(TokenBlacklist.jti == jti).exists()
    sentinel_bl = (
        select(TokenBlacklist.id)
        .where(
            TokenBlacklist.user_id == User.id,  # correlated with the outer users row
            TokenBlacklist.reason.like("all_user_tokens:%"),
            TokenBlacklist.expires_at > datetime.now(UTC),
        )
        .exists()
    )
    stmt = select(
        User,
        jti_bl.label("jti_bl"),
        sentinel_bl.label("sentinel_bl"),
    ).where(subject_filter)

    execute_callable = getattr(db, "execute", None)
    if inspect.iscoroutinefunction(execute_callable):
        row = (await db.execute(stmt)).first()
    else:
        row = db.execute(stmt).first()

    if row is None:
        return None, False

    found_user, jti_hit, sentinel_hit = row
    return found_user, bool(jti_hit or sentinel_hit)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db=Depends(get_db),
) -> User:
    """
    Dependency that returns the current authenticated User.
    Works with either async or sync DB sessions returned by get_db().
    Raises 401 on invalid token or missing user.

    Perf (#2772): user fetch and token blacklist check (jti + all-user
    sentinel) run as ONE SQL roundtrip via _get_user_with_blacklist —
    same semantics as the previous up-to-3 sequential SELECTs.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
    except JWTError as jwt_error:
        logger.debug(
            "get_current_user: JWT decode error (%s)",
            type(jwt_error).__name__,
        )
        payload = {}

    # Пытаемся поддержать оба варианта: username или числовой sub (user_id)
    username = _subject_from_payload(payload)
    sub = payload.get("sub")
    jti = payload.get("jti")
    user: User | None = None
    blacklisted = False

    try:
        if username:
            logger.debug(
                "get_current_user: trying primary subject lookup (%s)",
                _token_subject_kind(username),
            )
            # Если username содержит только цифры, то это ID
            if username.isdigit():
                logger.debug("get_current_user: primary subject is numeric")
                user, blacklisted = await _get_user_with_blacklist(
                    db, jti=jti, user_id=int(username)
                )
            else:
                logger.debug("get_current_user: primary subject is text")
                user, blacklisted = await _get_user_with_blacklist(
                    db, jti=jti, username=username
                )
            logger.debug(
                "get_current_user: primary lookup found_user=%s",
                user is not None,
            )
        else:
            logger.debug(
                "get_current_user: no username claim, falling back to sub (%s)",
                _token_subject_kind(sub),
            )
            # Падаем обратно на извлечение sub и поиск по ID
            if isinstance(sub, str) and sub.isdigit():
                logger.debug("get_current_user: fallback sub is numeric")
                user, blacklisted = await _get_user_with_blacklist(
                    db, jti=jti, user_id=int(sub)
                )
            elif isinstance(sub, int):
                logger.debug("get_current_user: fallback sub is numeric")
                user, blacklisted = await _get_user_with_blacklist(
                    db, jti=jti, user_id=sub
                )
            elif isinstance(sub, str):
                logger.debug("get_current_user: fallback sub is text")
                user, blacklisted = await _get_user_with_blacklist(
                    db, jti=jti, username=sub
                )
    except Exception as e:
        logger.warning(
            "get_current_user: validation failed (%s)",
            type(e).__name__,
            exc_info=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if not user:
        logger.warning("[deps.get_current_user] user not found (username from token may not exist in DB)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if blacklisted:
        logger.warning(
            "[deps.get_current_user] token jti=%s is blacklisted (revoked)",
            jti,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # QD-1.1 (queue resource role cleanup, Codex round-1): internal-only
    # sentinel roles are structural non-logins — even a hand-minted or
    # legacy token must not authenticate a synthetic queue-resource
    # account. This also closes any token that could ever be minted via
    # the 2FA-exchange surface: a pending 2FA token cannot be issued for
    # a login-blocked account, and any pre-existing token fails here.
    if is_login_blocked_role(getattr(user, "role", None)):
        logger.warning(
            "[deps.get_current_user] internal-only role rejected (user_id=%s)",
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(
        "[deps.get_current_user] authenticated user resolved role=%s active=%s",
        getattr(user, "role", None),
        getattr(user, "is_active", None),
    )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that returns the current authenticated and active User.
    Raises 403 if user is not active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован"
        )
    return current_user


# require_roles() перемещена в app.core.security (SSOT)
# Импортируем для обратной совместимости
def require_roles(*roles: str) -> Callable[..., Any]:
    """
    Dependency factory для проверки ролей (перенаправляет на SSOT).

    Эта функция теперь является алиасом для app.core.security.require_roles()
    для обратной совместимости. Новый код должен использовать security.require_roles().
    """
    from app.core.security import require_roles as _require_roles

    return _require_roles(*roles)


def get_current_user_from_request(request: Request) -> User | None:
    """Получить текущего пользователя из состояния запроса (для middleware)"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        return None

    # Получаем сессию БД
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    finally:
        db.close()


def get_current_user_id(request: Request) -> int | None:
    """Получить ID текущего пользователя из состояния запроса"""
    return getattr(request.state, 'user_id', None)


def get_current_user_role(request: Request) -> str | None:
    """Получить роль текущего пользователя из состояния запроса"""
    return getattr(request.state, 'role', None)


def require_authentication(request: Request) -> User:
    """Требует аутентификации пользователя"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется аутентификация"
        )
    return user


def require_active_user(request: Request) -> User:
    """Требует активного пользователя"""
    user = require_authentication(request)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован"
        )
    return user


def require_superuser(request: Request) -> User:
    """Требует суперпользователя"""
    user = require_active_user(request)
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права суперпользователя",
        )
    return user


def require_admin(request: Request) -> User:
    """Требует администратора"""
    user = require_active_user(request)
    if user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )
    return user


def require_doctor_or_admin(request: Request) -> User:
    """Требует врача или администратора"""
    user = require_active_user(request)
    if user.role not in ["Admin", "Doctor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права врача или администратора",
        )
    return user


def require_staff(request: Request) -> User:
    """Требует сотрудника клиники"""
    user = require_active_user(request)
    # E-4 (Receptionist alias removal): the legacy spelling dropped —
    # canonical vocabulary only (stored Receptionist rows = 0, §4.1.27).
    if user.role not in ["Admin", "Doctor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права сотрудника клиники",
        )
    return user


def get_optional_user(request: Request) -> User | None:
    """Получить пользователя, если он аутентифицирован (опционально)"""
    return get_current_user_from_request(request)


def validate_token(token: str, db: Session) -> dict | None:
    """Валидирует JWT токен"""
    if not get_authentication_service:
        return None

    try:
        auth_service = get_authentication_service()
        payload = auth_service.verify_token(token, "access")
        return payload
    except Exception:
        return None


def get_user_from_token(token: str, db: Session) -> User | None:
    """Получить пользователя по токену"""
    payload = validate_token(token, db)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        return db.query(User).filter(User.id == int(user_id)).first()
    except (ValueError, TypeError):
        return None
