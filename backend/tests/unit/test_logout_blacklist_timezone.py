"""Logout must hand the blacklist an timezone-AWARE expiry.

Follow-up to the logout revocation fix (#3122): once the UserSession
revocation stopped failing early, the flow reached the per-token
blacklist step - and crashed there with "can't compare offset-naive and
offset-aware datetimes", because the access-token expiry was built via
``utcfromtimestamp`` (naive). The comparison against now(UTC) silently
skipped the per-token revocation.

Run:
    pytest backend/tests/unit/test_logout_blacklist_timezone.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.authentication import RefreshToken, UserSession
from app.models.user import User
from app.services.auth_svc import AuthenticationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def test_logout_blacklist_receives_timezone_aware_expiry(db_session, monkeypatch):
    """The expiry handed to blacklist_token must be timezone-aware so the
    internal comparison against now(UTC) cannot raise."""
    import time as time_module

    recorded: list[dict] = []

    user = User(username="bl_probe", hashed_password="x", role="Doctor", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token="bl-probe-refresh",
            jti="bl-probe-jti",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    db_session.add(
        UserSession(
            user_id=user.id,
            refresh_token="bl-probe-refresh",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked=False,
        )
    )
    db_session.commit()

    access_exp = datetime.now(UTC) + timedelta(minutes=15)
    captured: dict = {}

    from app.services import token_blacklist_service as tbs_module

    class FakeBlacklist:
        def blacklist_token(self, db, jti, expires_at, user_id, reason):
            captured.update(jti=jti, expires_at=expires_at, user_id=user_id, reason=reason)

        def blacklist_all_user_tokens(self, db, user_id, reason):
            captured["all"] = reason

    monkeypatch.setattr(
        "app.services.token_blacklist_service.token_blacklist_service",
        FakeBlacklist(),
    )
    # module-level import inside logout flow resolves the same object
    import app.services.token_blacklist_service as tbs
    monkeypatch.setattr(tbs, "token_blacklist_service", FakeBlacklist())

    service = AuthenticationService()
    result = service.logout_user(
        db_session,
        refresh_token="bl-probe-refresh",
        user_id=user.id,
        access_token_jti="bl-probe-jti",
        access_token_exp=access_exp,
    )

    assert result.get("success") is True, result
    assert captured["jti"] == "bl-probe-jti"
    assert captured["expires_at"].tzinfo is not None, (
        "blacklist expiry must be timezone-aware"
    )
    # (time_module imported for symmetry with the assertion message)
    assert time_module.monotonic() > 0
