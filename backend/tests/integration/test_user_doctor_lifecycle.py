"""Lifecycle tests: User.is_active is mirrored onto the linked Doctor profile.

Ghost-doctor prevention contract (PR: fix/doctor-lifecycle-ghost-doctor):

- deleting a User deactivates (never deletes) their Doctor profile(s) in the
  same transaction; historical visits/EMR keep referencing the Doctor row;
- deactivating a User (single update or bulk action) deactivates the Doctor
  profile; reactivating restores it;
- /auth/me stops advertising specialty/doctor_id/cabinet once the Doctor
  profile is inactive (no clinical panel routing for deactivated doctors).
"""
from __future__ import annotations

from datetime import date

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _create_doctor_with_profile(
    db_session, label: str, *, role: str = "Doctor"
) -> tuple[User, Doctor]:
    user = User(
        username=f"lc_{label}",
        email=f"lc-{label}@test.com",
        full_name=f"Lifecycle {label}",
        hashed_password=get_password_hash("secret123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(user_id=user.id, specialty="stomatology", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_visit(db_session, doctor: Doctor) -> Visit:
    patient = Patient(
        first_name="Life",
        last_name="Cycle",
        phone="+998900000999",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_user_deactivates_doctor_and_preserves_history(
    client, db_session, auth_headers
):
    user, doctor = _create_doctor_with_profile(db_session, "del")
    visit = _create_visit(db_session, doctor)

    response = client.delete(
        f"/api/v1/users/users/{user.id}", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    # User is gone
    assert db_session.query(User).filter(User.id == user.id).first() is None

    # Doctor row survives (FK SET NULL) but is deactivated — no ghost doctor
    db_session.expire_all()
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).first()
    assert doctor_row is not None
    assert doctor_row.active is False
    assert doctor_row.user_id is None

    # Historical clinical data untouched
    visit_row = db_session.query(Visit).filter(Visit.id == visit.id).first()
    assert visit_row is not None
    assert visit_row.doctor_id == doctor.id


def test_bulk_deactivate_then_activate_mirrors_to_doctor(
    client, db_session, auth_headers
):
    user, doctor = _create_doctor_with_profile(db_session, "bulk")

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "deactivate"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is False

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "activate"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is True


def test_bulk_delete_deactivates_doctor(client, db_session, auth_headers):
    user, doctor = _create_doctor_with_profile(db_session, "bulkdel")

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "delete"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    assert db_session.query(User).filter(User.id == user.id).first() is None
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).first()
    assert doctor_row is not None
    assert doctor_row.active is False


def test_update_user_is_active_mirrors_to_doctor(client, db_session, auth_headers):
    user, doctor = _create_doctor_with_profile(db_session, "upd")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is False

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"is_active": True},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is True


def _patch_auth_me_sessionlocal(monkeypatch, db_session) -> None:
    """Route /auth/me's internal SessionLocal to the test DB.

    GET /auth/me builds a fresh SessionLocal() instead of using the get_db
    dependency, so in the test environment it must be pointed at the same
    connection-bound session factory the fixtures use.
    """
    from sqlalchemy.orm import sessionmaker

    from app.db import session as session_module

    def _fake_session_local():
        maker = sessionmaker(
            autocommit=False, autoflush=False, bind=db_session.get_bind()
        )
        return maker()

    monkeypatch.setattr(session_module, "SessionLocal", _fake_session_local)


def test_auth_me_hides_doctor_fields_for_inactive_doctor(
    client, db_session, monkeypatch
):
    user, doctor = _create_doctor_with_profile(db_session, "me")
    _patch_auth_me_sessionlocal(monkeypatch, db_session)

    headers = _doctor_headers(client, user)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["doctor_id"] == doctor.id
    assert body["specialty"] == "stomatology"

    # Deactivate the Doctor profile (e.g. owner deactivated by admin)
    doctor.active = False
    db_session.commit()

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["doctor_id"] is None
    assert body["specialty"] is None
    assert body["cabinet"] is None



# ---------------------------------------------------------------------------
# Role-change lifecycle invariant (decision #12):
#     role=Doctor-family  <->  active linked Doctor profile
# ---------------------------------------------------------------------------


def _create_user_with_role(db_session, label: str, role: str) -> User:
    """Create a user of any role directly via ORM (bypasses UserCreate regex)."""
    user = User(
        username=f"rc_{label}",
        email=f"rc-{label}@test.com",
        full_name=f"RoleChange {label}",
        hashed_password=get_password_hash("secret123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_promotion_registrar_to_doctor_creates_incomplete_profile(
    client, db_session, auth_headers
):
    """Registrar -> Doctor: linked Doctor profile provisioned in the
    controlled default (incomplete, specialty="general") state."""
    user = _create_user_with_role(db_session, "promo", "Registrar")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "Doctor"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    doctor = db_session.query(Doctor).filter(Doctor.user_id == user.id).one()
    assert doctor.active is True
    assert doctor.specialty == "general"  # incomplete sentinel (decision #5)

    # Admin sees the incompleteness on the doctors contract
    doctors = client.get("/api/v1/admin/doctors", headers=auth_headers)
    assert doctors.status_code == 200, doctors.text
    payload = {d["id"]: d for d in doctors.json()}
    assert payload[doctor.id]["profile_incomplete"] is True

    # ...and on the users contract
    users = client.get("/api/v1/users/users?search=rc_promo", headers=auth_headers)
    assert users.status_code == 200, users.text
    matched = [u for u in users.json()["users"] if u["id"] == user.id]
    assert matched and matched[0]["doctor_profile_incomplete"] is True


def test_demotion_doctor_to_registrar_deactivates_profile_and_keeps_history(
    client, db_session, auth_headers
):
    """Doctor -> Registrar: clinical profile deactivated, user_id link and
    historical visits preserved (nothing deleted, nothing detached)."""
    user, doctor = _create_doctor_with_profile(db_session, "demo")
    visit = _create_visit(db_session, doctor)

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "Registrar"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
    assert doctor_row.active is False
    assert doctor_row.user_id == user.id  # link kept for history continuity

    visit_row = db_session.query(Visit).filter(Visit.id == visit.id).one()
    assert visit_row.doctor_id == doctor.id  # history untouched


def test_repromotion_reactivates_same_doctor_profile(client, db_session, auth_headers):
    """Doctor -> Registrar -> Doctor: the SAME Doctor row (same clinical
    identity) is reactivated, not a duplicate."""
    user, doctor = _create_doctor_with_profile(db_session, "repro")

    for role in ("Registrar", "Doctor"):
        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": role},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    db_session.expire_all()
    doctors = db_session.query(Doctor).filter(Doctor.user_id == user.id).all()
    assert len(doctors) == 1
    assert doctors[0].id == doctor.id
    assert doctors[0].active is True


def test_legacy_dentist_to_canonical_doctor_keeps_profile(
    client, db_session, auth_headers
):
    """dentist -> Doctor (inside doctor-family): profile untouched — same
    identity, specialty preserved (legacy compatibility, decision #12)."""
    user = _create_user_with_role(db_session, "legacy", "dentist")
    doctor = Doctor(user_id=user.id, specialty="dentistry", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "Doctor"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    doctors = db_session.query(Doctor).filter(Doctor.user_id == user.id).all()
    assert len(doctors) == 1
    assert doctors[0].id == doctor.id
    assert doctors[0].specialty == "dentistry"
    assert doctors[0].active is True


def test_doctor_to_admin_demotion_deactivates_profile(
    client, db_session, auth_headers
):
    """Doctor -> Admin: same demotion contract (decision #17 matrix)."""
    user, doctor = _create_doctor_with_profile(db_session, "adm")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "Admin"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    assert (
        db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
        is False
    )


def test_admin_to_doctor_promotion_creates_profile(
    client, db_session, auth_headers
):
    """Admin -> Doctor: promotion contract applies to any non-doctor role."""
    user = _create_user_with_role(db_session, "adm2doc", "Admin")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "Doctor"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    doctor = db_session.query(Doctor).filter(Doctor.user_id == user.id).one()
    assert doctor.active is True
    assert doctor.specialty == "general"


def test_doctor_to_legacy_role_accepted_by_aligned_user_update_schema(
    client, db_session, auth_headers
):
    """D-3 RBAC unification: UserUpdate.role now shares UserCreate's
    vocabulary, so family-internal transitions to a legacy spelling
    (Doctor -> dentist) are ACCEPTED (no more create/update drift).
    Both roles belong to the doctor family, so the linked Doctor profile
    stays active and untouched (same clinical identity, specialty kept).
    The demotion path (family -> non-family) is covered by
    test_demote_doctor_deactivates_profile."""
    user, doctor = _create_doctor_with_profile(db_session, "toleg")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"role": "dentist"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    row = db_session.query(User).filter(User.id == user.id).one()
    assert row.role == "dentist"
    profile = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
    assert profile.active is True  # family-internal: profile preserved
    assert profile.user_id == user.id  # link preserved


# ---------------------------------------------------------------------------
# Decision #13: API must not create/produce ACTIVE userless Doctors
# (POST/PUT /admin/doctors). Inactive userless rows stay legal (historical).
# ---------------------------------------------------------------------------


def test_create_active_userless_doctor_rejected(client, db_session, auth_headers):
    response = client.post(
        "/api/v1/admin/doctors",
        json={"specialty": "dentistry", "active": True},
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text
    assert "user_id" in response.json()["detail"]
    assert (
        db_session.query(Doctor).filter(Doctor.user_id.is_(None)).count() == 0
    )


def test_create_inactive_userless_doctor_allowed_for_history(
    client, db_session, auth_headers
):
    # Medical Specialty Catalog (0051) is the write-boundary SSOT: even a
    # historical inactive row must carry a canonical ACTIVE catalog code.
    from app.services.medical_specialty_seed import seed_medical_specialties

    seed_medical_specialties(db_session.connection())
    db_session.commit()

    response = client.post(
        "/api/v1/admin/doctors",
        json={"specialty": "dentistry", "active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] is None
    assert body["active"] is False
    assert body["profile_incomplete"] is False  # real specialty supplied


def test_activate_userless_doctor_rejected(client, db_session, auth_headers):
    doctor = Doctor(user_id=None, specialty="dentistry", active=False)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    response = client.put(
        f"/api/v1/admin/doctors/{doctor.id}",
        json={"active": True},
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text

    db_session.expire_all()
    assert (
        db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
        is False
    )


def test_unset_user_on_active_doctor_rejected(client, db_session, auth_headers):
    user = _create_user_with_role(db_session, "unset", "Doctor")
    doctor = Doctor(user_id=user.id, specialty="dentistry", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    response = client.put(
        f"/api/v1/admin/doctors/{doctor.id}",
        json={"user_id": None},
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text

    db_session.expire_all()
    row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
    assert row.user_id == user.id
    assert row.active is True


def test_doctors_list_flags_incomplete_general_specialty(
    client, db_session, auth_headers
):
    """profile_incomplete=True only for the "general" placeholder."""
    user = _create_user_with_role(db_session, "flag", "Doctor")
    incomplete = Doctor(user_id=user.id, specialty="general", active=True)
    complete = Doctor(user_id=None, specialty="dentistry", active=False)
    db_session.add_all([incomplete, complete])
    db_session.commit()
    db_session.refresh(incomplete)
    db_session.refresh(complete)

    doctors = client.get("/api/v1/admin/doctors", headers=auth_headers)
    assert doctors.status_code == 200, doctors.text
    payload = {d["id"]: d for d in doctors.json()}
    assert payload[incomplete.id]["profile_incomplete"] is True
    assert payload[complete.id]["profile_incomplete"] is False
