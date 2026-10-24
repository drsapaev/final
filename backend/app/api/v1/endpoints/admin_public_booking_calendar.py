"""Admin-only API for the annual public-booking holiday calendar."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.public_booking_calendar import (
    PublicBookingCalendarConfirm,
    PublicBookingCalendarErrorOut,
    PublicBookingCalendarUpdate,
    PublicBookingCalendarYearOut,
)
from app.services.public_booking_calendar_settings import (
    PublicBookingCalendarSettingsError,
    PublicBookingCalendarSettingsService,
)

router = APIRouter()

_CALENDAR_ERROR_RESPONSES = {
    409: {
        "model": PublicBookingCalendarErrorOut,
        "description": "The calendar changed or must be saved before confirmation.",
    },
    503: {
        "model": PublicBookingCalendarErrorOut,
        "description": "The saved calendar settings are invalid.",
    },
}


def _raise_calendar_error(exc: PublicBookingCalendarSettingsError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code},
    ) from exc


@router.get(
    "/public-booking-calendar/{year}",
    response_model=PublicBookingCalendarYearOut,
    responses=_CALENDAR_ERROR_RESPONSES,
    operation_id="admin_get_public_booking_calendar_year",
    summary="Get an annual public booking calendar",
)
def get_public_booking_calendar_year(
    year: Annotated[int, Path(ge=2000, le=2200)],
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("Admin")),
) -> PublicBookingCalendarYearOut:
    try:
        return PublicBookingCalendarSettingsService(db).get_year(year)
    except PublicBookingCalendarSettingsError as exc:
        _raise_calendar_error(exc)


@router.put(
    "/public-booking-calendar/{year}",
    response_model=PublicBookingCalendarYearOut,
    responses=_CALENDAR_ERROR_RESPONSES,
    operation_id="admin_update_public_booking_calendar_year",
    summary="Replace official holidays for a booking calendar year",
)
def update_public_booking_calendar_year(
    year: Annotated[int, Path(ge=2000, le=2200)],
    update: PublicBookingCalendarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> PublicBookingCalendarYearOut:
    try:
        return PublicBookingCalendarSettingsService(db).update_holidays(
            year=year,
            update=update,
            actor_user_id=current_user.id,
        )
    except PublicBookingCalendarSettingsError as exc:
        _raise_calendar_error(exc)


@router.post(
    "/public-booking-calendar/{year}/confirm",
    response_model=PublicBookingCalendarYearOut,
    responses=_CALENDAR_ERROR_RESPONSES,
    operation_id="admin_confirm_public_booking_calendar_year",
    summary="Confirm that an annual holiday calendar is complete",
)
def confirm_public_booking_calendar_year(
    year: Annotated[int, Path(ge=2000, le=2200)],
    confirmation: PublicBookingCalendarConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> PublicBookingCalendarYearOut:
    try:
        return PublicBookingCalendarSettingsService(db).confirm_year(
            year=year,
            expected_version=confirmation.expected_version,
            actor_user_id=current_user.id,
        )
    except PublicBookingCalendarSettingsError as exc:
        _raise_calendar_error(exc)
