"""Reports endpoints must not swallow 500 root causes.

The nightly 500s on /api/v1/reports/* were invisible in Sentry: the shared
helper logged a bare warning (no traceback) and raised a generic
HTTPException, so only the "request.completed" span event survived. The
helper must log the full stack (exception level) and attach the exception
to Sentry before raising the client-facing 500.
"""

import logging

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.reports import (
    log_report_service_error,
    raise_report_internal_error,
)


@pytest.fixture
def sentry_spy(monkeypatch):
    calls = []
    import app.core.sentry as sentry_module

    def fake_capture(exc, **context):
        calls.append(exc)

    monkeypatch.setattr(sentry_module, "capture_exception", fake_capture)
    return calls


def test_raise_report_internal_error_logs_traceback_and_captures(
    caplog, sentry_spy
):
    original = RuntimeError("boom: queues seed missing")

    with pytest.raises(HTTPException) as exc_info:
        raise_report_internal_error("reports/files", "Ошибка отчетов", original)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Ошибка отчетов"
    assert sentry_spy == [original], "exception was not attached to Sentry"

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and "reports/files" in r.getMessage()
    ]
    assert error_records, "no error-level log record emitted"
    assert error_records[0].exc_info is not None, "traceback not attached"
    assert error_records[0].levelname == "ERROR"


def test_raise_report_internal_error_sentry_failure_does_not_block_500(
    caplog, monkeypatch
):
    import app.core.sentry as sentry_module

    def broken_capture(exc, **context):
        raise RuntimeError("sentry transport down")

    monkeypatch.setattr(sentry_module, "capture_exception", broken_capture)

    with pytest.raises(HTTPException) as exc_info:
        raise_report_internal_error("reports/files", "Ошибка отчетов", RuntimeError("x"))

    assert exc_info.value.status_code == 500
    error_records = [r for r in caplog.records if r.exc_info]
    assert error_records, "stack trace must still reach the log"


def test_log_report_service_error_stays_warning(caplog):
    """The service-returned-error path carries no exception object, so a
    warning (no traceback) is the correct level there."""
    log_report_service_error("daily_summary")

    records = [r for r in caplog.records if "daily_summary" in r.getMessage()]
    assert records and records[0].levelname == "WARNING"
    assert records[0].exc_info is None


class TestDailySummaryErrorExposure:
    """CodeQL py/stack-trace-exposure #1324: generate_daily_summary must
    return a STATIC sentinel on failure — never str(exception). The dict
    flows to GET /api/v1/reports/daily-summary; the endpoint maps any
    "error" key to a 500 with a static detail, but the taint source has
    to go too (CodeQL tracks the whole dict through the return). The
    exception detail belongs to the log/Sentry sink only."""

    def test_error_returns_static_sentinel_and_logs_detail(self, caplog, tmp_path, monkeypatch):
        import app.services.reporting_svc as svc_pkg
        from app.services.reporting_svc import ReportingService

        # Keep the constructor's reports_dir out of the repo working dir.
        monkeypatch.chdir(tmp_path)

        secret_detail = (
            "sqlalchemy internal failure: SELECT visits.visit_date, "
            "patients.phone FROM ... (psycopg2.InternalError)"
        )

        class BoomDB:
            def query(self, *args, **kwargs):
                raise RuntimeError(secret_detail)

        svc = ReportingService(BoomDB())
        with caplog.at_level(logging.ERROR):
            result = svc.generate_daily_summary(None)

        assert result == {"error": "internal_error"}
        assert "sqlalchemy" not in repr(result), "no exception text may leak"
        assert "psycopg2" not in repr(result)

        error_records = [
            r
            for r in caplog.records
            if r.levelno >= logging.ERROR and "ежедневной сводки" in r.getMessage()
        ]
        assert error_records, "detail must reach the log sink"
        assert any(secret_detail in r.getMessage() for r in error_records)
