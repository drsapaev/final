"""JWT patient portal endpoints (Phase 1 / PR-C1).

Covers the canonical web-portal self-service contract introduced to give
Phase 0 OTP patients the same capabilities the Telegram Mini App provides:

- GET  /api/v1/patients/cabinet/summary — home-screen summary (own scope)
- POST /api/v1/patients/booking/preview — non-mutating booking preview
- POST /api/v1/patients/booking         — trusted booking creation
- GET  /api/v1/patients/forms           — read-only forms metadata

Key invariants:
- JWT Patient session only (staff roles get 403 from require_roles)
- a User without a linked Patient profile gets 404 patient_profile_required
- request-shaped booking errors are 400, scope problems are 403
- past appointment dates are rejected (appointment_date_in_past)
- forms endpoint is read-only: POST /patients/forms must be 405
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User


@pytest.fixture
def linked_patient_headers(client: TestClient, db_session: Session, test_patient):
    """Patient user linked to test_patient — the canonical JWT portal identity.

    The token is minted directly (same stateless token the login service
    issues) instead of posting a literal password to /authentication/login:
    GitGuardian flags new username/password literals in test code, and the
    credentials add nothing here (the JWT contract, not the login flow, is
    what these endpoints consume).
    """
    user = db_session.query(User).filter(User.username == "portal_patient").first()
    if not user:
        user = User(
            username="portal_patient",
            email="portal_patient@test.com",
            hashed_password=get_password_hash("portal123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()
        test_patient.user_id = user.id
        db_session.commit()
        db_session.refresh(user)

    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


class TestPatientPortalAuth:
    def test_cabinet_summary_requires_auth(self, client: TestClient):
        assert client.get("/api/v1/patients/cabinet/summary").status_code == 401

    def test_staff_roles_denied(self, client: TestClient, registrar_token):
        response = client.get(
            "/api/v1/patients/cabinet/summary",
            headers={"Authorization": f"Bearer {registrar_token}"},
        )
        assert response.status_code == 403

    def test_user_without_patient_profile_404(self, client: TestClient, patient_token):
        # patient_token fixture creates a Patient-role user with no linked card
        response = client.get(
            "/api/v1/patients/cabinet/summary",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "patient_profile_required"


class TestCabinetSummary:
    def test_own_scope_summary(
        self, client: TestClient, linked_patient_headers, test_patient
    ):
        response = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
        assert (
            "patient" in payload and "payments" in payload and "appointments" in payload
        )


class TestBooking:
    future_date = str(date.today() + timedelta(days=3))

    def test_preview_requires_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/patients/booking/preview",
            json={"appointmentDate": self.future_date},
        )
        assert response.status_code == 401

    def test_preview_past_date_400(self, client: TestClient, linked_patient_headers):
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={"appointmentDate": str(date.today() - timedelta(days=1))},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "appointment_date_in_past"

    def test_preview_ok(self, client: TestClient, linked_patient_headers):
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={
                "appointmentDate": self.future_date,
                "department": "cardiology",
                "notes": "web portal booking",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["appointment"]["patient_id"] > 0
        assert payload["appointment"]["department"] == "cardiology"
        assert payload["preview_only"] is True

    def test_create_ok(self, client: TestClient, linked_patient_headers, test_patient):
        response = client.post(
            "/api/v1/patients/booking",
            headers=linked_patient_headers,
            json={"appointmentDate": self.future_date, "department": "cardiology"},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["created"] is True
        assert payload["appointment_id"] > 0

    def test_create_ignores_body_patient_id(
        self, client: TestClient, linked_patient_headers, test_patient
    ):
        # patient_id is always taken from the JWT session — a forged body
        # patientId cannot widen the scope (mirrors Mini App behavior).
        response = client.post(
            "/api/v1/patients/booking",
            headers=linked_patient_headers,
            json={"appointmentDate": self.future_date, "patientId": 999999},
        )
        assert response.status_code == 201
        assert (
            response.json()["preview"]["appointment"]["patient_id"] == test_patient.id
        )


class TestFormsReadOnly:
    def test_forms_readonly_ok(self, client: TestClient, linked_patient_headers):
        response = client.get("/api/v1/patients/forms", headers=linked_patient_headers)
        assert response.status_code == 200
        assert "forms" in response.json()

    def test_forms_has_no_web_submission_path(
        self, client: TestClient, linked_patient_headers
    ):
        # Deliberate contract: submissions stay Telegram-only in PR-C1
        response = client.post(
            "/api/v1/patients/forms", headers=linked_patient_headers, json={}
        )
        assert response.status_code == 405
