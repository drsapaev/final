"""Patient session authority, expiry, replay and refresh/revoke guardrails."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt
import pytest
from sqlalchemy import update

from app.core.config import settings
from app.models.authentication import UserSession
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.telegram_mini_app_session import TelegramMiniAppSession
from app.repositories.telegram_mini_app_session_repository import (
    TelegramMiniAppSessionRepository,
)
from app.services.telegram_mini_app_jwt import (
    PATIENT_JWT_ALGORITHM,
    PATIENT_JWT_AUDIENCE,
    PATIENT_JWT_ISSUER,
    TelegramMiniAppAuthExchangeError,
    authenticate_patient_session,
    exchange_init_data_for_jwt,
    list_patient_sessions,
    refresh_patient_session,
    revoke_patient_sessions,
    verify_patient_jwt,
)

BOT_TOKEN = "123456:synthetic-session-tests-only"


def signed_init_data(chat_id=730001, *, nonce=None, age=0):
    values = {
        "auth_date": str(int((datetime.now(UTC) - timedelta(seconds=age)).timestamp())),
        "query_id": nonce or uuid.uuid4().hex,
        "user": json.dumps({"id": chat_id}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})


def link_patient(db, patient, chat_id=730001):
    link = TelegramUser(
        patient_id=patient.id,
        chat_id=chat_id,
        active=True,
        blocked=False,
    )
    db.add(link)
    db.commit()
    return link


def create_session(db, chat_id=730001, **kwargs):
    return exchange_init_data_for_jwt(
        db,
        signed_init_data(chat_id),
        bot_token=BOT_TOKEN,
        **kwargs,
    )


def verified_claims(token):
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[PATIENT_JWT_ALGORITHM],
        audience=PATIENT_JWT_AUDIENCE,
        issuer=PATIENT_JWT_ISSUER,
    )


@pytest.fixture
def linked(db_session, test_patient):
    return link_patient(db_session, test_patient)


def test_exchange_creates_patient_session_without_staff_identity(db_session, linked):
    pair = create_session(
        db_session, request_user_agent="Synthetic Android private-header"
    )
    auth = authenticate_patient_session(db_session, pair["access_token"])
    row = auth.session
    assert row.patient_id == linked.patient_id
    assert row.patient_link_epoch == linked.patient_link_epoch
    assert db_session.query(UserSession).count() == 0
    assert (
        row.refresh_token_hash
        == hashlib.sha256(pair["refresh_token"].encode()).hexdigest()
    )
    assert row.device_label == "Android"
    assert set(pair) == {"access_token", "refresh_token", "token_type", "expires_in"}
    assert 890 <= pair["expires_in"] <= 900
    claims = jwt.decode(
        pair["access_token"],
        settings.SECRET_KEY,
        algorithms=[PATIENT_JWT_ALGORITHM],
        audience=PATIENT_JWT_AUDIENCE,
        issuer=PATIENT_JWT_ISSUER,
    )
    assert claims["sid"] == row.id
    assert claims["sub"] == f"telegram-patient:{linked.patient_id}"
    assert "telegram_user_id" not in claims
    assert "patient_link_epoch" not in claims
    assert pair["refresh_token"] not in repr(row.__dict__)


def test_exchange_is_one_time_even_when_query_fields_are_reordered(db_session, linked):
    data = signed_init_data()
    exchange_init_data_for_jwt(db_session, data, bot_token=BOT_TOKEN)
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="init_data_replayed"):
        exchange_init_data_for_jwt(
            db_session,
            "&".join(reversed(data.split("&"))),
            bot_token=BOT_TOKEN,
        )
    assert db_session.query(TelegramMiniAppSession).count() == 1


def test_new_login_keeps_other_devices_active(db_session, linked):
    first = create_session(db_session)
    second = create_session(db_session)
    auth, data = list_patient_sessions(db_session, second["access_token"])
    assert data["total"] == 2
    assert sum(row["is_current"] for row in data["sessions"]) == 1
    assert (
        next(row for row in data["sessions"] if row["is_current"])["id"]
        == auth.session.id
    )
    assert verify_patient_jwt(first["access_token"], db_session)


@pytest.mark.parametrize(
    "age,token", [(301, BOT_TOKEN), (0, "invalid-synthetic-bot-token")]
)
def test_bad_or_expired_init_data_never_creates_a_session(
    db_session, linked, age, token
):
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        exchange_init_data_for_jwt(
            db_session, signed_init_data(age=age), bot_token=token
        )
    assert db_session.query(TelegramMiniAppSession).count() == 0


def test_refresh_rotates_and_reuse_revokes_the_family(db_session, linked):
    first = create_session(db_session)
    second = refresh_patient_session(db_session, first["refresh_token"])
    assert second["refresh_token"] != first["refresh_token"]
    assert verify_patient_jwt(second["access_token"], db_session)
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="session_invalid"):
        refresh_patient_session(db_session, first["refresh_token"])
    assert verify_patient_jwt(second["access_token"], db_session) is None
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        refresh_patient_session(db_session, second["refresh_token"])


def test_forged_refresh_cannot_revoke_known_session(db_session, linked):
    pair = create_session(db_session)
    chunks = pair["refresh_token"].split(".")
    chunks[2] = "invalid_signature"
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        refresh_patient_session(db_session, ".".join(chunks))
    assert verify_patient_jwt(pair["access_token"], db_session)
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        refresh_patient_session(db_session, pair["access_token"])


def test_server_expiry_blocks_unexpired_access_and_refresh(db_session, linked):
    pair = create_session(db_session)
    row = authenticate_patient_session(db_session, pair["access_token"]).session
    row.created_at = datetime.now(UTC) - timedelta(days=8)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert verify_patient_jwt(pair["access_token"], db_session) is None
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        refresh_patient_session(db_session, pair["refresh_token"])


@pytest.mark.parametrize(
    "claim,value",
    [
        ("aud", "staff"),
        ("iss", "other"),
        ("scope", "staff"),
        ("type", "refresh"),
        ("sub", "telegram-patient:999999"),
        ("sid", None),
        ("exp", 1),
        ("iat", 4102444800),
    ],
)
def test_wrong_claims_are_denied(db_session, linked, claim, value):
    pair = create_session(db_session)
    payload = verified_claims(pair["access_token"])
    payload[claim] = value
    changed = jwt.encode(payload, settings.SECRET_KEY, algorithm=PATIENT_JWT_ALGORITHM)
    assert verify_patient_jwt(changed, db_session) is None


@pytest.mark.parametrize("claim", ["aud", "iss", "iat", "exp", "sub", "jti", "sid"])
def test_required_claims_cannot_be_omitted(db_session, linked, claim):
    pair = create_session(db_session)
    payload = verified_claims(pair["access_token"])
    payload.pop(claim)
    changed = jwt.encode(payload, settings.SECRET_KEY, algorithm=PATIENT_JWT_ALGORITHM)
    assert verify_patient_jwt(changed, db_session) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("active", False),
        ("blocked", True),
        ("patient_id", None),
    ],
)
def test_changed_telegram_link_denies_existing_session(
    db_session, linked, field, value
):
    pair = create_session(db_session)
    setattr(linked, field, value)
    db_session.commit()
    assert verify_patient_jwt(pair["access_token"], db_session) is None
    with pytest.raises(TelegramMiniAppAuthExchangeError):
        refresh_patient_session(db_session, pair["refresh_token"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("patient_id", None),
        ("chat_id", 730002),
        ("active", False),
        ("blocked", True),
        ("notifications_enabled", False),
        ("appointment_reminders", False),
    ],
)
def test_restored_link_never_revives_old_session(db_session, linked, field, value):
    launch = signed_init_data()
    pair = exchange_init_data_for_jwt(db_session, launch, bot_token=BOT_TOKEN)
    old_id = verified_claims(pair["access_token"])["sid"]
    old_epoch = linked.patient_link_epoch
    original = getattr(linked, field)

    setattr(linked, field, value)
    db_session.commit()
    assert linked.patient_link_epoch != old_epoch
    assert verify_patient_jwt(pair["access_token"], db_session) is None
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="session_invalid"):
        refresh_patient_session(db_session, pair["refresh_token"])

    setattr(linked, field, original)
    db_session.commit()
    assert linked.patient_link_epoch != old_epoch
    assert verify_patient_jwt(pair["access_token"], db_session) is None
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="session_invalid"):
        refresh_patient_session(db_session, pair["refresh_token"])
    old_row = db_session.get(TelegramMiniAppSession, old_id)
    assert old_row.patient_link_epoch == old_epoch
    assert old_row.revoked_at is None

    current = create_session(db_session)
    auth, listed = list_patient_sessions(db_session, current["access_token"])
    assert auth.session.patient_link_epoch == linked.patient_link_epoch
    assert [row["id"] for row in listed["sessions"]] == [auth.session.id]
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="init_data_replayed"):
        exchange_init_data_for_jwt(db_session, launch, bot_token=BOT_TOKEN)


@pytest.mark.parametrize("field", ["notifications_enabled", "appointment_reminders"])
def test_delivery_opt_out_does_not_prevent_a_fresh_patient_session(
    db_session, linked, field
):
    setattr(linked, field, False)
    db_session.commit()
    pair = create_session(db_session)
    assert verify_patient_jwt(pair["access_token"], db_session)
    assert refresh_patient_session(db_session, pair["refresh_token"])


def test_exchange_reads_current_epoch_after_patient_lock(
    db_session, linked, monkeypatch
):
    cached_epoch = linked.patient_link_epoch
    lock_patient = TelegramMiniAppSessionRepository.lock_patient

    def advance_before_link_lock(repo, patient_id):
        lock_patient(repo, patient_id)
        # Simulate a DB-side generation change after scope resolution.
        # Keep the already-loaded TelegramUser stale to exercise the scalar read.
        db_session.execute(
            update(TelegramUser)
            .where(TelegramUser.id == linked.id)
            .values(patient_link_epoch=cached_epoch + 1)
            .execution_options(synchronize_session=False)
        )
        assert linked.patient_link_epoch == cached_epoch

    monkeypatch.setattr(
        TelegramMiniAppSessionRepository, "lock_patient", advance_before_link_lock
    )
    pair = create_session(db_session)
    auth = authenticate_patient_session(db_session, pair["access_token"])
    assert auth.session.patient_link_epoch == cached_epoch + 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("patient_id", None),
        ("chat_id", 730002),
        ("active", False),
        ("blocked", True),
    ],
)
def test_exchange_rechecks_link_after_patient_lock(
    db_session, linked, monkeypatch, field, value
):
    lock_patient = TelegramMiniAppSessionRepository.lock_patient

    def change_before_link_lock(repo, patient_id):
        lock_patient(repo, patient_id)
        db_session.execute(
            update(TelegramUser)
            .where(TelegramUser.id == linked.id)
            .values(**{field: value})
            .execution_options(synchronize_session=False)
        )

    monkeypatch.setattr(
        TelegramMiniAppSessionRepository, "lock_patient", change_before_link_lock
    )
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="patient_link_invalid"):
        create_session(db_session)
    assert db_session.query(TelegramMiniAppSession).count() == 0


def test_soft_deleted_patient_is_denied(db_session, linked, test_patient):
    pair = create_session(db_session)
    test_patient.is_deleted = True
    db_session.commit()
    assert verify_patient_jwt(pair["access_token"], db_session) is None


def test_revoke_others_preserves_current_access_and_refresh(db_session, linked):
    other = create_session(db_session)
    current = create_session(db_session)
    _, count = revoke_patient_sessions(db_session, current["access_token"])
    assert count == 1
    assert verify_patient_jwt(other["access_token"], db_session) is None
    assert verify_patient_jwt(current["access_token"], db_session)
    refresh_patient_session(db_session, current["refresh_token"])


def test_individual_revoke_is_owned_and_current_requires_logout(db_session, linked):
    current = create_session(db_session)
    other_patient = Patient(last_name="SYNTHETIC-SESSION", first_name="SYNTHETIC")
    db_session.add(other_patient)
    db_session.commit()
    link_patient(db_session, other_patient, chat_id=730002)
    foreign = create_session(db_session, chat_id=730002)
    foreign_id = authenticate_patient_session(
        db_session, foreign["access_token"]
    ).session.id
    with pytest.raises(TelegramMiniAppAuthExchangeError, match="session_not_found"):
        revoke_patient_sessions(
            db_session, current["access_token"], target_id=foreign_id
        )
    current_id = authenticate_patient_session(
        db_session, current["access_token"]
    ).session.id
    with pytest.raises(
        TelegramMiniAppAuthExchangeError, match="current_session_requires_logout"
    ):
        revoke_patient_sessions(
            db_session, current["access_token"], target_id=current_id
        )
    assert list_patient_sessions(db_session, current["access_token"])[1]["total"] == 1
    _, count = revoke_patient_sessions(db_session, current["access_token"], logout=True)
    assert count == 1
    assert verify_patient_jwt(current["access_token"], db_session) is None
    assert verify_patient_jwt(foreign["access_token"], db_session)
