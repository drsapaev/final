"""Admin-only API for clinic-wide public booking configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.models.user import User
from app.schemas.public_booking_settings import (
    PublicBookingSettingsOut,
    PublicBookingSettingsUpdate,
)
from app.services.public_booking_settings import (
    PublicBookingSettingsError,
    PublicBookingSettingsService,
)

router = APIRouter()

_ERROR_RESPONSES = {
    409: {"description": "The settings changed; reload before saving."},
    422: {"description": "The requested booking configuration is incomplete."},
    503: {"description": "The stored booking settings are invalid."},
}


def _raise_settings_error(exc: PublicBookingSettingsError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code},
    ) from exc


@router.get(
    "/public-booking-settings",
    response_model=PublicBookingSettingsOut,
    responses={503: _ERROR_RESPONSES[503]},
    operation_id="admin_get_public_booking_settings",
    summary="Get clinic-wide public booking configuration",
)
def get_public_booking_settings(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_active_roles("Admin")),
) -> PublicBookingSettingsOut:
    try:
        return PublicBookingSettingsService(db).get_settings()
    except PublicBookingSettingsError as exc:
        _raise_settings_error(exc)


@router.put(
    "/public-booking-settings",
    response_model=PublicBookingSettingsOut,
    responses=_ERROR_RESPONSES,
    operation_id="admin_update_public_booking_settings",
    summary="Replace clinic-wide public booking configuration",
)
def update_public_booking_settings(
    update: PublicBookingSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Admin")),
) -> PublicBookingSettingsOut:
    try:
        return PublicBookingSettingsService(db).update_settings(
            update=update,
            actor_user_id=current_user.id,
        )
    except PublicBookingSettingsError as exc:
        _raise_settings_error(exc)
