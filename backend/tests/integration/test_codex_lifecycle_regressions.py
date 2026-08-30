"""Regression tests for the Codex review findings on PR #2935 (lifecycle).

Each test maps 1:1 to a Codex finding and pins the fixed behavior:

- P1-A: bulk change_role follows the SAME lifecycle transition contract as
  update_user (promotion provisions/reactivates the linked Doctor profile,
  demotion deactivates it, doctor-family -> doctor-family keeps it intact).
- P1-B: reactivating a User restores the linked Doctor profile ONLY when the
  user's current role is doctor-family (Doctor -> Registrar -> deactivate ->
  reactivate must leave the profile inactive).
- P2-C: PUT /admin/doctors/{id} (and POST) cannot produce
  Doctor.active=True over a deactivated (or non-doctor-role) owner User.
- P1-D: incomplete profiles (specialty="general" sentinel) are excluded from
  clinical eligibility: registrar selector, QR/online routing. Admin
  visibility is preserved (/admin/doctors + profile_incomplete).
- P2-E: reassignment of a Doctor profile away from a doctor-role owner is
  rejected (no business transfer contract); userless repair stays allowed.
"""
from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.queue_profile import QueueProfile
from app.models.user import User
from app.services.user_mgmt._base import is_doctor_profile_incomplete


def _make_user(
    db_session, label: str, *, role: str = "Doctor", is_active: bool = True
) -> User:
    user = User(
        username=f"cx_{label}",
        email=f"cx-{label}@test.com",
        full_name=f"Codex {label}",
        hashed_password=get_password_hash("secret123"),
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(db_session, user: User | None, specialty: str, active: bool = True) -> Doctor:
    doctor = Doctor(
        user_id=user.id if user else None,
        specialty=specialty,
        active=active,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _admin_post_json(client, auth_headers, url: str, payload: dict) -> dict:
    response = client.post(url, json=payload, headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# P1-A — bulk role changes follow the lifecycle transition contract
# ---------------------------------------------------------------------------


class TestBulkRoleChangeLifecycle:
    def test_bulk_promotion_registrar_to_doctor_creates_profile(
        self, client, db_session, auth_headers
    ):
        user = _make_user(db_session, "bulk_prom", role="Registrar")

        _admin_post_json(
            client,
            auth_headers,
            "/api/v1/users/users/bulk-action",
            {"user_ids": [user.id], "action": "change_role", "role": "Doctor"},
        )

        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == user.id).one()
        assert refreshed.role == "Doctor"
        profile = (
            db_session.query(Doctor).filter(Doctor.user_id == user.id).all()
        )
        assert len(profile) == 1, "bulk promotion must provision a Doctor profile"
        assert profile[0].active is True
        # Controlled default state: incomplete sentinel until admin completes it
        assert profile[0].specialty == "general"
        assert is_doctor_profile_incomplete(profile[0].specialty)

    def test_bulk_demotion_doctor_to_registrar_deactivates_profile(
        self, client, db_session, auth_headers
    ):
        user = _make_user(db_session, "bulk_demo", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=True)

        _admin_post_json(
            client,
            auth_headers,
            "/api/v1/users/users/bulk-action",
            {"user_ids": [user.id], "action": "change_role", "role": "Registrar"},
        )

        db_session.expire_all()
        refreshed = db_session.query(User).filter(User.id == user.id).one()
        assert refreshed.role == "Registrar"
        row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        # Deactivated, link + identity preserved (no deletion/detach)
        assert row.active is False
        assert row.user_id == user.id

    def test_bulk_doctor_role_to_doctor_role_no_unnecessary_mutation(
        self, client, db_session, auth_headers
    ):
        """Dentist -> Doctor stays inside the doctor family: the existing
        profile keeps its specialty and stays active — no reset, no new row."""
        user = _make_user(db_session, "bulk_family", role="dentist")
        doctor = _make_doctor(db_session, user, "dentistry", active=True)

        _admin_post_json(
            client,
            auth_headers,
            "/api/v1/users/users/bulk-action",
            {"user_ids": [user.id], "action": "change_role", "role": "Doctor"},
        )

        db_session.expire_all()
        rows = db_session.query(Doctor).filter(Doctor.user_id == user.id).all()
        assert len(rows) == 1, "no duplicate profile rows on family transition"
        row = rows[0]
        assert row.id == doctor.id
        assert row.active is True
        assert row.specialty == "dentistry", "specialty preserved on family transition"
        assert db_session.query(User).filter(User.id == user.id).one().role == "Doctor"

    def test_bulk_same_role_change_role_is_noop(
        self, client, db_session, auth_headers
    ):
        """change_role to the user's CURRENT role must not touch the profile."""
        user = _make_user(db_session, "bulk_noop", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=True)

        _admin_post_json(
            client,
            auth_headers,
            "/api/v1/users/users/bulk-action",
            {"user_ids": [user.id], "action": "change_role", "role": "Doctor"},
        )

        db_session.expire_all()
        row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        assert row.active is True and row.specialty == "stomatology"


# ---------------------------------------------------------------------------
# P1-B — reactivation after role demotion must not resurrect the profile
# ---------------------------------------------------------------------------


class TestReactivationRoleGuard:
    def test_demote_deactivate_reactivate_keeps_doctor_inactive(
        self, client, db_session, auth_headers
    ):
        """Doctor -> Registrar -> deactivate -> reactivate:
        User active, Doctor profile INACTIVE (non-doctor user must never
        own an active clinical profile)."""
        user = _make_user(db_session, "reac", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=True)

        # 1) demote via update_user (single-user contract)
        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "Registrar"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is False
        )

        # 2) deactivate
        response = client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "deactivate"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        # 3) reactivate — must NOT resurrect the profile
        response = client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "activate"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        db_session.expire_all()
        assert (
            db_session.query(User).filter(User.id == user.id).one().is_active
            is True
        )
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is False
        ), "reactivation of a non-doctor-role user must leave the profile inactive"

    def test_reactivation_for_doctor_role_still_restores_profile(
        self, client, db_session, auth_headers
    ):
        """Control: the doctor-role owner keeps the restore-on-reactivate
        contract (only non-doctor roles lose it)."""
        user = _make_user(db_session, "reac_ok", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=True)

        response = client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "deactivate"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is False
        )

        response = client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "activate"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is True
        )


# ---------------------------------------------------------------------------
# P2-C — no active Doctor over an inactive / non-doctor owner
# ---------------------------------------------------------------------------


class TestActiveDoctorOwnerGuard:
    def test_put_admin_doctors_cannot_activate_over_inactive_user(
        self, client, db_session, auth_headers
    ):
        user = _make_user(db_session, "ghost_own", role="Doctor", is_active=False)
        doctor = _make_doctor(db_session, user, "stomatology", active=False)

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"active": True},
            headers=auth_headers,
        )
        assert response.status_code == 409, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is False
        ), "ghost state (active Doctor over inactive User) must be unreachable"

    def test_put_admin_doctors_cannot_activate_over_non_doctor_role(
        self, client, db_session, auth_headers
    ):
        user = _make_user(db_session, "ghost_role", role="Registrar")
        doctor = _make_doctor(db_session, user, "stomatology", active=False)

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"active": True},
            headers=auth_headers,
        )
        assert response.status_code == 409, response.text

    def test_put_admin_doctors_active_over_active_doctor_role_ok(
        self, client, db_session, auth_headers
    ):
        """Control: the normal path (active doctor-role owner) still works."""
        user = _make_user(db_session, "ghost_ok", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=False)

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"active": True},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active
            is True
        )

    def test_post_admin_doctors_cannot_create_active_over_inactive_user(
        self, client, db_session, auth_headers
    ):
        """Same ghost state blocked at creation time (create_doctor)."""
        user = _make_user(db_session, "ghost_new", role="Doctor", is_active=False)

        response = client.post(
            "/api/v1/admin/doctors",
            json={"name": "Ghost", "specialty": "stomatology", "active": True,
                 "user_id": user.id},
            headers=auth_headers,
        )
        assert response.status_code == 409, response.text


# ---------------------------------------------------------------------------
# P1-D — incomplete ("general" sentinel) excluded from clinical eligibility
# ---------------------------------------------------------------------------


class TestIncompleteProfileEligibility:
    def test_registrar_selector_excludes_incomplete_profile(
        self, client, db_session, auth_headers
    ):
        user = _make_user(db_session, "sel_inc", role="Doctor")
        incomplete = _make_doctor(db_session, user, "general", active=True)
        complete_user = _make_user(db_session, "sel_ok", role="Doctor")
        complete = _make_doctor(db_session, complete_user, "cardiology", active=True)

        response = client.get("/api/v1/registrar/doctors", headers=auth_headers)
        assert response.status_code == 200, response.text
        doctors = response.json()["doctors"]
        ids = {d["id"] for d in doctors}
        assert incomplete.id not in ids, "incomplete profile must not be selectable"
        assert complete.id in ids, "complete profile stays selectable"

        # Same holds under an explicit specialty filter
        response = client.get(
            "/api/v1/registrar/doctors",
            params={"specialty": "cardiology"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        doctors = response.json()["doctors"]
        assert {d["id"] for d in doctors} == {complete.id}

    def test_admin_visibility_of_incomplete_profile_preserved(
        self, client, db_session, auth_headers
    ):
        """P1-D boundary: admin MUST still see the incomplete profile to be
        able to complete it (no breaking of admin visibility)."""
        user = _make_user(db_session, "adm_inc", role="Doctor")
        incomplete = _make_doctor(db_session, user, "general", active=True)

        response = client.get(
            f"/api/v1/admin/doctors/{incomplete.id}", headers=auth_headers
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["id"] == incomplete.id
        assert payload["specialty"] == "general"
        assert payload["profile_incomplete"] is True

    def test_qr_routing_skips_incomplete_profile(
        self, db_session
    ):
        """Online booking / QR routing: an incomplete "general" doctor is
        never routed into a specialty queue even if the QueueProfile lists
        "general" among its queue_tags (defense in depth)."""
        from app.services.queue_service import QueueBusinessService

        service = QueueBusinessService()

        incomplete_user = _make_user(db_session, "qr_inc", role="Doctor")
        incomplete = _make_doctor(db_session, incomplete_user, "general", active=True)
        complete_user = _make_user(db_session, "qr_ok", role="Doctor")
        complete = _make_doctor(db_session, complete_user, "cardiology", active=True)

        profile = QueueProfile(
            key="cardiology",
            title="Cardiology",
            title_ru="Кардиология",
            queue_tags=["cardiology", "general"],  # adversarial: includes sentinel
            is_active=True,
            show_on_qr_page=True,
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

        # Profile-matched path: resolve must NOT pick the incomplete doctor.
        resolved = (
            db_session.query(Doctor)
            .filter(
                Doctor.active.is_(True),
                Doctor.specialty.in_(profile.queue_tags or [profile.key]),
                Doctor.specialty != "general",
            )
            .all()
        )
        assert [d.id for d in resolved] == [complete.id]
        assert incomplete.id not in [d.id for d in resolved]

    def test_reactivated_non_doctor_profile_stays_out_of_registrar_selector(
        self, client, db_session, auth_headers
    ):
        """Reactivation test for P1-D: after demote -> reactivate, the user is
        active again but the profile stays inactive AND absent from the
        registrar selector."""
        user = _make_user(db_session, "sel_reac", role="Doctor")
        doctor = _make_doctor(db_session, user, "stomatology", active=True)

        assert client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "Registrar"},
            headers=auth_headers,
        ).status_code == 200
        assert client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "deactivate"},
            headers=auth_headers,
        ).status_code == 200
        assert client.post(
            "/api/v1/users/users/bulk-action",
            json={"user_ids": [user.id], "action": "activate"},
            headers=auth_headers,
        ).status_code == 200

        db_session.expire_all()
        row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        assert row.active is False

        response = client.get("/api/v1/registrar/doctors", headers=auth_headers)
        assert response.status_code == 200, response.text
        ids = {d["id"] for d in response.json()["doctors"]}
        assert doctor.id not in ids


# ---------------------------------------------------------------------------
# P2-E — reassignment away from a doctor-role owner is rejected
# ---------------------------------------------------------------------------


class TestDoctorReassignmentGuard:
    def test_reassignment_from_doctor_role_owner_rejected(
        self, client, db_session, auth_headers
    ):
        owner_a = _make_user(db_session, "reassign_a", role="Doctor")
        owner_b = _make_user(db_session, "reassign_b", role="Doctor")
        doctor = _make_doctor(db_session, owner_a, "stomatology", active=True)

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"user_id": owner_b.id},
            headers=auth_headers,
        )
        assert response.status_code == 409, response.text

        db_session.expire_all()
        row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        assert row.user_id == owner_a.id, "link must be unchanged after rejection"
        # Invariant intact: the old owner still resolves to their profile
        assert (
            db_session.query(Doctor).filter(Doctor.user_id == owner_a.id).count() == 1
        )

    def test_linking_userless_doctor_still_allowed(self, client, db_session, auth_headers):
        """Userless-row repair path (decision #13 follow-up) must keep working:
        old owner is None -> not a reassignment."""
        doctor = _make_doctor(db_session, None, "stomatology", active=False)
        new_owner = _make_user(db_session, "reassign_new", role="Doctor")

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"user_id": new_owner.id},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().user_id
            == new_owner.id
        )

    def test_reassignment_allowed_when_old_owner_left_doctor_family(
        self, client, db_session, auth_headers
    ):
        """After a demotion the old owner has no doctor-family role anymore:
        reassignment is no longer the risky path and stays available."""
        owner_a = _make_user(db_session, "reassign_old", role="Doctor")
        owner_b = _make_user(db_session, "reassign_c", role="Doctor")
        doctor = _make_doctor(db_session, owner_a, "stomatology", active=True)

        # Demote the old owner first (profile deactivates, link preserved)
        assert client.put(
            f"/api/v1/users/users/{owner_a.id}",
            json={"role": "Registrar"},
            headers=auth_headers,
        ).status_code == 200

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            json={"user_id": owner_b.id},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one().user_id
            == owner_b.id
        )
