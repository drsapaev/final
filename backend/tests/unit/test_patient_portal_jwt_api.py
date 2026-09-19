"""JWT patient portal endpoints (Phase 1 / PR-C1).

Covers the canonical web-portal self-service contract introduced to give
Phase 0 OTP patients the same capabilities the Telegram Mini App provides:

- GET  /api/v1/patients/cabinet/summary — home-screen summary (own scope)
- POST /api/v1/patients/booking/preview — non-mutating booking preview
- POST /api/v1/patients/booking         — trusted booking creation
- GET  /api/v1/patients/forms           — read-only forms metadata

Key invariants:
- JWT Patient session only (staff roles get 403 from require_roles)
- the portal principal must be an ACTIVE user (round-2 P1: require_roles
  alone delegates to get_current_user, which never checks is_active)
- a User without a linked Patient profile gets 404 patient_profile_required
- a SOFT-DELETED patient card is rejected with 403 patient_link_invalid
  (round-2 P1: soft deletion only flips the flag, the relationship keeps
  resolving — the Mini App SSOT check must hold for the JWT portal too)
- request-shaped booking errors are 400, scope problems are 403
- `department` resolves through the canonical Department.key (unknown key /
  inactive department → 400) and the created Appointment carries the
  resolved `department_id` (round-2 P1: no NULL routing context)
- POST /patients/booking REQUIRES Idempotency-Key; same key + same payload
  replays the committed 201 → exactly one Appointment (round-2 P2)
- past appointment dates are rejected (appointment_date_in_past)
- forms endpoint is read-only: POST /patients/forms must be 405
- the OpenAPI document publishes the typed DTOs and the real error surface
  (round-2 P2: no dict[str, Any], no undeclared 4xx)
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.user import User

_FRONTEND_API_TS = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "types"
    / "generated"
    / "api.ts"
)


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


@pytest.fixture
def portal_department(db_session: Session) -> Department:
    """Canonical booking department — requests use its unique `key`."""
    row = db_session.query(Department).filter(Department.key == "cardio").first()
    if not row:
        row = Department(
            key="cardio",
            name_ru="Кардиология",
            name_uz="Kardiologiya",
            active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
    return row


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


class TestSoftDeletedPatientRejected:
    """Round-2 P1: soft deletion only flips is_deleted — the JWT portal must
    honor the same `patient_link_invalid` SSOT check as the Mini App."""

    def _soft_delete(self, db_session: Session, test_patient):
        test_patient.is_deleted = True
        db_session.commit()

    def test_soft_deleted_patient_cannot_read_cabinet(
        self, client: TestClient, linked_patient_headers, db_session, test_patient
    ):
        self._soft_delete(db_session, test_patient)
        response = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"]["reason"] == "patient_link_invalid"

    def test_soft_deleted_patient_cannot_read_forms(
        self, client: TestClient, linked_patient_headers, db_session, test_patient
    ):
        self._soft_delete(db_session, test_patient)
        response = client.get("/api/v1/patients/forms", headers=linked_patient_headers)
        assert response.status_code == 403
        assert response.json()["detail"]["reason"] == "patient_link_invalid"

    def test_soft_deleted_patient_cannot_book(
        self, client: TestClient, linked_patient_headers, db_session, test_patient
    ):
        self._soft_delete(db_session, test_patient)
        future_date = str(date.today() + timedelta(days=3))
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "softdel-1"},
            json={"appointmentDate": future_date},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["reason"] == "patient_link_invalid"
        assert db_session.query(Appointment).count() == 0


class TestDeactivatedUserRejected:
    """Round-2 P1: an admin-deactivated Patient user must not keep PHI read
    or booking access just because the JWT is still unexpired."""

    def _deactivate(self, db_session: Session) -> None:
        user = db_session.query(User).filter(User.username == "portal_patient").first()
        assert user is not None
        user.is_active = False
        db_session.commit()

    def test_deactivated_user_cannot_read_cabinet(
        self, client: TestClient, linked_patient_headers, db_session
    ):
        self._deactivate(db_session)
        response = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert response.status_code == 403

    def test_deactivated_user_cannot_book(
        self, client: TestClient, linked_patient_headers, db_session
    ):
        self._deactivate(db_session)
        future_date = str(date.today() + timedelta(days=3))
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "deact-1"},
            json={"appointmentDate": future_date},
        )
        assert response.status_code == 403
        assert db_session.query(Appointment).count() == 0

    def test_deactivated_user_cannot_read_forms(
        self, client: TestClient, linked_patient_headers, db_session
    ):
        self._deactivate(db_session)
        response = client.get("/api/v1/patients/forms", headers=linked_patient_headers)
        assert response.status_code == 403


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

    def test_preview_ok(
        self, client: TestClient, linked_patient_headers, portal_department
    ):
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
                "notes": "web portal booking",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["appointment"]["patient_id"] > 0
        assert payload["appointment"]["department"] == portal_department.key
        assert payload["appointment"]["department_id"] == portal_department.id
        assert payload["preview_only"] is True

    def test_preview_unknown_department_400(
        self, client: TestClient, linked_patient_headers
    ):
        # Round-2 P1: a department label that is not a canonical key must be
        # rejected up front, not echoed and then silently dropped on create.
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={"appointmentDate": self.future_date, "department": "cardiology"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "department_unknown"

    def test_preview_inactive_department_400(
        self, client: TestClient, linked_patient_headers, db_session, portal_department
    ):
        portal_department.active = False
        db_session.commit()
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "department_inactive"

    def test_create_ok(
        self,
        client: TestClient,
        linked_patient_headers,
        db_session,
        test_patient,
        portal_department,
    ):
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "create-ok-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["created"] is True
        assert payload["appointment_id"] > 0
        assert (
            payload["preview"]["appointment"]["department_id"] == portal_department.id
        )

        # Round-2 P1: the routing context is PERSISTED — the created row
        # carries the resolved department_id, not a NULL column.
        row = db_session.get(Appointment, payload["appointment_id"])
        assert row is not None
        assert row.department_id == portal_department.id
        assert row.patient_id == test_patient.id

    def test_create_unknown_department_400_no_row(
        self, client: TestClient, linked_patient_headers, db_session
    ):
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "create-bad-dep"},
            json={"appointmentDate": self.future_date, "department": "no-such-dep"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "department_unknown"
        assert db_session.query(Appointment).count() == 0

    def test_create_ignores_body_patient_id(
        self, client: TestClient, linked_patient_headers, test_patient
    ):
        # patient_id is always taken from the JWT session — a forged body
        # patientId cannot widen the scope (mirrors Mini App behavior).
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "scope-1"},
            json={"appointmentDate": self.future_date, "patientId": 999999},
        )
        assert response.status_code == 201
        assert (
            response.json()["preview"]["appointment"]["patient_id"] == test_patient.id
        )


class TestBookingIdempotency:
    """Round-2 P2: the middleware is opt-in — the portal mandates the key."""

    future_date = str(date.today() + timedelta(days=3))

    def test_create_requires_idempotency_key(
        self, client: TestClient, linked_patient_headers
    ):
        response = client.post(
            "/api/v1/patients/booking",
            headers=linked_patient_headers,
            json={"appointmentDate": self.future_date},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("Idempotency-Key" in str(item.get("loc", [])) for item in detail)

    def test_same_key_replays_single_appointment(
        self, client: TestClient, linked_patient_headers, db_session, test_patient
    ):
        # The duplicate-booking scenario: date-only request (no doctor slot
        # lock applies), response lost, browser retries with the SAME key —
        # the middleware must replay the committed 201, not re-execute.
        key = "portal-retry-1"
        body = {"appointmentDate": self.future_date}
        first = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert first.status_code == 201
        second = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert second.status_code == 201
        assert second.json()["appointment_id"] == first.json()["appointment_id"]
        assert (
            db_session.query(Appointment)
            .filter(Appointment.patient_id == test_patient.id)
            .count()
            == 1
        )

    def test_different_key_creates_independent_appointment(
        self, client: TestClient, linked_patient_headers, db_session, test_patient
    ):
        # Distinct booking attempts (distinct keys) must NOT be deduplicated.
        for i in (1, 2):
            response = client.post(
                "/api/v1/patients/booking",
                headers={**linked_patient_headers, "Idempotency-Key": f"attempt-{i}"},
                json={"appointmentDate": self.future_date},
            )
            assert response.status_code == 201
        assert (
            db_session.query(Appointment)
            .filter(Appointment.patient_id == test_patient.id)
            .count()
            == 2
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


class TestOpenAPIContract:
    """Round-2 P2: the published contract is typed and documents its errors.

    PR-C2 consumes the generated TypeScript — `dict[str, Any]` responses
    compile to `{[key: string]: unknown}` and undeclared 4xx leaves the
    runtime contract drifting from the OpenAPI contract.
    """

    @pytest.fixture(scope="function")
    def openapi(self, client: TestClient) -> dict:
        return client.get("/openapi.json").json()

    def _responses(self, openapi: dict, path: str, method: str) -> dict:
        return openapi["paths"][path][method]["responses"]

    def test_booking_publishes_typed_success_and_errors(self, openapi):
        booking = self._responses(openapi, "/api/v1/patients/booking", "post")
        assert set(booking) == {"201", "400", "401", "403", "409", "422"}
        assert (
            booking["201"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalBookingCreatedResponse"
        )
        assert (
            booking["409"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )

    def test_booking_requires_idempotency_key_header(self, openapi):
        operation = openapi["paths"]["/api/v1/patients/booking"]["post"]
        header_params = [
            p
            for p in operation.get("parameters", [])
            if p.get("in") == "header" and p.get("name") == "Idempotency-Key"
        ]
        assert header_params, "Idempotency-Key header must be published"
        assert header_params[0]["required"] is True

    def test_preview_publishes_typed_success_and_errors(self, openapi):
        preview = self._responses(openapi, "/api/v1/patients/booking/preview", "post")
        assert set(preview) == {"200", "400", "401", "403", "422"}
        assert (
            preview["200"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalBookingPreviewResponse"
        )

    def test_cabinet_publishes_typed_success_and_errors(self, openapi):
        cabinet = self._responses(openapi, "/api/v1/patients/cabinet/summary", "get")
        assert set(cabinet) == {"200", "401", "403", "404"}
        assert (
            cabinet["200"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalCabinetSummaryResponse"
        )

    def test_forms_publishes_typed_success_and_errors(self, openapi):
        forms = self._responses(openapi, "/api/v1/patients/forms", "get")
        assert set(forms) == {"200", "400", "401", "403"}
        assert (
            forms["200"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalFormsResponse"
        )

    def test_generated_typescript_contains_portal_dtos(self, openapi):
        schemas = openapi["components"]["schemas"]
        for name in (
            "PatientPortalBookingCreatedResponse",
            "PatientPortalBookingPreviewResponse",
            "PatientPortalCabinetSummaryResponse",
            "PatientPortalFormsResponse",
            "PatientPortalErrorResponse",
            "PatientPortalBookingRequest",
        ):
            assert name in schemas
        # The generated TS contract PR-C2 builds against is regenerated from
        # this spec (CI gate: generate:api-types:check) — the DTOs must be
        # present there too, typed rather than `{[key: string]: unknown}`.
        generated = _FRONTEND_API_TS.read_text(encoding="utf-8")
        assert "PatientPortalBookingCreatedResponse" in generated
        assert "PatientPortalFormsResponse" in generated
        assert "department_id" in generated
