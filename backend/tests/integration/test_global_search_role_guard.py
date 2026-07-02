from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.patient import Patient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_registrar_can_search_patient_directory(
    client: TestClient,
    db_session: Session,
    registrar_token: str,
) -> None:
    patient = Patient(
        first_name="Searchable",
        last_name="Patient",
        phone="+998901110000",
        birth_date=date(1991, 2, 3),
    )
    db_session.add(patient)
    db_session.commit()

    response = client.get(
        "/api/v1/global-search",
        headers=_auth_headers(registrar_token),
        params={"q": "Searchable", "limit": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] >= 1
    assert any(result["id"] == patient.id for result in payload["patients"])


def test_patient_cannot_search_global_patient_directory(
    client: TestClient,
    patient_token: str,
) -> None:
    response = client.get(
        "/api/v1/global-search",
        headers=_auth_headers(patient_token),
        params={"q": "Patient", "limit": 5},
    )

    assert response.status_code == 403


def test_patient_cannot_log_global_search_clicks(
    client: TestClient,
    patient_token: str,
) -> None:
    response = client.post(
        "/api/v1/global-search/log-click",
        headers=_auth_headers(patient_token),
        json={"opened_type": "patient", "opened_id": 1, "query": "Patient"},
    )

    assert response.status_code == 403
