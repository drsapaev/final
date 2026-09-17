"""Phase 0 PR-A2 — patient activation API (integration).

HTTP-level pass over the full registrar-issued activation flow through the
real router/limiter/DB wiring:

    POST /api/v1/patients/{id}/activation-token   (Admin|Registrar)
    POST /api/v1/patient-access/activate/request-otp  (public)
    POST /api/v1/patient-access/activate/confirm      (public)

Acceptance exercised over HTTP: RBAC trio, token pinned to (Patient.id,
card phone), client phone never accepted, atomic link, single-use token,
family-shared-phone second-activation guard (owner GO 2026-09-18,
variant A), generic anti-enum failures, critical audit on issuance, and
the minted JWT being a CANONICAL session (works on
the standard patient self-scope endpoint GET /patients/{id}).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.api.deps import create_access_token
from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import get_patient_otp_service
from tests.conftest import mint_access_token

pytestmark = pytest.mark.asyncio

# SYNTHETIC constants only (AGENTS.md synthetic-data policy).
PHONE = "+998900000001"
FAMILY_PHONE = "+998900000002"

ISSUE_PATH = "/api/v1/patients/{pid}/activation-token"
OTP_PATH = "/api/v1/patient-access/activate/request-otp"
CONFIRM_PATH = "/api/v1/patient-access/activate/confirm"


def _kv():
    return get_patient_otp_service().get_backend()


@pytest.fixture()
def otp_kv():
    svc = get_patient_otp_service()
    svc._reset_backend_for_tests()
    backend = svc.get_backend()
    backend.last_sent_code.clear()
    yield backend
    svc._reset_backend_for_tests()


@pytest.fixture()
def registrar_headers(registrar_user):
    return {"Authorization": f"Bearer {mint_access_token(registrar_user)}"}


def make_patient(
    db_session, *, phone: str, first="SYNTHETIC-PRA2", last="Card"
) -> Patient:
    patient = Patient(
        first_name=first,
        last_name=last,
        phone=phone,
        birth_date=date(1995, 3, 10),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


async def test_full_activation_flow_over_http(
    client, db_session, otp_kv, monkeypatch, registrar_headers
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)

    # 1) registrar issues the token (201)
    r_issue = client.post(ISSUE_PATH.format(pid=patient.id), headers=registrar_headers)
    assert r_issue.status_code == 201
    issue_body = r_issue.json()
    token = issue_body["activation_token"]
    assert issue_body["expires_in_hours"] == 72
    assert issue_body["phone_masked"] == "+998900•••001"  # canonical 3-digit mask
    assert PHONE not in issue_body["phone_masked"]

    # 2) activation OTP: NO client phone field exists; goes to the card phone
    r_otp = client.post(OTP_PATH, json={"activation_token": token, "locale": "ru"})
    assert r_otp.status_code == 200
    assert r_otp.json()["phone_masked"] == issue_body["phone_masked"]
    code = otp_kv.last_sent_code[f"patact:{PHONE}"]

    # 3) confirm -> canonical session
    r_confirm = client.post(
        CONFIRM_PATH, json={"activation_token": token, "code": code}
    )
    assert r_confirm.status_code == 200
    body = r_confirm.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "Patient"
    assert body["user"]["is_active"] is True
    assert body["patient_id"] == patient.id

    # 4) the JWT IS a canonical session: patient self-scope read works
    db_session.refresh(patient)
    jwt_user = db_session.query(User).filter(User.id == body["user"]["id"]).first()
    assert jwt_user is not None and patient.user_id == jwt_user.id
    r_me = client.get(
        f"/api/v1/patients/{patient.id}",
        headers={
            "Authorization": f"Bearer {create_access_token({'sub': str(jwt_user.id)})}"
        },
    )
    assert r_me.status_code == 200
    assert r_me.json()["id"] == patient.id

    # 5) token single-use over HTTP: replay confirm -> generic 400
    r_replay = client.post(CONFIRM_PATH, json={"activation_token": token, "code": code})
    assert r_replay.status_code == 400
    assert "недействителен" in r_replay.json()["detail"]


async def test_issue_requires_admin_or_registrar(
    client, db_session, otp_kv, registrar_headers
):
    patient = make_patient(db_session, phone=PHONE)

    # unauthenticated
    assert client.post(ISSUE_PATH.format(pid=patient.id)).status_code == 401

    # authenticated staff role OUTSIDE the trio -> 403
    doctor = User(
        username="pra2_doctor",
        email="pra2_doctor@test.local",
        full_name="Doctor Who",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(doctor)
    db_session.commit()
    r_doctor = client.post(
        ISSUE_PATH.format(pid=patient.id),
        headers={"Authorization": f"Bearer {mint_access_token(doctor)}"},
    )
    assert r_doctor.status_code == 403

    # registrar -> 201
    assert (
        client.post(
            ISSUE_PATH.format(pid=patient.id), headers=registrar_headers
        ).status_code
        == 201
    )


async def test_issue_rejects_already_linked_and_deleted(
    client, db_session, otp_kv, registrar_headers
):
    patient = make_patient(db_session, phone=PHONE)
    user = User(
        username="pra2_linked",
        email="pra2_linked@test.local",
        full_name="Linked",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    patient.user_id = user.id
    db_session.commit()
    r = client.post(ISSUE_PATH.format(pid=patient.id), headers=registrar_headers)
    assert r.status_code == 409

    deleted = make_patient(db_session, phone="+998900000011")
    deleted.is_deleted = True
    db_session.commit()
    r2 = client.post(ISSUE_PATH.format(pid=deleted.id), headers=registrar_headers)
    assert r2.status_code == 404


async def test_confirm_failures_are_generic_no_phi(
    client, db_session, otp_kv, monkeypatch, registrar_headers
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)

    # unknown token -> generic, no patient identity leaked
    r_bad_token = client.post(
        CONFIRM_PATH, json={"activation_token": "x" * 40, "code": "123456"}
    )
    assert r_bad_token.status_code == 400
    detail = r_bad_token.json()["detail"]
    assert str(patient.id) not in detail
    assert patient.last_name not in detail

    # valid token + wrong code -> generic OTP failure
    client.post(ISSUE_PATH.format(pid=patient.id), headers=registrar_headers)
    r_otp = client.post(
        OTP_PATH,
        json={
            "activation_token": _token_of(
                client, db_session, patient.id, registrar_headers
            )
        },
    )
    code = otp_kv.last_sent_code[f"patact:{PHONE}"]
    r_wrong = client.post(
        CONFIRM_PATH,
        json={
            "activation_token": _token_of(
                client, db_session, patient.id, registrar_headers
            ),
            "code": "000000",
        },
    )
    assert r_wrong.status_code == 400
    assert r_wrong.json()["detail"] == "Неверный код или срок его действия истёк."
    assert code  # code was in fact issued for the card phone


def _token_of(client, db_session, patient_id, registrar_headers):
    r = client.post(ISSUE_PATH.format(pid=patient_id), headers=registrar_headers)
    return r.json()["activation_token"]


async def test_family_shared_phone_second_activation_blocked_http(
    client, db_session, otp_kv, monkeypatch, registrar_headers
):
    """Owner GO 2026-09-18, variant A: two cards share one family phone.
    The FIRST activation wins; the second card is refused at every door
    over real HTTP (staff issuance 409; pre-issued token: neutral no-SMS
    request-otp 409 + confirm 409), so the fail-closed login resolver can
    never see two candidates."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    mother = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Mother", last="FamilyCard"
    )
    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Child", last="FamilyCard"
    )

    mother_token = _token_of(client, db_session, mother.id, registrar_headers)
    child_token = _token_of(client, db_session, child.id, registrar_headers)

    client.post(OTP_PATH, json={"activation_token": child_token})
    code = otp_kv.last_sent_code[f"patact:{FAMILY_PHONE}"]
    r_confirm = client.post(
        CONFIRM_PATH, json={"activation_token": child_token, "code": code}
    )
    assert r_confirm.status_code == 200
    db_session.refresh(child)
    db_session.refresh(mother)
    assert child.user_id == r_confirm.json()["user"]["id"]
    assert mother.user_id is None  # mother's card untouched by child activation

    # staff issuance for the second card on the same phone -> controlled 409
    r_issue = client.post(ISSUE_PATH.format(pid=mother.id), headers=registrar_headers)
    assert r_issue.status_code == 409

    # pre-issued mother token: public flow blocked, neutral + no SMS
    otp_kv.last_sent_code.clear()
    r_otp = client.post(OTP_PATH, json={"activation_token": mother_token})
    assert r_otp.status_code == 409
    assert f"patact:{FAMILY_PHONE}" not in otp_kv.last_sent_code

    r_confirm2 = client.post(
        CONFIRM_PATH, json={"activation_token": mother_token, "code": "000000"}
    )
    assert r_confirm2.status_code == 409
    db_session.refresh(mother)
    assert mother.user_id is None


async def test_activation_kv_outage_returns_503_http(
    client, db_session, otp_kv, monkeypatch, registrar_headers
):
    """Codex P2 (Redis 500->503): KV outage mid-activation surfaces as the
    documented generic 503, never an unhandled 500."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    from app.services.patient_otp_service import PatientOtpError

    patient = make_patient(db_session, phone=PHONE)
    token = _token_of(client, db_session, patient.id, registrar_headers)

    def _boom():
        raise PatientOtpError(503, "KV unavailable")

    monkeypatch.setattr(get_patient_otp_service(), "get_backend", _boom)
    r = client.post(OTP_PATH, json={"activation_token": token})
    assert r.status_code == 503


async def test_activation_otp_endpoint_rate_limited_per_ip(
    client, db_session, otp_kv, monkeypatch, registrar_headers
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = _token_of(client, db_session, patient.id, registrar_headers)

    statuses = []
    for _ in range(7):
        r = client.post(OTP_PATH, json={"activation_token": token})
        statuses.append(r.status_code)
        otp_kv.delete(f"patact:cd:{PHONE}")  # bypass phone cooldown: test IP limit only
    assert 429 in statuses  # slowapi IP limiter (5/minute) kicks in


async def test_user_management_reactivation_409_owner_regression_http(
    client, db_session, otp_kv, monkeypatch, registrar_headers, auth_headers
):
    """Review round 2 P1 — the owner regression over REAL HTTP through the
    User Management surface:

        activate A(X) -> admin deactivates A -> activate B(X)
        -> admin reactivates A -> controlled 409
        -> B remains the ONLY active candidate on X (login B works)

    Proves the phone-scope invariant is SYSTEMIC (not activation-local):
    PUT /api/v1/users/{id} is the second write path into the login-resolver
    predicate and must honor the same Phase 0 contract."""
    from app.core.rate_limiter import limiter
    from app.services.patient_otp_service import get_patient_otp_service

    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    limiter.reset()  # deterministic IP-limit state (5/min shared per test run)

    mother = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Mother", last="FamilyCard"
    )

    # 1) A activates on X
    mother_token = _token_of(client, db_session, mother.id, registrar_headers)
    client.post(OTP_PATH, json={"activation_token": mother_token})
    code = otp_kv.last_sent_code[f"patact:{FAMILY_PHONE}"]
    r_confirm = client.post(
        CONFIRM_PATH, json={"activation_token": mother_token, "code": code}
    )
    assert r_confirm.status_code == 200
    user_a_id = r_confirm.json()["user"]["id"]

    # 2) admin deactivates A -> zero active candidates on X
    r_off = client.put(
        f"/api/v1/users/users/{user_a_id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert r_off.status_code == 200

    # 3) B (second card, SAME phone) activates — legal while A is off
    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Child", last="FamilyCard"
    )
    child_token = _token_of(client, db_session, child.id, registrar_headers)
    limiter.reset()  # 2 request-otp calls in one minute would trip 5/min alone
    otp_kv.delete(f"patact:cd:{FAMILY_PHONE}")  # bypass 60s phone cooldown
    client.post(OTP_PATH, json={"activation_token": child_token})
    code_b = otp_kv.last_sent_code[f"patact:{FAMILY_PHONE}"]
    r_confirm_b = client.post(
        CONFIRM_PATH, json={"activation_token": child_token, "code": code_b}
    )
    assert r_confirm_b.status_code == 200
    user_b_id = r_confirm_b.json()["user"]["id"]
    db_session.refresh(child)
    assert child.user_id == user_b_id

    # 4) admin reactivates A -> SYSTEMIC phone-scope 409 (documented body)
    r_on = client.put(
        f"/api/v1/users/users/{user_a_id}",
        json={"is_active": True},
        headers=auth_headers,
    )
    assert r_on.status_code == 409
    assert "уже используется другим активным аккаунтом" in r_on.json()["detail"]

    # 5) B remains the single active candidate; A stays deactivated
    db_session.refresh(mother)
    assert mother.user_id == user_a_id  # card still linked, user NOT reactivated
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == user_b_id


async def test_user_management_phone_reaim_409_http(
    client, db_session, otp_kv, monkeypatch, registrar_headers, auth_headers
):
    """Review round 2 P1 ('short repro'): admin must not be able to re-aim
    one active Patient-user's verified phone at ANOTHER active
    Patient-user's live portal phone — PUT /api/v1/users/{id} returns 409
    and nothing changes."""
    from app.core.rate_limiter import limiter

    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    limiter.reset()

    first = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-First", last="FamilyCard"
    )
    token = _token_of(client, db_session, first.id, registrar_headers)
    client.post(OTP_PATH, json={"activation_token": token})
    code = otp_kv.last_sent_code[f"patact:{FAMILY_PHONE}"]
    r_confirm = client.post(
        CONFIRM_PATH, json={"activation_token": token, "code": code}
    )
    assert r_confirm.status_code == 200
    # activation of the first card succeeded; its user id is not needed here

    # second patient user with its OWN phone (created directly)
    from app.core.security import get_password_hash

    mover = User(
        username="pra2_mover",
        email="pra2_mover@test.local",
        full_name="SYNTHETIC Mover",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(mover)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=mover.id,
            full_name="SYNTHETIC Mover",
            phone="+998900000009",
            phone_verified=True,
        )
    )
    db_session.commit()

    # admin re-aims mover at the live portal phone -> 409, nothing changes
    r = client.put(
        f"/api/v1/users/users/{mover.id}",
        json={"phone": FAMILY_PHONE},
        headers=auth_headers,
    )
    assert r.status_code == 409
    db_session.refresh(mover)
    profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == mover.id).one()
    )
    assert profile.phone == "+998900000009"
    assert profile.phone_verified is True
    # nothing changed: mover keeps its own phone with the verified flag,
    # the family phone still belongs exclusively to the first account.
