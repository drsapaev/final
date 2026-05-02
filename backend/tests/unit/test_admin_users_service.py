from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.admin_users_service import AdminUsersService


@pytest.mark.unit
class TestAdminUsersService:
    def test_list_users_maps_to_api_payload(self):
        repository = SimpleNamespace(
            list_users=lambda: [
                SimpleNamespace(
                    id=10,
                    username="admin",
                    full_name="Admin User",
                    email="admin@example.com",
                    role="Admin",
                    is_active=True,
                )
            ]
        )
        service = AdminUsersService(db=None, repository=repository)

        result = service.list_users()

        assert result == [
            {
                "id": 10,
                "username": "admin",
                "full_name": "Admin User",
                "email": "admin@example.com",
                "role": "Admin",
                "is_active": True,
            }
        ]

