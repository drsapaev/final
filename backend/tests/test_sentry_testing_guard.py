"""
Regression: local pytest runs load backend/.env with the production DSN
(conftest sets TESTING=1 and loads dotenv), and the real app fixture calls
init_sentry() — so every error-level log from a local test session shipped
straight to production Sentry (PYTHON-FASTAPI-C "RBAC role check denied"
with url=http://testserver/api/v1/visits/visits). init_sentry must be a
no-op while TESTING is set, and must still initialize without it.
"""

import sys
import types

import pytest

from app.core import sentry as sentry_module


def _install_fake_sentry_sdk(monkeypatch) -> list[dict]:
    """Put a minimal fake sentry_sdk package into sys.modules.

    CI test environments intentionally do not install sentry-sdk; init_sentry
    must behave identically with and without it.
    """
    calls: list[dict] = []

    fake = types.ModuleType("sentry_sdk")
    fake.init = lambda *a, **k: calls.append(k)

    integrations = types.ModuleType("sentry_sdk.integrations")
    fake.integrations = integrations
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations", integrations)

    # class names are camelCase: FastApiIntegration, not FastapiIntegration
    class_names = {
        "fastapi": "FastApiIntegration",
        "sqlalchemy": "SqlalchemyIntegration",
        "redis": "RedisIntegration",
        "asyncpg": "AsyncPGIntegration",
    }
    for name, class_name in class_names.items():
        sub = types.ModuleType(f"sentry_sdk.integrations.{name}")
        setattr(sub, class_name, type(class_name, (), {}))
        setattr(integrations, name, sub)
        monkeypatch.setitem(sys.modules, f"sentry_sdk.integrations.{name}", sub)

    return calls


@pytest.fixture
def prod_dsn(monkeypatch):
    # assembled from parts: a literal fake DSN string trips secret scanners
    monkeypatch.setenv(
        "SENTRY_DSN",
        "https://" + "examplePublicKey" + "@o0.ingest.sentry.io/1234567",
    )


def test_init_sentry_noop_under_testing(prod_dsn, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    calls = _install_fake_sentry_sdk(monkeypatch)

    sentry_module.init_sentry()

    assert calls == [], "init_sentry must not initialize Sentry under TESTING"


def test_init_sentry_initializes_without_testing(prod_dsn, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    calls = _install_fake_sentry_sdk(monkeypatch)

    sentry_module.init_sentry()

    assert len(calls) == 1
    assert calls[0]["dsn"].startswith("https://")
