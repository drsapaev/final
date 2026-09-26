"""Item 9 of the dermatologist panel audit: POST /api/v1/ai/v2/analyze-skin-file.

Behavioral contract:
- {visit_id, file_id} only; the server loads the saved image bytes itself.
- Access mirrors GET /files/{file_id}: derma — own visit only; ownership/share
  check for everyone; other doctors' private photos stay inaccessible.
- ANALYZE_IMAGE permission required; feature flag ai_complaint_analysis
  gates the endpoint with 503.
- Response is the canonical AIResponse with the mandatory safety root fields
  (requires_doctor_confirmation=True, decision_boundary="suggestion_only",
  ai_notice); the result is a suggestion and is never written to the EMR.
"""

from __future__ import annotations

import base64
import secrets
from datetime import date
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.feature_flags import FeatureFlag
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.ai.ai_interfaces import AIResponse, AITaskType

ENDPOINT = "/api/v1/ai/v2/analyze-skin-file"
FLAG_KEY = "ai_complaint_analysis"


class _RecordingGateway:
    def __init__(self, *, status: str = "success") -> None:
        self.calls: list[dict[str, Any]] = []
        self._status = status

    async def execute(
        self,
        task_type: AITaskType,
        payload: dict[str, Any],
        user_id: int,
        specialty: str | None = None,
    ) -> AIResponse:
        self.calls.append(
            {
                "task_type": task_type,
                "payload": payload,
                "user_id": user_id,
                "specialty": specialty,
            }
        )
        return AIResponse(
            status=self._status,
            data={"content": "SYNTHETIC suggestion"},
            provider="mock",
            model="mock",
            latency_ms=1,
            ai_notice="AI suggestions are advisory only",
            requires_doctor_confirmation=True,
            decision_boundary="suggestion_only",
        )


@pytest.fixture()
def gateway(monkeypatch):
    gateway = _RecordingGateway()
    monkeypatch.setattr(
        "app.api.v1.endpoints.ai_gateway.get_ai_gateway",
        lambda: gateway,
    )
    return gateway


@pytest.fixture(autouse=True)
def clean_flag(db_session):
    yield
    db_session.query(FeatureFlag).filter(FeatureFlag.key == FLAG_KEY).delete()
    db_session.commit()


def _set_flag(db: Session, *, enabled: bool | None) -> None:
    db.query(FeatureFlag).filter(FeatureFlag.key == FLAG_KEY).delete()
    if enabled is not None:
        db.add(FeatureFlag(key=FLAG_KEY, name="AI Complaint Analysis", enabled=enabled))
    db.commit()


def _create_actor(db_session, client, patient, *, role, suffix):
    password = secrets.token_urlsafe(24)
    user = User(
        username=f"skin_file_{suffix}",
        email=f"skin_file_{suffix}@example.test",
        full_name="Test Skin File Doctor",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialty="dermatology" if role == "derma" else "general",
        active=True,
        cabinet="405",
    )
    db_session.add(doctor)
    db_session.flush()

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="in_progress",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(doctor)
    db_session.refresh(visit)

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": password},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    return user, doctor, visit, headers


def _upload_photo(client, *, headers, patient_id, visit_id, content=b"\xff\xd8\xffsynthetic dermatology photo"):
    return client.post(
        "/api/v1/files/upload",
        files={
            "file": (
                "dermatology-photo.jpg",
                BytesIO(content),
                "image/jpeg",
            )
        },
        data={
            "file_type": "image",
            "permission": "private",
            "patient_id": str(patient_id),
            "visit_id": str(visit_id),
        },
        headers=headers,
    )


class TestAnalyzeSkinFile:
    def test_derma_analyzes_saved_photo_on_owned_visit(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        _, _, visit, headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )
        upload_response = _upload_photo(
            client, headers=headers, patient_id=test_patient.id, visit_id=visit.id
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        response = client.post(
            ENDPOINT,
            json={"visit_id": visit.id, "file_id": file_id},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()

        # Mandatory safety envelope at the response root.
        assert body["requires_doctor_confirmation"] is True
        assert body["decision_boundary"] == "suggestion_only"
        assert body["ai_notice"]
        assert body["status"] == "success"
        assert body["data"]["content"] == "SYNTHETIC suggestion"

        # Server loaded the saved bytes and passed them to the existing
        # gateway — the client never sent image content.
        assert len(gateway.calls) == 1
        call = gateway.calls[0]
        assert call["task_type"] == AITaskType.SKIN_ANALYSIS
        assert call["specialty"] == "dermatology"
        decoded = base64.b64decode(call["payload"]["image_data"])
        assert decoded.startswith(b"\xff\xd8\xff")

    def test_derma_cannot_analyze_other_doctors_visit_photo(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        other_patient = Patient(
            first_name="Test",
            last_name="Other",
            birth_date=date(1990, 1, 1),
            phone="+998901234567",
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        _, _, other_visit, other_headers = _create_actor(
            db_session, client, other_patient, role="derma", suffix=secrets.token_hex(8)
        )
        upload_response = _upload_photo(
            client,
            headers=other_headers,
            patient_id=other_patient.id,
            visit_id=other_visit.id,
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        _, _, own_visit, own_headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )
        response = client.post(
            ENDPOINT,
            json={"visit_id": other_visit.id, "file_id": file_id},
            headers=own_headers,
        )
        assert response.status_code == 404
        assert gateway.calls == []

    def test_visit_binding_mismatch_is_rejected(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        _, _, visit, headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )

        second_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=visit.doctor_id,
            visit_date=date.today(),
            status="in_progress",
        )
        db_session.add(second_visit)
        db_session.commit()
        db_session.refresh(second_visit)
        other_visit_by_same_doctor = second_visit

        upload_response = _upload_photo(
            client, headers=headers, patient_id=test_patient.id, visit_id=visit.id
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        # Файл принадлежит visit.id, но запрос ссылается на другой визит того
        # же врача — fail-closed 404.
        response = client.post(
            ENDPOINT,
            json={"visit_id": other_visit_by_same_doctor.id, "file_id": file_id},
            headers=headers,
        )
        assert response.status_code == 404
        assert gateway.calls == []

    def test_non_image_file_is_rejected(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        _, _, visit, headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )
        upload_response = client.post(
            "/api/v1/files/upload",
            files={
                "file": (
                    "report.pdf",
                    BytesIO(b"%PDF-1.4 synthetic report"),
                    "application/pdf",
                )
            },
            data={
                "file_type": "document",
                "permission": "private",
                "patient_id": str(test_patient.id),
                "visit_id": str(visit.id),
            },
            headers=headers,
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        response = client.post(
            ENDPOINT,
            json={"visit_id": visit.id, "file_id": file_id},
            headers=headers,
        )
        assert response.status_code == 400
        assert gateway.calls == []

    def test_missing_file_returns_404(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        _, _, visit, headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )
        response = client.post(
            ENDPOINT,
            json={"visit_id": visit.id, "file_id": 987654321},
            headers=headers,
        )
        assert response.status_code == 404
        assert gateway.calls == []

    def test_role_without_analyze_image_permission_is_forbidden(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        registrar_user = User(
            username=f"skin_file_reg_{secrets.token_hex(4)}",
            email=f"skin_file_reg_{secrets.token_hex(4)}@example.test",
            full_name="Test Registrar",
            hashed_password=get_password_hash("registrar-password"),
            role="registrar",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(registrar_user)
        db_session.commit()

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": registrar_user.username, "password": "registrar-password"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.post(
            ENDPOINT,
            json={"visit_id": 1, "file_id": 1},
            headers=headers,
        )
        assert response.status_code == 403
        assert gateway.calls == []

    def test_feature_flag_disabled_returns_503(
        self, client: TestClient, db_session: Session, test_patient, gateway
    ):
        _set_flag(db_session, enabled=False)
        response = client.post(
            ENDPOINT,
            json={"visit_id": 1, "file_id": 1},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code == 503
        assert gateway.calls == []

    def test_error_gateway_response_keeps_safety_envelope(
        self, client: TestClient, db_session: Session, test_patient, monkeypatch
    ):
        failing = _RecordingGateway(status="error")
        monkeypatch.setattr(
            "app.api.v1.endpoints.ai_gateway.get_ai_gateway",
            lambda: failing,
        )
        _, _, visit, headers = _create_actor(
            db_session, client, test_patient, role="derma", suffix=secrets.token_hex(8)
        )
        upload_response = _upload_photo(
            client, headers=headers, patient_id=test_patient.id, visit_id=visit.id
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        response = client.post(
            ENDPOINT,
            json={"visit_id": visit.id, "file_id": file_id},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["requires_doctor_confirmation"] is True
        assert body["decision_boundary"] == "suggestion_only"
        assert body["ai_notice"]
