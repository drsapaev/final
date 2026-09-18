"""Phase 0 PR #3320 round 2 — SYSTEMIC phone-scope invariant (review P1).

Owner regression (round-2 review, reproducible chain): the activation-flow
guard alone is NOT enough because the EXISTING User Management can make a
record join the login-resolver predicate (active + role=Patient +
UserProfile.phone + phone_verified) without any phone-scope check:

    Patient A, phone X -> activation -> User A active + verified X
    admin deactivates User A
    Patient B, same phone X -> activation passes (active candidates = 0)
    admin reactivates User A   <-- MUST be a controlled 409
    (otherwise: 2 candidates -> fail-closed resolver -> BOTH accounts 401)

The fix routes EVERY such mutation through the same
patient_phone_scope.ensure_phone_scope_free() primitive (same advisory
lock, same resolver-predicate mirror) that the activation flow uses:

    - reactivation of a Patient-user            -> 409 when phone taken;
    - role change -> Patient (active, verified) -> 409 when phone taken;
    - verified-phone change of a Patient-user   -> 409 when the NEW phone
      is taken, and the changed phone loses phone_verified (possession is
      not proven for an admin-entered number — parity with the
      self-service phone change), so the record LEAVES the resolver
      predicate instead of silently re-aiming it.

Runs on SQLite: the advisory lock is a no-op there; the candidate
re-check carries the contract (the PostgreSQL serialization proof for the
activation path lives in test_patient_activation_pg_phone_scope.py).
SYNTHETIC data only (AGENTS.md).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.roles import Roles
from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user_management import UserUpdateRequest
from app.services.patient_activation_service import PatientActivationService
from app.services.patient_otp_service import (
    get_patient_otp_service,
)
from app.services.patient_phone_scope import (
    ERR_PHONE_SCOPE_CONFLICT,
    PatientPhoneScopeConflict,
)
from app.services.user_management_service import UserManagementService

# SYNTHETIC constants only (AGENTS.md synthetic-data policy).
FAMILY_PHONE = "+998900000002"
OTHER_PHONE = "+998900000003"
FREE_PHONE = "+998900000007"

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def isolated_kv():
    otp = get_patient_otp_service()
    otp._reset_backend_for_tests()
    backend = otp.get_backend()
    backend.last_sent_code.clear()
    yield backend
    otp._reset_backend_for_tests()


@pytest.fixture()
def svc() -> PatientActivationService:
    return PatientActivationService()


@pytest.fixture()
def ums() -> UserManagementService:
    return UserManagementService()


def _kv():
    return get_patient_otp_service().get_backend()


def _admin(db_session) -> User:
    user = db_session.query(User).filter(User.username == "syn_admin").first()
    if user:
        return user
    user = User(
        username="syn_admin",
        email="syn_admin@synthetic.local",
        full_name="SYNTHETIC Admin",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_patient(
    db_session, *, phone: str, first: str, last: str = "FamilyCard"
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


def _patient_user(
    db_session, *, username: str, phone: str, verified: bool = True
) -> User:
    user = User(
        username=username,
        email=f"{username}@synthetic.local",
        full_name="SYNTHETIC User",
        hashed_password=get_password_hash("Passw0rd!123"),
        role=Roles.PATIENT,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            full_name="SYNTHETIC User",
            phone=phone,
            phone_verified=verified,
        )
    )
    db_session.commit()
    db_session.refresh(user)
    return user


async def _activated_card(
    db_session, svc: PatientActivationService, phone: str, *, label: str
) -> tuple[Patient, User]:
    """Happy-path activation; returns (patient, created User)."""
    # bypass the 60s phone cooldown when a test activates a SECOND card on
    # the same family phone (real cooldown semantics, not under test here)
    _kv().delete(f"patact:cd:{phone}")
    patient = make_patient(db_session, phone=phone, first=f"SYNTHETIC-{label}")
    token = svc.issue_activation_token(db_session, patient.id)["activation_token"]
    await svc.request_activation_otp(db_session, token)
    code = _kv().last_sent_code[f"patact:{phone}"]
    out = svc.activate(db_session, token, code)
    db_session.refresh(patient)
    user = db_session.get(User, out["user"]["id"])
    return patient, user


# ------------------------------------------------- owner regression chain
async def test_reactivation_blocked_after_second_card_took_the_phone(
    db_session, svc, ums
):
    """THE owner regression:
    activate A(X) -> deactivate A -> activate B(X) -> reactivate A
    -> controlled 409; B remains the ONLY active candidate; login works."""
    admin = _admin(db_session)

    patient_a, user_a = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Mother"
    )
    assert user_a.role == Roles.PATIENT and user_a.is_active

    # admin deactivates A -> zero active candidates on X
    ok, msg = ums.update_user(
        db_session, user_a.id, UserUpdateRequest(is_active=False), admin.id
    )
    assert ok, msg
    db_session.refresh(user_a)
    assert user_a.is_active is False

    # B activates on the SAME phone — legal while A is deactivated
    patient_b, user_b = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Child"
    )

    # admin reactivates A -> MUST be a controlled 409, not a silent
    # second-candidate creation
    with pytest.raises(PatientPhoneScopeConflict) as err:
        ums.update_user(
            db_session, user_a.id, UserUpdateRequest(is_active=True), admin.id
        )
    assert err.value.status_code == 409
    assert err.value.detail == ERR_PHONE_SCOPE_CONFLICT

    db_session.refresh(user_a)
    assert user_a.is_active is False  # nothing changed
    # B remains the ONLY active verified Patient-user on the phone
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == user_b.id


async def test_role_change_to_patient_blocked_when_phone_taken(db_session, ums):
    """Role -> Patient on an active user with a verified phone joins the
    resolver predicate — blocked when the phone already backs another
    active patient portal account."""
    admin = _admin(db_session)
    _patient_user(db_session, username="syn_holder", phone=FAMILY_PHONE)

    staff = User(
        username="syn_staff_to_patient",
        email="syn_staff_to_patient@synthetic.local",
        full_name="SYNTHETIC Staff",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(staff)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=staff.id,
            full_name="SYNTHETIC Staff",
            phone=FAMILY_PHONE,
            phone_verified=True,
        )
    )
    db_session.commit()

    with pytest.raises(PatientPhoneScopeConflict) as err:
        ums.update_user(
            db_session,
            staff.id,
            UserUpdateRequest(role=Roles.PATIENT),
            admin.id,
        )
    assert err.value.status_code == 409
    db_session.refresh(staff)
    assert staff.role == "Registrar"  # nothing changed


async def test_phone_change_to_live_portal_phone_blocked(db_session, ums):
    """A Patient-user may not be re-aimed at a phone that already backs
    another active patient portal account (the 'short repro' from the
    review: admin changes one active Patient-user's phone to another's)."""
    admin = _admin(db_session)
    holder = _patient_user(db_session, username="syn_holder2", phone=FAMILY_PHONE)
    mover = _patient_user(db_session, username="syn_mover", phone=OTHER_PHONE)

    with pytest.raises(PatientPhoneScopeConflict) as err:
        ums.update_user(
            db_session,
            mover.id,
            UserUpdateRequest(phone=FAMILY_PHONE),
            admin.id,
        )
    assert err.value.status_code == 409
    db_session.refresh(mover)
    profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == mover.id).one()
    )
    assert profile.phone == OTHER_PHONE  # nothing changed
    # holder keeps exclusive access to the phone
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == holder.id


async def test_conflicting_phone_change_does_not_reset_verified_state(db_session, ums):
    """Rejection must be atomic: the guard fires BEFORE any field write,
    so a 409'd phone change must not leave the profile mutated."""
    admin = _admin(db_session)
    _patient_user(db_session, username="syn_holder3", phone=FAMILY_PHONE)
    mover = _patient_user(db_session, username="syn_mover2", phone=OTHER_PHONE)

    with pytest.raises(PatientPhoneScopeConflict):
        ums.update_user(
            db_session,
            mover.id,
            UserUpdateRequest(phone=FAMILY_PHONE),
            admin.id,
        )
    profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == mover.id).one()
    )
    assert profile.phone == OTHER_PHONE
    assert profile.phone_verified is True


async def test_nonconflicting_phone_change_resets_verified_flag(db_session, ums):
    """Admin-entered numbers are UNPROVEN possession: any successful phone
    change resets phone_verified (parity with the self-service phone
    change), so the record leaves the resolver predicate instead of
    silently re-aiming a working OTP login at a new number."""
    admin = _admin(db_session)
    mover = _patient_user(db_session, username="syn_mover3", phone=OTHER_PHONE)

    ok, msg = ums.update_user(
        db_session, mover.id, UserUpdateRequest(phone=FREE_PHONE), admin.id
    )
    assert ok, msg
    profile = (
        db_session.query(UserProfile).filter(UserProfile.user_id == mover.id).one()
    )
    assert profile.phone == FREE_PHONE
    assert profile.phone_verified is False
    # NOT a resolver candidate anymore (unverified), even though active
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FREE_PHONE
    )
    assert resolved is None


async def test_reactivation_with_free_phone_still_allowed(db_session, svc, ums):
    """Control: deactivation -> reactivation with the phone STILL free
    must keep working (the invariant guards candidate #2, not the
    deactivate/activate lifecycle itself)."""
    admin = _admin(db_session)
    patient_a, user_a = await _activated_card(
        db_session, svc, OTHER_PHONE, label="Control"
    )

    ok, msg = ums.update_user(
        db_session, user_a.id, UserUpdateRequest(is_active=False), admin.id
    )
    assert ok, msg
    ok, msg = ums.update_user(
        db_session, user_a.id, UserUpdateRequest(is_active=True), admin.id
    )
    assert ok, msg
    db_session.refresh(user_a)
    assert user_a.is_active is True
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, OTHER_PHONE
    )
    assert resolved is not None and resolved.id == user_a.id


async def test_conflicting_change_spends_nothing_and_releases_scope(
    db_session, svc, ums
):
    """After a 409'd reactivation the phone scope must be USABLE again by
    the activation flow on the SAME session (lock released by the
    service-side rollback) — no stuck serialization."""
    admin = _admin(db_session)
    patient_a, user_a = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Again"
    )
    ok, _ = ums.update_user(
        db_session, user_a.id, UserUpdateRequest(is_active=False), admin.id
    )
    assert ok
    patient_b, user_b = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Child2"
    )
    with pytest.raises(PatientPhoneScopeConflict):
        ums.update_user(
            db_session, user_a.id, UserUpdateRequest(is_active=True), admin.id
        )
    # same-session activation machinery still works afterwards: a third
    # card on the phone is refused by the activation guard itself (not by
    # a dangling lock/exception state)
    third = make_patient(db_session, phone=FAMILY_PHONE, first="SYNTHETIC-3rd")
    with pytest.raises(Exception) as err:
        svc.issue_activation_token(db_session, third.id)
    assert "уже активирован" in str(err.value.detail)
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == user_b.id


# ================================================= round 3 (review P1+P2)
# P1: bulk User Management is the THIRD door into the login-resolver
# predicate — bulk activate / bulk change_role -> Patient must pass the
# SAME phone-scope primitive, or the owner chain reproduces over the bulk
# surface. Batch nuance (autoflush=False): sequential per-row counts can
# not see intra-batch pending activations, so the preflight guarantees at
# most ONE entering candidate per phone per batch, and phones take their
# advisory locks in deterministic (sorted) order.
# P2: the generic field updater persisted the RAW admin-entered phone —
# a reformatted (normalized-equal) input kept phone_verified=True while
# SQL equality against the normalized value silently dropped the record
# out of the resolver predicate (login 401).
from app.schemas.user_management import UserBulkActionRequest  # noqa: E402
from app.services.patient_phone_scope import (  # noqa: E402
    count_active_verified_patient_users,
)


async def test_bulk_activate_blocked_after_second_card_took_the_phone(
    db_session, svc, ums
):
    """THE owner round-3 regression over the BULK surface:
    activate A(X) -> bulk deactivate A -> activate B(X)
    -> bulk activate [A] -> A stays inactive (failed_count=1);
    B remains the ONLY active verified candidate; login B works."""
    admin = _admin(db_session)

    patient_a, user_a = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Mother"
    )
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[user_a.id], action="deactivate"),
        admin.id,
    )
    assert ok, msg
    assert result["processed_count"] == 1
    db_session.refresh(user_a)
    assert user_a.is_active is False

    # B activates on the SAME phone — legal while A is deactivated
    patient_b, user_b = await _activated_card(
        db_session, svc, FAMILY_PHONE, label="Child"
    )

    # bulk activate A -> per-user phone-scope failure, batch succeeds
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[user_a.id], action="activate"),
        admin.id,
    )
    assert ok  # batch-level success with a PER-USER phone-scope failure
    assert result["processed_count"] == 0
    assert result["failed_count"] == 1
    assert result["failed_users"][0]["user_id"] == user_a.id
    assert result["failed_users"][0]["error"] == ERR_PHONE_SCOPE_CONFLICT

    db_session.refresh(user_a)
    assert user_a.is_active is False  # nothing changed
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == user_b.id


async def test_bulk_change_role_to_patient_blocked_when_phone_taken(
    db_session, ums
):
    """Bulk change_role -> Patient on an ACTIVE verified user whose phone
    already backs another active patient portal account: per-user
    phone-scope failure; the role stays unchanged; the existing candidate
    keeps the phone."""
    admin = _admin(db_session)
    holder = _patient_user(
        db_session, username="syn_bulk_holder", phone=FAMILY_PHONE
    )

    staff = User(
        username="syn_bulk_registrar",
        email="syn_bulk_registrar@synthetic.local",
        full_name="SYNTHETIC Registrar",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(staff)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=staff.id,
            full_name="SYNTHETIC Registrar",
            phone=FAMILY_PHONE,
            phone_verified=True,
        )
    )
    db_session.commit()
    db_session.refresh(staff)

    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(
            user_ids=[staff.id], action="change_role", role="Patient"
        ),
        admin.id,
    )
    assert ok  # batch-level success with a PER-USER phone-scope failure
    assert result["processed_count"] == 0
    assert result["failed_count"] == 1
    assert result["failed_users"][0]["user_id"] == staff.id
    assert result["failed_users"][0]["error"] == ERR_PHONE_SCOPE_CONFLICT

    db_session.refresh(staff)
    assert staff.role == "Registrar"  # nothing changed
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == holder.id


async def test_bulk_activate_same_phone_in_batch_single_winner(db_session, ums):
    """autoflush=False batch nuance (owner round-3 note): two INACTIVE
    verified Patient-users sharing a phone in ONE bulk activate must not
    BOTH pass sequential per-row counts — at most ONE entering candidate
    per phone per batch; the other fails per-user."""
    admin = _admin(db_session)
    first = _patient_user(
        db_session, username="syn_bulk_first", phone=FAMILY_PHONE
    )
    second = _patient_user(
        db_session, username="syn_bulk_second", phone=FAMILY_PHONE
    )

    # bulk deactivate both — legal (leaves the predicate)
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(
            user_ids=[first.id, second.id], action="deactivate"
        ),
        admin.id,
    )
    assert ok, msg
    assert result["processed_count"] == 2

    # one batch, one phone, two entering candidates -> single winner
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(
            user_ids=[first.id, second.id], action="activate"
        ),
        admin.id,
    )
    assert ok
    assert result["processed_count"] == 1
    assert result["failed_count"] == 1

    db_session.refresh(first)
    db_session.refresh(second)
    winner, loser = (first, second) if first.is_active else (second, first)
    assert winner.is_active is True
    assert loser.is_active is False  # blocked, nothing changed
    assert count_active_verified_patient_users(db_session, FAMILY_PHONE) == 1
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == winner.id


async def test_bulk_activate_free_phone_still_works(db_session, ums):
    """Control: bulk activate on a FREE phone keeps working (the guard
    only fires on an occupied scope)."""
    admin = _admin(db_session)
    user = _patient_user(
        db_session, username="syn_bulk_free", phone=FREE_PHONE
    )
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[user.id], action="deactivate"),
        admin.id,
    )
    assert ok, msg
    ok, msg, result = ums.bulk_action_users(
        db_session,
        UserBulkActionRequest(user_ids=[user.id], action="activate"),
        admin.id,
    )
    assert ok, msg
    assert result["processed_count"] == 1
    assert result["failed_count"] == 0
    db_session.refresh(user)
    assert user.is_active is True
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FREE_PHONE
    )
    assert resolved is not None and resolved.id == user.id


async def test_phone_change_stores_canonical_normalized_value(db_session, ums):
    """Round-3 P2: a reformatted (normalized-equal) phone input must
    persist the CANONICAL value, keep phone_verified=True and keep the
    record resolver-visible — otherwise SQL equality against the
    normalized value silently drops the user out of OTP login (401)."""
    admin = _admin(db_session)
    user = _patient_user(
        db_session, username="syn_canonical", phone=FAMILY_PHONE
    )

    reformatted = "+998 90 000 00 02"  # normalizes to FAMILY_PHONE
    ok, msg = ums.update_user(
        db_session, user.id, UserUpdateRequest(phone=reformatted), admin.id
    )
    assert ok, msg

    profile = (
        db_session.query(UserProfile)
        .filter(UserProfile.user_id == user.id)
        .first()
    )
    assert profile.phone == FAMILY_PHONE  # canonical, NOT the raw input
    assert profile.phone_verified is True  # normalized-equal: no re-bind
    resolved = get_patient_otp_service().resolve_patient_user_by_phone(
        db_session, FAMILY_PHONE
    )
    assert resolved is not None and resolved.id == user.id
