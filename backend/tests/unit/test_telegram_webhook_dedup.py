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


@pytest.fixture(autouse=True)
def _deterministic_bot_identity(monkeypatch, request):
    """Resolve identities deterministically (no real getMe) for every test
    except the ones exercising the real resolver logic."""
    if request.node.get_closest_marker("real_identity_resolver"):
        return

    async def fake_resolve(token):
        return telegram_webhook_dedup.ledger_bot_identity(token)

    monkeypatch.setattr(
        telegram_webhook_dedup,
        "resolve_ledger_bot_identity",
        fake_resolve,
    )
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.resolve_ledger_bot_identity",
        fake_resolve,
    )


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


def test_claim_disambiguates_in_flight_from_duplicate(db_session):
    """Codex round 20 (P1): a retry while the first handler is STILL
    running is IN_FLIGHT (must not be ACKed as handled); once the first
    handler completed, the retry is a true DUPLICATE (ACK ok)."""
    assert telegram_webhook_dedup.claim_update(db_session, 102) == (
        telegram_webhook_dedup.CLAIMED
    )
    assert telegram_webhook_dedup.claim_update(db_session, 102) == (
        telegram_webhook_dedup.IN_FLIGHT
    )

    telegram_webhook_dedup.mark_processed(db_session, 102)
    assert telegram_webhook_dedup.claim_update(db_session, 102) == (
        telegram_webhook_dedup.DUPLICATE
    )
    # The ledger still holds exactly one row for the update.
    assert len(_dedup_rows(db_session, 102)) == 1


def test_claim_none_update_id_is_claimed_without_row(db_session):
    result = telegram_webhook_dedup.claim_update(db_session, None)

    assert result == telegram_webhook_dedup.CLAIMED
    assert db_session.query(TelegramWebhookDedup).count() == 0


def test_ledger_bot_identity_is_stable_and_non_secret():
    """The fallback identity binds a claim to its credential without
    leaking it."""
    token = "123456789:test-only-not-a-real-credential-value"
    identity = telegram_webhook_dedup.ledger_bot_identity(token)

    assert identity is not None
    assert identity == telegram_webhook_dedup.ledger_bot_identity(token)
    assert token not in identity
    assert len(identity) == len("cred:") + 32  # sha256 hex prefix, String(64)
    # A different credential (replacement bot or rotation) gets a
    # different identity; no credential at all gets None ("unknown" ns).
    assert identity != telegram_webhook_dedup.ledger_bot_identity("other-token")
    assert telegram_webhook_dedup.ledger_bot_identity(None) is None
    assert telegram_webhook_dedup.ledger_bot_identity("") is None


@pytest.mark.real_identity_resolver
@pytest.mark.asyncio
async def test_resolve_persists_getme_id_and_caches():
    """Codex round 24: the getMe-resolved id is PERSISTED (so every
    uvicorn worker / the polling worker shares ONE namespace) and cached
    in-process (one getMe per credential)."""
    token = "123456789:resolve-stable-token"
    telegram_webhook_dedup._IDENTITY_BY_TOKEN.pop(token, None)
    calls = []
    persisted = []

    async def fake_fetch(t):
        calls.append(t)
        return "777000"

    def fake_persist(t, identity):
        persisted.append((t, identity))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(telegram_webhook_dedup, "_read_persisted_identity", lambda t: None)
        mp.setattr(telegram_webhook_dedup, "_fetch_bot_id", fake_fetch)
        mp.setattr(telegram_webhook_dedup, "_persist_bot_identity", fake_persist)
        first = await telegram_webhook_dedup.resolve_ledger_bot_identity(token)
        second = await telegram_webhook_dedup.resolve_ledger_bot_identity(token)

    assert first == second == "tgbot:777000"
    assert calls == [token]  # cached — one getMe per credential
    assert persisted == [(token, "tgbot:777000")]
    telegram_webhook_dedup._IDENTITY_BY_TOKEN.pop(token, None)


@pytest.mark.real_identity_resolver
@pytest.mark.asyncio
async def test_resolve_uses_persisted_identity_without_getme():
    """Codex round 24 (P1) core pin: a worker whose getMe keeps failing
    still claims under the SAME namespace as the workers that resolved
    the id — the persisted telegram_configs.bot_identity is read first
    and getMe is never needed."""
    token = "123456789:resolve-persisted-token"
    telegram_webhook_dedup._IDENTITY_BY_TOKEN.pop(token, None)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            telegram_webhook_dedup,
            "_read_persisted_identity",
            lambda t: "tgbot:777000",
        )
        fetch = AsyncMock(return_value=None)
        mp.setattr(telegram_webhook_dedup, "_fetch_bot_id", fetch)
        identity = await telegram_webhook_dedup.resolve_ledger_bot_identity(token)

    assert identity == "tgbot:777000"
    fetch.assert_not_awaited()
    telegram_webhook_dedup._IDENTITY_BY_TOKEN.pop(token, None)


@pytest.mark.real_identity_resolver
@pytest.mark.asyncio
async def test_resolve_returns_none_without_caching_when_getme_fails():
    """Codex rounds 24-26: a failed getMe must NOT produce a claimable
    identity (the caller defers the delivery instead) and nothing is
    cached — the next resolution retries getMe / re-reads the persisted
    value so every worker converges on one namespace."""
    token = "123456789:resolve-fallback-token"
    telegram_webhook_dedup._IDENTITY_BY_TOKEN.pop(token, None)
    fetch_calls = []

    async def fake_fetch(t):
        fetch_calls.append(t)
        return None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(telegram_webhook_dedup, "_read_persisted_identity", lambda t: None)
        mp.setattr(telegram_webhook_dedup, "_fetch_bot_id", fake_fetch)
        first = await telegram_webhook_dedup.resolve_ledger_bot_identity(token)
        second = await telegram_webhook_dedup.resolve_ledger_bot_identity(token)

    assert first is None and second is None  # defer, never a fallback key
    assert fetch_calls == [token, token]  # retried — nothing was cached
    assert token not in telegram_webhook_dedup._IDENTITY_BY_TOKEN


def _patch_service_session(monkeypatch, db_session):
    """Point the dedup service's own-session helpers at the fixture db."""
    monkeypatch.setattr(
        "app.db.session.SessionLocal",
        lambda: _NoCloseSession(db_session),
    )


def test_persisted_identity_roundtrip_is_credential_bound(
    db_session, monkeypatch
):
    """Codex round 25: the persisted identity lives in clinic_settings
    (covers env-backed credentials too) and is bound to the credential
    fingerprint it was resolved for — a different credential does not
    inherit it."""
    import json as _json

    from app.models.clinic import ClinicSettings

    _patch_service_session(monkeypatch, db_session)
    token = "123456789:env-backed-token"
    identity = "tgbot:777000"

    telegram_webhook_dedup._persist_bot_identity(token, identity)

    row = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == telegram_webhook_dedup.BOT_IDENTITY_SETTING_KEY)
        .one()
    )
    payload = _json.loads(row.value)
    assert payload == {
        "cred": telegram_webhook_dedup.ledger_bot_identity(token),
        "identity": identity,
    }

    # The SAME credential reads it back — without getMe.
    assert telegram_webhook_dedup._read_persisted_identity(token) == identity

    # A DIFFERENT credential (replacement bot / rotation) does not
    # inherit the identity: the fingerprint stops matching.
    assert telegram_webhook_dedup._read_persisted_identity("other-token") is None


def test_persisted_identity_upserts_for_env_backed_credentials(
    db_session, monkeypatch
):
    """Codex round 25 (P1): the persist path must not depend on
    telegram_configs at all — an env-backed credential (no config row)
    still shares its identity across workers."""
    import json as _json

    from app.models.clinic import ClinicSettings

    _patch_service_session(monkeypatch, db_session)
    assert db_session.query(TelegramConfig).count() == 0  # env-backed

    telegram_webhook_dedup._persist_bot_identity("123456789:env-token", "tgbot:42")

    row = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == telegram_webhook_dedup.BOT_IDENTITY_SETTING_KEY)
        .one()
    )
    payload = _json.loads(row.value)
    assert payload == {
        "cred": telegram_webhook_dedup.ledger_bot_identity("123456789:env-token"),
        "identity": "tgbot:42",
    }
    assert telegram_webhook_dedup._read_persisted_identity(
        "123456789:env-token"
    ) == "tgbot:42"


def test_claims_of_different_bots_do_not_collide(db_session):
    """Codex round 20 core scenario: the ledger key is per-bot. The same
    numeric update_id of a DIFFERENT bot must claim cleanly."""
    identity_a = telegram_webhook_dedup.ledger_bot_identity("123456789:bot-a")
    identity_b = telegram_webhook_dedup.ledger_bot_identity("123456789:bot-b")

    assert telegram_webhook_dedup.claim_update(db_session, 710, identity_a) == (
        telegram_webhook_dedup.CLAIMED
    )
    # The previous bot already processed this numeric id.
    telegram_webhook_dedup.mark_processed(db_session, 710, identity_a)

    # The replacement bot's update happens to carry the same numeric id —
    # it must NOT be suppressed by the previous bot's retained row.
    assert telegram_webhook_dedup.claim_update(db_session, 710, identity_b) == (
        telegram_webhook_dedup.CLAIMED
    )
    rows = {
        (r.bot_identity, r.status)
        for r in db_session.query(TelegramWebhookDedup)
        .filter(TelegramWebhookDedup.update_id == 710)
        .all()
    }
    assert rows == {(identity_a, "processed"), (identity_b, "processing")}


def test_mark_and_release_are_scoped_to_the_claiming_bot(db_session):
    identity_a = telegram_webhook_dedup.ledger_bot_identity("123456789:bot-a")
    identity_b = telegram_webhook_dedup.ledger_bot_identity("123456789:bot-b")
    telegram_webhook_dedup.claim_update(db_session, 711, identity_a)
    telegram_webhook_dedup.claim_update(db_session, 711, identity_b)

    # Bot A completes: only A's row is flipped / deleted.
    telegram_webhook_dedup.mark_processed(db_session, 711, identity_a)
    statuses = {
        r.bot_identity: r.status
        for r in db_session.query(TelegramWebhookDedup)
        .filter(TelegramWebhookDedup.update_id == 711)
        .all()
    }
    assert statuses == {identity_a: "processed", identity_b: "processing"}

    telegram_webhook_dedup.release_claim(db_session, 711, identity_a)
    remaining = {
        r.bot_identity
        for r in db_session.query(TelegramWebhookDedup)
        .filter(TelegramWebhookDedup.update_id == 711)
        .all()
    }
    assert remaining == {identity_b}


def test_unique_index_enforces_claim_at_db_level(db_session):
    """The dedup guarantee is the UNIQUE index, not app-level checks."""
    telegram_webhook_dedup.claim_update(db_session, 103)

    inspector = sa_inspect(db_session.bind)
    indexes = {
        ix["name"]: ix for ix in inspector.get_indexes("telegram_webhook_dedup")
    }
    # sqlite introspection yields 1/0, PostgreSQL True/False.
    uq = indexes["uq_telegram_webhook_dedup_bot_update_id"]
    assert bool(uq["unique"]) is True
    # The ledger key is (bot_identity, update_id) — Telegram update_id
    # sequences are per-bot (codex round 20).
    assert set(uq["column_names"]) == {"bot_identity", "update_id"}


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


def test_fresh_processing_claim_is_in_flight(db_session):
    """A LIVE handler owns the update — the retry must NOT be ACKed as
    handled (a premature 200 plus a later failure of the owner would
    lose the update; codex round 20)."""
    db_session.add(TelegramWebhookDedup(update_id=111, status="processing"))
    db_session.commit()

    assert telegram_webhook_dedup.claim_update(db_session, 111) == (
        telegram_webhook_dedup.IN_FLIGHT
    )
    # The in-flight row was left untouched (still the owner's claim).
    (row,) = _dedup_rows(db_session, 111)
    assert row.status == "processing"


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


# ================= service: identity-change reset =================


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


def test_webhook_claims_are_bound_to_credential_identity(
    client, db_session, monkeypatch
):
    """Codex round 20: claims carry a stable, non-secret per-credential
    identity derived from the resolved bot token."""
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    response = client.post(
        WEBHOOK_URL, json={"update_id": 506}, headers=SECRET_HEADER
    )

    assert response.status_code == 200
    (row,) = _dedup_rows(db_session, 506)
    assert row.bot_identity == telegram_webhook_dedup.ledger_bot_identity(
        "bot-token"
    )


def test_webhook_old_bot_row_never_suppresses_new_bot(
    client, db_session, monkeypatch
):
    """Codex round 20: a row retained by a PREVIOUS bot (different
    identity, same numeric update_id) must not suppress the current
    bot's delivery."""
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )
    stale_identity = telegram_webhook_dedup.ledger_bot_identity(
        "123456789:previous-bot"
    )
    db_session.add(
        TelegramWebhookDedup(
            update_id=507, bot_identity=stale_identity, status="processed"
        )
    )
    db_session.commit()

    response = client.post(
        WEBHOOK_URL, json={"update_id": 507}, headers=SECRET_HEADER
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    fake.process_webhook_update.assert_awaited_once()


def test_webhook_in_flight_delivery_is_not_acknowledged(
    client, db_session, monkeypatch
):
    """Codex round 20 (P1): a retry arriving while the original handler
    is STILL running must not be ACKed with a success — if the original
    handler later fails, only an un-ACKed delivery is retried by
    Telegram. The endpoint answers 503 and leaves the owner's claim
    alone."""
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )
    live_identity = telegram_webhook_dedup.ledger_bot_identity("bot-token")
    db_session.add(
        TelegramWebhookDedup(
            update_id=508, bot_identity=live_identity, status="processing"
        )
    )
    db_session.commit()

    response = client.post(
        WEBHOOK_URL, json={"update_id": 508}, headers=SECRET_HEADER
    )

    # Retryable 503 (not a success ACK) so Telegram redelivers later.
    assert response.status_code == 503
    assert response.json() == {"status": "update_in_flight"}
    # The handler did not run, and the live claim was NOT released.
    fake.process_webhook_update.assert_not_awaited()
    (row,) = _dedup_rows(db_session, 508)
    assert row.status == "processing"


def test_webhook_identity_unavailable_delivery_is_deferred(
    client, db_session, monkeypatch
):
    """Codex round 26 (P1): without a SHARED identity a claim could land
    in a transient namespace another worker does not use — the delivery
    is deferred (503) instead of being claimed under a fallback key."""
    _add_secret_config(db_session)
    fake = FakeTelegramBotService()
    monkeypatch.setattr(
        telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=fake)
    )

    async def no_identity(token):
        return None

    monkeypatch.setattr(
        telegram_webhook_dedup,
        "resolve_ledger_bot_identity",
        no_identity,
    )

    response = client.post(
        WEBHOOK_URL, json={"update_id": 509}, headers=SECRET_HEADER
    )

    assert response.status_code == 503
    assert response.json() == {"status": "identity_unavailable"}
    fake.process_webhook_update.assert_not_awaited()
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
async def test_worker_claims_are_bound_to_credential_identity(
    worker, db_session, monkeypatch
):
    """Codex round 20: worker claims carry the identity derived from the
    polled token (the same credential the batch was fetched with)."""
    fake = _FakeWorkerBotService()
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )

    await worker._handle_update(
        {"update_id": 604},
        telegram_webhook_dedup.ledger_bot_identity("123456789:worker-token"),
    )

    (row,) = _dedup_rows(db_session, 604)
    assert row.status == "processed"
    assert row.bot_identity == telegram_webhook_dedup.ledger_bot_identity(
        "123456789:worker-token"
    )


@pytest.mark.asyncio
async def test_worker_skips_in_flight_update(worker, db_session, monkeypatch):
    """Codex round 20 (P1): a live claim of the same identity is skipped
    without dispatching a concurrent handler."""
    fake = _FakeWorkerBotService()
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )
    identity = telegram_webhook_dedup.ledger_bot_identity("123456789:worker")
    telegram_webhook_dedup.claim_update(db_session, 605, identity)

    await worker._handle_update({"update_id": 605}, identity)

    fake.process_webhook_update.assert_not_awaited()
    (row,) = _dedup_rows(db_session, 605)
    assert row.status == "processing"


@pytest.mark.asyncio
async def test_worker_identity_unavailable_leaves_batch_unconfirmed(
    worker, db_session, monkeypatch
):
    """Codex round 26 (P1): without a SHARED identity the batch is left
    unconfirmed instead of being claimed under a transient fallback key
    another worker would not use."""
    resolutions = {"123456789:token-a": None}

    async def fake_resolve(t):
        return resolutions[t]

    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.resolve_ledger_bot_identity",
        fake_resolve,
    )
    worker.once = False
    polls = []
    handled = []

    async def fake_load():
        return "123456789:token-a"

    async def fake_handle(update, identity=None):
        handled.append(update.get("update_id"))

    def fake_get_updates(session, token, offset):
        polls.append((token, offset))
        if len(polls) == 1:
            return [{"update_id": 902}]
        worker.request_stop()
        return []

    monkeypatch.setattr(worker, "_load_bot_token", fake_load)
    monkeypatch.setattr(worker, "_handle_update", fake_handle)
    monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

    exit_code = await worker.run()

    assert exit_code == 0
    # Nothing was dispatched, and the offset did NOT move: update 902
    # stays pending for the cycle where an identity becomes available.
    assert handled == []
    assert polls == [("123456789:token-a", None), ("123456789:token-a", None)]
    assert db_session.query(TelegramWebhookDedup).count() == 0


@pytest.mark.asyncio
async def test_worker_failure_does_not_release_a_claim_it_does_not_own(
    worker, db_session, monkeypatch
):
    """Codex round 26 (P2): after a fail-open UNAVAILABLE claim this
    worker owns NOTHING — a handler exception must not delete another
    delivery's live or processed row once the database has recovered."""
    fake = _FakeWorkerBotService()
    fake.process_webhook_update = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.get_telegram_bot_service",
        AsyncMock(return_value=fake),
    )
    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.claim_update",
        lambda db, update_id, bot_identity=None: telegram_webhook_dedup.UNAVAILABLE,
    )
    # Another delivery's live claim for the same update.
    telegram_webhook_dedup.claim_update(db_session, 606)

    disposition = await worker._handle_update({"update_id": 606})

    # The handler failed (disposition None) — but the release was skipped
    # because the fail-open UNAVAILABLE claim was never owned.
    assert disposition is None
    # The other delivery's claim SURVIVED the failure path.
    (row,) = _dedup_rows(db_session, 606)
    assert row.status == "processing"


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


# ================ worker: credential-change ledger reset ================


@pytest.mark.asyncio
async def test_worker_same_bot_rotation_keeps_ledger(worker, db_session, monkeypatch):
    """Codex round 22 (P2): the identity is the STABLE per-bot id — a
    same-bot token rotation must NOT wipe the ledger, so an update that
    was processed just before the rotation but not yet confirmed is
    still deduplicated after it."""
    identity = "tgbot:777000"
    resolutions = {
        "123456789:token-a": identity,
        "123456789:token-b": identity,  # same bot, rotated token
    }

    async def fake_resolve(t):
        return resolutions[t]

    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.resolve_ledger_bot_identity",
        fake_resolve,
    )
    telegram_webhook_dedup.claim_update(db_session, 850, identity)
    telegram_webhook_dedup.mark_processed(db_session, 850, identity)

    worker.once = False
    polls = []

    async def fake_load():
        # initial: token-a; cycle-top: rotated to token-b; stay there.
        return "123456789:token-a" if not polls else "123456789:token-b"

    def fake_get_updates(session, token, offset):
        polls.append((token, offset))
        if len(polls) == 1:
            return [{"update_id": 851}]
        worker.request_stop()
        return []

    monkeypatch.setattr(worker, "_load_bot_token", fake_load)
    monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

    exit_code = await worker.run()

    assert exit_code == 0
    # The rotation reset the offset (superseded credential)...
    assert polls[1] == ("123456789:token-b", None)
    # ...but the ledger SURVIVED: update 851 (a fresh update) was claimed
    # and processed under the SAME identity namespace.
    db_session.expire_all()
    (row,) = _dedup_rows(db_session, 850)
    assert row.status == "processed"


@pytest.mark.asyncio
async def test_worker_in_flight_update_is_left_unconfirmed(
    worker, db_session, monkeypatch
):
    """Codex round 22 (P1): an IN_FLIGHT update must NOT be confirmed —
    advancing the offset past it would ACK a crashed worker's orphaned
    claim before the stale-reclaim path can run. The worker keeps the
    offset and stops consuming the batch."""
    identity = "tgbot:777000"
    resolutions = {"123456789:token-a": identity}

    async def fake_resolve(t):
        return resolutions[t]

    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.resolve_ledger_bot_identity",
        fake_resolve,
    )
    # An orphaned claim from a crashed previous instance: fresh
    # 'processing' row → IN_FLIGHT for the whole stale window.
    telegram_webhook_dedup.claim_update(db_session, 901, identity)

    worker.once = False
    polls = []

    async def fake_load():
        return "123456789:token-a"

    def fake_get_updates(session, token, offset):
        polls.append((token, offset))
        if len(polls) == 1:
            return [{"update_id": 901}]
        worker.request_stop()
        return []

    monkeypatch.setattr(worker, "_load_bot_token", fake_load)
    monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

    exit_code = await worker.run()

    assert exit_code == 0
    # The second poll still uses the OLD offset: update 901 was NOT
    # confirmed, so Telegram keeps redelivering it until the orphaned
    # claim is reclaimed (stale) or released.
    assert polls == [("123456789:token-a", None), ("123456789:token-a", None)]
    db_session.expire_all()
    (row,) = _dedup_rows(db_session, 901)
    assert row.status == "processing"  # untouched — the reclaim path stays available


@pytest.mark.asyncio
async def test_worker_post_poll_identity_change_resets_offset(
    worker, db_session, monkeypatch
):
    """A rotation landing during the long poll drops the stale batch and
    resets the offset — and does NOT purge the ledger (codex round 27):
    deleting rows could drop a live claim of an in-flight old-bot
    delivery, while the composite key already isolates the new bot."""
    identity_a = "tgbot:777000"
    resolutions = {
        "123456789:token-a": identity_a,
        "123456789:token-b": "tgbot:888000",
    }

    async def fake_resolve(t):
        return resolutions[t]

    monkeypatch.setattr(
        "app.scripts.telegram_polling_worker.resolve_ledger_bot_identity",
        fake_resolve,
    )
    telegram_webhook_dedup.claim_update(db_session, 802, identity_a)
    telegram_webhook_dedup.mark_processed(db_session, 802, identity_a)
    tokens = iter(
        ["123456789:token-a", "123456789:token-a", "123456789:token-b"]
    )
    handled = []

    async def fake_load():
        return next(tokens)

    async def fake_handle(update):
        handled.append(update.get("update_id"))

    def fake_get_updates(session, token, offset):
        return [{"update_id": 802}]

    monkeypatch.setattr(worker, "_load_bot_token", fake_load)
    monkeypatch.setattr(worker, "_handle_update", fake_handle)
    monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

    exit_code = await worker.run()

    assert exit_code == 0
    # The stale batch was dropped, not dispatched.
    assert handled == []
    db_session.expire_all()
    # The superseded identity's rows are NOT deleted (a live claim of an
    # in-flight old-bot delivery must survive); they age out via
    # retention.
    (row,) = _dedup_rows(db_session, 802)
    assert row.status == "processed"
