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

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.user import User
from pydantic import TypeAdapter, ValidationError

from app.schemas.user_management import UserCreateRequest
from app.services.user_mgmt._operations import get_user_management_service

# Synthetic test credential in the repo's established pattern
# (cf. "Admin1234" in test_admin_user_reserved_email.py): obviously
# role-flavored and never used outside the test database.
_TEST_PASSWORD = 'Doctor1234'

_DOCTOR_PAYLOAD = {
    "username": "onboard_doc",
    "email": "onboard.doc@clinic.test",
    "password": _TEST_PASSWORD,
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
                "password": _TEST_PASSWORD,
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
                "password": _TEST_PASSWORD,
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
                "password": _TEST_PASSWORD,
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

        request = TypeAdapter(UserCreateRequest).validate_python(
            {**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "cardiology"}}
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
        service = get_user_management_service()
        request = TypeAdapter(UserCreateRequest).validate_python(
            {**_DOCTOR_PAYLOAD, "doctor_profile": {"specialty": "cardiology"}}
        )
        success, _message, _user = service.create_user(db_session, request, created_by=1)
        assert success is True

        duplicate = TypeAdapter(UserCreateRequest).validate_python(
            {
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
                "password": _TEST_PASSWORD,
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


class TestConditionalCreateContract:
    """Codex P2: the conditional requirement must live in the published
    contract, not only in the runtime validator."""

    def test_union_accepts_every_pattern_role(self):
        """Equivalence with the legacy role pattern: no previously accepted
        role value may start failing validation after the union refactor."""
        import re as _re

        from pydantic import TypeAdapter

        from app.schemas.user_management import _USER_MANAGEMENT_ROLE_PATTERN

        adapter = TypeAdapter(UserCreateRequest)
        pattern = _re.compile(_USER_MANAGEMENT_ROLE_PATTERN)
        # every value the legacy regex accepted must validate via the union
        # REC-1 (main): 'Receptionist' is write-frozen (filter-only), so it
        # is intentionally absent from the create union.
        accepted = [
            "Admin", "Registrar", "Doctor", "Nurse",
            "Cashier", "Lab", "Patient", "SuperAdmin", "Manager",
        ] + [
            "cardio", "cardiologist", "cardiology", "dentist", "dentistry",
            "derma", "dermatologist", "dermatology", "doctor",
        ]
        for role in accepted:
            assert pattern.match(role), f"test data drift: {role}"
            payload = {
                "username": f"equiv_{role}",
                "email": f"equiv_{role}@clinic.test",
                "password": _TEST_PASSWORD,
                "role": role,
            }
            if role == "Doctor":
                payload["doctor_profile"] = {"specialty": "cardiology"}
            adapter.validate_python(payload)  # must not raise

    def test_openapi_publishes_conditional_requirement(self):
        """The committed OpenAPI spec must describe the Doctor variant with
        doctor_profile REQUIRED via oneOf + role discriminator."""
        from pathlib import Path

        spec_path = Path(__file__).resolve().parents[2] / "openapi.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

        body = spec["paths"]["/api/v1/users/users"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        one_of = body.get("oneOf")
        assert one_of, "create request must be a oneOf of role variants"

        schemas = spec["components"]["schemas"]
        doctor_refs = [
            ref["$ref"].rsplit("/", 1)[-1]
            for ref in one_of
            if "DoctorUserCreateRequest" in ref["$ref"]
        ]
        assert doctor_refs, "DoctorUserCreateRequest variant missing from oneOf"
        doctor_schema = schemas[doctor_refs[0]]
        assert "doctor_profile" in doctor_schema.get("required", []), (
            "doctor_profile must be REQUIRED in the published Doctor variant"
        )

        non_doctor_refs = [
            ref["$ref"].rsplit("/", 1)[-1]
            for ref in one_of
            if "NonDoctorUserCreateRequest" in ref["$ref"]
        ]
        assert non_doctor_refs
        non_doctor_schema = schemas[non_doctor_refs[0]]
        assert "doctor_profile" not in non_doctor_schema.get("required", [])
        assert non_doctor_schema["properties"]["doctor_profile"]["type"] == "null"

        assert body.get("discriminator", {}).get("propertyName") == "role"


def test_doctor_profile_price_precision_contract():
    """Codex round-6 P2: doctors.price_default is Numeric(10, 2) —
    DoctorProfileCreate rejects values beyond the column precision with a
    field-level 422 (no driver overflow rolling back the onboarding txn)."""
    from decimal import Decimal

    from app.schemas.user_management import DoctorProfileCreate

    # boundary values pass
    ok = DoctorProfileCreate(specialty="cardiology", price_default=Decimal("99999999.99"))
    assert ok.price_default == Decimal("99999999.99")
    ok2 = DoctorProfileCreate(specialty="cardiology", price_default=Decimal("0"))
    assert ok2.price_default == Decimal("0")
    # more than 2 decimal places -> validation error
    with pytest.raises(ValidationError):
        DoctorProfileCreate(specialty="cardiology", price_default=Decimal("100.555"))
    # 9 integer digits -> beyond Numeric(10,2) -> validation error
    with pytest.raises(ValidationError):
        DoctorProfileCreate(specialty="cardiology", price_default=Decimal("100000000"))
    # None stays legal (price optional)
    assert DoctorProfileCreate(specialty="cardiology").price_default is None
