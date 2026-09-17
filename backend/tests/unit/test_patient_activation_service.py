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

# SYNTHETIC constants only (AGENTS.md synthetic-data policy): obviously
# fake sequential numbers, never a real-looking name+phone combination.
PHONE = "+998900000001"
FAMILY_PHONE = "+998900000002"
CHANGED_PHONE = "+998900000009"

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
    db_session, *, phone: str | None, first="SYNTHETIC-PRA2", last="Card"
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
def test_mask_phone_canonical_last_three_digits_only():
    """Codex P1 (PR #3320 round 1): the repo-canonical PII mask keeps only
    the LAST THREE digits (+998901•••233, AGENTS.md / app/core/pii_masker).
    The local 4-digit mask was a policy violation."""
    masked = mask_phone(PHONE)
    assert masked == "+998900•••001"
    assert PHONE not in masked
    assert "0001" not in masked  # no fourth trailing digit
    assert mask_phone("") == "***"
    assert mask_phone("123") == "***"  # non-maskable input never leaks
    assert mask_phone("+998") == "***"


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

    patient.phone = CHANGED_PHONE
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


def _bound_portal_user(db_session, phone: str, username: str) -> User:
    """Conflict simulator: an active verified Patient-user ALREADY on phone."""
    user = User(
        username=username,
        email=f"{username}@synthetic.local",
        full_name="SYNTHETIC Bound User",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            full_name="SYNTHETIC Bound User",
            phone=phone,
            phone_verified=True,
        )
    )
    db_session.commit()
    return user


async def _activated_card(db_session, svc, phone: str, *, label: str) -> Patient:
    """Happy-path activation of one card; returns the linked patient."""
    patient = make_patient(
        db_session, phone=phone, first=f"SYNTHETIC-{label}", last="FamilyCard"
    )
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{phone}"]
    out = svc.activate(db_session, token, code)
    db_session.refresh(patient)
    assert patient.user_id == out["user"]["id"]
    return patient


async def test_family_shared_phone_only_first_activation_wins(
    db_session, svc, monkeypatch
):
    """Owner GO 2026-09-18, variant A (Codex P1 shared-phone lockout):
    two cards share one family phone. The FIRST activation succeeds; the
    second card can NEVER create a second portal identity on the same
    phone — staff issuance is a controlled 409, and any pre-issued token
    fails without consuming OTP or sending SMS — so the fail-closed login
    resolver can never see two candidates (no permanent 401 lockout)."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    from app.services import patient_activation_service as pas

    mother = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Mother", last="FamilyCard"
    )
    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Child", last="FamilyCard"
    )

    mother_token = issued_token(db_session, svc, mother)  # pre-conflict issuance
    child_token = issued_token(db_session, svc, child)

    await svc.request_activation_otp(db_session, child_token)
    code = _kv().last_sent_code[f"patact:{FAMILY_PHONE}"]
    out = svc.activate(db_session, child_token, code)  # FIRST activation wins

    db_session.refresh(mother)
    db_session.refresh(child)
    assert child.user_id == out["user"]["id"]
    assert mother.user_id is None  # mother's card untouched

    # second identity on the same phone is refused at every door
    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, mother.id)
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_ISSUANCE_PHONE_BOUND

    _kv().last_sent_code.clear()
    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, mother_token)
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_ACTIVATION_GENERIC  # neutral, no SMS

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, mother_token, "000000")
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_PHONE_ALREADY_BOUND

    # login on the shared phone resolves exactly the ONE portal user
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == out["user"]["id"]


async def test_issuance_blocked_when_phone_already_bound(db_session, svc, monkeypatch):
    """GO point 1 (owner variant A): the staff early check fires BEFORE any
    token exists, so the registrar learns about the conflict immediately."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    from app.services import patient_activation_service as pas

    await _activated_card(db_session, svc, FAMILY_PHONE, label="Mother")
    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Child", last="FamilyCard"
    )

    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, child.id)
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_ISSUANCE_PHONE_BOUND
    db_session.refresh(child)
    assert child.user_id is None


async def test_activate_conflict_409_and_token_not_consumed(db_session, svc):
    """GO point 4: authoritative conflict -> 409, NOTHING created, token NOT
    consumed, card stays user_id=NULL (registrar keeps control)."""
    from app.services import patient_activation_service as pas

    child = make_patient(
        db_session, phone=FAMILY_PHONE, first="SYNTHETIC-Child", last="FamilyCard"
    )
    child_token = issued_token(db_session, svc, child)
    _bound_portal_user(db_session, FAMILY_PHONE, "synthetic_bound_user")

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, child_token, "000000")
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_PHONE_ALREADY_BOUND
    # token NOT consumed -> still resolvable (registrar can re-redeem later
    # once the conflict is resolved, or reissue)
    assert svc._lookup_entry(child_token) is not None
    db_session.refresh(child)
    assert child.user_id is None


async def test_activate_rechecks_conflict_under_lock_before_otp(
    db_session, svc, monkeypatch
):
    """GO points 3+5: the authoritative candidate re-read happens INSIDE the
    phone-scope lock and BEFORE the single-use OTP consume — a race-window
    conflict (created between precheck and lock) must not eat a valid OTP.
    The counter mock models exactly that race: first read 0, second read 1."""
    from app.services import patient_activation_service as pas

    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)

    calls = {"n": 0}

    def _conflict_appears_after_precheck(db, phone):
        calls["n"] += 1
        return 1 if calls["n"] >= 2 else 0

    monkeypatch.setattr(
        pas, "_portal_user_count_for_phone", _conflict_appears_after_precheck
    )

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, "000000")  # wrong code on purpose
    assert err.value.status_code == 409
    assert err.value.detail == pas.ERR_PHONE_ALREADY_BOUND
    assert calls["n"] == 2  # precheck + authoritative re-read under the lock
    # OTP NOT consumed, token entry still resolvable
    assert svc._lookup_entry(token) is not None


def test_lookup_is_idx_authoritative_reissue_race(db_session, svc):
    """Codex P2 (reissue race): the revocation index is the source of truth —
    a losing reissue token whose KV entry outlives its revocation must NOT
    resolve, even though its own entry is still present."""
    patient = make_patient(db_session, phone=PHONE)
    old_token = issued_token(db_session, svc, patient)
    backend = _kv()

    # reissue race leftover: the index moved to a DIFFERENT hash while the
    # losing token's own entry survived
    backend.set(f"patact:idx:{patient.id}", "f" * 64, 3600)
    assert svc._lookup_entry(old_token) is None

    # a missing index revokes too (defensive: single source of truth)
    second = issued_token(db_session, svc, patient)  # proper reissue
    backend.delete(f"patact:idx:{patient.id}")
    assert svc._lookup_entry(second) is None


async def test_kv_outage_translated_to_activation_503(db_session, svc, monkeypatch):
    """Codex P2 (Redis 500->503): a KV outage during ANY activation step
    surfaces as the documented generic ActivationError(503), never an
    unhandled PatientOtpError that would become a 500."""
    from app.services.patient_otp_service import PatientOtpError

    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)  # issued BEFORE the outage

    def _boom():
        raise PatientOtpError(503, "KV unavailable")

    monkeypatch.setattr(get_patient_otp_service(), "get_backend", _boom)

    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, patient.id)
    assert err.value.status_code == 503

    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, token)
    assert err.value.status_code == 503

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, "123456")
    assert err.value.status_code == 503


# ----------------------------------------------- round 2: KV mid-session
class _DroppingRedisClient:
    """Models the round-2 Codex P2 scenario EXACTLY: the backend was
    created successfully (init + ping passed), THEN the Redis connection
    drops — every subsequent operation raises redis.ConnectionError."""

    def get(self, key):
        import redis

        raise redis.ConnectionError("connection dropped mid-session")

    def set(self, *args, **kwargs):
        import redis

        raise redis.ConnectionError("connection dropped mid-session")

    def delete(self, *args, **kwargs):
        import redis

        raise redis.ConnectionError("connection dropped mid-session")

    def execute_command(self, *args, **kwargs):
        import redis

        raise redis.ConnectionError("connection dropped mid-session")

    def pipeline(self):
        import redis

        raise redis.ConnectionError("connection dropped mid-session")


def _dropped_backend():
    from app.services.patient_otp_service import _RedisBackend

    backend = _RedisBackend.__new__(_RedisBackend)
    backend._client = _DroppingRedisClient()
    return backend


def test_redis_backend_normalizes_midsession_infra_failures():
    """_RedisBackend normalizes connection/timeout failures into
    PatientOtpError(503) so EVERY caller contract holds after init."""
    import redis

    from app.services.patient_otp_service import PatientOtpError, _RedisBackend

    backend = _dropped_backend()
    for call in (
        lambda: backend.get("k"),
        lambda: backend.set("k", "v", 60),
        lambda: backend.delete("k"),
        lambda: backend.getdel("k"),
    ):
        with pytest.raises(PatientOtpError) as err:
            call()
        assert err.value.status_code == 503

    # ResponseError (a programming bug) must NOT masquerade as 503
    class _Buggy:
        def execute_command(self, *a, **k):
            raise redis.ResponseError("unknown command")

    backend2 = _RedisBackend.__new__(_RedisBackend)
    backend2._client = _Buggy()
    with pytest.raises(redis.ResponseError):
        backend2.getdel("k")


async def test_midsession_kv_drop_is_503_at_every_activation_door(
    db_session, svc, monkeypatch
):
    """Backend created OK, THEN Redis drops: issue/request-otp/activate all
    surface the documented ActivationError(503) — never a raw
    redis.ConnectionError (undocumented 500)."""
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)  # backend was healthy here

    otp = get_patient_otp_service()
    monkeypatch.setattr(otp, "_backend", _dropped_backend())

    with pytest.raises(ActivationError) as err:
        svc.issue_activation_token(db_session, patient.id)
    assert err.value.status_code == 503

    with pytest.raises(ActivationError) as err:
        await svc.request_activation_otp(db_session, token)
    assert err.value.status_code == 503

    with pytest.raises(ActivationError) as err:
        svc.activate(db_session, token, "123456")
    assert err.value.status_code == 503


async def test_post_commit_cleanup_failure_still_returns_jwt(
    db_session, svc, monkeypatch
):
    """Codex round-2 P2 (post-commit): DB commit SUCCEEDS, then the KV
    cleanup (getdel/delete) fails with a raw redis.ConnectionError — the
    committed activation MUST still return 200 + JWT, never a 500."""
    from app.services.patient_otp_service import _MemoryBackend

    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{PHONE}"]

    real = _kv()

    class _CleanupFailsBackend(_MemoryBackend):
        """Healthy for reads/writes; the POST-COMMIT cleanup doors explode
        raw (token GETDEL + revocation-index DELETE) — everything needed
        BEFORE the commit (OTP code consume) stays healthy."""

        def getdel(self, key):
            import redis

            raise redis.ConnectionError("dropped right after commit")

        def delete(self, key):
            import redis

            if key.startswith("patact:idx:"):
                raise redis.ConnectionError("dropped right after commit")
            return super().delete(key)

    failing = _CleanupFailsBackend()
    failing._store = real._store
    failing._counters = real._counters
    failing.last_sent_code = real.last_sent_code
    otp = get_patient_otp_service()
    monkeypatch.setattr(otp, "_backend", failing)

    out = svc.activate(db_session, token, code)
    assert out["access_token"]  # JWT issued despite the cleanup failure
    db_session.refresh(patient)
    assert patient.user_id == out["user"]["id"]  # link committed


async def test_long_name_bounded_for_user_and_profile(db_session, svc, monkeypatch):
    """Codex round-2 P2: users.full_name is VARCHAR(100) while Patient
    names are 3 x VARCHAR(128). A schema-valid name longer than 100 chars
    must NOT break the activation after the single-use OTP was consumed —
    ONE bounded display name for BOTH User and UserProfile."""
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    long_last = "S" * 50  # SYNTHETIC-only letter run
    long_first = "y" * 60
    assert len(long_last) + 1 + len(long_first) > 100
    patient = make_patient(db_session, phone=PHONE, first=long_first, last=long_last)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{PHONE}"]

    out = svc.activate(db_session, token, code)

    user = db_session.get(User, out["user"]["id"])
    profile = db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).scalar_one()
    assert len(user.full_name) <= 100  # flushes on PostgreSQL VARCHAR(100)
    assert user.full_name == profile.full_name  # computed ONCE, same value
    assert user.full_name == patient.short_name()[:100]


async def test_activation_linking_audited_in_same_transaction(db_session, svc):
    """Codex round-2 P2: the IDENTITY LINKING itself (Patient.id N bound to
    User.id M — a new authentication principal) needs a durable audit row
    written in the SAME transaction as the link, so the state
    'link committed, audit missing' is impossible."""
    patient = make_patient(db_session, phone=PHONE)
    token = issued_token(db_session, svc, patient)
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{PHONE}"]

    out = svc.activate(db_session, token, code)

    from app.models.user_profile import UserAuditLog

    rows = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "patients",
            UserAuditLog.resource_id == patient.id,
            UserAuditLog.action == "UPDATE",
        )
        .all()
    )
    assert rows, "activation linking must leave a critical audit row"
    linked = [
        r
        for r in rows
        if (r.new_values or {}).get("user_id") == out["user"]["id"]
        and (r.old_values or {}).get("user_id", "missing") is None
    ]
    assert linked, "audit must record user_id: NULL -> <new user id>"
    assert "activation" in linked[0].description.lower()
