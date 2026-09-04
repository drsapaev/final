"""P0 2026-08-28 follow-up: libpq-level resilience knobs for the remote
Supabase pooler (connect_timeout / TCP keepalives / statement_timeout /
application_name).

A blackholed TCP route left psycopg ``wait_select`` spinning forever, which
was the mechanism of the origin-wide freeze once sync I/O moved off the event
loop (#2874): the loop stayed responsive, but requests waited on pool
connections that could never complete. These knobs turn the indefinite waits
into bounded failures.

Run:
    pytest backend/tests/unit/test_db_session_connect_args.py -v
"""

from __future__ import annotations

import pytest

from app.db.session import _postgres_connect_args


def test_postgres_connect_args_defaults(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "DB_CONNECT_TIMEOUT_S",
        "DB_TCP_KEEPALIVE_IDLE_S",
        "DB_TCP_KEEPALIVE_INTERVAL_S",
        "DB_TCP_KEEPALIVE_COUNT",
        "DB_STATEMENT_TIMEOUT_MS",
        "DB_APPLICATION_NAME",
    ):
        monkeypatch.delenv(key, raising=False)

    args = _postgres_connect_args()

    assert args["connect_timeout"] == 10
    assert args["application_name"] == "clinic-api"
    assert args["keepalives"] == 1
    assert args["keepalives_idle"] == 30
    assert args["keepalives_interval"] == 10
    assert args["keepalives_count"] == 5
    assert args["options"] == "-c statement_timeout=60000"
    # SQLite-only flag must never leak into postgres connect args.
    assert "check_same_thread" not in args


def test_postgres_connect_args_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", "5")
    monkeypatch.setenv("DB_TCP_KEEPALIVE_IDLE_S", "15")
    monkeypatch.setenv("DB_TCP_KEEPALIVE_INTERVAL_S", "3")
    monkeypatch.setenv("DB_TCP_KEEPALIVE_COUNT", "4")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "15000")
    monkeypatch.setenv("DB_APPLICATION_NAME", "clinic-test")

    args = _postgres_connect_args()

    assert args["connect_timeout"] == 5
    assert args["keepalives_idle"] == 15
    assert args["keepalives_interval"] == 3
    assert args["keepalives_count"] == 4
    assert args["options"] == "-c statement_timeout=15000"
    assert args["application_name"] == "clinic-test"


def test_postgres_connect_args_can_disable_knobs(monkeypatch: pytest.MonkeyPatch):
    """0 must disable a knob entirely (maintenance tooling that legitimately
    needs unbounded statements, or hosts where keepalives are unwanted)."""
    monkeypatch.setenv("DB_TCP_KEEPALIVE_IDLE_S", "0")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "0")

    args = _postgres_connect_args()

    assert "keepalives" not in args
    assert "keepalives_idle" not in args
    assert "options" not in args
    assert args["connect_timeout"] == 10
