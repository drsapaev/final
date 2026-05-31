from app.api.v1.endpoints import user_management
from app.main import app


def _allow_staff_dependency(monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        user_management.require_staff,
        lambda: type(
            "StaffUser",
            (),
            {"id": 1, "role": "Admin", "is_active": True},
        )(),
    )


class _FakeUserManagementService:
    def get_user_stats(self, db):
        return {
            "total_users": 3,
            "active_users": 2,
            "inactive_users": 1,
            "suspended_users": 0,
            "locked_users": 0,
            "users_by_role": {"Admin": 1, "Doctor": 1, "Patient": 1},
            "users_with_profiles": 2,
            "users_with_2fa": 1,
            "recent_registrations": 1,
            "recent_logins": 1,
        }

    def get_user_profile(self, db, user_id):
        if user_id != 12345:
            return None
        return {
            "id": 12345,
            "username": "route_user",
            "email": "route.user@test.com",
            "full_name": "Route User",
            "role": "Doctor",
            "is_active": True,
            "is_superuser": False,
            "created_at": None,
            "updated_at": None,
            "profile": None,
            "preferences": None,
            "roles": [],
            "groups": [],
        }


def test_user_stats_route_dispatches_before_user_id(client, monkeypatch):
    _allow_staff_dependency(monkeypatch)
    monkeypatch.setattr(
        user_management,
        "get_user_management_service",
        lambda: _FakeUserManagementService(),
    )

    response = client.get("/api/v1/users/users/stats")

    assert response.status_code == 200
    assert response.json()["total_users"] == 3
    assert response.json()["users_by_role"]["Admin"] == 1


def test_user_health_route_dispatches_before_user_id(client):
    response = client.get("/api/v1/users/users/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "user_management"


def test_numeric_user_id_route_remains_available(client, monkeypatch):
    _allow_staff_dependency(monkeypatch)
    monkeypatch.setattr(
        user_management,
        "get_user_management_service",
        lambda: _FakeUserManagementService(),
    )

    response = client.get("/api/v1/users/users/12345")

    assert response.status_code == 200
    assert response.json()["id"] == 12345
