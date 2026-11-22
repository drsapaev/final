from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import engine
from app.services.public_site_media_cleanup import (
    _CLEANUP_LOCK_KEY,
    _run_cleanup_with_postgres_lock,
)

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="cleanup coordination uses PostgreSQL advisory locks",
)
_TEST_LOCK_KEY = _CLEANUP_LOCK_KEY - 1


def test_cleanup_skips_when_another_worker_holds_the_transaction_lock() -> None:
    called = False

    def cleanup() -> int:
        nonlocal called
        called = True
        return 1

    with engine.begin() as holder:
        holder.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _TEST_LOCK_KEY},
        )

        assert _run_cleanup_with_postgres_lock(cleanup, lock_key=_TEST_LOCK_KEY) is None

    assert called is False


def test_cleanup_runs_after_acquiring_the_transaction_lock() -> None:
    lock_key = _TEST_LOCK_KEY - 1
    assert _run_cleanup_with_postgres_lock(lambda: 3, lock_key=lock_key) == 3

    with engine.begin() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
    assert acquired is True
