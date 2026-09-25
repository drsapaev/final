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
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
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
        # Round-3 P2: 404 is real (no linked Patient profile / doctor
        # eligibility) and must be published.
        # Round-6 (owner P2): 503 is real — required idempotency coordination
        # down (code=idempotency_unavailable) — and must be published too.
        assert set(booking) == {
            "201", "400", "401", "403", "404", "409", "422", "503",
        }
        assert (
            booking["201"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalBookingCreatedResponse"
        )
        assert (
            booking["404"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert (
            booking["409"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert (
            booking["503"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert "idempotency_unavailable" in booking["503"]["description"]

    def test_booking_requires_idempotency_key_header(self, openapi):
        operation = openapi["paths"]["/api/v1/patients/booking"]["post"]
        header_params = [
            p
            for p in operation.get("parameters", [])
            if p.get("in") == "header" and p.get("name") == "Idempotency-Key"
        ]
        assert header_params, "Idempotency-Key header must be published"
        assert header_params[0]["required"] is True
        # Round-6 (owner P1): the caller-owned key is BOUNDED — oversized
        # keys are a 400 idempotency_key_invalid, the contract is published.
        assert header_params[0]["schema"].get("maxLength") == 128
        assert header_params[0]["schema"].get("minLength") == 1

    def test_idempotency_error_code_is_typed(self, openapi):
        """Round-6 (owner P2): the middleware's 409/503 bodies carry a
        machine top-level `code` the client must branch on (retry the same
        key / new key / reconcile / wait for Redis). The published DTO must
        describe it, or the regenerated TypeScript silently drops half the
        runtime contract."""
        schema = openapi["components"]["schemas"]["PatientPortalErrorResponse"]
        props = schema["properties"]
        assert "code" in props
        # `str | None` serializes as anyOf(string, null) under Pydantic v2.
        code_types = {
            variant.get("type") for variant in props["code"].get("anyOf", [])
        }
        assert "string" in code_types, "code must be a string-typed discriminator"
        # Optional: endpoint-level errors (slot occupied) carry no code.
        assert "code" not in schema.get("required", [])
        assert "idempotency_scope_mismatch" in self._responses(
            openapi, "/api/v1/patients/booking", "post"
        )["409"]["description"]
        assert "idempotency_uncertain_outcome" in self._responses(
            openapi, "/api/v1/patients/booking", "post"
        )["409"]["description"]

    def test_preview_publishes_typed_success_and_errors(self, openapi):
        preview = self._responses(openapi, "/api/v1/patients/booking/preview", "post")
        # Round-3 P2: `_require_patient`'s 404 is declared here too.
        # Round-7 (owner P2): the keyed surface is PUBLISHED — the middleware
        # processes every preview that carries an Idempotency-Key (the
        # operation-scoping tests below depend on it), so 409/503 are real
        # runtime outcomes, not undocumented surprises.
        assert set(preview) == {"200", "400", "401", "403", "404", "409", "422", "503"}
        assert (
            preview["404"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert (
            preview["200"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalBookingPreviewResponse"
        )
        assert (
            preview["409"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert (
            preview["503"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
        assert "idempotency_payload_mismatch" in preview["409"]["description"]
        assert "idempotency_uncertain_outcome" in preview["409"]["description"]
        assert "idempotency_unavailable" in preview["503"]["description"]

    def test_preview_publishes_optional_idempotency_key_header(self, openapi):
        """Round-7 (owner P2): the keyed preview contract is explicit —
        OPTIONAL header (a preview works without a key), bounded like the
        create endpoint (1..128 chars)."""
        operation = openapi["paths"]["/api/v1/patients/booking/preview"]["post"]
        header_params = [
            p
            for p in operation.get("parameters", [])
            if p.get("in") == "header" and p.get("name") == "Idempotency-Key"
        ]
        assert header_params, "Idempotency-Key header must be published on preview"
        assert header_params[0]["required"] is False
        # `str | None` serializes as anyOf(string, null) under Pydantic v2 —
        # the constraints live on the string variant.
        schema = header_params[0]["schema"]
        string_variant = next(
            (v for v in schema.get("anyOf", []) if v.get("type") == "string"),
            schema,
        )
        assert string_variant.get("maxLength") == 128
        assert string_variant.get("minLength") == 1

    def test_cabinet_publishes_typed_success_and_errors(self, openapi):
        cabinet = self._responses(openapi, "/api/v1/patients/cabinet/summary", "get")
        assert set(cabinet) == {"200", "401", "403", "404"}
        assert (
            cabinet["200"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalCabinetSummaryResponse"
        )

    def test_forms_publishes_typed_success_and_errors(self, openapi):
        forms = self._responses(openapi, "/api/v1/patients/forms", "get")
        # Round-3 P2: `_require_patient`'s 404 is declared here too.
        assert set(forms) == {"200", "400", "401", "403", "404"}
        assert (
            forms["404"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/PatientPortalErrorResponse"
        )
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


class TestReplayPatientPolicy:
    """Round-3 owner P1 + round-4 owner P1: the idempotency replay must
    never outrun the portal's card guards.

    - A snapshot committed under card A cannot be served for a soft-deleted
      card (the namespace bypasses replay entirely — the endpoint 403s +
      audits) — round-3.
    - One Idempotency-Key means ONE booking attempt: the key is bound to
      the card it FIRST ran under and never follows a re-link. The same key
      replayed after the account was re-linked to card B is a 409
      `idempotency_scope_mismatch` — NOT a fresh execution that would
      create a second appointment for another patient. The re-linked card
      books with a NEW key — round-4."""

    future_date = str(date.today() + timedelta(days=3))

    def test_replay_after_soft_delete_returns_403_not_cached_201(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        key = "replay-softdel-1"
        body = {"appointmentDate": self.future_date}
        first = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert first.status_code == 201

        # Card revoked AFTER the committed booking — the exact round-3 P1
        # sequence (successful request -> soft delete -> same key/body).
        test_patient.is_deleted = True
        db_session.commit()

        replay = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert replay.status_code == 403
        assert replay.json()["detail"]["reason"] == "patient_link_invalid"
        # The cached snapshot must not materialize anything either.
        assert (
            db_session.query(Appointment)
            .filter(Appointment.patient_id == test_patient.id)
            .count()
            == 1
        )

    def test_replay_after_card_relink_refused_with_scope_mismatch(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        """Round-4 owner P1: the round-3 namespace scoping alone made the
        same key look FRESH after a re-link (the namespace moved with the
        current card), so the retry re-executed the booking for the NEW
        card — two appointments for two patients from one logical submit.
        The stable key→card binding must refuse the retry instead."""
        user = (
            db_session.query(User).filter(User.username == "portal_patient").first()
        )
        assert user is not None
        key = "replay-relink-2"
        body = {"appointmentDate": self.future_date}
        first = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert first.status_code == 201
        first_appointment_id = first.json()["appointment_id"]

        # Re-link the SAME portal account to a DIFFERENT card after the
        # committed booking (lost response + admin relink — the dangerous
        # interleaving from the review).
        card_b = Patient(
            first_name="Пётр",
            last_name="Петров",
            middle_name="Петрович",
            phone="+998900000001",
            birth_date=date(1991, 2, 2),
            address="Адрес 2",
        )
        db_session.add(card_b)
        db_session.flush()
        test_patient.user_id = None
        card_b.user_id = user.id
        db_session.commit()

        # Same key + same body after the re-link: the key is still bound to
        # card A — non-executing 409, never a fresh booking for card B.
        replay = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert replay.status_code == 409, replay.text
        assert replay.json()["code"] == "idempotency_scope_mismatch"

        # Exactly ONE appointment exists, and it belongs to card A.
        assert db_session.query(Appointment).count() == 1
        row = db_session.get(Appointment, first_appointment_id)
        assert row is not None
        assert row.patient_id == test_patient.id

        # A NEW booking attempt for the re-linked card uses a NEW key —
        # and works exactly like a first booking.
        second = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "replay-relink-2-new-card"},
            json=body,
        )
        assert second.status_code == 201, second.text
        second_row = db_session.get(Appointment, second.json()["appointment_id"])
        assert second_row is not None
        assert second_row.patient_id == card_b.id


class TestKeyOperationScoping:
    """Round-3 owner P2: the idempotency identity is the OPERATION
    (method + path), not just (user, key, body) — one key cannot alias
    preview and create, which share the same request DTO."""

    future_date = str(date.today() + timedelta(days=3))

    def test_same_key_preview_then_create_executes_create(
        self, client, linked_patient_headers, db_session
    ):
        key = "shared-key-1"
        body = {"appointmentDate": self.future_date}
        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert preview.status_code == 200

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert created.status_code == 201, (
            "create must EXECUTE — a cached 200 preview must never satisfy the create"
        )
        assert created.json()["created"] is True
        assert db_session.query(Appointment).count() == 1

    def test_same_key_create_then_preview_returns_preview_shape(
        self, client, linked_patient_headers, db_session
    ):
        key = "shared-key-2"
        body = {"appointmentDate": self.future_date}
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert created.status_code == 201

        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert preview.status_code == 200
        payload = preview.json()
        assert "created" not in payload, (
            "preview must not replay the create snapshot"
        )
        assert "appointment" in payload
        # And the preview must not have double-booked either.
        assert db_session.query(Appointment).count() == 1


class TestCabinetPolicySSOT:
    """Round-3 owner P2: the JWT cabinet must return the SAME policy
    payload as the Mini App SSOT builder — no silent response-filter
    drops."""

    def test_cabinet_policy_payload_full_parity(
        self, client, linked_patient_headers
    ):
        response = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert response.status_code == 200
        policy = response.json()["policy"]
        assert policy == {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "pdf_included": False,
        }


class TestLegacyCreateNoClientDepartmentFK:
    """Round-3 owner P2: `department_id` is a portal-INTERNAL, server-
    resolved FK. The legacy `POST /appointments/` inherits the shared
    `AppointmentCreate` WITHOUT the field, so a client-supplied value is
    dropped — the pre-#3340 contract, no bypass of the portal's
    department validation."""

    def test_general_endpoint_ignores_client_department_id(
        self,
        client,
        admin_auth_headers,
        db_session,
        test_patient,
        test_doctor,
    ):
        body = {
            "patient_id": test_patient.id,
            "doctor_id": test_doctor.id,
            "appointment_date": str(date.today() + timedelta(days=4)),
            "appointment_time": "09:30",
            # Nonexistent FK: must be DROPPED by the schema, never persisted
            # (previously it went straight to the INSERT → IntegrityError/500
            # or an unvalidated routing context).
            "department_id": 999999,
        }
        response = client.post(
            "/api/v1/appointments/", headers=admin_auth_headers, json=body
        )
        assert response.status_code == 200, response.json()
        row = db_session.get(Appointment, response.json()["id"])
        assert row is not None
        assert row.department_id is None


class TestDeniedAuditRows:
    """Round-3 owner P2: portal refusals write `outcome="denied"` audit
    rows with the failure reason — post-revocation access attempts stay
    visible in the per-patient trail (SSOT parity with the Mini App)."""

    future_date = str(date.today() + timedelta(days=3))

    def _latest_denied(self, db_session, subject_patient_id):
        return (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == subject_patient_id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .first()
        )

    def test_soft_delete_denial_writes_audit_row(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        body = {"appointmentDate": self.future_date}
        first = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "audit-sd-1"},
            json=body,
        )
        assert first.status_code == 201
        test_patient.is_deleted = True
        db_session.commit()

        # Fresh key: the denial itself (not the replay policy) is under test.
        denied = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "audit-sd-2"},
            json=body,
        )
        assert denied.status_code == 403

        row = self._latest_denied(db_session, test_patient.id)
        assert row is not None, "the post-revocation attempt must leave a trail row"
        assert row.extra_data["reason"] == "patient_link_invalid"
        assert row.extra_data["surface"] == "jwt_portal"

    def test_unknown_department_denial_writes_audit_row(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        denied = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "audit-dep-1"},
            json={
                "appointmentDate": self.future_date,
                "department": "no-such-dep",
            },
        )
        assert denied.status_code == 400
        row = self._latest_denied(db_session, test_patient.id)
        assert row is not None
        assert row.extra_data["reason"] == "department_unknown"

    def test_occupied_slot_denial_writes_audit_row(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_patient,
        test_doctor,
        portal_department,
    ):
        # Round-9 (owner P1): a doctor booking requires the doctor's
        # canonical department — bind the harness doctor before booking.
        test_doctor.department_id = portal_department.id
        db_session.commit()

        body = {
            "appointmentDate": self.future_date,
            "appointmentTime": "10:00",
            "doctorId": test_doctor.id,
        }
        first = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "audit-slot-1"},
            json=body,
        )
        assert first.status_code == 201, first.json()

        second = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "audit-slot-2"},
            json=body,
        )
        assert second.status_code == 409
        row = self._latest_denied(db_session, test_patient.id)
        assert row is not None
        assert row.extra_data["reason"] == "appointment_time_slot_occupied"


class TestCanonicalReadAfterPortalBooking:
    """Round-4 owner P1: the ORM `department` attribute is the Department
    RELATIONSHIP while the read DTO declared `department: str | None` under
    the same name — the first row with a persisted department_id (which the
    portal booking now guarantees) turned every canonical Appointment read
    into a response-validation 500. The regression reads the portal-created
    row through BOTH canonical endpoints (registrar/admin surface)."""

    future_date = str(date.today() + timedelta(days=3))

    def test_list_and_detail_return_200_after_portal_booking(
        self,
        client,
        linked_patient_headers,
        admin_auth_headers,
        db_session,
        portal_department,
    ):
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "canonical-read-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        # GET /api/v1/appointments/ — one poisoned row used to 500 the WHOLE
        # list (the model_validate ran per row).
        listed = client.get("/api/v1/appointments/", headers=admin_auth_headers)
        assert listed.status_code == 200, listed.text
        items = [a for a in listed.json() if a["id"] == appointment_id]
        assert len(items) == 1, "the portal-created row must appear in the list"
        item = items[0]
        assert item["department_id"] == portal_department.id
        assert item["department"] == portal_department.key
        assert item["department_key"] == portal_department.key
        assert item["department_name"] == portal_department.name_ru

        # GET /api/v1/appointments/{id} — the same ORM object is validated
        # by response_model directly.
        detail = client.get(
            f"/api/v1/appointments/{appointment_id}", headers=admin_auth_headers
        )
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["department_id"] == portal_department.id
        assert payload["department"] == portal_department.key
        assert payload["department_key"] == portal_department.key
        assert payload["department_name"] == portal_department.name_ru

    def test_row_without_department_still_reads_null(
        self, client, admin_auth_headers, db_session, test_patient, test_doctor
    ):
        # Legacy rows (department_id NULL) must keep serializing department
        # as null — the mapper never invents a value.
        legacy_row = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today() + timedelta(days=5),
            appointment_time="11:00",
        )
        db_session.add(legacy_row)
        db_session.commit()
        db_session.refresh(legacy_row)

        detail = client.get(
            f"/api/v1/appointments/{legacy_row.id}", headers=admin_auth_headers
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["department"] is None
        assert detail.json()["department_key"] is None
        assert detail.json()["department_name"] is None


class TestDeactivatedUserAuditTrail:
    """Round-4 owner P2: the composed dependency refused a deactivated
    account BEFORE the endpoint body ran — the denied-audit writer never
    executed and the linked card's trail lost the attempt. The audited
    dependency resolves the actor, writes the row, THEN raises the 403."""

    def test_deactivated_cabinet_attempt_writes_denied_row(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        user = db_session.query(User).filter(User.username == "portal_patient").first()
        assert user is not None
        user.is_active = False
        db_session.commit()

        response = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"]["reason"] == "user_deactivated"

        row = (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .first()
        )
        assert row is not None, (
            "the deactivated attempt must leave a row in the per-patient trail"
        )
        assert row.extra_data["reason"] == "user_deactivated"
        assert row.extra_data["surface"] == "jwt_portal"
        assert row.resource_type == "cabinet_summary"

    def test_deactivated_forms_attempt_writes_denied_row(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        user = db_session.query(User).filter(User.username == "portal_patient").first()
        assert user is not None
        user.is_active = False
        db_session.commit()

        response = client.get("/api/v1/patients/forms", headers=linked_patient_headers)
        assert response.status_code == 403
        row = (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.extra_data["reason"] == "user_deactivated"
        assert row.resource_type == "patient_form"


class TestDepartmentNormalization:
    """Round-4 owner P2: the SSOT builder strips the draft department while
    the portal resolver queried the RAW request string — `" cardio "` passed
    the builder, then missed the exact `Department.key` match and answered
    400 for a department the preview had already accepted."""

    future_date = str(date.today() + timedelta(days=3))

    def test_padded_department_resolves_on_preview_and_create(
        self, client, linked_patient_headers, db_session, portal_department
    ):
        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={
                "appointmentDate": self.future_date,
                "department": f"  {portal_department.key}  ",
            },
        )
        assert preview.status_code == 200, preview.json()
        payload = preview.json()
        assert payload["appointment"]["department"] == portal_department.key
        assert payload["appointment"]["department_id"] == portal_department.id

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "normalize-1"},
            json={
                "appointmentDate": self.future_date,
                "department": f"  {portal_department.key}  ",
            },
        )
        assert created.status_code == 201, created.json()
        row = db_session.get(Appointment, created.json()["appointment_id"])
        assert row is not None
        assert row.department_id == portal_department.id

    def test_whitespace_only_department_stays_empty(self, client, linked_patient_headers):
        # "   " normalizes to None — no department context, no 400.
        response = client.post(
            "/api/v1/patients/booking/preview",
            headers=linked_patient_headers,
            json={"appointmentDate": self.future_date, "department": "   "},
        )
        assert response.status_code == 200
        assert response.json()["appointment"]["department"] is None


class TestCabinetDepartmentLabel:
    """Round-4 owner P2: `Department` has no `name` column (key/name_ru/
    name_uz) — the cabinet summary showed `department: null` for every
    booked row even after the portal started persisting department_id."""

    future_date = str(date.today() + timedelta(days=3))

    def test_cabinet_summary_shows_booked_department_name(
        self, client, linked_patient_headers, db_session, portal_department
    ):
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "cabinet-label-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        summary = client.get(
            "/api/v1/patients/cabinet/summary", headers=linked_patient_headers
        )
        assert summary.status_code == 200
        booked = [
            a
            for a in summary.json()["appointments"]
            if a["id"] == appointment_id
        ]
        assert len(booked) == 1
        assert booked[0]["department"] == portal_department.name_ru


class TestDeactivatedKeyedBookingAudit:
    """Round-5 owner P2: POST /patients/booking requires an Idempotency-Key,
    so a deactivated account's request is decided by the idempotency
    MIDDLEWARE before any endpoint dependency runs — the round-4 audited
    principal factory never executes on that path. The middleware must
    write the denied PHI-audit row itself (same contract: outcome=denied,
    reason=user_deactivated, surface=jwt_portal, the linked card as
    subject) and answer the non-executing 403."""

    def test_deactivated_keyed_booking_writes_denied_row(
        self, client, linked_patient_headers, db_session, test_patient
    ):
        user = db_session.query(User).filter(User.username == "portal_patient").first()
        assert user is not None
        user.is_active = False
        db_session.commit()

        future_date = str(date.today() + timedelta(days=3))
        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "deact-audit-1"},
            json={"appointmentDate": future_date},
        )
        assert response.status_code == 403
        assert db_session.query(Appointment).count() == 0

        row = (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .first()
        )
        assert row is not None, (
            "the keyed booking refusal must leave a row in the per-patient trail"
        )
        assert row.extra_data["reason"] == "user_deactivated"
        assert row.extra_data["surface"] == "jwt_portal"
        assert row.resource_type == "appointment"
        assert row.action == "create"


class TestCanonicalDepartmentFilter:
    """Round-5 owner P2: the declared `?department=` filter of the canonical
    appointment list compared the ORM RELATIONSHIP to the string parameter —
    ArgumentError, 500. The natural registrar query for a department with a
    portal-created booking must answer 200 with the right rows."""

    future_date = str(date.today() + timedelta(days=3))

    def test_department_filter_returns_200_after_portal_booking(
        self,
        client,
        linked_patient_headers,
        admin_auth_headers,
        db_session,
        portal_department,
    ):
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "canonical-filter-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        listed = client.get(
            f"/api/v1/appointments/?department={portal_department.key}",
            headers=admin_auth_headers,
        )
        assert listed.status_code == 200, listed.text
        items = [a for a in listed.json() if a["id"] == appointment_id]
        assert len(items) == 1, "the booked row must match its own department key"
        assert items[0]["department_key"] == portal_department.key

        # A different department's filter is 200 and never leaks the row.
        other = client.get(
            "/api/v1/appointments/?department=derma", headers=admin_auth_headers
        )
        assert other.status_code == 200, other.text
        assert all(a["id"] != appointment_id for a in other.json())


class TestRegistrarReadModelDepartmentContract:
    """Round-6 owner P1: /registrar/visits and /registrar/all-appointments
    still fed the ORM RELATIONSHIP into a `department: str | None` read DTO —
    the first portal-created row (non-NULL department_id) failed response
    validation (or produced a Department object in the dict), the broad
    `except Exception` swallowed it and the portal booking silently
    DISAPPEARED from the working registrar read-model (PatientPickupView
    reads /registrar/visits for patient history).

    The unified mapper (department_id / department_key / department_name /
    legacy department = canonical key) must give every Appointment read
    surface the SAME contract for one portal-created row."""

    future_date = str(date.today() + timedelta(days=3))

    def test_portal_booking_department_contract_across_all_read_surfaces(
        self,
        client,
        linked_patient_headers,
        admin_auth_headers,
        db_session,
        portal_department,
        test_patient,
    ):
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "registrar-contract-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        expected = {
            "department": portal_department.key,
            "department_id": portal_department.id,
            "department_key": portal_department.key,
            "department_name": portal_department.name_ru,
        }

        # 1. Canonical list — GET /api/v1/appointments/
        listed = client.get("/api/v1/appointments/", headers=admin_auth_headers)
        assert listed.status_code == 200, listed.text
        item = next(a for a in listed.json() if a["id"] == appointment_id)
        for field, value in expected.items():
            assert item[field] == value, f"canonical list.{field}"

        # 2. Canonical detail — GET /api/v1/appointments/{id}
        detail = client.get(
            f"/api/v1/appointments/{appointment_id}", headers=admin_auth_headers
        )
        assert detail.status_code == 200, detail.text
        for field, value in expected.items():
            assert detail.json()[field] == value, f"canonical detail.{field}"

        # 3. Working registrar read-model — GET /api/v1/registrar/visits
        #    (the appointments block used to be silently dropped for rows
        #    with a persisted department_id).
        visits = client.get(
            f"/api/v1/registrar/visits?patient_id={test_patient.id}&limit=500",
            headers=admin_auth_headers,
        )
        assert visits.status_code == 200, visits.text
        # Legacy appointments are exposed under the +10000 id offset.
        appointment_row = next(
            (
                r
                for r in visits.json()
                if r["id"] == appointment_id + 10000 and r["patient_id"] == test_patient.id
            ),
            None,
        )
        assert appointment_row is not None, (
            "the portal-created booking must appear in /registrar/visits — "
            "a Department object in the response DTO used to make the broad "
            "except drop the whole appointments block"
        )
        for field, value in expected.items():
            assert appointment_row[field] == value, f"registrar/visits.{field}"

        # 4. Merged listing — GET /api/v1/registrar/all-appointments
        merged = client.get(
            "/api/v1/registrar/all-appointments?limit=1000", headers=admin_auth_headers
        )
        assert merged.status_code == 200, merged.text
        merged_row = next(
            (
                r
                for r in merged.json()["data"]
                if r.get("appointment_id") == appointment_id
            ),
            None,
        )
        assert merged_row is not None, "the booking must appear in all-appointments"
        for field, value in expected.items():
            assert merged_row[field] == value, f"all-appointments.{field}"

    def test_department_filter_on_registrar_visits_matches_portal_row(
        self,
        client,
        linked_patient_headers,
        admin_auth_headers,
        db_session,
        portal_department,
        test_patient,
    ):
        """The ?department= filter of /registrar/visits compared the ORM
        RELATIONSHIP to the string parameter (ArgumentError → the broad
        except dropped the appointments block). Same repair as the canonical
        list: filter through the relationship predicate."""
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "registrar-filter-1"},
            json={
                "appointmentDate": self.future_date,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        filtered = client.get(
            f"/api/v1/registrar/visits?department={portal_department.key}&limit=500",
            headers=admin_auth_headers,
        )
        assert filtered.status_code == 200, filtered.text
        rows = [r for r in filtered.json() if r["id"] == appointment_id + 10000]
        assert len(rows) == 1, "the booked row must match its own department key"
        assert rows[0]["department_key"] == portal_department.key

        other = client.get(
            "/api/v1/registrar/visits?department=derma&limit=500",
            headers=admin_auth_headers,
        )
        assert other.status_code == 200, other.text
        assert all(
            r["id"] != appointment_id + 10000 for r in other.json()
        ), "a foreign department's filter must not leak the row"


class TestDoctorDepartmentRouting:
    """Round-9 owner P1 (PR #3340): a doctor-booking's routing department is
    the doctor's CANONICAL department — never the independently submitted
    string. Preview and create agree on the routing context; a foreign
    submitted department is a controlled 400; a departmentless doctor is an
    explicit refusal instead of a persisted NULL."""

    future_date = str(date.today() + timedelta(days=3))

    def _bind_doctor(self, db_session: Session, test_doctor, portal_department):
        test_doctor.department_id = portal_department.id
        db_session.commit()
        db_session.refresh(test_doctor)

    def test_create_persists_doctor_canonical_department(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
    ):
        self._bind_doctor(db_session, test_doctor, portal_department)
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "route-1"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
            },
        )
        assert created.status_code == 201, created.json()
        row = db_session.get(Appointment, created.json()["appointment_id"])
        assert row is not None
        # Pre-round-9 this row was created with department_id = NULL.
        assert row.department_id == portal_department.id

    def test_preview_and_create_agree_on_routing_context(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
    ):
        self._bind_doctor(db_session, test_doctor, portal_department)
        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": "route-pv-1"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
            },
        )
        assert preview.status_code == 200, preview.json()
        assert preview.json()["appointment"]["department_id"] == portal_department.id, (
            "the preview echoes the doctor's canonical routing context"
        )

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "route-cr-1"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
            },
        )
        assert created.status_code == 201, created.json()
        row = db_session.get(Appointment, created.json()["appointment_id"])
        assert row.department_id == portal_department.id

    def test_foreign_submitted_department_rejected_400(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
    ):
        self._bind_doctor(db_session, test_doctor, portal_department)
        other = Department(
            key="dentistry",
            name_ru="Стоматология",
            name_uz="Stomatologiya",
            active=True,
        )
        db_session.add(other)
        db_session.commit()

        body = {
            "appointmentDate": self.future_date,
            "doctorId": test_doctor.id,
            "department": other.key,
        }
        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": "route-pv-2"},
            json=body,
        )
        assert preview.status_code == 400, preview.json()
        assert preview.json()["detail"]["reason"] == "doctor_department_mismatch"

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "route-cr-2"},
            json=body,
        )
        assert created.status_code == 400, created.json()
        assert created.json()["detail"]["reason"] == "doctor_department_mismatch"
        assert db_session.query(Appointment).count() == 0, (
            "a routing contradiction never materializes an appointment"
        )

    def test_departmentless_doctor_explicitly_refused(
        self, client, linked_patient_headers, db_session, test_doctor
    ):
        # The harness doctor has NO canonical department: an explicit 400,
        # never a silent NULL routing context (create + preview).
        body = {"appointmentDate": self.future_date, "doctorId": test_doctor.id}
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "route-cr-3"},
            json=body,
        )
        assert created.status_code == 400, created.json()
        assert created.json()["detail"]["reason"] == "doctor_department_missing"

        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": "route-pv-3"},
            json=body,
        )
        assert preview.status_code == 400, preview.json()
        assert preview.json()["detail"]["reason"] == "doctor_department_missing"
        assert db_session.query(Appointment).count() == 0

    def test_matching_submitted_department_still_books(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
    ):
        # The doctor's own department submitted explicitly: accepted, and
        # the persisted FK is the same canonical department.
        self._bind_doctor(db_session, test_doctor, portal_department)
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "route-cr-4"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        row = db_session.get(Appointment, created.json()["appointment_id"])
        assert row.department_id == portal_department.id


class TestClinicCalendarDateValidation:
    """Round-9 owner P2 (PR #3340): the booking past-day check follows the
    CLINIC's calendar (`clinic_today`, Asia/Tashkent queue-settings SSOT),
    not the UTC host's `date.today()` — on a UTC host between 00:00 and
    04:59 Tashkent time the old validation accepted the previous clinic
    day and let patients create already-past appointments."""

    def _shift_clinic_today(self, monkeypatch):
        import app.api.v1.endpoints.patient_portal as portal_module

        monkeypatch.setattr(
            portal_module,
            "clinic_today",
            lambda db: date.today() + timedelta(days=1),
        )

    def test_previous_clinic_day_refused_on_both_surfaces(
        self, client, linked_patient_headers, db_session, monkeypatch
    ):
        self._shift_clinic_today(monkeypatch)
        # host-today is already YESTERDAY for the clinic (the UTC-host
        # window the finding describes).
        body = {"appointmentDate": str(date.today())}

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "cal-cr-1"},
            json=body,
        )
        assert created.status_code == 400, created.json()
        assert created.json()["detail"]["reason"] == "appointment_date_in_past"

        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": "cal-pv-1"},
            json=body,
        )
        assert preview.status_code == 400, preview.json()
        assert preview.json()["detail"]["reason"] == "appointment_date_in_past"

        assert db_session.query(Appointment).count() == 0, (
            "an already-past (by the clinic calendar) day never books"
        )

    def test_clinic_today_is_still_accepted(
        self,
        client,
        linked_patient_headers,
        db_session,
        portal_department,
        monkeypatch,
    ):
        self._shift_clinic_today(monkeypatch)
        # host-tomorrow == clinic-TODAY: valid on the clinic calendar.
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "cal-cr-2"},
            json={
                "appointmentDate": str(date.today() + timedelta(days=1)),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()


class TestPortalBookingRound12:
    """Round-12 (PR #3386 review): atomic routing + contract ordering on the
    JWT portal surface. The FINAL department row is re-validated under FOR
    UPDATE next to the INSERT (an admin deactivate/delete racing the
    booking cannot persist a routing context pointing at a non-active
    department). Rebased onto #3402: the portal keeps the owner-reviewed
    up-front submitted-key resolution (a request-shaped routing 400
    outranks the doctor_not_eligible 409); the Mini App surface keeps its
    eligibility-first ordering — an intentional, flagged divergence."""

    future_date = str(date.today() + timedelta(days=3))

    def test_create_revalidates_department_under_lock(
        self,
        client: TestClient,
        linked_patient_headers,
        db_session: Session,
        test_patient,
        test_doctor,
        portal_department,
        monkeypatch,
    ):
        # P1: the create path calls the lock_department_for_booking
        # re-validation and answers the SAME department_inactive contract
        # instead of persisting a stale routing context. NOTE: this
        # sqlite harness runs the "admin" mutation on the SAME session —
        # commit() expires the identity map, so this pin proves the
        # WIRING, not the two-session race. The real cross-transaction
        # identity-map proof (stale active=True surviving FOR UPDATE
        # without populate_existing) lives in
        # tests/integration/test_booking_department_lock_pg.py.
        import app.api.v1.endpoints.patient_portal as portal_module

        test_doctor.department_id = portal_department.id
        db_session.commit()
        db_session.refresh(test_doctor)

        real_routing = portal_module._resolve_doctor_routing_department

        def racing_admin_deactivation(doctor_row, submitted_row):
            resolved = real_routing(doctor_row, submitted_row)
            portal_department.active = False
            db_session.commit()
            return resolved

        monkeypatch.setattr(
            portal_module,
            "_resolve_doctor_routing_department",
            racing_admin_deactivation,
        )

        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "r12-lock-1"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
                "department": portal_department.key,
            },
        )
        assert response.status_code == 400, response.json()
        assert response.json()["detail"]["reason"] == "department_inactive"
        assert db_session.query(Appointment).count() == 0, (
            "a raced deactivation never materializes an appointment with a "
            "stale routing context"
        )

    def test_create_submitted_key_resolve_precedes_eligibility(
        self,
        client: TestClient,
        linked_patient_headers,
        db_session: Session,
        test_patient,
        test_doctor,
    ):
        # Merge-parity note (PR #3386 rebased onto #3402): the portal keeps
        # the owner-reviewed #3402 order — the submitted department key is
        # resolved UP FRONT ("P1 (round 2): resolve BEFORE any mutation"),
        # so a request that is both ineligible-doctor AND bad-department
        # answers the request-shaped 400 department_unknown. The Mini App
        # surface keeps its eligibility-first ordering (intentional
        # divergence between the two surfaces, flagged for review).
        # Either way nothing persists.
        test_doctor.active = False
        db_session.commit()

        response = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "r12-order-1"},
            json={
                "appointmentDate": self.future_date,
                "doctorId": test_doctor.id,
                "department": "nonexistent-department",
            },
        )
        assert response.status_code == 400, response.json()
        assert response.json()["detail"]["reason"] == "department_unknown"
        assert db_session.query(Appointment).count() == 0

    def test_lock_department_for_booking_semantics(
        self, db_session: Session, portal_department, monkeypatch
    ):
        # Unit contract of the atomic re-validation helper itself: an active
        # row passes through, a deactivated row is a controlled 400, a
        # deleted row is department_unknown (never an IntegrityError/500),
        # None passes through (departmentless booking).
        from fastapi import HTTPException

        from app.services.appointment_booking_routing import lock_department_for_booking

        assert lock_department_for_booking(db_session, None) is None

        locked = lock_department_for_booking(db_session, portal_department)
        assert int(locked.id) == int(portal_department.id)

        portal_department.active = False
        db_session.commit()
        with pytest.raises(HTTPException) as inactive_exc:
            lock_department_for_booking(db_session, portal_department)
        assert inactive_exc.value.detail == {"reason": "department_inactive"}

        db_session.delete(portal_department)
        db_session.commit()
        with pytest.raises(HTTPException) as deleted_exc:
            lock_department_for_booking(db_session, portal_department)
        assert deleted_exc.value.detail == {"reason": "department_unknown"}


class TestInactiveCanonicalDepartmentRouting:
    """Round-10 owner P1 (PR #3340): `_resolve_doctor_routing_department`
    returned the doctor's canonical department WITHOUT an `active` check —
    an active Doctor (active User) bound to a DEACTIVATED department still
    booked, and the preview even echoed the inactive department_id the
    create then persisted. The canonical path must refuse with the SAME
    published 400 `department_inactive` reason every other department path
    uses, BEFORE any mutation, on BOTH booking surfaces."""

    future_date = str(date.today() + timedelta(days=3))

    def test_inactive_canonical_department_refused_on_both_surfaces(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
        test_patient,
    ):
        # Active doctor, active user, canonical department DEACTIVATED.
        test_doctor.department_id = portal_department.id
        portal_department.active = False
        db_session.commit()
        db_session.refresh(test_doctor)
        db_session.refresh(portal_department)

        body = {"appointmentDate": self.future_date, "doctorId": test_doctor.id}

        preview = client.post(
            "/api/v1/patients/booking/preview",
            headers={**linked_patient_headers, "Idempotency-Key": "inactive-pv-1"},
            json=body,
        )
        assert preview.status_code == 400, preview.json()
        assert preview.json()["detail"]["reason"] == "department_inactive"

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "inactive-cr-1"},
            json=body,
        )
        assert created.status_code == 400, created.json()
        assert created.json()["detail"]["reason"] == "department_inactive"
        assert db_session.query(Appointment).count() == 0, (
            "a booking routed to an inactive canonical department never "
            "materializes an appointment"
        )

        # The refusals leave the portal's denied audit trail (SSOT parity
        # with every other booking refusal).
        denied = (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .all()
        )
        reasons = [
            (row.extra_data or {}).get("reason")
            for row in denied
            if (row.extra_data or {}).get("reason") == "department_inactive"
        ]
        assert len(reasons) >= 2, (
            "both the preview and the create refusal are audited"
        )

    def test_reactivated_canonical_department_books_again(
        self,
        client,
        linked_patient_headers,
        db_session,
        test_doctor,
        portal_department,
    ):
        # Control: the SAME doctor + department books the moment the
        # canonical department is ACTIVE — the refusal above is caused by
        # the inactivity, not by the routing resolution itself.
        test_doctor.department_id = portal_department.id
        portal_department.active = False
        db_session.commit()

        body = {"appointmentDate": self.future_date, "doctorId": test_doctor.id}
        refused = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "react-cr-a"},
            json=body,
        )
        assert refused.status_code == 400, refused.json()

        portal_department.active = True
        db_session.commit()

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "react-cr-b"},
            json=body,
        )
        assert created.status_code == 201, created.json()
        row = db_session.get(Appointment, created.json()["appointment_id"])
        assert row is not None and row.department_id == portal_department.id


class TestReplayAuditTrail:
    """Round-10 owner P2 (PR #3340): a patient-scope REPLAY never ran the
    endpoint, so the endpoint's audited dependency never executed and the
    per-patient PHI trail lost the attempt. The middleware now writes its
    OWN `patient_access_audit` row (surface=jwt_portal, replayed=true,
    outcome=success) before serving the stored snapshot — local and
    distributed sources alike. Contract for two HTTP requests of one
    logical booking: handler executed ONCE (exactly one Appointment), the
    trail carries TWO success rows (the original execution's endpoint row
    + the replay's middleware row)."""

    future_date = str(date.today() + timedelta(days=3))

    def _booking_body(self, portal_department):
        return {
            "appointmentDate": self.future_date,
            "department": portal_department.key,
        }

    def _success_create_rows(self, db_session, test_patient):
        return (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.resource_type == "appointment",
                PatientAccessAuditLog.action == "create",
                PatientAccessAuditLog.outcome == "success",
            )
            .all()
        )

    def test_local_replay_writes_own_audit_row(
        self,
        client,
        linked_patient_headers,
        db_session,
        portal_department,
        test_patient,
    ):
        body = self._booking_body(portal_department)
        key = "replay-audit-local-1"
        headers = {**linked_patient_headers, "Idempotency-Key": key}

        first = client.post("/api/v1/patients/booking", headers=headers, json=body)
        assert first.status_code == 201, first.json()

        rows_after_first = self._success_create_rows(db_session, test_patient)
        assert len(rows_after_first) == 1, "the execution attempt is audited"
        assert all(
            not (row.extra_data or {}).get("replayed") for row in rows_after_first
        ), "the original execution is NOT marked as a replay"

        # Same worker (same TestClient/process): the LOCAL snapshot answers.
        replay = client.post("/api/v1/patients/booking", headers=headers, json=body)
        assert replay.status_code == 201, replay.json()
        assert replay.json() == first.json(), "the committed response is replayed"

        assert db_session.query(Appointment).count() == 1, (
            "the replay never re-executes the handler"
        )

        rows_after_replay = self._success_create_rows(db_session, test_patient)
        assert len(rows_after_replay) == 2, (
            "two HTTP attempts = two audited rows (execution + replay)"
        )
        replay_rows = [
            row for row in rows_after_replay if (row.extra_data or {}).get("replayed")
        ]
        assert len(replay_rows) == 1, "exactly the replay attempt is marked"
        assert replay_rows[0].extra_data.get("surface") == "jwt_portal"
        assert replay_rows[0].resource_type == "appointment"
        assert replay_rows[0].action == "create"
        assert replay_rows[0].subject_patient_id == test_patient.id

    def test_preview_replay_writes_preview_audit_row(
        self,
        client,
        linked_patient_headers,
        db_session,
        portal_department,
        test_patient,
    ):
        body = self._booking_body(portal_department)
        key = "replay-audit-preview-1"
        headers = {**linked_patient_headers, "Idempotency-Key": key}

        first = client.post("/api/v1/patients/booking/preview", headers=headers, json=body)
        assert first.status_code == 200, first.json()
        replay = client.post("/api/v1/patients/booking/preview", headers=headers, json=body)
        assert replay.status_code == 200, replay.json()
        assert replay.json() == first.json()

        replay_rows = (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == test_patient.id,
                PatientAccessAuditLog.outcome == "success",
            )
            .all()
        )
        marked = [
            row
            for row in replay_rows
            if (row.extra_data or {}).get("replayed")
            and row.action == "preview"
            and row.resource_type == "appointment"
        ]
        assert len(marked) == 1, (
            "the keyed preview replay is audited under its own action"
        )


class TestAnalyticsDepartmentContractE2E:
    """Round-10 owner P2 (PR #3340): the appointment analytics surfaces kept
    comparing the ORM RELATIONSHIP to the request string
    (`Appointment.department == department`) and fed Department OBJECTS
    into string fields — the E2E chain "portal booking department=cardio →
    appointment-flow?department=cardio → advanced analytics (department=
    cardio) → admin stats" must return the STRING canonical department
    contract everywhere, with no ORM object and no 500.

    The shared SSOT (`department_ids_for_filter`) resolves the key ONCE and
    every surface filters on `Appointment.department_id`; labels come from
    the `department_key` accessor. An unknown key answers an EMPTY result
    (exact-key semantics, the round-9 schedule-readers contract)."""

    future_date = str(date.today() + timedelta(days=3))

    def _book(self, client, linked_patient_headers, portal_department, doctor, key):
        body = {
            "appointmentDate": self.future_date,
            "department": portal_department.key,
        }
        if doctor is not None:
            body["doctorId"] = doctor.id
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": key},
            json=body,
        )
        assert created.status_code == 201, created.json()
        return created.json()["appointment_id"]

    def test_portal_booking_flows_through_analytics_surfaces(
        self,
        client,
        linked_patient_headers,
        admin_auth_headers,
        db_session,
        portal_department,
        test_doctor,
    ):
        test_doctor.department_id = portal_department.id
        db_session.commit()
        appointment_id = self._book(
            client, linked_patient_headers, portal_department, test_doctor, "analytics-e2e-1"
        )

        # 1. appointment-flow analytics — the flagged relationship-vs-string
        #    filter answered ArgumentError (500) on the first keyed query;
        #    the grouping fell into Department's numeric id fallback.
        flow = client.get(
            "/api/v1/analytics/appointment-flow",
            headers=admin_auth_headers,
            params={
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=7)),
                "department": portal_department.key,
            },
        )
        assert flow.status_code == 200, flow.text
        flow_payload = flow.json()
        assert flow_payload["summary"]["total_appointments"] >= 1
        assert portal_department.key in flow_payload.get(
            "department_performance", {}
        ), "the department breakdown is keyed by the canonical KEY string"
        assert str(portal_department.id) not in flow_payload.get(
            "department_performance", {}
        ), "no surrogate-PK grouping keys leak into the contract"

        # 2. advanced analytics (doctor performance — the reachable flagged
        #    AdvancedAnalyticsService surface) — same key, same FK filter.
        perf = client.get(
            "/api/v1/analytics/advanced/doctors/performance",
            headers=admin_auth_headers,
            params={
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=7)),
                "department": portal_department.key,
            },
        )
        assert perf.status_code == 200, perf.text
        perf_payload = perf.json()
        assert "error" not in perf_payload, perf_payload.get("error")
        assert any(
            entry.get("total_appointments", 0) >= 1
            for entry in perf_payload.get("doctor_performance", [])
        ), "the portal booking is attributed under the FK filter"

        # 3. admin stats overview — the flagged topDoctors serialization fed
        #    a Department OBJECT into the JSON payload (500 for every doctor
        #    whose first appointment carried a non-NULL department_id).
        overview = client.get(
            "/api/v1/admin/analytics/overview",
            headers=admin_auth_headers,
            params={
                "period": "month",
                "department": portal_department.key,
            },
        )
        assert overview.status_code == 200, overview.text
        overview_payload = overview.json()
        top = overview_payload.get("topDoctors", [])
        assert top, "the booked doctor appears in the filtered overview"
        assert all(
            isinstance(entry.get("department"), str) for entry in top
        ), "the topDoctors department contract is a STRING (canonical key)"
        assert any(
            entry["department"] == portal_department.key for entry in top
        ), "the canonical key string, not the ORM object, is published"

        # 4. Exact-key control: an UNKNOWN key answers an EMPTY analytics
        #    result (never the unfiltered payload, never a 500).
        unknown = client.get(
            "/api/v1/analytics/appointment-flow",
            headers=admin_auth_headers,
            params={
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=7)),
                "department": "definitely-not-a-department-key",
            },
        )
        assert unknown.status_code == 200, unknown.text
        assert unknown.json()["summary"]["total_appointments"] == 0

        # 5. The unfiltered surface keeps its "all departments" behavior.
        unfiltered = client.get(
            "/api/v1/analytics/appointment-flow",
            headers=admin_auth_headers,
            params={
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=7)),
            },
        )
        assert unfiltered.status_code == 200, unfiltered.text
        assert unfiltered.json()["summary"]["total_appointments"] >= 1

    def test_advanced_service_filters_by_department_fk(
        self,
        client,
        linked_patient_headers,
        db_session,
        portal_department,
        test_doctor,
    ):
        """Service-level pin for the AdvancedAnalyticsService sites the E2E
        cannot reach through HTTP (get_kpi_metrics / get_revenue_analytics
        have no endpoint): the flagged `filters.append(...)` lines resolve
        through the SAME SSOT — a known key filters by the FK, an unknown
        key matches NOTHING (get_doctor_performance is the one service that
        still composes end-to-end, so it carries the assertion)."""
        from datetime import datetime

        from app.services.advanced_analytics import AdvancedAnalyticsService

        test_doctor.department_id = portal_department.id
        db_session.commit()
        self._book(client, linked_patient_headers, portal_department, test_doctor, "analytics-svc-1")

        start = datetime.combine(date.today(), datetime.min.time())
        end = datetime.combine(date.today() + timedelta(days=7), datetime.min.time())

        known = AdvancedAnalyticsService.get_doctor_performance(
            db_session, start, end, department=portal_department.key
        )
        assert "error" not in known, known.get("error")
        assert any(
            entry.get("total_appointments", 0) >= 1
            for entry in known.get("doctor_performance", [])
        )

        unknown = AdvancedAnalyticsService.get_doctor_performance(
            db_session, start, end, department="definitely-not-a-key"
        )
        assert "error" not in unknown, unknown.get("error")
        assert unknown.get("doctor_performance") == [], (
            "an unknown key answers an EMPTY result (exact-key semantics)"
        )
