"""Admin doctor onboarding UX — canonical User+Doctor creation contract.

Owner decision 2026-09-01: creating a new system doctor must be ONE
operation from the Users module:

    POST /users/users  role=Doctor  +  doctor_profile{specialty=...}

Invariants under test:
- 422 matrix: Doctor without profile / sentinel / non-canonical specialty /
  doctor_profile on non-Doctor roles;
- OK matrix: canonical specialties create a linked, COMPLETE Doctor profile
  in the same transaction (User + UserProfile + Preferences + Notifications
  + Doctor — one commit);
- atomicity: Doctor failure leaves no User; User failure leaves no Doctor;
- legacy doctor-role spellings via API keep the compatibility auto-map;
- GET /admin/doctors/specialty-vocabulary exposes the onboarding registry.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.user import User
from app.services.user_mgmt._operations import get_user_management_service

_DOCTOR_PAYLOAD = {
    "username": "onboard_doc",
    "email": "onboard.doc@clinic.test",
    "password": "Passw0rd123",
    "full_name": "Onboard Doctor",
    "role": "Doctor",
}


def _post_doctor(client: TestClient, **overrides) -> tuple[int, dict]:
    payload = {**_DOCTOR_PAYLOAD, **overrides}
    for key, value in overrides.get("_remove", {}).items():  # type: ignore[union-attr]
        payload.pop(key, None)
    payload.pop("_remove", None)
    response = client.post("/api/v1/users/users", json=payload)
    return response.status_code, (response.json() if response.status_code != 422 else response.json())


class TestOnboardingValidationMatrix:
    def test_doctor_without_profile_is_rejected(self, client, auth_headers):
        response = client.post("/api/v1/users/users", headers=auth_headers, json=_DOCTOR_PAYLOAD)
        assert response.status_code == 422

    def test_doctor_with_general_sentinel_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "general"}},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("specialty", ["dental", "stomatology", "dentist", "Cardiology", "kardio", ""])
    def test_doctor_with_non_canonical_specialty_is_rejected(self, client, auth_headers, specialty):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": specialty}},
        )
        assert response.status_code == 422

    def test_doctor_with_unknown_specialty_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "neurology"}},
        )
        assert response.status_code == 422

    def test_doctor_profile_on_non_doctor_role_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                "username": "plain_reg",
                "email": "plain.reg@clinic.test",
                "password": "Passw0rd123",
                "full_name": "Plain Registrar",
                "role": "Registrar",
                "doctor_profile": {"specialty": "cardiology"},
            },
        )
        assert response.status_code == 422

    def test_doctor_profile_on_legacy_doctor_role_is_rejected(self, client, auth_headers):
        """Legacy spellings are a compatibility surface without a UI path:
        they must keep the auto-map, not the canonical block."""
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                "username": "legacy_cardio",
                "email": "legacy.cardio@clinic.test",
                "password": "Passw0rd123",
                "full_name": "Legacy Cardio",
                "role": "cardio",
                "doctor_profile": {"specialty": "cardiology"},
            },
        )
        assert response.status_code == 422


class TestOnboardingSuccess:
    @pytest.mark.parametrize("specialty", ["cardiology", "dermatology", "dentistry"])
    def test_canonical_onboarding_creates_complete_doctor(
        self, client, auth_headers, db_session, specialty
    ):
        username = f"onboard_{specialty}"
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                "username": username,
                "email": f"{username}@clinic.test",
                "password": "Passw0rd123",
                "full_name": f"Onboard {specialty}",
                "role": "Doctor",
                "doctor_profile": {
                    "specialty": specialty,
                    "cabinet": "12",
                    "price_default": 150000,
                },
            },
        )
        assert response.status_code == 200, response.text

        user = db_session.query(User).filter(User.username == username).first()
        assert user is not None and user.role == "Doctor"
        doctor = db_session.query(Doctor).filter(Doctor.user_id == user.id).first()
        assert doctor is not None, "linked Doctor profile must exist"
        assert doctor.user_id == user.id
        assert doctor.specialty == specialty
        from app.services.user_mgmt._base import is_doctor_profile_incomplete

        assert is_doctor_profile_incomplete(doctor.specialty) is False
        assert doctor.cabinet == "12"

    def test_optional_fields_use_doctor_defaults(
        self, client, auth_headers, db_session
    ):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                **_DOCTOR_PAYLOAD,
                "doctor_profile": {"specialty": "cardiology"},
            },
        )
        assert response.status_code == 200, response.text
        doctor = (
            db_session.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.username == _DOCTOR_PAYLOAD["username"])
            .first()
        )
        assert doctor is not None
        assert doctor.start_number_online == 1
        assert doctor.max_online_per_day == 15


class TestOnboardingAtomicity:
    def test_doctor_failure_leaves_no_user(self, client, auth_headers, db_session, monkeypatch):
        """Regression (owner invariant): if Doctor creation fails inside the
        transaction, the User must NOT remain created."""
        from app.services.user_mgmt import _core as user_mgmt_core

        def _boom(*args, **kwargs):
            raise RuntimeError("injected doctor failure")

        monkeypatch.setattr(user_mgmt_core, "Doctor", _boom)
        service = get_user_management_service()

        from app.schemas.user_management import UserCreateRequest

        request = UserCreateRequest(
            **{**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "cardiology"}}
        )
        success, _message, user = service.create_user(db_session, request, created_by=1)
        assert success is False
        remaining = (
            db_session.query(User)
            .filter(User.username == _DOCTOR_PAYLOAD["username"])
            .first()
        )
        assert remaining is None, "rollback must remove the half-created User"

    def test_user_failure_leaves_no_doctor(self, client, auth_headers, db_session):
        """Duplicate username fails the User step; no Doctor row may appear."""
        from app.schemas.user_management import UserCreateRequest

        service = get_user_management_service()
        request = UserCreateRequest(
            **{**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "cardiology"}}
        )
        success, _message, _user = service.create_user(db_session, request, created_by=1)
        assert success is True

        duplicate = UserCreateRequest(
            **{
                **_DOCTOR_PAYLOAD,
                "email": "second.mail@clinic.test",
                "doctor_profile": {"specialty": "cardiology"},
            }
        )
        success2, _message2, _user2 = service.create_user(db_session, duplicate, created_by=1)
        assert success2 is False

        doctors = (
            db_session.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.username == _DOCTOR_PAYLOAD["username"])
            .all()
        )
        assert len(doctors) == 1, "failed duplicate must not add a second Doctor"


class TestLegacyRoleCompatibility:
    def test_legacy_cardio_role_keeps_auto_map(self, client, auth_headers, db_session):
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                "username": "legacy_automap",
                "email": "legacy.automap@clinic.test",
                "password": "Passw0rd123",
                "full_name": "Legacy Automap",
                "role": "cardio",
            },
        )
        assert response.status_code == 200, response.text
        doctor = (
            db_session.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.username == "legacy_automap")
            .first()
        )
        assert doctor is not None
        assert doctor.specialty == "cardiology"


class TestSpecialtyVocabularyEndpoint:
    def test_vocabulary_returns_canonical_ids_only(
        self, client, auth_headers
    ):
        response = client.get(
            "/api/v1/admin/doctors/specialty-vocabulary", headers=auth_headers
        )
        assert response.status_code == 200
        codes = [item["code"] for item in response.json()]
        assert codes == ["cardiology", "dermatology", "dentistry"]
        assert "general" not in codes

    def test_vocabulary_requires_admin(self, client, auth_headers):
        response = client.get("/api/v1/admin/doctors/specialty-vocabulary")
        assert response.status_code in (401, 403)
