from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.setting import Setting as SettingSchema
from app.services.setting_endpoint_service import SettingDomainError, SettingService

router = APIRouter()


@router.get("/settings", response_model=list[SettingSchema])
def get_settings(
    category: str = Query(..., description="Category of settings"),
    db: Session = Depends(get_db),
):
    """
    Return list of settings for given category.
    Example: GET /api/v1/settings?category=printer
    """
    service = SettingService(db)
    try:
        return service.get_settings(category=category)
    except SettingDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.detail
        ) from exc
