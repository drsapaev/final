"""Services admin/audit surfaces must not be anonymous.

PR-0a of the public-site program (docs/plans/2026-09-28-kosmed-site-data-audit.md §7):
GET /services/admin/doctors, GET /services/{id}/history and
GET /services/admin/audit/recent previously had NO auth dependency and exposed
staff full names, service price old/new diffs and doctor listings to any
unauthenticated caller. Their only consumers are admin-panel components
(frontend/src/components/admin/ServiceCatalog.tsx, AdminSetupDirections.tsx,
ServiceAuditHistory.tsx), so Admin is the correct guard role.
"""

from app.models.clinic import Doctor
from app.models.service import Service
from app.models.user import User

ANONYMOUS_PATHS = [
    "/api/v1/services/admin/doctors",
    "/api/v1/services/admin/audit/recent",
]


def _make_service(db) -> Service:
    service = Service(name="Аудит-тест услуга", price=10000, active=True)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def test_temp_doctor_list_rejects_anonymous(client):
    response = client.get("/api/v1/services/admin/doctors")
    assert response.status_code == 401, response.text


def test_recent_audit_rejects_anonymous(client):
    response = client.get("/api/v1/services/admin/audit/recent")
    assert response.status_code == 401, response.text


def test_service_history_rejects_anonymous(client, db):
    service = _make_service(db)
    response = client.get(f"/api/v1/services/{service.id}/history")
    assert response.status_code == 401, response.text


def test_admin_can_read_temp_doctor_list(client, auth_headers):
    response = client.get("/api/v1/services/admin/doctors", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_compact_doctor_options_include_display_name_and_apply_database_pagination(
    client, db_session, auth_headers
):
    user = User(
        username="synthetic_compact_doctor_options",
        email="synthetic-compact-doctor-options@example.test",
        full_name="  SYNTHETIC Compact Doctor  ",
        hashed_password="not-used-by-test",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(
        user_id=user.id,
        specialty="synthetic-compact-specialty",
        cabinet="12",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    offset = (
        db_session.query(Doctor)
        .filter(Doctor.active.is_(True), Doctor.id < doctor.id)
        .count()
    )
    response = client.get(
        "/api/v1/services/admin/doctors",
        params={"limit": 1, "offset": offset},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": doctor.id,
            "specialty": "synthetic-compact-specialty",
            "cabinet": "12",
            "active": True,
            "display_name": "SYNTHETIC Compact Doctor",
        }
    ]


def test_admin_can_read_service_history(client, db, auth_headers):
    service = _make_service(db)
    response = client.get(
        f"/api/v1/services/{service.id}/history", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_admin_can_read_recent_audit(client, auth_headers):
    response = client.get("/api/v1/services/admin/audit/recent", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
