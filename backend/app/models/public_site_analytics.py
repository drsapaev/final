"""Aggregate public-site interactions for a clinic calendar day."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, Date, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PublicSiteAnalyticsEvent(StrEnum):
    SITE_VIEW = "site_view"
    PHONE_CLICK = "phone_click"
    BOOKING_FORM_OPEN = "booking_form_open"


class PublicSiteDailyCount(Base):
    __tablename__ = "public_site_daily_counts"
    __table_args__ = (
        PrimaryKeyConstraint(
            "clinic_day", "event_code", name="pk_public_site_daily_counts"
        ),
        CheckConstraint(
            "event_code IN ('site_view', 'phone_click', 'booking_form_open')",
            name="ck_public_site_daily_counts_event_code",
        ),
        CheckConstraint("total > 0", name="ck_public_site_daily_counts_total"),
    )

    clinic_day: Mapped[date] = mapped_column(Date, nullable=False)
    event_code: Mapped[str] = mapped_column(String(24), nullable=False)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False)
