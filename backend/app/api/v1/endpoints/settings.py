from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.setting import Setting as SettingSchema
from app.services.setting_api_service import SettingApiDomainError, SettingApiService

router = APIRouter()


class SettingUpsertIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field("", max_length=500)


@router.get("/settings", response_model=list[SettingSchema])
def get_settings(
    category: str = Query(..., description="Category of settings"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Return list of settings for given category.
    Example: GET /api/v1/settings?category=printer
    """
    service = SettingApiService(db)
    try:
        return service.get_settings(category=category)
    except SettingApiDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.detail
        ) from exc


@router.put("/settings", response_model=SettingSchema)
def upsert_setting(
    payload: SettingUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Create or update one generic key/value setting for the admin settings page."""
    service = SettingApiService(db)
    try:
        return service.upsert_setting(
            category=payload.category,
            key=payload.key,
            value=payload.value,
        )
    except SettingApiDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.detail
        ) from exc
