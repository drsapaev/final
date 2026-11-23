"""Runtime proofs for account-bound refresh rotation and logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.authentication import RefreshToken, TokenBlacklist, UserSession
from app.models.user import User
from app.services.auth_svc import AuthenticationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def seed(db, *, epoch=0, linked=False):
    user = User(
        username=f"SYNTHETIC-{uuid.uuid4().hex}",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        auth_epoch=epoch,
    )
    db.add(user)
    db.flush()
    service = AuthenticationService()
    jti = str(uuid.uuid4())
    token = service.create_refresh_token(user.id, jti, auth_epoch=epoch)
    row = RefreshToken(
        user_id=user.id,
        token=token,
        jti=jti,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(row)
    if linked:
        db.add(
            UserSession(
                user_id=user.id,
                refresh_token=token,
                expires_at=datetime.now(UTC) + timedelta(days=1),
                revoked=False,
            )
        )
    db.commit()
    return service, user, token, row


def test_refresh_rotates_real_jwt_and_linked_session(db_session):
    service, user, token, old = seed(db_session, epoch=4, linked=True)
    result = service.refresh_access_token(db_session, token)
    assert result["success"] is True
    assert result["refresh_token"] != token
    assert service.verify_token(result["access_token"], "access")["auth_epoch"] == 4
    claims = service.verify_token(result["refresh_token"], "refresh")
    assert claims["user_id"] == user.id and claims["auth_epoch"] == 4
    db_session.refresh(old)
    assert old.revoked is True
    assert (
        db_session.query(RefreshToken)
        .filter_by(token=result["refresh_token"], revoked=False)
        .one()
    )
    assert (
        db_session.query(UserSession)
        .filter_by(user_id=user.id, revoked=False)
        .one()
        .refresh_token
        == result["refresh_token"]
    )


def test_access_validation_uses_immutable_numeric_subject(db_session):
    service, user, _, _ = seed(db_session)
    legacy = service.create_access_token({"sub": user.username, "auth_epoch": 0})
    numeric = service.create_access_token({"sub": str(user.id), "auth_epoch": 0})
    assert service.verify_token_with_blacklist(db_session, legacy) is None
    user.username = f"SYNTHETIC-renamed-{uuid.uuid4().hex}"
    db_session.commit()
    assert service.verify_token_with_blacklist(db_session, numeric) is not None


def test_user_access_boundary_rejects_signed_cross_domain_tokens(db_session):
    from app.core.config import settings
    from app.models.patient import Patient

    service, user, _, _ = seed(db_session)
    user.role = "Patient"
    card = Patient(user_id=user.id, first_name="SYNTHETIC", last_name="SYNTHETIC")
    db_session.add(card)
    db_session.commit()
    base = {
        "sub": str(user.id),
        "exp": datetime.now(UTC) + timedelta(minutes=10),
        "jti": str(uuid.uuid4()),
    }

    def signed(**claims):
        return jwt.encode(
            {**base, **claims}, settings.SECRET_KEY, algorithm=service.algorithm
        )

    assert (
        service.verify_token_with_blacklist(
            db_session, signed(scope="telegram_miniapp", patient_id=user.id)
        )
        is None
    )
    assert (
        service.verify_token_with_blacklist(db_session, signed(type="display_device"))
        is None
    )
    patient_token = signed(scope="patient_portal", patient_id=card.id)
    assert service.verify_token_with_blacklist(db_session, patient_token) is not None
    card.user_id = None
    db_session.commit()
    assert service.verify_token_with_blacklist(db_session, patient_token) is None


def test_logout_rejects_revoked_bearer_and_blacklist_storage_failure(db_session):
    from sqlalchemy.exc import OperationalError

    service, user, token, row = seed(db_session)
    bearer = service.create_access_token({"sub": str(user.id), "auth_epoch": 0})
    claims = service.verify_token(bearer)
    db_session.add(
        TokenBlacklist(
            jti=claims["jti"],
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            reason="logout",
        )
    )
    db_session.commit()
    assert (
        service.logout_user(
            db_session, user_id=user.id, logout_all=True, access_token=bearer
        )["success"]
        is False
    )
    db_session.query(TokenBlacklist).delete()
    db_session.commit()

    def break_blacklist(conn, cursor, statement, parameters, context, executemany):
        if (
            "token_blacklist" in statement.lower()
            and statement.lstrip().upper().startswith("SELECT")
        ):
            raise OperationalError(
                "synthetic query", (), RuntimeError("synthetic outage")
            )

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", break_blacklist)
    try:
        assert (
            service.logout_user(
                db_session, user_id=user.id, refresh_token=token, access_token=bearer
            )["success"]
            is False
        )
    finally:
        event.remove(engine, "before_cursor_execute", break_blacklist)
    db_session.refresh(row)
    assert not row.revoked and user.auth_epoch == 0


def test_logout_rechecks_signed_bearer_and_commits_atomically(db_session):
    from app.core.config import settings

    service, user, token, row = seed(db_session, linked=True)
    expired = service.create_access_token(
        {"sub": str(user.id), "auth_epoch": 0}, expires_delta=timedelta(seconds=-1)
    )
    missing_jti = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm=service.algorithm,
    )
    for bearer in (expired, missing_jti):
        assert (
            service.logout_user(db_session, user_id=user.id, access_token=bearer)[
                "success"
            ]
            is False
        )
    bearer = service.create_access_token({"sub": str(user.id), "auth_epoch": 0})
    jti = service.verify_token(bearer)["jti"]
    assert (
        service.logout_user(
            db_session, user_id=user.id, refresh_token=token, access_token=bearer
        )["success"]
        is True
    )
    db_session.refresh(row)
    assert (
        row.revoked
        and db_session.query(TokenBlacklist).filter_by(jti=jti, user_id=user.id).count()
        == 1
    )


def test_replay_of_rotated_refresh_revokes_new_epoch_and_sessions(db_session):
    service, user, token, _ = seed(db_session, linked=True)
    first = service.refresh_access_token(db_session, token)
    assert first["success"] is True
    assert service.refresh_access_token(db_session, token)["success"] is False
    db_session.refresh(user)
    assert user.auth_epoch == 1
    assert (
        db_session.query(RefreshToken).filter_by(user_id=user.id, revoked=False).count()
        == 0
    )
    assert (
        db_session.query(UserSession).filter_by(user_id=user.id, revoked=False).count()
        == 0
    )
    assert (
        service.refresh_access_token(db_session, first["refresh_token"])["success"]
        is False
    )


def test_refresh_rejects_epoch_mismatch_or_deactivated_user(db_session):
    service, user, token, _ = seed(db_session)
    user.auth_epoch = 1
    db_session.commit()
    assert service.refresh_access_token(db_session, token)["success"] is False
    token2 = service.create_refresh_token(user.id, str(uuid.uuid4()), auth_epoch=1)
    claims = service.verify_token(token2, "refresh")
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token=token2,
            jti=claims["jti"],
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    user.is_active = False
    db_session.commit()
    assert service.refresh_access_token(db_session, token2)["success"] is False


def test_legacy_refresh_without_epoch_works_only_at_epoch_zero(db_session):
    import jwt

    from app.core.config import settings

    service, user, _token, _row = seed(db_session)
    jti = str(uuid.uuid4())
    claims = {
        "user_id": user.id,
        "jti": jti,
        "type": "refresh",
        "exp": datetime.now(UTC) + timedelta(days=1),
    }
    token = jwt.encode(
        claims,
        settings.REFRESH_TOKEN_SECRET or settings.SECRET_KEY,
        algorithm=service.algorithm,
    )
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token=token,
            jti=jti,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db_session.commit()
    assert service.refresh_access_token(db_session, token)["success"] is True

    second_jti = str(uuid.uuid4())
    claims["jti"] = second_jti
    stale = jwt.encode(
        claims,
        settings.REFRESH_TOKEN_SECRET or settings.SECRET_KEY,
        algorithm=service.algorithm,
    )
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token=stale,
            jti=second_jti,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    user.auth_epoch = 1
    db_session.commit()
    assert service.refresh_access_token(db_session, stale)["success"] is False


def test_refresh_rejects_individual_blacklist_and_legacy_marker(db_session):
    service, user, token, row = seed(db_session)
    db_session.add(
        TokenBlacklist(
            jti=row.jti,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            reason="logout",
        )
    )
    db_session.commit()
    assert service.refresh_access_token(db_session, token)["success"] is False
    db_session.query(TokenBlacklist).delete()
    db_session.add(
        TokenBlacklist(
            jti=f"all_user_{uuid.uuid4().hex[:20]}",
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            reason="all_user_tokens:legacy",
        )
    )
    db_session.commit()
    assert service.refresh_access_token(db_session, token)["success"] is False


def test_refresh_blacklist_storage_failure_is_fail_closed(db_session):
    from sqlalchemy.exc import OperationalError

    service, user, token, _ = seed(db_session)
    engine = db_session.get_bind()

    def break_blacklist(conn, cursor, statement, parameters, context, executemany):
        if (
            "token_blacklist" in statement.lower()
            and statement.lstrip().upper().startswith("SELECT")
        ):
            raise OperationalError(
                "synthetic query", (), RuntimeError("synthetic outage")
            )

    event.listen(engine, "before_cursor_execute", break_blacklist)
    try:
        assert service.refresh_access_token(db_session, token)["success"] is False
    finally:
        event.remove(engine, "before_cursor_execute", break_blacklist)
    assert (
        db_session.query(RefreshToken).filter_by(user_id=user.id, revoked=False).count()
        == 1
    )


def test_single_logout_revokes_only_its_session_and_access_jti(db_session):
    service, user, token, row = seed(db_session, epoch=3, linked=True)
    other_jti = str(uuid.uuid4())
    other = service.create_refresh_token(user.id, other_jti, auth_epoch=3)
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token=other,
            jti=other_jti,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db_session.commit()
    result = service.logout_user(
        db_session,
        user_id=user.id,
        refresh_token=token,
        access_token_jti="SYNTHETIC-JTI",
        access_token_exp=datetime.now(UTC) + timedelta(minutes=10),
    )
    assert result["success"] is True
    db_session.refresh(user)
    assert user.auth_epoch == 3
    db_session.refresh(row)
    assert row.revoked is True
    assert (
        db_session.query(TokenBlacklist)
        .filter_by(jti="SYNTHETIC-JTI", user_id=user.id)
        .count()
        == 1
    )
    assert service.refresh_access_token(db_session, other)["success"] is True


def test_logout_all_bumps_epoch_and_revokes_sessions(db_session):
    service, user, token, _ = seed(db_session, linked=True)
    assert (
        service.logout_user(db_session, user_id=user.id, logout_all=True)["success"]
        is True
    )
    db_session.refresh(user)
    assert user.auth_epoch == 1
    assert (
        db_session.query(RefreshToken).filter_by(user_id=user.id, revoked=False).count()
        == 0
    )
    assert (
        db_session.query(UserSession).filter_by(user_id=user.id, revoked=False).count()
        == 0
    )
    assert service.refresh_access_token(db_session, token)["success"] is False


def test_logout_rollback_preserves_epoch_and_tokens_on_db_failure(db_session):
    service, user, token, row = seed(db_session, linked=True)

    def fail_before_flush(session, context, instances):
        raise RuntimeError("synthetic failure")

    event.listen(db_session, "before_flush", fail_before_flush)
    try:
        result = service.logout_user(db_session, user_id=user.id, logout_all=True)
    finally:
        event.remove(db_session, "before_flush", fail_before_flush)
    assert result["success"] is False
    db_session.expire_all()
    assert user.auth_epoch == 0 and row.revoked is False
    assert (
        db_session.query(UserSession).filter_by(user_id=user.id, revoked=False).count()
        == 1
    )
