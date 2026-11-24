"""Privacy checks for the fixed public-site aggregate intake path."""

import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from slowapi import Limiter

from app.core import rate_limiter
from app.core.config import get_settings
from app.core.pii_masker import PUBLIC_SITE_ANALYTICS_INGEST_PATH
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.csrf_middleware import CSRFMiddleware
from app.middleware.idempotency_middleware import IdempotencyMiddleware
from app.middleware.observability_middleware import ObservabilityMiddleware
from app.middleware.public_site_analytics_middleware import (
    PublicSiteAnalyticsIntakeMiddleware,
)
from tests.unit.test_sentry_sanitization import _make_before_send

INGEST = PUBLIC_SITE_ANALYTICS_INGEST_PATH
NEIGHBOR = f"{INGEST}/other"
INPUT_MARKER = "synthetic_input_marker"


def test_only_the_analytics_intake_bypasses_request_tracking_and_csrf():
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(ObservabilityMiddleware)

    @app.post(INGEST)
    def limited():
        return Response(status_code=429, headers={"Cache-Control": "public"})

    @app.post(NEIGHBOR)
    def neighbor():
        return Response(status_code=204)

    with TestClient(app) as client:
        with (
            patch.object(AuditMiddleware, "_audit_log_request") as audit,
            patch.object(ObservabilityMiddleware, "_extract_client_ip") as client_ip,
        ):
            response = client.post(
                INGEST,
                params={"unexpected": INPUT_MARKER},
                headers={"X-Forwarded-For": "192.0.2.8"},
            )
            assert response.status_code == 429
            assert response.headers["Cache-Control"] == "no-store"
            assert "X-Request-ID" not in response.headers
            assert "X-Trace-ID" not in response.headers
            audit.assert_not_called()
            client_ip.assert_not_called()

        assert client.post(NEIGHBOR).status_code == 403
        assert client.post(f"{INGEST}/", follow_redirects=False).status_code == 403

        with patch.object(AuditMiddleware, "_audit_log_request") as audit:
            client.cookies.set("csrf_token", "test-csrf")
            response = client.post(NEIGHBOR, headers={"X-CSRF-Token": "test-csrf"})
            assert response.status_code == 204
            assert "X-Request-ID" in response.headers
            audit.assert_called_once()


def test_analytics_intake_rejects_keys_and_oversized_bodies_before_reading():
    from app.main import app as deployed_app

    middleware = [entry.cls for entry in deployed_app.user_middleware]
    assert middleware.index(PublicSiteAnalyticsIntakeMiddleware) < middleware.index(
        IdempotencyMiddleware
    )

    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(PublicSiteAnalyticsIntakeMiddleware)

    @app.post(INGEST)
    async def record(request: Request):
        await request.body()
        return Response(status_code=204)

    with TestClient(app) as client, patch.object(Request, "body") as read_body:
        keyed = client.post(
            INGEST, content=b"site_view", headers={"Idempotency-Key": "synthetic"}
        )
        oversized = client.post(INGEST, content=b"x" * 18)
        for response, status_code in [(keyed, 400), (oversized, 413)]:
            assert response.status_code == status_code
            assert response.headers["Cache-Control"] == "no-store"
            assert response.content == b""

        read_body.assert_not_called()
        valid = client.post(INGEST, content=b"booking_form_open")
        assert valid.status_code == 204
        read_body.assert_called_once()


@pytest.mark.parametrize("callback_name", ["before_send", "before_send_transaction"])
def test_sentry_callbacks_drop_only_analytics_intake(monkeypatch, callback_name):
    callback = _make_before_send(monkeypatch, callback_name=callback_name)
    encoded = INGEST.replace("/events", "/%65vents")
    event = {
        "request": {
            "url": f"https://testserver{encoded}?unexpected={INPUT_MARKER}",
            "body": INPUT_MARKER,
        }
    }
    assert callback(event, {}) is None
    assert callback({"transaction": f"POST {INGEST}"}, {}) is None
    assert callback({"transaction": f"POST {NEIGHBOR}"}, {}) is not None


def test_analytics_rate_limit_preserves_the_limit_without_logging_the_client(
    monkeypatch, caplog
):
    peer = "192.0.2.28"
    isolated_limiter = Limiter(
        key_func=rate_limiter.get_client_ip, storage_uri="memory://"
    )
    monkeypatch.setattr(rate_limiter, "limiter", isolated_limiter)
    monkeypatch.setattr(rate_limiter, "TRUSTED_PROXIES", set())
    monkeypatch.setattr(get_settings(), "TESTING", False)

    app = FastAPI()
    rate_limiter.setup_rate_limiting(app)

    @isolated_limiter.limit("1/minute")
    def limited(request: Request) -> Response:
        return Response(status_code=204)

    app.add_api_route(INGEST, limited, methods=["POST"])
    app.add_api_route(NEIGHBOR, limited, methods=["POST"])

    with (
        caplog.at_level(logging.WARNING, logger="slowapi"),
        TestClient(app, client=(peer, 50000)) as client,
        TestClient(app, client=("192.0.2.29", 50000)) as other_client,
    ):
        assert client.post(INGEST).status_code == 204
        rejected = client.post(INGEST)
        assert rejected.status_code == 429
        assert int(rejected.headers["Retry-After"]) > 0
        assert other_client.post(INGEST).status_code == 204
        assert client.post(NEIGHBOR).status_code == 204
        assert client.post(NEIGHBOR).status_code == 429

    analytics_warning, neighbor_warning = [
        record for record in caplog.records if record.name == "slowapi"
    ]
    assert analytics_warning.getMessage().endswith(f"exceeded at endpoint: {INGEST}")
    assert peer not in analytics_warning.getMessage()
    assert peer not in repr(analytics_warning.args)
    assert (
        neighbor_warning.getMessage()
        == f"ratelimit 1 per 1 minute ({peer}) exceeded at endpoint: {NEIGHBOR}"
    )


def test_analytics_rate_limit_hides_invalid_forwarded_value(monkeypatch, caplog):
    trusted_peer = "192.0.2.40"
    invalid_marker = "synthetic_invalid_forwarded_value"
    monkeypatch.setattr(rate_limiter, "TRUSTED_PROXIES", {trusted_peer})

    with caplog.at_level(logging.WARNING, logger=rate_limiter.__name__):
        for path in (INGEST, NEIGHBOR):
            request = Request(
                {
                    "type": "http",
                    "path": path,
                    "client": (trusted_peer, 50000),
                    "headers": [(b"x-forwarded-for", invalid_marker.encode("ascii"))],
                }
            )
            assert rate_limiter.get_client_ip(request) == trusted_peer

    analytics_warning, neighbor_warning = [
        record for record in caplog.records if record.name == rate_limiter.__name__
    ]
    assert "Invalid IP in X-Forwarded-For header" in analytics_warning.getMessage()
    assert invalid_marker not in analytics_warning.getMessage()
    assert invalid_marker not in repr(analytics_warning.args)
    assert (
        neighbor_warning.getMessage()
        == f"Invalid IP in X-Forwarded-For header: {invalid_marker!r}"
    )
