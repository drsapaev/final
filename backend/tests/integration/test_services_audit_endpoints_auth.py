"""Services admin/audit surfaces must not be anonymous.

PR-0a of the public-site program (docs/plans/2026-09-28-kosmed-site-data-audit.md §7):
GET /services/admin/doctors, GET /services/{id}/history and
GET /services/admin/audit/recent previously had NO auth dependency and exposed
staff full names, service price old/new diffs and doctor listings to any
unauthenticated caller. Their only consumers are admin-panel components
(frontend/src/components/admin/ServiceCatalog.tsx, AdminSetupDirections.tsx,
ServiceAuditHistory.tsx), so Admin is the correct guard role.
"""

from app.models.service import Service

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
