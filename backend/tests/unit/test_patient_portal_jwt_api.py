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
