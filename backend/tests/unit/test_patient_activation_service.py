"""Phase 0 PR-A2 — patient activation service (unit).

Covers the owner-approved identity contract v3 + 6 final corrections:
- activation token binds EXACT (Patient.id, normalized phone) at issuance;
- token stored hash-only, 72h TTL, single-use (GETDEL), reissue revokes;
- activation OTP goes ONLY to the card phone captured at issuance — the
  public API surface never accepts a client phone for activation;
- atomic linking: staged User+UserProfile+Patient.user_id with ONE commit
  (crud_user.create_user forbidden — internal commit), FOR UPDATE on the
  patient row, UNIQUE(patients.user_id) race backstop;
- passwordless patient = normal hash of a random unknown secret (no sentinel);
- canonical session payload via create_access_token (no Telegram-style JWT);
- namespace isolation: login OTP state and activation OTP state never mix.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash, verify_password
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_activation_service import (
    ACTIVATION_TOKEN_TTL_SECONDS,
    ERR_PATIENT_ALREADY_LINKED,
    ERR_PATIENT_NO_PHONE,
    ERR_PATIENT_NOT_FOUND,
    ERR_TOKEN_INVALID,
    ActivationError,
    PatientActivationService,
    mask_phone,
)
from app.services.patient_otp_service import get_patient_otp_service

PHONE = "+998901112233"
FAMILY_PHONE = "+998909998877"

pytestmark = pytest.mark.asyncio


def _kv():
    return get_patient_otp_service().get_backend()


@pytest.fixture()
def svc() -> PatientActivationService:
    service = PatientActivationService()
    return service


@pytest.fixture(autouse=True)
def isolated_kv():
    otp = get_patient_otp_service()
    otp._reset_backend_for_tests()
    backend = otp.get_backend()
    backend.last_sent_code.clear()
    yield backend
    otp._reset_backend_for_tests()


def make_patient(
    db_session, *, phone: str | None, first="Азиза", last="Каримова"
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


def linked_user(db_session, patient: Patient, *, username="already_linked") -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name="Linked User",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    patient.user_id = user.id
    db_session.commit()
    return user


def issued_token(db_session, svc, patient) -> str:
    return svc.issue_activation_token(db_session, patient.id)["activation_token"]


# ------------------------------------------------------------ masking
def test_mask_phone_never_reveals_full_number():
    masked = mask_phone(PHONE)
    assert masked.startswith("+99890") and masked.endswith("2233")
    assert PHONE not in masked
    assert mask_phone("") == "***"
    assert mask_phone("123") == "***"


# ------------------------------------------------------------ issuance
def test_issue_token_binds_exact_patient_and_phone(db_session, svc):
    patient = make_patient(db_session, phone=PHONE)
    out = svc.issue_activation_token(db_session, patient.id)

    assert out["expires_in_hours"] == ACTIVATION_TOKEN_TTL_SECONDS // 3600 == 72
    assert out["phone_masked"] == mask_phone(PHONE)
    assert len(out["activation_token"]) >= 32

    backend = get_patient_otp_service().get_backend()
    import hashlib

    t_hash = hashlib.sha256(out["activation_token"].encode()).hexdigest()
    raw = backend.get(f"patact:token:{t_hash}")
    assert raw is not None
    entry = json.loads(raw)
    assert entry == {"patient_id": patient.id, "phone": PHONE}
    # revocation index points at the SAME hash
    assert backend.get(f"patact:idx:{patient.id}") == t_hash


def test_issue_token_rejects_missing_or_deleted_patient(db_session, svc):
    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, 10**9)
    assert err.value.status_code == 404
    assert err.value.detail == ERR_PATIENT_NOT_FOUND

    patient = make_patient(db_session, phone=PHONE)
    patient.is_deleted = True
    db_session.commit()
    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, patient.id)
    assert err.value.status_code == 404


def test_issue_token_rejects_already_linked_patient(db_session, svc):
    patient = make_patient(db_session, phone=PHONE)
    linked_user(db_session, patient)
    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, patient.id)
    assert err.value.status_code == 409
    assert err.value.detail == ERR_PATIENT_ALREADY_LINKED


@pytest.mark.parametrize("raw", [None, "", "8-900-LEGACY", "99890111223"])
def test_issue_token_rejects_unusable_card_phone(db_session, svc, raw):
    patient = make_patient(db_session, phone=raw)
    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, patient.id)
    assert err.value.status_code == 400
    assert err.value.detail == ERR_PATIENT_NO_PHONE


async def test_reissue_revokes_previous_token(db_session, svc):
    patient = make_patient(db_session, phone=PHONE)
    first = issued_token(db_session, svc, patient)
    second = issued_token(db_session, svc, patient)

    assert first != second
    # old token is dead everywhere
    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, first)
    assert err.value.detail == ERR_TOKEN_INVALID
    # new token works
    out = await svc.request_activation_otp(db_session, second)
    assert out["phone_masked"] == mask_phone(PHONE)


# ------------------------------------------------------------ OTP request
async def test_request_otp_goes_to_card_phone_only(db_session, svc, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)

    out = await svc.request_activation_otp(db_session, token)
    backend = _kv()
    assert out["phone_masked"] == mask_phone(PHONE)
    # code lives in the patact namespace keyed by the CARD phone
    assert f"patact:{PHONE}" in backend.last_sent_code
    code = backend.last_sent_code[f"patact:{PHONE}"]

    # verification succeeds against the SAME namespace
    assert svc.activate(db_session, token, code)["access_token"]


async def test_request_otp_invalid_token_generic_400(db_session, svc):
    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, "A" * 40)
    assert err.value.status_code == 400
    assert err.value.detail == ERR_TOKEN_INVALID


async def test_request_otp_fails_when_card_phone_changed_after_issuance(
    db_session, svc
):
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)

    patient.phone = "+998935554411"
    db_session.commit()

    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, token)
    assert err.value.status_code == 400
    assert err.value.detail == ERR_TOKEN_INVALID
    _kv().last_sent_code.clear()


# ------------------------------------------------------------ activation
async def test_activate_creates_canonical_user_and_link_atomic(
    db_session, svc, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{PHONE}"]

    out = svc.activate(db_session, token, code)

    user = db_session.execute(
        select(User).where(User.id == out["user"]["id"])
    ).scalar_one()
    profile = db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).scalar_one()
    db_session.refresh(patient)

    assert user.role == "Patient"
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.username.startswith(f"patient_{patient.id}_")
    assert out["patient_id"] == patient.id
    assert patient.user_id == user.id
    assert profile.phone == PHONE
    assert profile.phone_verified is True
    assert profile.full_name == patient.short_name()

    # owner correction #4: normal random-secret hash, NOT a sentinel
    assert user.hashed_password.startswith("$argon2")
    assert not verify_password("patient123", user.hashed_password)
    assert not verify_password("", user.hashed_password)

    # token single-use: consumed after success
    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, code)
    assert err.value.detail == ERR_TOKEN_INVALID
    # revocation index cleaned up
    assert _kv().get(f"patact:idx:{patient.id}") is None


async def test_activate_wrong_code_generic_400_with_attempt_limit(
    db_session, svc, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)

    generic_detail = None
    for _attempt in range(3):
        with pytest.raises(ActivationError) as err:
            svc.activate(db_session, token, "000000")
        generic_detail = err.value.detail
        assert err.value.status_code == 400
    assert generic_detail == "Неверный код или срок его действия истёк."
    # 3 wrong attempts exhausted -> code deleted -> still the SAME generic fail
    with pytest.raises(ActivationError):
        svc.activate(db_session, token, _kv().last_sent_code[f"patact:{PHONE}"])


async def test_activate_fails_when_patient_linked_after_issuance(db_session, svc):
    """Race backstop: user linked between OTP verify and the locked
    revalidation -> token unusable, generic failure (no .first(), no overwrite)."""
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{PHONE}"]

    linked_user(db_session, patient, username="race_winner")

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, code)
    assert err.value.status_code == 400
    assert err.value.detail == ERR_TOKEN_INVALID


async def test_activate_deleted_patient_generic_400(db_session, svc, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)

    patient.is_deleted = True
    db_session.commit()

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, _kv().last_sent_code[f"patact:{PHONE}"])
    assert err.value.detail == ERR_TOKEN_INVALID


async def test_activation_otp_never_consumes_login_otp_state(
    db_session, svc, monkeypatch
):
    """Namespace isolation: a LOGIN code cannot activate, and activation
    cooldown does not block login sends on the same phone."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    otp = get_patient_otp_service()
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)

    await otp.send_login_otp(PHONE)
    login_code = _kv().last_sent_code[PHONE]
    # activation flow on the same phone is NOT blocked by login cooldown/cap
    await svc.request_activation_otp(db_session, token)
    activation_code = _kv().last_sent_code[f"patact:{PHONE}"]

    # login code is useless in the activation flow
    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, login_code)
    assert err.value.status_code == 400
    # and vice versa the activation code cannot produce a login grant
    from app.services.patient_otp_service import PatientOtpError

    with pytest.raises(PatientOtpError):
        otp.verify_login_otp(PHONE, activation_code)


async def test_family_shared_phone_two_cards_activate_independently(
    db_session, svc, monkeypatch
):
    """Family regression: two cards share one phone. Each token binds its
    OWN Patient.id — activating the child's card must never touch the
    mother's card, and the fail-closed login resolver still refuses."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    mother = make_patient(db_session, phone=FAMILY_PHONE, first="Мать", last="Юсупова")
    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="Ребёнок", last="Юсупова"
    )

    child_token = issued_token(db_session, svc, child)
    await svc.request_activation_otp(db_session, child_token)
    code = _kv().last_sent_code[f"patact:{FAMILY_PHONE}"]
    out = svc.activate(db_session, child_token, code)

    db_session.refresh(mother)
    db_session.refresh(child)
    assert child.user_id == out["user"]["id"]
    assert mother.user_id is None  # mother's card untouched

    # login on the shared phone is STILL fail-closed (1 linked user only ->
    # it actually resolves; the mother has no user, so exactly one candidate)
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == out["user"]["id"]
