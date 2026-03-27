from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.roles import Roles
from app.core.security import require_roles


@pytest.mark.unit
class TestRequireRolesNormalization:
    def test_nested_list_argument_is_flattened(self):
        dependency = require_roles(["Admin", "Doctor"])
        current_user = SimpleNamespace(
            id=1,
            username="test_admin",
            role="Admin",
            is_superuser=False,
        )

        assert dependency(current_user=current_user, db=SimpleNamespace()) is current_user

    def test_roles_enum_argument_is_flattened(self):
        dependency = require_roles([Roles.ADMIN, Roles.DOCTOR])
        current_user = SimpleNamespace(
            id=2,
            username="test_doctor",
            role=Roles.DOCTOR,
            is_superuser=False,
        )

        assert dependency(current_user=current_user, db=SimpleNamespace()) is current_user
