"""Exercise the health response with an isolated router import and fake DB."""

import runpy
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import health
from app.db import session as db_session

REVISION = "0123456789abcdef0123456789abcdef01234567"
HEALTH_PATH = "/api/v1/health"


def _health_client(monkeypatch, revision, engine):
    if revision is None:
        monkeypatch.delenv("APP_GIT_REVISION", raising=False)
    else:
        monkeypatch.setenv("APP_GIT_REVISION", revision)
    monkeypatch.setattr(db_session, "engine", engine)
    # Load the router with fresh startup state, separate from the main app.
    namespace = runpy.run_path(health.__file__)
    app = FastAPI()
    app.include_router(namespace["router"], prefix="/api/v1")
    return TestClient(app)


def test_health_reports_the_captured_revision(monkeypatch):
    engine = MagicMock()
    with _health_client(monkeypatch, REVISION, engine) as client:
        monkeypatch.setenv("APP_GIT_REVISION", "a" * 40)
        response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {"ok": True, "db": "ok", "revision": REVISION}
    engine.connect.assert_called_once_with()
    (query,) = engine.connect.return_value.__enter__.return_value.execute.call_args.args
    assert str(query) == "SELECT 1"


@pytest.mark.parametrize(
    "revision",
    [None, "", "unverified", REVISION[:-1], REVISION.upper(), f"{REVISION}\n"],
)
def test_health_omits_unverified_revision(monkeypatch, revision):
    with _health_client(monkeypatch, revision, MagicMock()) as client:
        response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {"ok": True, "db": "ok"}


def test_health_preserves_liveness_when_database_fails(monkeypatch):
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("synthetic connection details")
    with _health_client(monkeypatch, REVISION, engine) as client:
        response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "ok": True,
        "db": "error: RuntimeError",
        "revision": REVISION,
    }
