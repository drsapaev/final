from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.patient import Patient


def test_patient_soft_delete_hides_normal_paths_and_restore_reenables(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
):
    patient = Patient(
        first_name="Soft",
        last_name="Deleted",
        phone="+998901234567",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    delete_response = client.delete(
        f"/api/v1/patients/{patient.id}/soft",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200

    db_session.expire_all()
    deleted_patient = db_session.get(Patient, patient.id)
    assert deleted_patient is not None
    assert deleted_patient.is_deleted is True
    assert deleted_patient.deleted_by is not None

    list_response = client.get(
        "/api/v1/patients/",
        params={"q": "Deleted"},
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert patient.id not in {item["id"] for item in list_response.json()}

    get_response = client.get(f"/api/v1/patients/{patient.id}", headers=auth_headers)
    assert get_response.status_code == 404

    deleted_response = client.get("/api/v1/patients/deleted", headers=auth_headers)
    assert deleted_response.status_code == 200
    assert patient.id in {item["id"] for item in deleted_response.json()}

    restore_response = client.post(
        f"/api/v1/patients/{patient.id}/restore",
        headers=auth_headers,
    )
    assert restore_response.status_code == 200

    restored_response = client.get(
        f"/api/v1/patients/{patient.id}",
        headers=auth_headers,
    )
    assert restored_response.status_code == 200
    assert restored_response.json()["id"] == patient.id

    deleted_after_restore_response = client.get(
        "/api/v1/patients/deleted",
        headers=auth_headers,
    )
    assert deleted_after_restore_response.status_code == 200
    assert patient.id not in {
        item["id"] for item in deleted_after_restore_response.json()
    }
