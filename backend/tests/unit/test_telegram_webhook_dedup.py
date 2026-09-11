"""PR-3: update_id dedup for both Telegram ingress paths.

Covers the atomic claim ledger (telegram_webhook_dedup), its wiring into
POST /telegram/webhook, the long-polling worker, and the daily retention
sweep. The failure-path invariant asserted throughout: dedup suppresses
duplicates, never blocks redelivery of a failed update, and never
reduces delivery availability (fail-open).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from app.api.v1.endpoints import telegram_webhook
from app.models.telegram_config import TelegramConfig
from app.models.telegram_webhook_dedup import TelegramWebhookDedup
from app.schemas.notifications import TelegramWebhookUpdateRequest
from app.services import telegram_webhook_dedup
from app.services.data_retention import run_scheduled_cleanup

WEBHOOK_URL = "/api/v1/telegram/webhook"
SECRET_HEADER = {"x-telegram-bot-api-secret-token": "topsecret"}


class FakeTelegramBotService:
    def __init__(self, active: bool = True):
        self.active = active
        self.initialize = AsyncMock(return_value=True)
        self.process_webhook_update = AsyncMock(return_value=None)
        self.bot_token = "bot-token"


def _add_secret_config(db_session) -> None:
    db_session.add(
        TelegramConfig(bot_token="bot-token", webhook_secret="topsecret", active=True)
    )
    db_session.commit()


def _dedup_rows(db_session, update_id: int) -> list[TelegramWebhookDedup]:
    db_session.expire_all()
    return (
        db_session.query(TelegramWebhookDedup)
        .filter(TelegramWebhookDedup.update_id == update_id)
        .all()
    )


# ============================ service: claim ============================


def test_claim_first_delivery_is_claimed(db_session):
    result = telegram_webhook_dedup.claim_update(db_session, 101)

    assert result == telegram_webhook_dedup.CLAIMED
    (row,) = _dedup_rows(db_session, 101)
    assert row.status == "processing"
    # sqlite returns naive datetimes; the column itself is TIMESTAMPTZ
    # and the service always writes timezone-aware UTC values.
    assert TelegramWebhookDedup.__table__.c.processed_at.type.timezone is True
    assert row.processed_at is not None


def test_claim_second_delivery_is_duplicate(db_session):
    assert telegram_webhook_dedup.claim_update(db_session, 102) == (
        telegram_webhook_dedup.CLAIMED
    )
    assert telegram_webhook_dedup.claim_update(db_session, 102) == (
        telegram_webhook_dedup.DUPLICATE
    )
    # The ledger still holds exactly one row for the update.
    assert len(_dedup_rows(db_session, 102)) == 1


def test_claim_none_update_id_is_claimed_without_row(db_session):
    result = telegram_webhook_dedup.claim_update(db_session, None)

    assert result == telegram_webhook_dedup.CLAIMED
    assert db_session.query(TelegramWebhookDedup).count() == 0


def test_unique_index_enforces_claim_at_db_level(db_session):
    """The dedup guarantee is the UNIQUE index, not app-level checks."""
    telegram_webhook_dedup.claim_update(db_session, 103)

    inspector = sa_inspect(db_session.bind)
    indexes = {
        ix["name"]: ix for ix in inspector.get_indexes("telegram_webhook_dedup")
    }
    # sqlite introspection yields 1/0, PostgreSQL True/False.
    assert bool(indexes["uq_telegram_webhook_dedup_update_id"]["unique"]) is True


def test_claim_supports_bigint_update_id(db_session):
    big = 2**31 + 7  # above the PostgreSQL INT4 range

    assert telegram_webhook_dedup.claim_update(db_session, big) == (
        telegram_webhook_dedup.CLAIMED
    )
    assert _dedup_rows(db_session, big)


# ===================== service: stale-crash recovery =====================


def test_stale_processing_claim_is_reclaimed(db_session):
    stale_at = datetime.now(timezone.utc) - timedelta(
        seconds=telegram_webhook_dedup.DEDUP_STALE_SECONDS + 60
    )
    db_session.add(
        TelegramWebhookDedup(update_id=110, status="processing", processed_at=stale_at)
    )
    db_session.commit()

    result = telegram_webhook_dedup.claim_update(db_session, 110)

    assert result == telegram_webhook_dedup.CLAIMED
    (row,) = _dedup_rows(db_session, 110)
    assert row.status == "processing"
    # sqlite hands the value back naive — normalize before comparing.
    stored = row.processed_at.replace(tzinfo=timezone.utc)
    assert stored > stale_at  # refreshed by the reclaim


def test_fresh_processing_claim_is_duplicate(db_session):
    db_session.add(TelegramWebhookDedup(update_id=111, status="processing"))
    db_session.commit()

    assert telegram_webhook_dedup.claim_update(db_session, 111) == (
        telegram_webhook_dedup.DUPLICATE
    )


def test_processed_row_is_duplicate_even_when_old(db_session):
    old = datetime.now(timezone.utc) - timedelta(
        seconds=telegram_webhook_dedup.DEDUP_STALE_SECONDS * 10
    )
    db_session.add(
        TelegramWebhookDedup(update_id=112, status="processed", processed_at=old)
    )
    db_session.commit()

    assert telegram_webhook_dedup.claim_update(db_session, 112) == (
        telegram_webhook_dedup.DUPLICATE
    )


# =================== service: mark / release / fail-open ===================


def test_mark_processed_flips_status(db_session):
    telegram_webhook_dedup.claim_update(db_session, 120)

    telegram_webhook_dedup.mark_processed(db_session, 120)

    (row,) = _dedup_rows(db_session, 120)
    assert row.status == "processed"


def test_release_claim_allows_reclaim(db_session):
    telegram_webhook_dedup.claim_update(db_session, 121)
    telegram_webhook_dedup.release_claim(db_session, 121)
    assert _dedup_rows(db_session, 121) == []

    # Redelivery of the released update is processed again.
    assert telegram_webhook_dedup.claim_update(db_session, 121) == (
        telegram_webhook_dedup.CLAIMED
    )


def test_fail_open_when_ledger_table_missing(db_session):
    db_session.execute(text("DROP TABLE telegram_webhook_dedup"))
    db_session.commit()

    assert telegram_webhook_dedup.claim_update(db_session, 130) == (
        telegram_webhook_dedup.UNAVAILABLE
    )
    # Best-effort companions never raise either.
    telegram_webhook_dedup.mark_processed(db_session, 130)
    telegram_webhook_dedup.release_claim(db_session, 130)


# ============================== purge ==============================


def test_purge_expired_deletes_only_old_rows(db_session):
    old = datetime.now(timezone.utc) - timedelta(
        days=telegram_webhook_dedup.DEDUP_RETENTION_DAYS + 1
    )
    db_session.add(
        TelegramWebhookDedup(update_id=140, status="processed", processed_at=old)
    )
    db_session.add(TelegramWebhookDedup(update_id=141, status="processed"))
    db_session.commit()

    deleted = telegram_webhook_dedup.purge_expired(db_session)

    assert deleted == 1
    assert _dedup_rows(db_session, 140) == []
    assert _dedup_rows(db_session, 141)


def test_run_scheduled_cleanup_includes_webhook_dedup(db_session):
    old = datetime.now(timezone.utc) - timedelta(
        days=telegram_webhook_dedup.DEDUP_RETENTION_DAYS + 1
    )
    db_session.add(
        TelegramWebhookDedup(update_id=150, status="processed", processed_at=old)
    )
    db_session.commit()

    results = run_scheduled_cleanup(db_session)

    assert "webhook_dedup" in results
    assert results["webhook_dedup"]["deleted"] == 1
    assert _dedup_rows(db_session, 150) == []


# ========================= webhook endpoint =========================


def test_webhook_first_delivery_processed_and_marked(client, db_session, monkeypatch):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    response = client.post(
        WEBHOOK_URL, json={"update_id": 501}, headers=SECRET_HEADER
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    fake.process_webhook_update.assert_awaited_once()
    (row,) = _dedup_rows(db_session, 501)
    assert row.status == "processed"


def test_webhook_duplicate_delivery_suppressed(client, db_session, monkeypatch):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )
    first = client.post(WEBHOOK_URL, json={"update_id": 502}, headers=SECRET_HEADER)
    assert first.status_code == 200

    second = client.post(WEBHOOK_URL, json={"update_id": 502}, headers=SECRET_HEADER)

    # ACK 200 so Telegram stops retrying, but the handler runs only once.
    assert second.status_code == 200
    assert second.json() == {"status": "ok", "handled": "duplicate_update"}
    assert fake.process_webhook_update.await_count == 1


def test_webhook_handler_failure_releases_claim(client, db_session, monkeypatch):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    fake.process_webhook_update = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    failed = client.post(WEBHOOK_URL, json={"update_id": 503}, headers=SECRET_HEADER)
    assert failed.status_code == 500
    # The claim was released: nothing suppresses the redelivery.
    assert _dedup_rows(db_session, 503) == []

    fake.process_webhook_update = AsyncMock(return_value=None)
    redelivered = client.post(
        WEBHOOK_URL, json={"update_id": 503}, headers=SECRET_HEADER
    )
    assert redelivered.status_code == 200
    assert fake.process_webhook_update.await_count == 1


def test_webhook_fail_open_when_ledger_missing(client, db_session, monkeypatch):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )
    db_session.execute(text("DROP TABLE telegram_webhook_dedup"))
    db_session.commit()

    response = client.post(WEBHOOK_URL, json={"update_id": 504}, headers=SECRET_HEADER)

    # Dedup unavailability must not block delivery.
    assert response.status_code == 200
    fake.process_webhook_update.assert_awaited_once()


def test_webhook_without_update_id_skips_ledger(client, db_session, monkeypatch):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    response = client.post(
        WEBHOOK_URL, json={"message": {"message_id": 55}}, headers=SECRET_HEADER
    )

    assert response.status_code == 200
    assert db_session.query(TelegramWebhookDedup).count() == 0


def test_webhook_secret_rejection_writes_no_ledger_row(
    client, db_session, monkeypatch
):
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    response = client.post(
        WEBHOOK_URL,
        json={"update_id": 505},
        headers={"x-telegram-bot-api-secret-token": "wrong"},
    )

    assert response.status_code == 403
    assert db_session.query(TelegramWebhookDedup).count() == 0


def test_webhook_update_schema_keeps_update_id_optional():
    """Contract pin: TelegramWebhookUpdateRequest.update_id feeds dedup."""
    assert TelegramWebhookUpdateRequest.model_fields["update_id"].default is None
    body = TelegramWebhookUpdateRequest.model_validate({"update_id": 9})
    assert body.update_id == 9


# ========================= polling worker =========================


class _NoCloseSession:
    """Delegates to the fixture session but owns no close lifecycle.

    PR-1 lesson: a second real session on the sqlite test database hits
    'database is locked', and closing the fixture session mid-test
    breaks the outer transaction — so the worker's SessionLocal is
    patched to this wrapper.
    """

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass


class _FakeWorkerBotService:
    def __init__(self):
        self.active = True
        self.initialize = AsyncMock(return_value=True)
        self.process_webhook_update = AsyncMock(return_value=None)


@pytest.fixture
def worker(monkeypatch, db_session):
    from app.scripts.telegram_polling_worker import TelegramPollingWorker

    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.SessionLocal",
        lambda: _NoCloseSession(db_session),
    )
    return TelegramPollingWorker(
        poll_timeout=1,
        request_timeout=2,
        retry_delay=0,
        drop_pending_updates=False,
        keep_webhook=True,
        once=True,
        max_updates=None,
    )


@pytest.mark.asyncio
async def test_worker_skips_duplicate_update(worker, db_session, monkeypatch):
    fake = _FakeWorkerBotService()
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )
    telegram_webhook_dedup.claim_update(db_session, 601)

    await worker._handle_update({"update_id": 601})

    fake.process_webhook_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_processes_and_marks_update(worker, db_session, monkeypatch):
    fake = _FakeWorkerBotService()
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )

    await worker._handle_update({"update_id": 602})

    fake.process_webhook_update.assert_awaited_once()
    (row,) = _dedup_rows(db_session, 602)
    assert row.status == "processed"


@pytest.mark.asyncio
async def test_worker_failure_releases_claim(worker, db_session, monkeypatch):
    fake = _FakeWorkerBotService()
    fake.process_webhook_update = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )

    await worker._handle_update({"update_id": 603})

    assert _dedup_rows(db_session, 603) == []
