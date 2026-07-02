from __future__ import annotations

import pytest

from app.models.role_permission import (
    Permission,
    Role,
    UserGroup,
    group_roles_table,
    user_groups_table,
    user_roles_table,
)


@pytest.mark.integration
def test_group_permissions_endpoints_return_live_group_and_user_data(
    client,
    db_session,
    admin_user,
    auth_headers,
):
    permission = Permission(
        name="QA Group Permission",
        codename="qa.group.permission",
        description="Permission used for group permissions smoke",
        category="qa",
        is_active=True,
    )
    role = Role(
        name="qa_group_role",
        display_name="QA Group Role",
        description="Role used for group permissions smoke",
        level=10,
        is_active=True,
        is_system=False,
    )
    group = UserGroup(
        name="qa_group_permissions",
        display_name="QA Group Permissions",
        description="Group used for smoke verification",
        group_type="custom",
        is_active=True,
    )
    db_session.add_all([permission, role, group])
    db_session.commit()
    db_session.refresh(permission)
    db_session.refresh(role)
    db_session.refresh(group)

    role.permissions.append(permission)
    db_session.commit()

    db_session.execute(
        user_roles_table.insert().values(
            user_id=admin_user.id,
            role_id=role.id,
            assigned_by=admin_user.id,
        )
    )
    db_session.execute(
        user_groups_table.insert().values(
            user_id=admin_user.id,
            group_id=group.id,
            added_by=admin_user.id,
        )
    )
    db_session.execute(
        group_roles_table.insert().values(
            group_id=group.id,
            role_id=role.id,
            assigned_by=admin_user.id,
        )
    )
    db_session.commit()

    groups_response = client.get(
        "/api/v1/admin/permissions/groups",
        headers=auth_headers,
    )
    assert groups_response.status_code == 200, groups_response.text
    groups_body = groups_response.json()
    assert any(
        item["name"] == "qa_group_permissions"
        and item["users_count"] == 1
        and item["roles_count"] == 1
        for item in groups_body
    ), groups_body

    user_permissions_response = client.get(
        f"/api/v1/admin/permissions/users/{admin_user.id}/permissions",
        headers=auth_headers,
    )
    assert user_permissions_response.status_code == 200, user_permissions_response.text
    user_permissions_body = user_permissions_response.json()
    assert user_permissions_body["username"] == admin_user.username
    assert "qa_group_role" in user_permissions_body["roles"]
    assert "qa_group_permissions" in user_permissions_body["groups"]
    assert "qa.group.permission" in user_permissions_body["permissions"]
