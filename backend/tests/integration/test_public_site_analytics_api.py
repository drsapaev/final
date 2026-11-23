"""HTTP boundary coverage for public-site aggregate analytics."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints import public_site_analytics as api
from app.core.config import Settings, settings
from app.main import app
from app.models.public_site_analytics import PublicSiteAnalyticsEvent
from app.models.user import User
from app.repositories.public_site_analytics_repository import PublicSiteDailyTotals
from tests.conftest import mint_access_token

_INGEST = "/api/v1/public-site/analytics/events"
_REPORT = "/api/v1/admin/public-site/analytics"
_ORIGIN = "https://synthetic-site.example.test"
_HEADERS = {"Origin": _ORIGIN, "Content-Type": "text/plain;charset=UTF-8"}


@pytest.fixture
def repo(monkeypatch):
    repository = Mock()
    monkeypatch.setattr(
        api, "PublicSiteAnalyticsRepository", Mock(return_value=repository)
    )
    return repository


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_SITE_ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", [_ORIGIN, "*", "null"])


def _assert_empty_no_store(response, status_code):
    assert response.status_code == status_code
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"


def test_collection_is_disabled_by_default(client, repo, monkeypatch):
    assert Settings.model_fields["PUBLIC_SITE_ANALYTICS_ENABLED"].default is False
    monkeypatch.setattr(settings, "PUBLIC_SITE_ANALYTICS_ENABLED", False)

    response = client.post(_INGEST, content=b"site_view", headers=_HEADERS)

    _assert_empty_no_store(response, 503)
    repo.increment.assert_not_called()


@pytest.mark.parametrize("event", list(PublicSiteAnalyticsEvent))
def test_record_accepts_each_enum_token_and_commits_off_loop(
    client, repo, enabled, db_session, monkeypatch, event
):
    def verify_worker(**_kwargs):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()

    repo.increment.side_effect = verify_worker
    commit = Mock()
    monkeypatch.setattr(db_session, "commit", commit)
    response = client.post(_INGEST, content=event.value, headers=_HEADERS)

    _assert_empty_no_store(response, 204)
    repo.increment.assert_called_once()
    assert repo.increment.call_args.kwargs["event_code"] is event
    assert repo.increment.call_args.kwargs["observed_at"].tzinfo is UTC
    commit.assert_called_once_with()


@pytest.mark.parametrize("origin", [None, "*", "null", "https://other.example.test"])
def test_unapproved_origins_cannot_write(client, repo, enabled, origin):
    headers = {"Content-Type": "text/plain"}
    if origin is not None:
        headers["Origin"] = origin

    response = client.post(_INGEST, content=b"site_view", headers=headers)

    _assert_empty_no_store(response, 403)
    repo.increment.assert_not_called()


@pytest.mark.parametrize(
    ("suffix", "extra_headers", "body", "status_code"),
    [
        ("?unexpected=SYNTHETIC_SENTINEL", {}, b"site_view", 400),
        ("", {"Authorization": "Bearer SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Cookie": "session=SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Proxy-Authorization": "SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Referer": "SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Sentry-Trace": "SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Baggage": "SYNTHETIC_SENTINEL"}, b"site_view", 400),
        ("", {"Content-Type": "application/json"}, b'"site_view"', 415),
        ("", {"Content-Encoding": "gzip"}, b"site_view", 415),
        ("", {}, b"site_view\n", 400),
        ("", {}, b"SYNTHETIC_INVALID", 400),
        ("", {}, b"\xff", 400),
        ("", {}, b"booking_form_open!", 413),
    ],
)
def test_malformed_input_does_not_write_or_echo(
    client, repo, enabled, caplog, suffix, extra_headers, body, status_code
):
    with caplog.at_level(logging.INFO):
        response = client.post(
            _INGEST + suffix, content=body, headers={**_HEADERS, **extra_headers}
        )

    _assert_empty_no_store(response, status_code)
    repo.increment.assert_not_called()
    assert "SYNTHETIC_SENTINEL" not in " ".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.")
    )
    assert "SYNTHETIC_INVALID" not in " ".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.")
    )


def test_stream_limit_applies_without_content_length(client, repo, enabled):
    def chunks():
        yield b"booking_form_open"
        yield b"!"

    response = client.post(_INGEST, content=chunks(), headers=_HEADERS)

    _assert_empty_no_store(response, 413)
    repo.increment.assert_not_called()


def test_record_rolls_back_and_sanitizes_database_failure(
    client, repo, enabled, db_session, monkeypatch, caplog
):
    repo.increment.side_effect = SQLAlchemyError("SYNTHETIC_DATABASE_DETAIL")
    rollback = Mock()
    commit = Mock()
    monkeypatch.setattr(db_session, "rollback", rollback)
    monkeypatch.setattr(db_session, "commit", commit)

    response = client.post(_INGEST, content=b"phone_click", headers=_HEADERS)

    _assert_empty_no_store(response, 503)
    assert "SYNTHETIC_DATABASE_DETAIL" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    rollback.assert_called_once_with()
    commit.assert_not_called()


@pytest.mark.parametrize(
    ("role", "superuser", "active"),
    [
        ("Doctor", False, True),
        ("Registrar", False, True),
        ("Doctor", True, True),
        ("Admin", False, False),
    ],
)
def test_report_rejects_non_admin_and_inactive_users(
    client, db_session, repo, role, superuser, active
):
    user = User(
        username="synthetic_analytics_identity",
        role=role,
        hashed_password="not-used-by-test",
        is_superuser=superuser,
        is_active=active,
    )
    db_session.add(user)
    db_session.flush()

    response = client.get(
        _REPORT, headers={"Authorization": f"Bearer {mint_access_token(user)}"}
    )

    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    repo.read_daily_totals.assert_not_called()


def test_report_requires_authenticated_identity(client, repo):
    response = client.get(_REPORT)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    repo.read_daily_totals.assert_not_called()


def test_admin_report_is_an_aggregate_read_when_collection_disabled(
    client, repo, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "PUBLIC_SITE_ANALYTICS_ENABLED", False)
    first_day = date(2001, 1, 1)
    repo.read_daily_totals.return_value = [
        PublicSiteDailyTotals(
            clinic_day=first_day + timedelta(days=index),
            site_views=index,
            phone_clicks=index,
            booking_form_opens=index,
            booking_requests_submitted=index,
        )
        for index in range(30)
    ]

    response = client.get(_REPORT, headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "enabled": False,
        "days": [
            {
                "clinic_day": (first_day + timedelta(days=index)).isoformat(),
                "site_views": index,
                "phone_clicks": index,
                "booking_form_opens": index,
                "booking_requests_submitted": index,
            }
            for index in range(30)
        ],
    }
    repo.read_daily_totals.assert_called_once()
    assert repo.read_daily_totals.call_args.kwargs["as_of"].tzinfo is UTC


def test_report_sanitizes_database_failure(client, repo, auth_headers, caplog):
    repo.read_daily_totals.side_effect = SQLAlchemyError("SYNTHETIC_DATABASE_DETAIL")

    response = client.get(_REPORT, headers=auth_headers)

    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["detail"] == "Public site analytics unavailable"
    assert "SYNTHETIC_DATABASE_DETAIL" not in caplog.text


def test_analytics_openapi_describes_enum_and_strict_report_shape():
    schema = app.openapi()
    ingest = schema["paths"][_INGEST]["post"]
    report = schema["paths"][_REPORT]["get"]

    assert ingest["operationId"] == "record_public_site_analytics_event"
    assert "security" not in ingest
    assert "422" not in ingest["responses"]
    assert "content" not in ingest["responses"]["204"]
    assert ingest["requestBody"] == {
        "required": True,
        "content": {
            "text/plain": {
                "schema": {
                    "type": "string",
                    "enum": [event.value for event in PublicSiteAnalyticsEvent],
                    "maxLength": 17,
                }
            }
        },
    }
    assert report["operationId"] == "admin_get_public_site_analytics"
    assert report["security"]
    assert report["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicSiteAnalyticsReportOut"
    }
    assert set(
        schema["components"]["schemas"]["PublicSiteAnalyticsDayOut"]["properties"]
    ) == {
        "clinic_day",
        "site_views",
        "phone_clicks",
        "booking_form_opens",
        "booking_requests_submitted",
    }
