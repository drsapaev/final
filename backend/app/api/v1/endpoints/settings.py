from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.setting import Setting as SettingSchema
from app.schemas.setting import SettingUpsert
from app.services.setting_api_service import SettingApiDomainError, SettingApiService

router = APIRouter()


@router.get("/settings", response_model=list[SettingSchema])
def get_settings(
    category: str = Query(..., description="Category of settings"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("Admin")),
):
    """
    Return list of settings for given category.
    Example: GET /api/v1/settings?category=printer
    """
    service = SettingApiService(db)
    try:
        return service.get_settings(category=category, limit=limit, offset=offset)
    except SettingApiDomainError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc


@router.put("/settings", response_model=SettingSchema)
def update_setting(
    body: SettingUpsert,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("Admin")),
):
    """
    Upsert a single system setting for the given category/key pair.
    Example: PUT /api/v1/settings {"category":"printer","key":"device_name","value":"HP"}
    """
    service = SettingApiService(db)
    try:
        return service.update_setting(
            category=body.category,
            key=body.key,
            value=body.value,
        )
    except SettingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
