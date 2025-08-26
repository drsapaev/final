from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.setting import Setting
from app.schemas.setting import Setting as SettingSchema
from app.db.session import get_db

router = APIRouter()

@router.get("/settings", response_model=list[SettingSchema])
async def get_settings(
    category: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Setting).where(Setting.category == category))
    return result.scalars().all()
