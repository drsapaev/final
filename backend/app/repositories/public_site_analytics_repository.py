"""Atomic writes and date-bounded, aggregate-only reads for site analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.public_booking_request import PublicBookingRequest
from app.models.public_site_analytics import (
    PublicSiteAnalyticsEvent,
    PublicSiteDailyCount,
)
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE

_PUBLIC_SITE_RETENTION_DAYS = 30


@dataclass(frozen=True)
class PublicSiteDailyTotals:
    clinic_day: date
    site_views: int
    phone_clicks: int
    booking_form_opens: int
    booking_requests_submitted: int


def _clinic_day(instant: datetime) -> date:
    if instant.utcoffset() is None:
        raise ValueError("Public site analytics requires a timezone-aware timestamp.")
    return instant.astimezone(PUBLIC_BOOKING_TIMEZONE).date()


def _first_retained_day(clinic_day: date) -> date:
    return clinic_day - timedelta(days=_PUBLIC_SITE_RETENTION_DAYS - 1)


class PublicSiteAnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def increment(
        self, *, event_code: PublicSiteAnalyticsEvent, observed_at: datetime
    ) -> None:
        stmt = insert(PublicSiteDailyCount).values(
            clinic_day=_clinic_day(observed_at),
            event_code=PublicSiteAnalyticsEvent(event_code).value,
            total=1,
        )
        self.db.execute(
            stmt.on_conflict_do_update(
                index_elements=[
                    PublicSiteDailyCount.clinic_day,
                    PublicSiteDailyCount.event_code,
                ],
                set_={"total": PublicSiteDailyCount.total + 1},
            )
        )

    def read_daily_totals(self, *, as_of: datetime) -> list[PublicSiteDailyTotals]:
        today = _clinic_day(as_of)
        first_day = _first_retained_day(today)
        browser_counts = {
            (clinic_day, code): total
            for clinic_day, code, total in self.db.execute(
                select(
                    PublicSiteDailyCount.clinic_day,
                    PublicSiteDailyCount.event_code,
                    PublicSiteDailyCount.total,
                ).where(PublicSiteDailyCount.clinic_day.between(first_day, today))
            )
        }

        # Count each persisted request once on its original submission day.
        # Filtering the original timestamp avoids a timezone cast in the WHERE.
        created_at = PublicBookingRequest.created_at
        submitted_day = cast(
            func.timezone(PUBLIC_BOOKING_TIMEZONE.key, created_at), Date
        )
        first_instant = datetime.combine(first_day, time.min, PUBLIC_BOOKING_TIMEZONE)
        submitted_counts = dict(
            self.db.execute(
                select(submitted_day, func.count())
                .where(created_at >= first_instant, created_at <= as_of)
                .group_by(submitted_day)
            ).all()
        )

        days = (
            first_day + timedelta(days=offset)
            for offset in range(_PUBLIC_SITE_RETENTION_DAYS)
        )
        return [
            PublicSiteDailyTotals(
                clinic_day=day,
                site_views=browser_counts.get(
                    (day, PublicSiteAnalyticsEvent.SITE_VIEW), 0
                ),
                phone_clicks=browser_counts.get(
                    (day, PublicSiteAnalyticsEvent.PHONE_CLICK), 0
                ),
                booking_form_opens=browser_counts.get(
                    (day, PublicSiteAnalyticsEvent.BOOKING_FORM_OPEN), 0
                ),
                booking_requests_submitted=submitted_counts.get(day, 0),
            )
            for day in days
        ]

    def delete_older_than_retention(self, *, as_of: datetime) -> int:
        first_day = _first_retained_day(_clinic_day(as_of))
        result = self.db.execute(
            delete(PublicSiteDailyCount.__table__).where(
                PublicSiteDailyCount.clinic_day < first_day
            )
        )
        return result.rowcount
