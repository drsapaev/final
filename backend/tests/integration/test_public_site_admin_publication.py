"""Admin-only editing and lifecycle rules for public-site content."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.clinic import Doctor
from app.models.service import Service
from app.models.user import User


def _service(db_session, label: str, *, active: bool = True) -> Service:
    row = Service(name=f"SYNTHETIC service {label}", active=active)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _doctor(db_session, label: str, *, active: bool = True) -> Doctor:
    user = User(
        username=f"synthetic_website_{label}",
        email=f"synthetic-website-{label}@example.test",
        full_name=f"SYNTHETIC Website Doctor {label}",
        hashed_password="not-used-by-test",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    doctor = Doctor(user_id=user.id, specialty="dentistry", active=active)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _utc_datetime(value: datetime | str | None) -> datetime:
    assert value is not None
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def test_website_content_api_is_admin_only(client, db_session):
    service = _service(db_session, "private")

    response = client.get(f"/api/v1/services/admin/website-content/{service.id}")

    assert response.status_code in {401, 403}


def test_service_publication_lifecycle_locks_slug_and_preserves_first_timestamp(
    client, db_session, auth_headers
):
    service = _service(db_session, "lifecycle")
    url = f"/api/v1/services/admin/website-content/{service.id}"

    saved = client.put(
        url,
        headers=auth_headers,
        json={
            "operation": "save_draft",
            "name_ru": "Консультация",
            "name_uz": "Maslahat",
            "description_ru": "Описание услуги.",
            "description_uz": "Xizmat tavsifi.",
            "slug": "consultation",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["show_on_website"] is False
    assert saved.json()["website_first_published_at"] is None

    published = client.put(
        url,
        headers=auth_headers,
        json={"operation": "publish"},
    )
    assert published.status_code == 200, published.text
    first_published_at = published.json()["website_first_published_at"]
    assert first_published_at
    assert published.json()["show_on_website"] is True
    assert published.json()["slug_locked"] is True

    edited = client.put(
        url,
        headers=auth_headers,
        json={"operation": "save_published", "name_uz": "Yangi maslahat"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["website_first_published_at"] == first_published_at
    assert edited.json()["show_on_website"] is True

    unpublished = client.put(
        url,
        headers=auth_headers,
        json={"operation": "unpublish"},
    )
    assert unpublished.status_code == 200, unpublished.text
    assert unpublished.json()["show_on_website"] is False
    assert unpublished.json()["website_first_published_at"] == first_published_at

    changed_slug = client.put(
        url,
        headers=auth_headers,
        json={"operation": "republish", "slug": "new-address"},
    )
    assert changed_slug.status_code == 409, changed_slug.text
    assert changed_slug.json()["detail"]["code"] == "website_slug_locked"

    republished = client.put(
        url,
        headers=auth_headers,
        json={"operation": "republish"},
    )
    assert republished.status_code == 200, republished.text
    assert republished.json()["show_on_website"] is True
    assert republished.json()["website_first_published_at"] == first_published_at


def test_service_publication_requires_both_locales_and_unique_slug(
    client, db_session, auth_headers
):
    first = _service(db_session, "incomplete")
    second = _service(db_session, "duplicate")
    first_url = f"/api/v1/services/admin/website-content/{first.id}"
    second_url = f"/api/v1/services/admin/website-content/{second.id}"

    incomplete = client.put(
        first_url,
        headers=auth_headers,
        json={"operation": "publish", "slug": "needs-content"},
    )
    assert incomplete.status_code == 422, incomplete.text
    assert "name_uz" in incomplete.json()["detail"]["missing_fields"]
    assert "description_uz" in incomplete.json()["detail"]["missing_fields"]

    complete_content = {
        "name_uz": "Maslahat",
        "description_ru": "Описание.",
        "description_uz": "Tavsif.",
        "slug": "same-address",
    }
    first_draft = client.put(
        first_url,
        headers=auth_headers,
        json={"operation": "save_draft", **complete_content},
    )
    assert first_draft.status_code == 200, first_draft.text

    duplicate_draft = client.put(
        second_url,
        headers=auth_headers,
        json={"operation": "save_draft", **complete_content},
    )
    assert duplicate_draft.status_code == 409, duplicate_draft.text
    assert duplicate_draft.json()["detail"]["code"] == "website_slug_conflict"

    first_publish = client.put(
        first_url,
        headers=auth_headers,
        json={"operation": "publish"},
    )
    assert first_publish.status_code == 200, first_publish.text


def test_doctor_publication_and_admin_deactivation_hide_without_resetting_slug(
    client, db_session, auth_headers
):
    doctor = _doctor(db_session, "deactivate")
    content_url = f"/api/v1/admin/doctors/{doctor.id}/website-content"

    draft = client.put(
        content_url,
        headers=auth_headers,
        json={
            "operation": "save_draft",
            "bio_ru": "Синтетическая биография.",
            "bio_uz": "Sintetik tarjimai hol.",
            "slug": "synthetic-doctor",
        },
    )
    assert draft.status_code == 200, draft.text

    published = client.put(
        content_url,
        headers=auth_headers,
        json={"operation": "publish"},
    )
    assert published.status_code == 200, published.text
    first_published_at = published.json()["website_first_published_at"]

    deactivated = client.put(
        f"/api/v1/admin/doctors/{doctor.id}",
        headers=auth_headers,
        json={"active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    db_session.expire_all()
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
    assert doctor_row.active is False
    assert doctor_row.show_on_website is False
    assert doctor_row.slug == "synthetic-doctor"
    assert _utc_datetime(doctor_row.website_first_published_at) == _utc_datetime(
        first_published_at
    )

    reactivated = client.put(
        f"/api/v1/admin/doctors/{doctor.id}",
        headers=auth_headers,
        json={"active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    db_session.expire_all()
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
    assert doctor_row.active is True
    assert doctor_row.show_on_website is False
    assert _utc_datetime(doctor_row.website_first_published_at) == _utc_datetime(
        first_published_at
    )


def test_service_batch_deactivation_unpublishes_and_reactivation_does_not_republish(
    client, db_session, auth_headers
):
    service = _service(db_session, "batch-deactivate")
    service.show_on_website = True
    service.slug = "synthetic-batch-service"
    service.website_first_published_at = datetime.now(UTC)
    db_session.commit()
    first_published_at = service.website_first_published_at

    for active in (False, True):
        response = client.post(
            "/api/v1/services/admin/batch-update",
            headers=auth_headers,
            json={"service_ids": [service.id], "updates": {"active": active}},
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        service_row = db_session.query(Service).filter(Service.id == service.id).one()
        assert service_row.active is active
        assert service_row.show_on_website is False
        assert service_row.slug == "synthetic-batch-service"
        assert service_row.website_first_published_at == first_published_at
