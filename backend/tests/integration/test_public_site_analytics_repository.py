"""Exercise the aggregate-only reporting repository against real PostgreSQL."""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

import app.db.base  # noqa: F401 - register the ORM metadata
from app.db.base_class import Base
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
)
from app.models.public_site_analytics import (
    PublicSiteAnalyticsEvent,
    PublicSiteDailyCount,
)
from app.models.service import Service
from app.repositories.public_site_analytics_repository import (
    PublicSiteAnalyticsRepository,
)
from tests._pg_admin_guard import is_local_admin_dsn

pytestmark = pytest.mark.integration

FIRST_DAY = date(2026, 10, 26)
TODAY = date(2026, 11, 24)
FIRST_DAY_START = datetime(2026, 10, 25, 19, tzinfo=UTC)
TODAY_START = datetime(2026, 11, 23, 19, tzinfo=UTC)
AS_OF = datetime(2026, 11, 23, 20, 30, tzinfo=UTC)
TOMORROW_START = datetime(2026, 11, 24, 19, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)


@pytest.fixture
def analytics_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not is_local_admin_dsn(raw_url):
        pytest.skip("public site analytics proof requires loopback PostgreSQL")

    url = make_url(raw_url)
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_site_analytics_" + uuid4().hex
    with_schema = create_engine(
        url,
        connect_args={
            "options": (
                f"-csearch_path={schema} -cstatement_timeout=10000 "
                "-clock_timeout=10000 -ctimezone=America/Los_Angeles"
            )
        },
    )
    admin = create_engine(url)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            Base.metadata.create_all(with_schema)
            yield with_schema
        finally:
            with_schema.dispose()
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


def test_concurrent_first_increments_share_one_daily_total(analytics_pg_engine):
    engine = analytics_pg_engine
    competing_pid: Future[int] = Future()

    def increment_from_another_transaction():
        with Session(engine) as db:
            competing_pid.set_result(
                db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            PublicSiteAnalyticsRepository(db).increment(
                event_code=PublicSiteAnalyticsEvent.SITE_VIEW, observed_at=AS_OF
            )
            db.commit()

    with ThreadPoolExecutor(max_workers=1) as executor, Session(engine) as writer:
        writer_pid = writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
        PublicSiteAnalyticsRepository(writer).increment(
            event_code=PublicSiteAnalyticsEvent.SITE_VIEW, observed_at=AS_OF
        )
        competing_write = executor.submit(increment_from_another_transaction)
        other_pid = competing_pid.result(timeout=5)
        assert other_pid != writer_pid
        with engine.connect() as observer:
            deadline = monotonic() + 5
            while True:
                blockers = observer.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": other_pid}
                ).scalar_one()
                if writer_pid in blockers:
                    break
                assert not competing_write.done(), "write ended before lock wait"
                assert monotonic() < deadline, "no lock wait seen"
                sleep(0.02)
        writer.commit()
        competing_write.result(timeout=5)

    with Session(engine) as db:
        rows = db.execute(
            select(
                PublicSiteDailyCount.clinic_day,
                PublicSiteDailyCount.event_code,
                PublicSiteDailyCount.total,
            )
        ).all()
    assert rows == [(TODAY, PublicSiteAnalyticsEvent.SITE_VIEW, 2)]


def test_clinic_day_window_is_ordered_zero_filled_and_expires_only_old_totals(
    analytics_pg_engine,
):
    with Session(analytics_pg_engine) as db:
        repo = PublicSiteAnalyticsRepository(db)
        for event, observed_at in (
            (PublicSiteAnalyticsEvent.SITE_VIEW, FIRST_DAY_START - ONE_SECOND),
            (PublicSiteAnalyticsEvent.SITE_VIEW, FIRST_DAY_START),
            (PublicSiteAnalyticsEvent.SITE_VIEW, TODAY_START - ONE_SECOND),
            (PublicSiteAnalyticsEvent.PHONE_CLICK, TODAY_START),
            (PublicSiteAnalyticsEvent.BOOKING_FORM_OPEN, TODAY_START),
            (PublicSiteAnalyticsEvent.SITE_VIEW, TOMORROW_START),
        ):
            repo.increment(event_code=event, observed_at=observed_at)

        report = repo.read_daily_totals(as_of=AS_OF)
        assert [row.clinic_day for row in report] == [
            FIRST_DAY + timedelta(days=offset) for offset in range(30)
        ]
        assert [row.site_views for row in report] == [1] + [0] * 27 + [1, 0]
        assert [row.phone_clicks for row in report] == [0] * 29 + [1]
        assert [row.booking_form_opens for row in report] == [0] * 29 + [1]
        assert [row.booking_requests_submitted for row in report] == [0] * 30

        assert repo.delete_older_than_retention(as_of=AS_OF) == 1
        db.commit()
        remaining_days = list(
            db.scalars(
                select(PublicSiteDailyCount.clinic_day)
                .distinct()
                .order_by(PublicSiteDailyCount.clinic_day)
            )
        )
        assert remaining_days == [
            FIRST_DAY,
            TODAY - timedelta(days=1),
            TODAY,
            TODAY + timedelta(days=1),
        ]


def test_report_counts_original_requests_without_counting_later_activity(
    analytics_pg_engine,
):
    with Session(analytics_pg_engine) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC-Analytics")
        doctor = Doctor(specialty="cardiology")
        service = Service(name="SYNTHETIC-Analytics service")
        db.add_all([patient, doctor, service])
        db.flush()
        slot_date = TODAY + timedelta(days=7)
        requests = [
            PublicBookingRequest(
                patient_id=patient.id,
                doctor_id=doctor.id,
                service_id=service.id,
                appointment_date=slot_date,
                appointment_time=time(hour),
                settings_version=1,
                created_at=created_at,
                updated_at=updated_at,
                status=status,
            )
            for hour, (created_at, updated_at, status) in enumerate(
                (
                    (
                        FIRST_DAY_START - ONE_SECOND,
                        FIRST_DAY_START - ONE_SECOND,
                        "pending",
                    ),
                    (FIRST_DAY_START, AS_OF, "withdrawn"),
                    (TODAY_START, TODAY_START, "pending"),
                    (AS_OF + ONE_SECOND, AS_OF + ONE_SECOND, "pending"),
                    (TOMORROW_START, TOMORROW_START, "pending"),
                ),
                start=9,
            )
        ]
        db.add_all(requests)
        db.flush()
        original = requests[1]
        db.add_all(
            [
                PublicBookingRequestEvent(
                    request_id=original.id,
                    event_type=event_type,
                    from_status=before,
                    to_status=after,
                    requested_appointment_date=original.appointment_date,
                    requested_appointment_time=original.appointment_time,
                    created_at=created_at,
                )
                for event_type, before, after, created_at in (
                    ("submitted", None, "pending", FIRST_DAY_START),
                    (
                        "staff_requested_new_time",
                        "pending",
                        "needs_new_time",
                        TODAY_START,
                    ),
                    (
                        "resubmitted",
                        "needs_new_time",
                        "pending",
                        TODAY_START + ONE_SECOND,
                    ),
                    ("withdrawn", "pending", "withdrawn", AS_OF),
                )
            ]
        )
        db.add(
            Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=slot_date,
                created_at=TODAY_START,
            )
        )
        db.commit()

        repo = PublicSiteAnalyticsRepository(db)
        report = repo.read_daily_totals(as_of=AS_OF)
        assert [row.booking_requests_submitted for row in report] == [1] + [0] * 28 + [
            1
        ]
        assert repo.delete_older_than_retention(as_of=AS_OF) == 0
        assert db.scalar(select(func.count()).select_from(PublicBookingRequest)) == 5
