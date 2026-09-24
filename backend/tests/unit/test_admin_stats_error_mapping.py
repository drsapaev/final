from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event

import app.api.v1.endpoints.admin_stats as admin_stats_module
from app.api.v1.endpoints.admin_stats import (
    get_activity_chart,
    get_admin_stats,
    get_analytics_charts,
    get_analytics_overview,
    get_quick_stats,
)
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment_webhook import PaymentWebhook
from app.models.user import User
from app.models.visit import Visit


class _BrokenDb:
    def query(self, *args, **kwargs):
        raise RuntimeError("sensitive internal diagnostic")


@pytest.mark.parametrize(
    "call_endpoint",
    [
        lambda db: get_admin_stats(db=db, _=object()),
        lambda db: get_quick_stats(db=db, _=object()),
        lambda db: get_activity_chart(days=1, db=db, _=object()),
        lambda db: get_analytics_overview(
            period="week",
            department=None,
            doctor_id=None,
            db=db,
            _=object(),
        ),
        lambda db: get_analytics_charts(
            period="week",
            chart_type="appointments",
            department=None,
            db=db,
            _=object(),
        ),
    ],
)
def test_admin_stats_500_errors_do_not_expose_exception_text(
    call_endpoint: Callable[[_BrokenDb], object],
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        call_endpoint(_BrokenDb())

    assert exc_info.value.status_code == 500
    assert "sensitive internal diagnostic" not in str(exc_info.value.detail)


def _get_stats_with_select_count(db_session):
    select_count = 0
    engine = db_session.get_bind().engine

    def count_selects(conn, cursor, statement, parameters, context, executemany):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        result = get_admin_stats(db=db_session, _=object())
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert select_count == 2
    datetime.fromisoformat(result["generatedAt"])
    return result


def test_admin_stats_empty_database_uses_two_selects(db_session):
    result = _get_stats_with_select_count(db_session)

    assert {key: value for key, value in result.items() if key != "generatedAt"} == {
        "totalUsers": 0,
        "totalDoctors": 0,
        "totalPatients": 0,
        "totalRevenue": 0.0,
        "appointmentsToday": 0,
        "visitsToday": 0,
        "pendingApprovals": 0,
        "newPatientsToday": 0,
        "roleStats": dict.fromkeys(
            ("admin", "registrar", "doctor", "cashier", "lab", "cardio", "derma", "dentist"),
            0,
        ),
    }


def test_admin_stats_nonempty_database_preserves_aggregate_filters(
    db_session, monkeypatch
):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = cls(2025, 1, 15, 12, tzinfo=UTC)
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(admin_stats_module, "datetime", FixedDateTime)
    today = FixedDateTime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    today_noon = datetime.combine(today, time(hour=12))
    yesterday_noon = datetime.combine(yesterday, time(hour=12))
    patient_today = Patient(
        last_name="SYNTHETIC-TODAY", first_name="TEST", created_at=today_noon
    )
    patient_yesterday = Patient(
        last_name="SYNTHETIC-YESTERDAY", first_name="TEST", created_at=yesterday_noon
    )
    db_session.add_all(
        [
            User(username="synthetic_admin", hashed_password="unused", role="Admin"),
            User(username="synthetic_doctor", hashed_password="unused", role="Doctor"),
            patient_today,
            patient_yesterday,
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            Appointment(
                patient_id=patient_today.id, appointment_date=today, status="scheduled"
            ),
            Appointment(
                patient_id=patient_yesterday.id,
                appointment_date=yesterday,
                status="pending",
            ),
            Visit(patient_id=patient_today.id, created_at=today_noon),
            Visit(patient_id=patient_yesterday.id, created_at=yesterday_noon),
            PaymentWebhook(
                provider="test",
                webhook_id="synthetic-processed",
                transaction_id="synthetic-processed",
                status="processed",
                amount=12345,
                raw_data={},
            ),
            PaymentWebhook(
                provider="test",
                webhook_id="synthetic-pending",
                transaction_id="synthetic-pending",
                status="pending",
                amount=99999,
                raw_data={},
            ),
        ]
    )
    db_session.flush()

    result = _get_stats_with_select_count(db_session)

    assert {key: value for key, value in result.items() if key != "generatedAt"} == {
        "totalUsers": 2,
        "totalDoctors": 1,
        "totalPatients": 2,
        "totalRevenue": 123.45,
        "appointmentsToday": 1,
        "visitsToday": 1,
        "pendingApprovals": 1,
        "newPatientsToday": 1,
        "roleStats": {
            "admin": 1,
            "registrar": 0,
            "doctor": 1,
            "cashier": 0,
            "lab": 0,
            "cardio": 0,
            "derma": 0,
            "dentist": 0,
        },
    }
