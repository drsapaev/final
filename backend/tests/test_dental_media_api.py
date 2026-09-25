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


# ---------------------------------------------------------------------------
# PR #3439 corrective follow-up regression block (P1-1 / P1-2 / P2 verdict).
# ---------------------------------------------------------------------------


def _make_bare_user(
    db_session: Session,
    *,
    role: str = "dentist",
    is_superuser: bool = False,
) -> User:
    """A clinician-role user WITHOUT any Doctor profile (legacy-fallback world)."""
    suffix = secrets.token_hex(6)
    user = User(
        username=f"dental_bare_{suffix}",
        email=f"dental_bare_{suffix}@example.test",
        full_name="Synthetic Bare Clinician",
        hashed_password=get_password_hash("not-a-real-user-password"),
        role=role,
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_colliding_victim_doctor(
    db_session: Session, *, doctor_id: int
) -> tuple[User, Doctor]:
    """Victim clinician whose Doctor.id equals an unrelated User.id."""
    suffix = secrets.token_hex(6)
    victim_user = User(
        username=f"dental_victim_{suffix}",
        email=f"dental_victim_{suffix}@example.test",
        full_name="Synthetic Victim Dentist",
        hashed_password=get_password_hash("not-a-real-user-password"),
        role="dentist",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(victim_user)
    db_session.flush()
    victim_doctor = Doctor(
        id=doctor_id,
        user_id=victim_user.id,
        specialty="dentistry",
        active=True,
        cabinet="406",
    )
    db_session.add(victim_doctor)
    db_session.commit()
    db_session.refresh(victim_user)
    db_session.refresh(victim_doctor)
    return victim_user, victim_doctor


def test_legacy_user_id_fallback_cannot_open_foreign_dental_archive(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """P1-1: Visit.doctor_id stores Doctor.id, never User.id — the legacy
    `visit.doctor_id == user.id` fallback must not authorize a dentist whose
    bare User.id collides with another clinician's Doctor.id."""
    attacker = _make_bare_user(db_session, role="dentist")
    attacker_id = attacker.id
    db_session.expunge(attacker)

    victim_user, victim_doctor = _make_colliding_victim_doctor(
        db_session, doctor_id=attacker_id
    )
    victim_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=victim_doctor.id
    )
    upload = _upload(
        client,
        headers=_headers(victim_user),
        patient_id=test_patient.id,
        visit_id=victim_visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]

    list_response = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": victim_visit.id},
        headers=_headers(attacker),
    )
    assert list_response.status_code == 404, list_response.text

    content_response = client.get(
        f"/api/v1/dental/media/{media_id}/content",
        params={"visit_id": victim_visit.id},
        headers=_headers(attacker),
    )
    assert content_response.status_code == 404, content_response.text

    edit_response = client.patch(
        f"/api/v1/dental/media/{media_id}",
        json={"title": "attacker rename"},
        headers=_headers(attacker),
    )
    assert edit_response.status_code == 403, edit_response.text

    delete_response = client.delete(
        f"/api/v1/dental/media/{media_id}",
        headers=_headers(attacker),
    )
    assert delete_response.status_code == 403, delete_response.text

    # The legitimate treating clinician keeps full access.
    victim_list = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": victim_visit.id},
        headers=_headers(victim_user),
    )
    assert victim_list.status_code == 200, victim_list.text
    assert {item["id"] for item in victim_list.json()["items"]} == {media_id}


def test_generic_file_surface_fail_closed_for_dental_media(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """P1-2: a dental-media tagged file must be unreachable through the
    generic /files surface — including for its own generic-surface owner —
    and must remain reachable through the dental surface. The owner uses the
    canonical "Doctor" role spelling (explicitly allowed by #3439): that is
    exactly the identity the generic endpoints' role gates let through."""
    owner, owner_doctor = _make_actor(db_session, role="Doctor")
    owner_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=owner_doctor.id
    )
    upload = _upload(
        client,
        headers=_headers(owner),
        patient_id=test_patient.id,
        visit_id=owner_visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]

    outsider, _outsider_doctor = _make_actor(db_session)

    generic_get = client.get(f"/api/v1/files/{media_id}", headers=_headers(owner))
    assert generic_get.status_code == 403, generic_get.text

    generic_download = client.get(
        f"/api/v1/files/{media_id}/download", headers=_headers(owner)
    )
    assert generic_download.status_code == 403, generic_download.text

    generic_preview = client.get(
        f"/api/v1/files/{media_id}/preview", headers=_headers(owner)
    )
    assert generic_preview.status_code == 403, generic_preview.text

    generic_shares = client.get(
        f"/api/v1/files/{media_id}/shares", headers=_headers(owner)
    )
    assert generic_shares.status_code == 403, generic_shares.text

    generic_share = client.post(
        f"/api/v1/files/{media_id}/share",
        json={
            "shared_with_user_id": outsider.id,
            "permission": "private",
        },
        headers=_headers(owner),
    )
    assert generic_share.status_code == 403, generic_share.text

    generic_update = client.put(
        f"/api/v1/files/{media_id}",
        data={"title": "generic rename"},
        headers=_headers(owner),
    )
    assert generic_update.status_code == 403, generic_update.text

    generic_replace = client.put(
        f"/api/v1/files/{media_id}/content",
        files={
            "file": (
                "replacement.jpg",
                BytesIO(b"\xff\xd8\xffreplacement image"),
                "image/jpeg",
            )
        },
        headers=_headers(owner),
    )
    assert generic_replace.status_code == 403, generic_replace.text

    generic_delete = client.delete(
        f"/api/v1/files/{media_id}", headers=_headers(owner)
    )
    assert generic_delete.status_code == 403, generic_delete.text

    generic_export = client.post(
        "/api/v1/files/export",
        json={"file_ids": [media_id], "format": "zip"},
        headers=_headers(owner),
    )
    assert generic_export.status_code == 403, generic_export.text

    # A share-based stranger cannot reach the file through the generic surface.
    stranger_get = client.get(f"/api/v1/files/{media_id}", headers=_headers(outsider))
    assert stranger_get.status_code in {403, 404}, stranger_get.text

    # The dental surface keeps serving and editing the same record.
    dental_content = client.get(
        f"/api/v1/dental/media/{media_id}/content",
        params={"visit_id": owner_visit.id},
        headers=_headers(owner),
    )
    assert dental_content.status_code == 200, dental_content.text
    assert dental_content.content == b"\xff\xd8\xffsynthetic dental image"

    dental_edit = client.patch(
        f"/api/v1/dental/media/{media_id}",
        json={"title": "dental surface rename"},
        headers=_headers(owner),
    )
    assert dental_edit.status_code == 200, dental_edit.text

    dental_delete = client.delete(
        f"/api/v1/dental/media/{media_id}", headers=_headers(owner)
    )
    assert dental_delete.status_code == 200, dental_delete.text

    db_session.expire_all()
    deleted_row = db_session.query(File).filter(File.id == media_id).one()
    assert deleted_row.status == FileStatus.DELETED


def test_dentistry_role_spelling_reaches_specialty_check(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """P2: doctor-family spellings from the IAM SSOT must not be rejected by
    the local hardcode before the dental specialty check."""
    clinician = _make_bare_user(db_session, role="dentistry")
    suffix = secrets.token_hex(6)
    doctor = Doctor(
        user_id=clinician.id,
        specialty="dentistry",
        active=True,
        cabinet=f"4{secrets.randbelow(90) + 10}",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=doctor.id
    )

    response = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": visit.id},
        headers=_headers(clinician),
    )
    assert response.status_code == 200, response.text


def test_superadmin_role_passes_admin_gate_on_dental_visit(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """P2: a superuser whose role string is the canonical SuperAdmin must not
    fall through the literal Admin check into a 403 on a dental visit."""
    suffix = secrets.token_hex(6)
    superadmin = User(
        username=f"dental_superadmin_{suffix}",
        email=f"dental_superadmin_{suffix}@example.test",
        full_name="Synthetic Super Admin",
        hashed_password=get_password_hash("not-a-real-user-password"),
        role="SuperAdmin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(superadmin)
    db_session.commit()
    db_session.refresh(superadmin)

    owner, owner_doctor = _make_actor(db_session)
    owner_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=owner_doctor.id
    )

    response = client.get(
        "/api/v1/dental/media",
        params={"patient_id": test_patient.id, "visit_id": owner_visit.id},
        headers=_headers(superadmin),
    )
    assert response.status_code == 200, response.text


def test_generic_list_and_search_exclude_protected_dental_media(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """Owner verdict on a7ec002e (P1): the generic reader surfaces —
    GET /files/ (list) and POST /files/search — must exclude protected-domain
    rows at the query level (before pagination/count/facets), the same way the
    item-level surfaces fail closed via ensure_generic_surface_allowed().
    A dental-media tagged file must not be listed or searchable by its own
    generic-surface owner, while ordinary files of the same owner stay
    visible (the exclusion must not over-filter)."""
    owner, owner_doctor = _make_actor(db_session, role="Doctor")
    owner_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=owner_doctor.id
    )

    upload = _upload(
        client,
        headers=_headers(owner),
        patient_id=test_patient.id,
        visit_id=owner_visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]

    control = client.post(
        "/api/v1/files/upload",
        files={
            "file": (
                "control-note.txt",
                BytesIO(b"plain control document"),
                "text/plain",
            )
        },
        data={"file_type": "document", "title": "control document"},
        headers=_headers(owner),
    )
    assert control.status_code in (200, 201), control.text
    control_id = control.json()["id"]

    # LIST surface: the protected row must not appear (owner scope).
    listing = client.get("/api/v1/files/", headers=_headers(owner))
    assert listing.status_code == 200, listing.text
    listed_ids = {f["id"] for f in listing.json()["files"]}
    assert media_id not in listed_ids, (
        "protected dental media leaked through generic list"
    )
    assert control_id in listed_ids, "control file must stay listed"

    # SEARCH surface (owner scope => strict equality is meaningful).
    search = client.post("/api/v1/files/search", json={}, headers=_headers(owner))
    assert search.status_code == 200, search.text
    searched_ids = {f["id"] for f in search.json()["files"]}
    assert media_id not in searched_ids, (
        "protected dental media leaked through generic search"
    )
    assert control_id in searched_ids, "control file must stay searchable"

    # An admin reader must not pull the protected row through search either.
    admin, _admin_doctor = _make_actor(db_session, role="Admin")
    admin_search = client.post(
        "/api/v1/files/search", json={}, headers=_headers(admin)
    )
    assert admin_search.status_code == 200, admin_search.text
    admin_ids = {f["id"] for f in admin_search.json()["files"]}
    assert media_id not in admin_ids, (
        "protected dental media leaked through admin generic search"
    )


def test_search_facets_scoped_to_base_query_not_whole_table(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """Owner verdict on e7fe45cac (P2): /files/search facets (file_types,
    permissions) must aggregate over the SAME base query as total/page —
    non-admin owner scope, requested search filters and the protected-domain
    exclusion — not over the whole files table. Separate unscoped aggregate
    queries leak global metadata (counts of foreign and protected rows) to
    readers whose files[] payload is correctly scoped."""
    owner, owner_doctor = _make_actor(db_session, role="Doctor")
    owner_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=owner_doctor.id
    )

    # Protected dental media owned by the reader: image/xray + private.
    upload = _upload(
        client,
        headers=_headers(owner),
        patient_id=test_patient.id,
        visit_id=owner_visit.id,
    )
    assert upload.status_code == 201, upload.text

    control = client.post(
        "/api/v1/files/upload",
        files={
            "file": (
                "scoped-note.txt",
                BytesIO(b"scoped control document"),
                "text/plain",
            )
        },
        data={"file_type": "document", "title": "scoped control"},
        headers=_headers(owner),
    )
    assert control.status_code in (200, 201), control.text
    control_id = control.json()["id"]

    # Foreign ordinary image of a file_type the owner does not have: its
    # type/permission aggregates must not surface in the owner's facets.
    foreign, _foreign_doctor = _make_actor(db_session, role="Doctor")
    foreign_file = client.post(
        "/api/v1/files/upload",
        files={
            "file": (
                "foreign-scan.png",
                BytesIO(b"\x89PNG\r\n\x1a\n synthetic foreign scan"),
                "image/png",
            )
        },
        data={"file_type": "image", "title": "foreign image"},
        headers=_headers(foreign),
    )
    assert foreign_file.status_code in (200, 201), foreign_file.text

    search = client.post("/api/v1/files/search", json={}, headers=_headers(owner))
    assert search.status_code == 200, search.text
    body = search.json()
    assert body["total"] == 1, "owner scope: only the control document"
    assert {f["id"] for f in body["files"]} == {control_id}

    # Facets must mirror the scoped result set: no "image" from the foreign
    # file, no image/xray from the protected dental row, single "private".
    file_types = {
        row["file_type"]: row["count"] for row in body["facets"]["file_types"]
    }
    assert file_types == {"document": 1}, file_types
    permissions = {
        row["permission"]: row["count"] for row in body["facets"]["permissions"]
    }
    assert permissions == {"private": 1}, permissions


def test_generic_surfaces_classify_tags_by_exact_token_not_substring(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """Owner verdict on e7fe45cac (P2): the protected-tag exclusion on the
    generic list/search must be an exact-tag check, not a substring (LIKE)
    check. A generic file whose ordinary user tag merely CONTAINS a protected
    tag as a substring (e.g. "dental-media:v1-backup") must stay visible on
    GET /files/ and POST /files/search and readable via GET /files/{file_id} —
    the query-level classification must agree with the item-level
    protected_domain_tag() classification (one classification per file)."""
    owner, _owner_doctor = _make_actor(db_session, role="Doctor")

    lookalike = client.post(
        "/api/v1/files/upload",
        files={
            "file": (
                "backup-notes.txt",
                BytesIO(b"ordinary backup document"),
                "text/plain",
            )
        },
        data={
            "file_type": "document",
            "title": "backup notes",
            "tags": "dental-media:v1-backup, year-2026",
        },
        headers=_headers(owner),
    )
    assert lookalike.status_code in (200, 201), lookalike.text
    lookalike_id = lookalike.json()["id"]

    listing = client.get("/api/v1/files/", headers=_headers(owner))
    assert listing.status_code == 200, listing.text
    listed_ids = {f["id"] for f in listing.json()["files"]}
    assert lookalike_id in listed_ids, (
        "substring exclusion misclassified a lookalike user tag as protected"
    )

    search = client.post("/api/v1/files/search", json={}, headers=_headers(owner))
    assert search.status_code == 200, search.text
    searched_ids = {f["id"] for f in search.json()["files"]}
    assert lookalike_id in searched_ids, (
        "substring exclusion misclassified a lookalike user tag as protected"
    )

    fetched = client.get(f"/api/v1/files/{lookalike_id}", headers=_headers(owner))
    assert fetched.status_code == 200, fetched.text


def test_superadmin_can_delete_dental_media_without_ownership(
    client: TestClient,
    db_session: Session,
    test_patient: Patient,
    dental_storage,
):
    """Owner verdict on a7ec002e (P2): a SuperAdmin passes the dental editor
    gate via the IAM SSOT (is_admin_role), so the service-level
    owner-or-Admin check (literal role == "Admin" in _is_admin) must not fall
    through to a 404 for a non-owning SuperAdmin deleting a dental media
    record."""
    owner, owner_doctor = _make_actor(db_session)
    owner_visit = _make_visit(
        db_session, patient_id=test_patient.id, doctor_id=owner_doctor.id
    )
    upload = _upload(
        client,
        headers=_headers(owner),
        patient_id=test_patient.id,
        visit_id=owner_visit.id,
    )
    assert upload.status_code == 201, upload.text
    media_id = upload.json()["id"]

    suffix = secrets.token_hex(6)
    superadmin = User(
        username=f"dental_superadmin_del_{suffix}",
        email=f"dental_superadmin_del_{suffix}@example.test",
        full_name="Synthetic Super Admin Deleter",
        hashed_password=get_password_hash("not-a-real-user-password"),
        role="SuperAdmin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(superadmin)
    db_session.commit()
    db_session.refresh(superadmin)

    response = client.delete(
        f"/api/v1/dental/media/{media_id}", headers=_headers(superadmin)
    )
    assert response.status_code == 200, response.text
