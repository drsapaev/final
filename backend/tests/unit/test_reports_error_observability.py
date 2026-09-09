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
