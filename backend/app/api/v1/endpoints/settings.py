from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# МОДЕЛИ/СХЕМЫ — как в проекте
from app.models.setting import Setting
from app.schemas.setting import SettingSchema

router = APIRouter()

# ===== ЛОКАЛЬНАЯ ЗАВИСИМОСТЬ get_db (не ломая остальной проект) =====
# Пытаемся подцепить любую из распространённых фабрик/депенденси из app.db.session.
# Это защищает от различий между проектами (AsyncSessionLocal / async_session_maker / async_session / get_async_session).
_SessionMaker: Optional[object] = None
_AltMaker1: Optional[object] = None
_AltMaker2: Optional[object] = None
_get_async_session = None

try:
    from app.db.session import AsyncSessionLocal as _SessionMaker  # type: ignore
except Exception:
    pass

try:
    from app.db.session import async_session_maker as _AltMaker1  # type: ignore
except Exception:
    pass

try:
    from app.db.session import async_session as _AltMaker2  # type: ignore
except Exception:
    pass

try:
    from app.db.session import get_async_session as _get_async_session  # type: ignore
except Exception:
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Универсальная зависимость получения AsyncSession:
    1) если есть get_async_session() -> используем её;
    2) иначе пытаемся вызвать одну из фабрик: AsyncSessionLocal / async_session_maker / async_session.
    """
    if _get_async_session:
        # Некоторые проекты определяют именно этот генератор-­депенденси
        async for session in _get_async_session():
            yield session
        return

    maker = _SessionMaker or _AltMaker1 or _AltMaker2
    if maker is None:
        raise RuntimeError(
            "Не найдено ни одной фабрики сессий в app.db.session "
            "(ожидались AsyncSessionLocal/async_session_maker/async_session/get_async_session)"
        )

    # maker может быть sessionmaker или функцией, которую нужно вызвать
    if callable(maker):
        async with maker() as session:  # type: ignore
            yield session
    else:
        # крайне редкий случай, если maker уже контекст/сессия
        async with maker as session:  # type: ignore
            yield session


# ===== ЭНДПОИНТЫ =====

@router.get("/settings", response_model=List[SettingSchema])
async def get_settings(
    category: str = Query(..., description="Категория настроек"),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список настроек по категории.
    Пример: GET /api/v1/settings?category=printer
    """
    result = await db.execute(select(Setting).where(Setting.category == category))
    return result.scalars().all()
