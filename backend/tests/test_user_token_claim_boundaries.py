"""Shared-key patient JWTs must never authenticate as an unrelated User."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from starlette.requests import Request

from app.api.deps import create_access_token
from app.api.v1.endpoints.websocket_auth import resolve_websocket_token_user
from app.core.config import settings
from app.middleware.idempotency_middleware import IdempotencyMiddleware
from app.services.ai_chat_api_service import AIChatApiService
from app.ws.cashier_ws import cashier_websocket
from app.ws.chat_ws import _authenticate_by_token


def _token(user_id, claims):
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            **claims,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


@pytest.fixture(
    params=[
        {"scope": "patient", "type": "access"},
        {"scope": "patient", "type": "refresh"},
        {"scope": None, "type": "access"},
        {"scope": "other", "type": "access"},
        {"type": "refresh"},
        {"type": "pending_2fa"},
        {"type": None},
        {"typ": "display_device"},
        {"token_type": "display_device"},
    ]
)
def rejected_token(request, admin_user):
    # Deliberate collision: a patient token's sub is an existing Admin user ID.
    return _token(admin_user.id, request.param)


def _request(token):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
    )


def test_non_user_tokens_cannot_read_staff_2fa_devices(client, rejected_token):
    response = client.get(
        "/api/v1/2fa/devices", headers={"Authorization": f"Bearer {rejected_token}"}
    )
    assert response.status_code == 401


def test_non_user_tokens_cannot_replay_cached_user_response(rejected_token):
    middleware = IdempotencyMiddleware(app=lambda *_: None)
    assert middleware._verified_principal(_request(rejected_token)) is None


def test_rejected_patient_token_cannot_consume_push_user_rate_bucket(
    client, admin_user, monkeypatch
):
    from app.core.rate_limiter import limiter

    token = _token(admin_user.id, {"scope": "patient", "type": "access"})
    checked = []
    monkeypatch.setattr(limiter, "_enabled", True)
    monkeypatch.setattr(
        limiter, "_check_request_limit", lambda *a, **kw: checked.append(1)
    )
    response = client.post(
        "/api/v1/push/devices/register",
        json={"provider": "fcm", "platform": "android", "token": "synthetic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert checked == []


def test_non_user_tokens_cannot_open_user_websockets(db_session, rejected_token):
    assert resolve_websocket_token_user(rejected_token, db_session) is None
    assert asyncio.run(_authenticate_by_token(rejected_token, db_session)) is None
    repository = SimpleNamespace(
        get_user=lambda _user_id: pytest.fail("user lookup must not occur")
    )
    service = AIChatApiService(db=None, repository=repository)
    assert (
        service.authenticate_websocket_user(
            token=rejected_token,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        is None
    )


def test_non_user_tokens_cannot_open_cashier_websocket(monkeypatch, rejected_token):
    monkeypatch.setattr(
        "app.api.v1.endpoints.ws_token.extract_ws_token", lambda _: rejected_token
    )
    websocket = SimpleNamespace(close=AsyncMock())
    asyncio.run(cashier_websocket(websocket))
    websocket.close.assert_awaited_once_with(code=4401)


@pytest.mark.parametrize("claims", [{}, {"type": "access"}])
def test_staff_user_access_and_replay_principal_are_preserved(
    client, admin_user, claims
):
    token = _token(admin_user.id, claims)
    response = client.get(
        "/api/v1/2fa/devices", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    middleware = IdempotencyMiddleware(app=lambda *_: None)
    assert middleware._verified_principal(_request(token))["sub"] == str(admin_user.id)


def test_canonical_patient_user_token_remains_accepted(client, db_session):
    from app.models.user import User

    user = User(
        username="synthetic-patient-auth",
        hashed_password="unused",
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token({"sub": str(user.id)})
    response = client.get(
        "/api/v1/2fa/devices", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.fixture
def patient_scoped_identity(db_session):
    from app.models.patient import Patient
    from app.models.user import User

    user = User(
        username="synthetic-scope-patient",
        hashed_password="unused",
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    patient = Patient(
        user_id=user.id, first_name="Synthetic", last_name="Scope", is_deleted=False
    )
    db_session.add(patient)
    db_session.commit()
    token = _token(user.id, {"scope": "patient_portal", "patient_id": patient.id})
    return user, patient, token


def _assert_scoped_ws(db, token, expected):
    from app.repositories.ai_chat_api_repository import AIChatApiRepository

    queue_user = resolve_websocket_token_user(token, db)
    chat_user = asyncio.run(_authenticate_by_token(token, db))
    ai_user = AIChatApiService(
        db, repository=AIChatApiRepository(db)
    ).authenticate_websocket_user(
        token=token, secret_key=settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    # Chat and AI sockets do not reauthorize live connections and so do not
    # accept patient-scoped tokens until they support live revocation.
    assert [u is not None for u in (queue_user, chat_user, ai_user)] == [
        expected,
        False,
        False,
    ]


@pytest.mark.parametrize(
    "change", ["role", "superuser", "inactive", "relink", "deleted"]
)
def test_scoped_patient_token_tracks_current_role_and_card(
    client, db_session, patient_scoped_identity, change
):
    user, patient, token = patient_scoped_identity
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/2fa/devices", headers=headers).status_code == 200
    _assert_scoped_ws(db_session, token, True)
    if change == "role":
        user.role = "Admin"
    elif change == "superuser":
        user.is_superuser = True
    elif change == "inactive":
        user.is_active = False
    elif change == "relink":
        patient.user_id = None
    else:
        patient.is_deleted = True
    db_session.commit()
    assert client.get("/api/v1/2fa/devices", headers=headers).status_code == 401
    _assert_scoped_ws(db_session, token, False)


@pytest.mark.parametrize("patient_id", [None, "1", 0, -1, True])
def test_patient_scope_requires_valid_card_id(client, admin_user, patient_id):
    token = _token(admin_user.id, {"scope": "patient_portal", "patient_id": patient_id})
    assert (
        client.get(
            "/api/v1/2fa/devices", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )


def test_patient_scope_refreshes_stale_identity_before_role_check(
    db_session, patient_scoped_identity
):
    from fastapi import HTTPException
    from sqlalchemy import update

    from app.api.deps import get_current_user
    from app.models.user import User

    user, _patient, token = patient_scoped_identity
    assert user.role == "Patient"
    db_session.execute(
        update(User)
        .where(User.id == user.id)
        .values(role="Admin")
        .execution_options(synchronize_session=False)
    )
    assert user.role == "Patient"  # cached ORM instance intentionally stale
    with pytest.raises(HTTPException) as failure:
        asyncio.run(get_current_user(token=token, db=db_session))
    assert failure.value.status_code == 401


def test_scoped_http_and_idempotency_authorization_use_one_snapshot(
    db_session, patient_scoped_identity
):
    from sqlalchemy import event

    from app.api.deps import get_current_user
    from app.middleware.idempotency_middleware import _user_authorized_in_db

    user, patient, token = patient_scoped_identity
    user_id, patient_id = user.id, patient.id
    selects = []

    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = db_session.get_bind().engine
    event.listen(engine, "before_cursor_execute", observe)
    try:
        assert asyncio.run(get_current_user(token=token, db=db_session)).id == user_id
        assert len(selects) == 1
        selects.clear()
        allowed, role, superuser = _user_authorized_in_db(
            db_session, user_id, None, None, patient_scope_id=patient_id
        )
        assert allowed and role == "Patient" and not superuser
        assert len(selects) == 1
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_scoped_http_and_idempotency_deny_blacklisted_token(
    client, db_session, patient_scoped_identity
):
    from app.middleware.idempotency_middleware import _user_authorized_in_db
    from app.models.authentication import TokenBlacklist

    user, patient, _ = patient_scoped_identity
    db_session.add(
        TokenBlacklist(
            user_id=user.id,
            jti="synthetic-denied-jti",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db_session.commit()
    allowed, _, _ = _user_authorized_in_db(
        db_session, user.id, None, "synthetic-denied-jti", patient_scope_id=patient.id
    )
    assert not allowed
    token = _token(
        user.id,
        {
            "scope": "patient_portal",
            "patient_id": patient.id,
            "jti": "synthetic-denied-jti",
        },
    )
    assert (
        client.get(
            "/api/v1/2fa/devices", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("change", ["role", "superuser", "relink", "deleted"])
def test_patient_scoped_booking_replay_rechecks_user_and_card(
    client, db_session, patient_scoped_identity, change
):
    from app.models.appointment import Appointment

    user, patient, token = patient_scoped_identity
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"synthetic-patient-scope-{change}",
    }
    body = {"appointmentDate": str(date.today() + timedelta(days=3))}
    first = client.post("/api/v1/patients/booking", headers=headers, json=body)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/patients/booking", headers=headers, json=body)
    assert second.status_code == 201, second.text
    assert second.json()["appointment_id"] == first.json()["appointment_id"]
    assert db_session.query(Appointment).filter_by(patient_id=patient.id).count() == 1

    if change == "role":
        user.role = "Admin"
    elif change == "superuser":
        user.is_superuser = True
    elif change == "relink":
        from app.models.patient import Patient

        patient.user_id = None
        db_session.flush()
        db_session.add(
            Patient(user_id=user.id, first_name="Synthetic", last_name="Relink")
        )
    else:
        patient.is_deleted = True
    db_session.commit()
    denied = client.post("/api/v1/patients/booking", headers=headers, json=body)
    assert denied.status_code != 201, denied.text
    assert db_session.query(Appointment).filter_by(patient_id=patient.id).count() == 1
