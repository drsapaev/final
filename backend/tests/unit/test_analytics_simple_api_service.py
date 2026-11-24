from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.analytics_simple_api_service import (
    AnalyticsSimpleApiService,
    AnalyticsSimpleDomainError,
)


@pytest.mark.unit
class TestAnalyticsSimpleApiService:
    def test_get_quick_stats_returns_expected_payload(self):
        repository = SimpleNamespace(
            count_patients=lambda: 7,
            count_appointments_for_date=lambda target_date: 3
            if target_date == date.today()
            else 0,
            count_appointments=lambda: 12,
            count_payments=lambda: 4,
        )
        service = AnalyticsSimpleApiService(db=None, repository=repository)

        result = service.get_quick_stats()

        assert result["total_patients"] == 7
        assert result["today_appointments"] == 3
        assert result["total_appointments"] == 12
        assert result["total_payments"] == 4
        assert result["date"] == date.today().isoformat()

    def test_get_dashboard_data_uses_today_and_tomorrow(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        repository = SimpleNamespace(
            count_patients=lambda: 11,
            count_appointments=lambda: 33,
            count_payments=lambda: 22,
            count_appointments_for_date=lambda target_date: {
                today: 5,
                tomorrow: 9,
            }.get(target_date, 0),
        )
        service = AnalyticsSimpleApiService(db=None, repository=repository)

        result = service.get_dashboard_data()

        assert result["overview"]["total_patients"] == 11
        assert result["overview"]["total_appointments"] == 33
        assert result["overview"]["total_payments"] == 22
        assert result["today"]["appointments"] == 5
        assert result["tomorrow"]["appointments"] == 9

    def test_get_trends_analytics_formats_rows(self):
        today = date.today()
        row = SimpleNamespace(date=today, count=8)
        repository = SimpleNamespace(
            list_appointment_trends=lambda start_date, end_date: [row]
        )
        service = AnalyticsSimpleApiService(db=None, repository=repository)

        result = service.get_trends_analytics(days=10)

        assert result["period_days"] == 10
        assert result["trends"] == [{"date": today.isoformat(), "appointments": 8}]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("operation", "repository_method", "kwargs"),
    [
        ("get_quick_stats", "count_patients", {}),
        ("get_dashboard_data", "count_patients", {}),
        ("get_trends_analytics", "list_appointment_trends", {"days": 10}),
    ],
)
def test_analytics_failures_keep_repository_details_private(
    operation,
    repository_method,
    kwargs,
    caplog,
):
    marker = "SYNTHETIC_REPOSITORY_FAILURE_DETAILS"

    def fail(*args, **kwargs):
        raise RuntimeError(marker)

    repository = SimpleNamespace(**{repository_method: fail})
    service = AnalyticsSimpleApiService(db=None, repository=repository)

    with pytest.raises(AnalyticsSimpleDomainError) as error:
        getattr(service, operation)(**kwargs)

    assert error.value.status_code == 500
    assert error.value.detail == "Internal server error"
    assert error.value.__suppress_context__ is True
    assert marker not in caplog.text
    assert "error_type=RuntimeError" in caplog.text
