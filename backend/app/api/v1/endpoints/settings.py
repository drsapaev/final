from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.setting import Setting
from app.schemas.setting import Setting as SettingSchema

router = APIRouter()


@router.get("/settings", response_model=List[SettingSchema])
def get_settings(
    category: str = Query(..., description="Category of settings"),
    db: Session = Depends(get_db),
):
    """
    Return list of settings for given category.
    Example: GET /api/v1/settings?category=printer
    """
    try:
        stmt = select(Setting).where(Setting.category == category)
        result = db.execute(stmt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )

    return result.scalars().all()
