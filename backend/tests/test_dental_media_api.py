"""Contract and access tests for the protected dental media archive."""

from __future__ import annotations

import secrets
from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.file_system import File, FileQuota, FileStatus
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.authentication_service import authentication_service
from app.services.file_system_service import get_file_system_service


@pytest.fixture
def dental_storage(tmp_path, monkeypatch):
    service = get_file_system_service()
    monkeypatch.setattr(service, "base_storage_path", str(tmp_path / "files"))
    monkeypatch.setattr(service, "temp_storage_path", str(tmp_path / "temp"))
    return service


def _make_actor(
    db_session: Session,
    *,
    specialty: str = "dentistry",
    role: str = "dentist",
) -> tuple[User, Doctor]:
    suffix = secrets.token_hex(6)
    user = User(
        username=f"dental_media_{suffix}",
        email=f"dental_media_{suffix}@example.test",
        full_name="Synthetic Dental Clinician",
        hashed_password=get_password_hash("not-a-real-user-password"),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
        cabinet="405",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(doctor)
    return user, doctor


def _make_visit(db_session: Session, *, patient_id: int, doctor_id: int) -> Visit:
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=date.today(),
        status="open",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _headers(user: User) -> dict[str, str]:
    token = authentication_service.create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _upload(
    client: TestClient,
    *,
    headers: dict[str, str],
    patient_id: int,
    visit_id: int,
    filename: str = "synthetic-dental.jpg",
    content: bytes = b"\xff\xd8\xffsynthetic dental image",
    mime_type: str = "image/jpeg",
    category: str = "photo",
):
    return client.post(
        "/api/v1/dental/media",
        files={"file": (filename, BytesIO(content), mime_type)},
        data={
            "patient_id": str(patient_id),
            "visit_id": str(visit_id),
            "category": category,
            "tooth": "26",
            "capture_date": "2026-09-25",
        },
        headers=headers,
    )


def test_dental_archive_persists_and_treating_dentist_can_view_other_author(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    author, author_doctor = _make_actor(db_session)
    viewer, viewer_doctor = _make_actor(db_session)
    author_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=author_doctor.id
    )
    viewer_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=viewer_doctor.id
    )

    upload = _upload(
        client,
        headers=_headers(author),
        patient_id=test_patient.id,
        visit_id=author_visit.id,
    )
    assert upload.status_code == 201, upload.text
    created = upload.json()
    assert created["category"] == "photo"
    assert created["tooth"] == "26"
    assert created["capture_date"] == "2026-09-25"
    assert "file_path" not in created
    assert "file_hash" not in created

    png_upload = _upload(
        client,
        headers=_headers(author),
        patient_id=test_patient.id,
        visit_id=author_visit.id,
        filename="synthetic-dental.png",
        content=b"\x89PNG\r\n\x1a\nsynthetic dental image",
        mime_type="image/png",
    )
    pdf_upload = _upload(
        client,
        headers=_headers(author),
        patient_id=test_patient.id,
        visit_id=author_visit.id,
        filename="synthetic-xray.pdf",
        content=b"%PDF-1.4\nsynthetic dental xray",
        mime_type="application/pdf",
        category="xray",
    )
    assert png_upload.status_code == 201, png_upload.text
    assert pdf_upload.status_code == 201, pdf_upload.text
    assert pdf_upload.json()["category"] == "xray"

    params = {"patient_id": test_patient.id, "visit_id": viewer_visit.id}
    first_load = client.get(
        "/api/v1/dental/media", params=params, headers=_headers(viewer)
    )
    second_load = client.get(
        "/api/v1/dental/media", params=params, headers=_headers(viewer)
    )
    assert first_load.status_code == 200
    assert second_load.status_code == 200
    assert len(first_load.json()["items"]) == 3
    assert {item["id"] for item in first_load.json()["items"]} >= {
        created["id"],
        png_upload.json()["id"],
        pdf_upload.json()["id"],
    }
    assert second_load.json()["items"][0]["capture_date"] == "2026-09-25"

    content = client.get(
        f"/api/v1/dental/media/{created['id']}/content",
        params={"visit_id": viewer_visit.id},
        headers=_headers(viewer),
    )
    assert content.status_code == 200
    assert content.content == b"\xff\xd8\xffsynthetic dental image"
    assert content.headers["cache-control"] == "private, no-store"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert "file_path" not in content.headers
    access_events = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == viewer.id,
            AuditLog.subject_patient_id == test_patient.id,
            AuditLog.event_type == "DENTAL_MEDIA_VIEW",
        )
        .all()
    )
    assert len(access_events) == 3
    assert {event.action for event in access_events} == {"view"}

    another_patient = Patient(first_name="S.", last_name="T.", phone=None)
    db_session.add(another_patient)
    db_session.commit()
    db_session.refresh(another_patient)
    another_visit = _make_visit(
        db_session, patient_id=another_patient.id, doctor_id=viewer_doctor.id
    )
    cross_patient_view = client.get(
        f"/api/v1/dental/media/{created['id']}/content",
        params={"visit_id": another_visit.id},
        headers=_headers(viewer),
    )
    assert cross_patient_view.status_code == 404


def test_dental_archive_rejects_mismatched_patient_visit_and_unsupported_formats(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    dentist, dentist_profile = _make_actor(db_session)
    another_patient = Patient(
        first_name="S.",
        last_name="T.",
        phone=None,
        birth_date=None,
    )
    db_session.add(another_patient)
    db_session.commit()
    db_session.refresh(another_patient)
    another_patient_visit = _make_visit(
        db_session,
        patient_id=another_patient.id,
        doctor_id=dentist_profile.id,
    )

    mismatch = _upload(
        client,
        headers=_headers(dentist),
        patient_id=test_patient.id,
        visit_id=another_patient_visit.id,
    )
    unsupported_video = _upload(
        client,
        headers=_headers(dentist),
        patient_id=another_patient.id,
        visit_id=another_patient_visit.id,
        filename="unsupported.mp4",
        content=b"\x00\x00\x00\x18ftypmp42synthetic video",
        mime_type="video/mp4",
    )
    unsupported_dicom = _upload(
        client,
        headers=_headers(dentist),
        patient_id=another_patient.id,
        visit_id=another_patient_visit.id,
        filename="unsupported.dcm",
        content=b"DICMsynthetic dicom",
        mime_type="application/dicom",
        category="xray",
    )

    assert mismatch.status_code == 404
    assert unsupported_video.status_code == 400
    assert unsupported_dicom.status_code == 400
    assert db_session.query(File).count() == 0

    invalid_list = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": another_patient_visit.id},
        headers=_headers(dentist),
    )
    assert invalid_list.status_code == 404


def test_only_author_or_admin_can_edit_and_delete_dental_media(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    admin_user: User,
    auth_headers: dict[str, str],
    dental_storage,
):
    author, author_doctor = _make_actor(db_session)
    other_dentist, other_doctor = _make_actor(db_session)
    author_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=author_doctor.id
    )
    other_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=other_doctor.id
    )
    owner_quota = FileQuota(
        user_id=author.id,
        max_storage_bytes=1_000_000,
        used_storage_bytes=0,
        max_files=20,
        used_files=0,
    )
    db_session.add(owner_quota)
    db_session.commit()

    upload = _upload(
        client,
        headers=_headers(author),
        patient_id=test_patient.id,
        visit_id=author_visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]
    quota_after_upload = (
        db_session.query(FileQuota).filter(FileQuota.user_id == author.id).one()
    )
    assert quota_after_upload.used_files == 1

    url = f"/api/v1/dental/media/{media_id}"
    denied_update = client.patch(
        url,
        json={"tooth": "27"},
        headers=_headers(other_dentist),
    )
    denied_delete = client.delete(url, headers=_headers(other_dentist))
    assert denied_update.status_code == 403
    assert denied_delete.status_code == 403

    update = client.patch(
        url,
        json={"tooth": "27", "capture_date": "2026-09-20"},
        headers=_headers(author),
    )
    assert update.status_code == 200, update.text
    assert update.json()["tooth"] == "27"
    assert update.json()["capture_date"] == "2026-09-20"

    admin_delete = client.delete(url, headers=auth_headers)
    assert admin_delete.status_code == 200
    assert admin_delete.json() == {"success": True}
    db_session.refresh(owner_quota)
    stored_file = db_session.query(File).filter(File.id == media_id).one()
    assert stored_file.status == FileStatus.DELETED
    assert owner_quota.used_files == 0
    assert owner_quota.used_storage_bytes == 0

    after_delete = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": other_visit.id},
        headers=_headers(other_dentist),
    )
    assert after_delete.status_code == 200
    assert after_delete.json()["items"] == []


def test_dental_media_routes_are_authenticated_and_do_not_publish_storage_path():
    from app.main import app

    spec = app.openapi()
    assert "/api/v1/dental/media" in spec["paths"]
    assert "/api/v1/dental/media/{media_id}/content" in spec["paths"]
    properties = spec["components"]["schemas"]["DentalMediaOut"]["properties"]
    assert "file_path" not in properties
    assert "file_metadata" not in properties


def test_dental_media_content_requires_authentication(
    client: TestClient,
):
    response = client.get("/api/v1/dental/media/1/content", params={"visit_id": 1})
    assert response.status_code == 401


def test_dental_media_view_rejects_storage_paths_outside_configured_root(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
    tmp_path,
):
    dentist, doctor = _make_actor(db_session)
    visit = _make_visit(db_session, patient_id=test_patient.id, doctor_id=doctor.id)
    upload = _upload(
        client,
        headers=_headers(dentist),
        patient_id=test_patient.id,
        visit_id=visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]

    outside_file = tmp_path / "outside.jpg"
    outside_file.write_bytes(b"synthetic outside file")
    stored_file = db_session.query(File).filter(File.id == media_id).one()
    stored_file.file_path = str(outside_file)
    db_session.commit()

    response = client.get(
        f"/api/v1/dental/media/{media_id}/content",
        params={"visit_id": visit.id},
        headers=_headers(dentist),
    )
    assert response.status_code == 404
    assert response.content != b"synthetic outside file"
