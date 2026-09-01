"""
Regression: local pytest runs load backend/.env with the production DSN
(conftest sets TESTING=1 and loads dotenv), and the real app fixture calls
init_sentry() — so every error-level log from a local test session shipped
straight to production Sentry (PYTHON-FASTAPI-C "RBAC role check denied"
with url=http://testserver/api/v1/visits/visits). init_sentry must be a
no-op while TESTING is set, and must still initialize without it.
"""

import sentry_sdk
import pytest

from app.core import sentry as sentry_module


@pytest.fixture
def prod_dsn(monkeypatch):
    monkeypatch.setenv(
        "SENTRY_DSN",
        "https://examplePublicKey@o0.ingest.sentry.io/1234567",
    )


def test_init_sentry_noop_under_testing(prod_dsn, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    calls: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append(k))

    sentry_module.init_sentry()

    assert calls == [], "init_sentry must not initialize Sentry under TESTING"


def test_init_sentry_initializes_without_testing(prod_dsn, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    calls: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: calls.append(k))

    sentry_module.init_sentry()

    assert len(calls) == 1
    assert calls[0]["dsn"].startswith("https://")
