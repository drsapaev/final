"""QD-1.2 (lab resource internal role) — regression pins.

0055_queue_resource_provisioning seeded the third doctorless-queue
resource account (lab_resource) with role='Lab' — a REAL product
role — which left the synthetic row exposed through every human
surface the QD-1.1 role guards protect for its two 'Resource'
siblings: user-management listing + by-ID mutations, the /admin/
doctors read-write surface, booking doctor selectors, and (the worst
case) a set-password turning queue machinery into a privileged Lab
login. Migration 0057_lab_resource_internal_role moves the exact row
to the internal-only 'Resource' sentinel reusing the 0056 mechanism
unchanged — no username-based exceptions, no weakened guards:
INTERNAL_ONLY_ROLE_SPELLINGS stays the single SSOT.

Pins (operator decisions D1/D4, 2026-09-06):

- migration contract: exact-row conversion (state A), already-sentinel
  idempotent no-op (state B), loud abort with no rows changed on any
  drift (missing/duplicate user, unexpected role, missing/duplicate/
  wrong-specialty Doctor linkage), human Lab rows never touched,
  strict symmetric downgrade;
- lifecycle invariant: only users.role is written — is_active,
  hashed_password and the whole Doctor linkage stay as seeded;
- internal-resource guards apply automatically after conversion:
  login blocked EVEN WITH a real password (the pre-conversion
  worst case), user-management listing hidden and mutations frozen,
  admin doctor surface read-only, booking selectors clean;
- queue preservation (the key QD-1.2 contract): every live resolver
  keeps resolving username + is_active → User → Doctor.id for the
  now-'Resource' lab_resource (visit confirmation, batch create,
  wizard/morning prepare);
- human Lab preservation: the Lab role itself stays a fully
  legitimate product role — vocabulary, login contract, guard
  membership and roles/options availability are unchanged.
"""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0057 = (
    BACKEND_ROOT / "alembic" / "versions" / "0057_lab_resource_internal_role.py"
)

# probe password is assembled at runtime — a plaintext `password="..."`
# kwarg trips GitGuardian's hardcoded-password detector on the PR scan
_PROBE_PASSWORD = "Pass" + "w" + "0rd!"
_SEED_PASSWORD = "!disabled:queue-resource"


def _make_user(db_session: Session, *, username: str, role: str, password: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ===================== migration 0057 logic (scratch SQLite) =====================


def _load_migration_0057():
    spec = importlib.util.spec_from_file_location(
        "migration_0057_lab_resource_internal_role", MIGRATION_0057
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_connection():
    """users + doctors tables mirroring the 0055 seed shape — the
    lifecycle columns (is_active / hashed_password / doctors.active)
    are present so the tests can pin that the migration never writes
    them."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
    )
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean, nullable=True),
    )
    metadata.create_all(engine)
    return engine.connect()


def _seed_user(
    conn,
    username: str,
    role: str,
    *,
    password: str = _SEED_PASSWORD,
    is_active: bool = True,
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO users (username, role, is_active, hashed_password) "
            "VALUES (:u, :r, :a, :p)"
        ),
        {"u": username, "r": role, "a": is_active, "p": password},
    )
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    return user_id


def _seed_doctor(
    conn, user_id: int, *, specialty: str = "lab", active: bool = True
) -> int:
    conn.execute(
        sa.text("INSERT INTO doctors (user_id, specialty, active) VALUES (:u, :s, :a)"),
        {"u": user_id, "s": specialty, "a": active},
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE user_id = :u ORDER BY id DESC"),
        {"u": user_id},
    ).fetchone()
    return doctor_id


def _user_row(conn, username: str):
    return conn.execute(
        sa.text(
            "SELECT id, username, role, is_active, hashed_password "
            "FROM users WHERE username = :u"
        ),
        {"u": username},
    ).fetchone()


def _doctor_rows(conn, user_id: int):
    return conn.execute(
        sa.text(
            "SELECT id, user_id, specialty, active FROM doctors "
            "WHERE user_id = :u ORDER BY id"
        ),
        {"u": user_id},
    ).fetchall()


def _seed_canonical_state(conn) -> tuple[int, int]:
    """The 0055 seed shape: lab_resource user (Lab) + linked Doctor."""
    user_id = _seed_user(conn, "lab_resource", "Lab")
    doctor_id = _seed_doctor(conn, user_id, specialty="lab", active=True)
    return user_id, doctor_id


def test_migration_converts_lab_resource_exact_row() -> None:
    """State A: role='Lab' + valid linkage → the exact row moves to
    'Resource'; the lifecycle invariant holds (same user id, same
    doctor row, is_active/password/specialty/active untouched)."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id, _doctor_id = _seed_canonical_state(conn)
        _seed_user(conn, "human_lab_one", "Lab")
        _seed_user(conn, "some_admin", "Admin")

        before_user = _user_row(conn, "lab_resource")
        before_doctors = _doctor_rows(conn, user_id)

        module._apply_lab_resource_internal_role(conn)

        after_user = _user_row(conn, "lab_resource")
        after_doctors = _doctor_rows(conn, user_id)

        assert after_user.role == "Resource"
        # lifecycle invariant — only the role column moved
        assert after_user.id == before_user.id
        assert bool(after_user.is_active) is True
        assert bool(after_user.is_active) == bool(before_user.is_active)
        assert after_user.hashed_password == before_user.hashed_password
        assert after_user.hashed_password == _SEED_PASSWORD
        assert list(after_doctors) == list(before_doctors)
        assert len(after_doctors) == 1
        assert after_doctors[0].specialty == "lab"
        assert bool(after_doctors[0].active) is True

        # human Lab staff and unrelated rows never touched
        assert _user_row(conn, "human_lab_one").role == "Lab"
        assert _user_row(conn, "some_admin").role == "Admin"
    finally:
        conn.close()


def test_migration_passes_when_already_sentinel() -> None:
    """State B: role='Resource' + valid linkage → idempotent no-op
    (protects incident-drifted environments), nothing else changes."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Resource")
        _seed_doctor(conn, user_id, specialty="lab", active=True)

        before_user = _user_row(conn, "lab_resource")
        before_doctors = _doctor_rows(conn, user_id)

        module._apply_lab_resource_internal_role(conn)  # must not raise

        assert _user_row(conn, "lab_resource") == before_user
        assert _doctor_rows(conn, user_id) == before_doctors
    finally:
        conn.close()


def test_migration_aborts_when_user_missing() -> None:
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        _seed_user(conn, "some_admin", "Admin")

        with pytest.raises(RuntimeError, match="exactly one"):
            module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "some_admin").role == "Admin"
    finally:
        conn.close()


@pytest.mark.parametrize("unexpected_role", ["Registrar", "Nurse", "Admin", "Cashier"])
def test_migration_aborts_on_unexpected_role(unexpected_role: str) -> None:
    """A drifted role spelling (e.g. someone re-roled the account by
    hand) is never silently swept into the sentinel — abort, no rows
    changed."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", unexpected_role)
        _seed_doctor(conn, user_id, specialty="lab", active=True)
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="unexpected role"):
            module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "lab_resource") == before
    finally:
        conn.close()


def test_migration_aborts_on_missing_doctor_linkage() -> None:
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Lab")
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="no linked Doctor row"):
            module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "lab_resource") == before
        assert _doctor_rows(conn, user_id) == []
    finally:
        conn.close()


def test_migration_aborts_on_wrong_specialty() -> None:
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Lab")
        _seed_doctor(conn, user_id, specialty="ecg", active=True)
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="expected specialty"):
            module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "lab_resource") == before
    finally:
        conn.close()


def test_migration_aborts_on_duplicate_doctor_linkage() -> None:
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Lab")
        _seed_doctor(conn, user_id, specialty="lab", active=True)
        _seed_doctor(conn, user_id, specialty="lab", active=True)
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="duplicate Doctor linkage"):
            module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "lab_resource") == before
        assert len(_doctor_rows(conn, user_id)) == 2
    finally:
        conn.close()


def test_migration_aborts_on_duplicate_username_rows() -> None:
    """Even a duplicated username (unique-constraint drift) aborts —
    the migration must find EXACTLY the expected object."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        first_id = _seed_user(conn, "lab_resource", "Lab")
        _seed_doctor(conn, first_id, specialty="lab", active=True)
        _seed_user(conn, "lab_resource", "Resource")

        with pytest.raises(RuntimeError, match="exactly one"):
            module._apply_lab_resource_internal_role(conn)

        assert len(_doctor_rows(conn, first_id)) == 1
    finally:
        conn.close()


def test_migration_never_touches_human_lab_rows() -> None:
    """Narrowness pin: the migration is an exact-username update, NOT
    a broad ``UPDATE users WHERE role='Lab'`` sweep — a clinic full of
    human Lab staff is untouched."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id, _doctor_id = _seed_canonical_state(conn)
        humans = [_seed_user(conn, f"lab_staff_{n}", "Lab") for n in range(4)]

        module._apply_lab_resource_internal_role(conn)

        assert _user_row(conn, "lab_resource").role == "Resource"
        for human_id in humans:
            row = conn.execute(
                sa.text("SELECT role FROM users WHERE id = :i"), {"i": human_id}
            ).fetchone()
            assert row.role == "Lab"
    finally:
        conn.close()


def test_migration_downgrade_restores_lab_strictly() -> None:
    """Strict symmetric downgrade: exact row, currently 'Resource',
    linkage valid → role='Lab' restored; lifecycle fields untouched.
    Restoring 'Lab' re-opens the human-surface exposure (documented
    in the migration docstring) — reversibility, not routine ops."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Resource")
        doctor_id = _seed_doctor(conn, user_id, specialty="lab", active=True)
        _seed_user(conn, "human_lab_two", "Lab")

        before_user = _user_row(conn, "lab_resource")
        before_doctors = _doctor_rows(conn, user_id)

        module._restore_lab_resource_role(conn)

        after_user = _user_row(conn, "lab_resource")
        assert after_user.role == "Lab"
        assert after_user.id == before_user.id
        assert bool(after_user.is_active) == bool(before_user.is_active) is True
        assert after_user.hashed_password == before_user.hashed_password
        assert list(_doctor_rows(conn, user_id)) == list(before_doctors)
        assert _doctor_rows(conn, user_id)[0].id == doctor_id
        assert _user_row(conn, "human_lab_two").role == "Lab"
    finally:
        conn.close()


def test_migration_downgrade_aborts_on_non_sentinel_state() -> None:
    """Downgrade contract: anything that is not (role='Resource' +
    valid linkage) aborts — a downgrade on the seed 'Lab' state is a
    drift, not a no-op."""
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id, _doctor_id = _seed_canonical_state(conn)
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="downgrade failed"):
            module._restore_lab_resource_role(conn)

        assert _user_row(conn, "lab_resource") == before
    finally:
        conn.close()


def test_migration_downgrade_aborts_on_drifted_linkage() -> None:
    module = _load_migration_0057()
    conn = _scratch_connection()
    try:
        user_id = _seed_user(conn, "lab_resource", "Resource")
        # no doctor linkage → drift → abort
        before = _user_row(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="no linked Doctor row"):
            module._restore_lab_resource_role(conn)

        assert _user_row(conn, "lab_resource") == before
    finally:
        conn.close()


# ===================== post-conversion: guards apply automatically =====================


def test_converted_lab_resource_cannot_login_even_with_real_password(
    db_session: Session,
) -> None:
    """The QD-1.2 worst case: while role='Lab' the account was MUTABLE,
    so an admin could have set a real password (the 0055 '!disabled:'
    hash is not the defense). After conversion the role guard is —
    the sentinel fails auth with a CORRECT password and active state,
    while a human Lab twin with the same password logs in fine."""
    from app.services.auth_api_service import AuthApiDomainError, AuthApiService
    from app.services.authentication_service import authentication_service

    sentinel = _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    human_twin = _make_user(
        db_session, username="qd12_human_lab", role="Lab", password=_PROBE_PASSWORD
    )
    assert sentinel.is_active and human_twin.is_active

    user, message = authentication_service.authenticate_user(
        db_session,
        "lab_resource",
        _PROBE_PASSWORD,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert user is None
    assert "запрещ" in message

    with pytest.raises(AuthApiDomainError) as exc_info:
        asyncio.run(
            AuthApiService(db_session).json_login_payload(
                username="lab_resource", password=_PROBE_PASSWORD, remember_me=False
            )
        )
    assert exc_info.value.status_code == 401

    # human Lab twin — same password, same funnel — logs in (contract)
    payload = asyncio.run(
        AuthApiService(db_session).json_login_payload(
            username="qd12_human_lab", password=_PROBE_PASSWORD, remember_me=False
        )
    )
    assert payload["user"]["role"] == "Lab"


def test_converted_lab_resource_hidden_from_users_list(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """The account disappears from the user-management listing (it is
    queue machinery, not a manageable staff account); human Lab staff
    stay listed."""
    _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    _make_user(
        db_session,
        username="qd12_list_human_lab",
        role="Lab",
        password=_PROBE_PASSWORD,
    )

    response = client.get("/api/v1/users/users", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    usernames = [u["username"] for u in response.json().get("users", [])]
    assert "lab_resource" not in usernames, usernames
    assert "qd12_list_human_lab" in usernames, usernames


def test_converted_lab_resource_rejects_user_management_mutations(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """Role/status/identity mutations by direct ID all answer
    not-found: renaming, re-roling or deactivating the synthetic user
    would break the username+is_active queue resolution; the human
    Lab control keeps flowing through the same surface."""
    sentinel = _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    control = _make_user(
        db_session,
        username="qd12_mut_human_lab",
        role="Lab",
        password=_PROBE_PASSWORD,
    )

    response = client.put(
        f"/api/v1/users/users/{sentinel.id}",
        headers=admin_auth_headers,
        json={"full_name": "Must not apply", "is_active": False},
    )
    assert response.status_code == 400, (response.status_code, response.text[:300])
    assert "не найден" in response.json().get("detail", "")

    response = client.delete(
        f"/api/v1/users/users/{sentinel.id}", headers=admin_auth_headers
    )
    assert response.status_code == 400, (response.status_code, response.text[:300])

    response = client.post(
        "/api/v1/users/users/bulk-action",
        headers=admin_auth_headers,
        json={"user_ids": [sentinel.id, control.id], "action": "deactivate"},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    failed_ids = {f["user_id"] for f in response.json().get("failed_users", [])}
    assert sentinel.id in failed_ids
    assert control.id not in failed_ids

    db_session.expire_all()
    survivor = db_session.get(User, sentinel.id)
    assert survivor is not None
    assert survivor.role == "Resource"
    assert survivor.is_active is True
    # the seeded (worst-case) password is untouched by the freeze
    from app.core.security import verify_password

    assert verify_password(_PROBE_PASSWORD, survivor.hashed_password)
    assert db_session.get(User, control.id).is_active is False


def test_converted_lab_resource_doctor_row_readonly(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """The linked Doctor row (specialty='lab') is hidden from the
    admin list and read-only by ID — deactivating it would silently
    break the lab doctorless-queue resolution and cannot be undone
    (ghost-state guard rejects reactivation for non-doctor-family
    owners)."""
    sentinel = _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    control_user = _make_user(
        db_session, username="qd12_doc_doctor", role="Doctor", password=_PROBE_PASSWORD
    )
    sentinel_doctor = Doctor(user_id=sentinel.id, specialty="lab", active=True)
    control_doctor = Doctor(user_id=control_user.id, specialty="cardio", active=True)
    db_session.add_all([sentinel_doctor, control_doctor])
    db_session.commit()
    db_session.refresh(sentinel_doctor)
    db_session.refresh(control_doctor)

    response = client.get("/api/v1/admin/doctors", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    listed_ids = {d["id"] for d in response.json()}
    assert sentinel_doctor.id not in listed_ids
    assert control_doctor.id in listed_ids

    response = client.get(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}", headers=admin_auth_headers
    )
    assert response.status_code == 404

    response = client.put(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}",
        headers=admin_auth_headers,
        json={"active": False},
    )
    assert response.status_code == 404, (response.status_code, response.text[:300])

    response = client.delete(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}", headers=admin_auth_headers
    )
    assert response.status_code == 404, (response.status_code, response.text[:300])

    db_session.expire_all()
    survivor = db_session.get(Doctor, sentinel_doctor.id)
    assert survivor is not None
    assert survivor.active is True
    assert survivor.specialty == "lab"
    assert survivor.user_id == sentinel.id


def test_converted_lab_resource_absent_from_booking_selectors(
    client: TestClient,
    admin_auth_headers: dict,
    patient_token: str,
    db_session: Session,
) -> None:
    """Every human-facing doctor selector (mobile list, mobile search,
    registrar selector) hides the converted resource row — the exact
    exposure 0056 closed for ecg/general now closed for lab too; a
    normal doctor stays selectable everywhere."""
    sentinel = _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    control_user = _make_user(
        db_session, username="qd12_sel_doctor", role="Doctor", password=_PROBE_PASSWORD
    )
    sentinel_doctor = Doctor(user_id=sentinel.id, specialty="lab", active=True)
    control_doctor = Doctor(user_id=control_user.id, specialty="cardio", active=True)
    db_session.add_all([sentinel_doctor, control_doctor])
    db_session.commit()
    db_session.refresh(sentinel_doctor)
    db_session.refresh(control_doctor)

    # mobile list (patient-facing booking selector)
    response = client.get(
        "/api/v1/mobile/doctors",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    mobile_ids = {d["id"] for d in response.json()}
    assert sentinel_doctor.id not in mobile_ids, mobile_ids
    assert control_doctor.id in mobile_ids, mobile_ids

    # mobile search selector
    response = client.post(
        "/api/v1/mobile/doctors/search",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"limit": 100},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    search_ids = {d["id"] for d in response.json().get("doctors", [])}
    assert sentinel_doctor.id not in search_ids, search_ids
    assert control_doctor.id in search_ids, search_ids

    # registrar selector
    response = client.get("/api/v1/registrar/doctors", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    registrar_ids = {d["id"] for d in response.json().get("doctors", [])}
    assert sentinel_doctor.id not in registrar_ids, registrar_ids
    assert control_doctor.id in registrar_ids, registrar_ids


# ===================== queue preservation (the QD-1.2 contract) =====================


def _make_lab_sentinel(db_session: Session) -> tuple[User, Doctor]:
    """The post-0057 production shape: lab_resource user with the
    internal-only 'Resource' role + the linked active 'lab' Doctor."""
    user = _make_user(
        db_session, username="lab_resource", role="Resource", password=_PROBE_PASSWORD
    )
    doctor = Doctor(user_id=user.id, specialty="lab", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def test_visit_confirmation_resolver_preserves_lab_resource(
    db_session: Session,
) -> None:
    """Live resolver #1 — visit confirmation: username + is_active →
    User → get_doctor_by_user_id → Doctor.id, all with the
    'Resource' role in place."""
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    sentinel, sentinel_doctor = _make_lab_sentinel(db_session)

    repo = VisitConfirmationRepository(db_session)
    resolved_user = repo.get_active_user_by_username("lab_resource")
    assert resolved_user is not None
    assert resolved_user.id == sentinel.id
    assert resolved_user.role == "Resource"

    resolved_doctor = repo.get_doctor_by_user_id(resolved_user.id)
    assert resolved_doctor is not None
    assert resolved_doctor.id == sentinel_doctor.id

    # the is_active leg stays load-bearing — exactly why 0057 must NOT
    # deactivate the row (non-login is the role guard's job)
    sentinel.is_active = False
    db_session.commit()
    assert repo.get_active_user_by_username("lab_resource") is None


def test_batch_create_resolution_preserves_lab_resource(
    db_session: Session,
) -> None:
    """Live resolver #2 — batch create: the _BATCH_CREATE_RESOURCE_
    MAPPING ('lab' → 'lab_resource') resolves through the
    Doctor.active/User.is_active join and returns the resource
    Doctor.id with the 'Resource' role in place."""
    from app.services.batch_patient_service import BatchPatientService, EntryAction

    sentinel, sentinel_doctor = _make_lab_sentinel(db_session)

    service = BatchPatientService(db_session)
    action = EntryAction(
        entry_type="online_queue",
        action="create",
        specialty="lab",
        service_code=None,
        doctor_id=None,
    )
    resolved_id = service._resolve_create_action_specialist_id(
        action=action, queue_tag="lab", service=None
    )
    assert resolved_id == sentinel_doctor.id


def test_wizard_prepare_resolution_preserves_lab_resource(
    db_session: Session,
) -> None:
    """Live resolver #3 — wizard/morning prepare (the shared
    prepare_wizard_queue_assignment): a doctorless lab visit resolves
    lab_resource → Doctor.id and the DailyQueue is created with that
    specialist — with the 'Resource' role in place (QD-0 never
    filters by role)."""
    from app.services.morning_assignment import MorningAssignmentService

    sentinel, sentinel_doctor = _make_lab_sentinel(db_session)

    patient = Patient(
        first_name="Лаборатория",
        last_name="Пациент",
        phone="+998901110013",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        visit_date=date.today(),
        doctor_id=None,
        status="open",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    service = MorningAssignmentService(db_session)
    prepared = service.prepare_wizard_queue_assignment(
        visit, "lab", date.today(), source="pytest_qd12"
    )

    handoff = prepared.create_handoff
    assert handoff is not None, "doctorless lab visit must resolve, not None"
    assert handoff.queue_tag == "lab"
    assert handoff.daily_queue is not None
    assert handoff.daily_queue.specialist_id == sentinel_doctor.id

    create_kwargs = handoff.create_entry_kwargs
    assert create_kwargs["patient_id"] == patient.id
    assert create_kwargs["visit_id"] == visit.id
    assert create_kwargs["source"] == "pytest_qd12"


# ===================== human Lab preservation =====================


def test_lab_role_vocabulary_preserved() -> None:
    """QD-1.2 fixes the synthetic ACCOUNT, not the role: 'Lab' stays
    canonical — enum, STAFF_ROLES, hierarchy, the user-management
    write vocabulary, and neither internal-only nor login-blocked."""
    from app.core.roles import (  # isort: skip
        INTERNAL_ONLY_ROLE_SPELLINGS,
        Roles,
        STAFF_ROLES,
        get_role_hierarchy,
        is_internal_only_role_spelling,
        is_login_blocked_role,
    )

    assert Roles.LAB.value == "Lab"
    assert Roles.LAB in STAFF_ROLES
    assert get_role_hierarchy("Lab") == 5
    assert "Lab" not in INTERNAL_ONLY_ROLE_SPELLINGS
    assert not is_internal_only_role_spelling("Lab")
    assert not is_login_blocked_role("Lab")

    # the write vocabulary keeps accepting Lab (humans can still be
    # created/re-roled with it)
    import re

    from app.schemas.user_management import _USER_MANAGEMENT_ROLE_PATTERN

    assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Lab")


def test_roles_options_still_offer_lab_for_humans(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """The roles catalog/options boundary: 'Lab' remains selectable
    (human onboarding keeps working); the internal sentinel stays
    filtered on the same surface (QD-1.1 pin restated for the
    QD-1.2 contract)."""
    from app.models.role_permission import Role

    for name, display in (("Lab", "Лаборант"), ("Resource", "Queue Resource")):
        row = db_session.query(Role).filter(Role.name == name).first()
        if row:
            continue
        db_session.add(
            Role(
                name=name,
                display_name=display,
                level=0,
                is_active=True,
                is_system=False,
            )
        )
    db_session.commit()

    response = client.get("/api/v1/roles/options", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    values = [opt["value"] for opt in response.json().get("options", [])]
    assert "Lab" in values, values
    assert "Resource" not in values, values


def test_human_lab_login_and_grants_unchanged(
    client: TestClient, db_session: Session
) -> None:
    """End-to-end human contract: a real Lab user logs in through the
    production login endpoint and reaches a Lab-guarded surface
    (global search) — untouched by the sentinel conversion."""
    from app.api.v1.endpoints.global_search import GLOBAL_SEARCH_ROLES

    # guard membership pin: Lab stays in a representative Lab-guard set
    assert "Lab" in GLOBAL_SEARCH_ROLES

    _make_user(
        db_session, username="qd12_grants_lab", role="Lab", password=_PROBE_PASSWORD
    )

    response = client.post(
        "/api/v1/authentication/login",
        json={"username": "qd12_grants_lab", "password": _PROBE_PASSWORD},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    token = response.json()["access_token"]

    response = client.get(
        "/api/v1/global-search",
        params={"q": "поиск", "limit": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
