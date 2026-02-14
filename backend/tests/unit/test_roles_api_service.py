from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.roles_api_service import RolesApiDomainError, RolesApiService


@pytest.mark.unit
class TestRolesApiService:
    def test_create_role_raises_for_duplicate_name(self):
        class Repository:
            def get_role_by_name(self, name):
                return SimpleNamespace(id=1)

        service = RolesApiService(db=None, repository=Repository())

        with pytest.raises(RolesApiDomainError) as exc_info:
            service.create_role({"name": "Admin"})

        assert exc_info.value.status_code == 400

    def test_update_role_blocks_system_field_changes(self):
        role = SimpleNamespace(is_system=True)

        class Repository:
            def get_role(self, role_id):
                return role

        service = RolesApiService(db=None, repository=Repository())

        with pytest.raises(RolesApiDomainError) as exc_info:
            service.update_role(role_id=1, update_data={"name": "x"})

        assert exc_info.value.status_code == 400
