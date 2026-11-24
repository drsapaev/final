"""Patient second-factor challenges against real PostgreSQL and Redis."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import jwt
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.authentication import UserSession
from app.models.patient import Patient
from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.services.authentication_service import get_authentication_service
from app.services.token_blacklist_service import revoke_account_sessions_locked
from app.services.two_factor_auth_api_service import TwoFactorAuthApiService
from app.services.two_factor_patient_pending import create_patient_pending_2fa_locked
from app.services.two_factor_service import (
    PendingSessionInvalid,
    get_two_factor_service,
)
from tests.integration.test_patient_otp_epoch_binding_pg import _patient, pg_otp  # noqa: F401


def _setup(engine):
    user_id = _patient(engine, "+998900000001")
    service = get_two_factor_service()
    secret = service.generate_totp_secret()
    with Session(engine) as db:
        db.add(
            TwoFactorAuth(
                user_id=user_id,
                totp_secret=secret,
                totp_enabled=True,
                totp_verified=True,
            )
        )
        db.commit()
    return user_id, secret


def _sms_pending(pg_otp, user_id):
    engine, service, _, sent = pg_otp
    phone = "+998900000001"
    with Session(engine) as db:
        binding = service.binding_for_phone(db, phone)
    assert binding.user_id == user_id
    asyncio.run(service.send_login_otp(phone, binding=binding))
    with Session(engine) as db:
        grant = service.verify_login_otp(phone, sent[-1], db=db)["verification_grant"]
    with Session(engine) as db:
        result = service.login_with_grant(db, phone, grant)
    assert result["requires_2fa"] and "access_token" not in result
    return result["pending_2fa_token"]


def _exchange(engine, user_id, pending, secret):
    with Session(engine) as db:
        try:
            ok, _, _ = get_two_factor_service().verify_two_factor(
                db,
                user_id,
                totp_code=get_two_factor_service().generate_totp_code(secret),
                pending_token=pending,
                commit=False,
            )
            if not ok:
                return None
            user = db.query(User).filter_by(id=user_id).one()
            return TwoFactorAuthApiService(db).exchange_pending_token_for_tokens(
                user=user,
                pending_token=pending,
                auth_service=get_authentication_service(),
            )
        except PendingSessionInvalid:
            db.rollback()
            return None


def test_sms_pending_single_use_under_concurrent_factor_verification(pg_otp):
    engine, _, _, _ = pg_otp
    user_id, secret = _setup(engine)
    pending = _sms_pending(pg_otp, user_id)
    barrier = Barrier(8)

    def exchange():
        barrier.wait()
        return _exchange(engine, user_id, pending, secret)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: exchange(), range(8)))
    winners = [result for result in results if result]
    assert len(winners) == 1
    assert "refresh_token" not in winners[0]
    claims = jwt.decode(
        winners[0]["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert claims["sub"] == str(user_id) and "scope" not in claims


def test_logout_revokes_pending_before_second_factor(pg_otp):
    engine, _, _, _ = pg_otp
    user_id, secret = _setup(engine)
    pending = _sms_pending(pg_otp, user_id)
    with Session(engine) as db:
        user = (
            db.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        )
        revoke_account_sessions_locked(db, user)
        db.commit()
    assert _exchange(engine, user_id, pending, secret) is None


@pytest.mark.parametrize("logout_first", [False, True])
def test_logout_and_second_factor_serialize(pg_otp, logout_first):
    engine, _, _, _ = pg_otp
    user_id, secret = _setup(engine)
    pending = _sms_pending(pg_otp, user_id)
    started, finished = Event(), Event()

    def logout():
        started.set()
        with Session(engine) as db:
            user = (
                db.query(User)
                .filter_by(id=user_id)
                .with_for_update(key_share=True)
                .one()
            )
            revoke_account_sessions_locked(db, user)
            db.commit()
        finished.set()

    def verify():
        started.set()
        result = _exchange(engine, user_id, pending, secret)
        finished.set()
        return result

    with Session(engine) as db, ThreadPoolExecutor(max_workers=1) as pool:
        if logout_first:
            user = (
                db.query(User)
                .filter_by(id=user_id)
                .with_for_update(key_share=True)
                .one()
            )
            revoke_account_sessions_locked(db, user)
            pending_result = pool.submit(verify)
            assert started.wait(5) and not finished.wait(0.3)
            db.commit()
            assert pending_result.result(timeout=10) is None
        else:
            ok, _, _ = get_two_factor_service().verify_two_factor(
                db,
                user_id,
                totp_code=get_two_factor_service().generate_totp_code(secret),
                pending_token=pending,
                commit=False,
            )
            assert ok
            pending_result = pool.submit(logout)
            assert started.wait(5) and not finished.wait(0.3)
            user = db.query(User).filter_by(id=user_id).one()
            result = TwoFactorAuthApiService(db).exchange_pending_token_for_tokens(
                user=user,
                pending_token=pending,
                auth_service=get_authentication_service(),
            )
            pending_result.result(timeout=10)
            claims = jwt.decode(
                result["access_token"],
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            with Session(engine) as check:
                assert check.get(User, user_id).auth_epoch > claims["auth_epoch"]


@pytest.mark.parametrize(
    "mutation", ["role", "disabled", "bad_scope", "wildcard_scope"]
)
def test_changed_identity_or_invalid_pending_kind_fails_closed(pg_otp, mutation):
    engine, _, _, _ = pg_otp
    user_id, secret = _setup(engine)
    pending = _sms_pending(pg_otp, user_id)
    with Session(engine) as db:
        if mutation == "role":
            user = (
                db.query(User)
                .filter_by(id=user_id)
                .with_for_update(key_share=True)
                .one()
            )
            user.role = "Doctor"
        elif mutation == "disabled":
            twofa = db.query(TwoFactorAuth).filter_by(user_id=user_id).one()
            twofa.totp_enabled = False
        else:
            session = db.query(UserSession).filter_by(refresh_token=pending).one()
            # Invalid canonical encoding and a SQL LIKE wildcard lookalike.
            session.session_kind = (
                "p2fa_pk:0001" if mutation == "bad_scope" else "p2faXpk:1"
            )
        db.commit()
    assert _exchange(engine, user_id, pending, secret) is None


@pytest.mark.parametrize("relinked", [False, True])
def test_passkey_pending_preserves_card_scope_and_rechecks_binding(pg_otp, relinked):
    engine, _, _, _ = pg_otp
    user_id, secret = _setup(engine)
    with Session(engine) as db:
        user = (
            db.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
        )
        patient = Patient(user_id=user_id, first_name="SYNTHETIC", last_name="PATIENT")
        db.add(patient)
        db.flush()
        patient_id = patient.id
        challenge = create_patient_pending_2fa_locked(db, user, patient_id=patient_id)
        pending = challenge["pending_2fa_token"]
        db.commit()
    if relinked:
        with Session(engine) as db:
            patient = db.query(Patient).filter_by(id=patient_id).with_for_update().one()
            patient.user_id = None
            db.commit()
    result = _exchange(engine, user_id, pending, secret)
    if relinked:
        assert result is None
    else:
        assert result and "refresh_token" not in result
        claims = jwt.decode(
            result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert claims["sub"] == str(user_id)
        assert (
            claims["scope"] == "patient_portal" and claims["patient_id"] == patient_id
        )
        assert _exchange(engine, user_id, pending, secret) is None
