from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.role_permission import Role, UserGroup
from app.services.group_permissions_api_service import (
    GroupPermissionsApiDomainError,
    GroupPermissionsApiService,
)


@pytest.mark.unit
class TestGroupPermissionsApiService:
    def test_get_user_permissions_payload_raises_for_missing_user(self):
        repository = SimpleNamespace(
            get_user=lambda user_id: None,
            get_user_role_names=lambda user_id: [],
            get_user_group_names=lambda user_id: [],
            count_group_users=lambda group_id: 0,
            count_group_roles=lambda group_id: 0,
        )
        permission_service = SimpleNamespace()
        service = GroupPermissionsApiService(
            db=None,
            repository=repository,
            permission_service=permission_service,
        )

        with pytest.raises(GroupPermissionsApiDomainError) as exc_info:
            service.get_user_permissions_payload(user_id=1, use_cache=True)

        assert exc_info.value.status_code == 404
        assert "Пользователь не найден" in exc_info.value.detail

    def test_get_user_permissions_payload_returns_roles_and_groups(self):
        user = SimpleNamespace(
            username="admin",
        )

        class FakeQuery:
            def __init__(self, items):
                self._items = items

            def join(self, *args, **kwargs):
                return self

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return list(self._items)

        class FakeDb:
            def query(self, model):
                if model is Role:
                    return FakeQuery([SimpleNamespace(name="Admin", is_active=True)])
                if model is UserGroup:
                    return FakeQuery([SimpleNamespace(name="main", is_active=True)])
                raise AssertionError(f"Unexpected model: {model!r}")

        repository = SimpleNamespace(
            get_user=lambda user_id: user,
            get_user_role_names=lambda user_id: ["Admin"],
            get_user_group_names=lambda user_id: ["main"],
            count_group_users=lambda group_id: 0,
            count_group_roles=lambda group_id: 0,
        )
        permission_service = SimpleNamespace(
            get_user_permissions=lambda db, user_id, use_cache: {"a.read", "a.write"}
        )
        service = GroupPermissionsApiService(
            db=FakeDb(),
            repository=repository,
            permission_service=permission_service,
        )

        payload = service.get_user_permissions_payload(user_id=7, use_cache=False)

        assert payload["user_id"] == 7
        assert payload["username"] == "admin"
        assert payload["permissions_count"] == 2
        assert payload["roles"] == ["Admin"]
        assert payload["groups"] == ["main"]

    def test_create_permission_override_creates_record_and_clears_cache(self):
        created_at = datetime(2026, 1, 1, 12, 0, 0)
        created_override = SimpleNamespace(id=99, created_at=created_at)
        cache_calls: list[int] = []
        repository = SimpleNamespace(
            get_user=lambda user_id: SimpleNamespace(id=user_id, username="u1"),
            get_permission=lambda permission_id: SimpleNamespace(
                id=permission_id,
                name="perm",
            ),
            get_active_override=lambda user_id, permission_id: None,
            create_override=lambda **kwargs: created_override,
            rollback=lambda: None,
            get_user_role_names=lambda user_id: [],
            get_user_group_names=lambda user_id: [],
            count_group_users=lambda group_id: 0,
            count_group_roles=lambda group_id: 0,
        )
        permission_service = SimpleNamespace(
            _clear_user_cache=lambda user_id: cache_calls.append(user_id),
        )
        service = GroupPermissionsApiService(
            db=None,
            repository=repository,
            permission_service=permission_service,
        )

        result = service.create_permission_override(
            user_id=10,
            permission_id=5,
            override_type="grant",
            reason="manual",
            expires_hours=None,
            granted_by_user_id=1,
            granted_by_username="admin",
        )

        assert result["success"] is True
        assert result["override_id"] == 99
        assert result["created_by"] == "admin"
        assert cache_calls == [10]

    def test_create_permission_override_rejects_duplicate_override(self):
        repository = SimpleNamespace(
            get_user=lambda user_id: SimpleNamespace(id=user_id, username="u1"),
            get_permission=lambda permission_id: SimpleNamespace(
                id=permission_id,
                name="perm",
            ),
            get_active_override=lambda user_id, permission_id: SimpleNamespace(id=1),
            create_override=lambda **kwargs: None,
            rollback=lambda: None,
            get_user_role_names=lambda user_id: [],
            get_user_group_names=lambda user_id: [],
            count_group_users=lambda group_id: 0,
            count_group_roles=lambda group_id: 0,
        )
        service = GroupPermissionsApiService(
            db=None,
            repository=repository,
            permission_service=SimpleNamespace(),
        )

        with pytest.raises(GroupPermissionsApiDomainError) as exc_info:
            service.create_permission_override(
                user_id=10,
                permission_id=5,
                override_type="grant",
                reason=None,
                expires_hours=None,
                granted_by_user_id=1,
                granted_by_username="admin",
            )

        assert exc_info.value.status_code == 400
