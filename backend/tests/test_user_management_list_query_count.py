"""Keep the admin user list query count independent of page size."""

from sqlalchemy import event

from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user_management import UserSearchRequest
from app.services.user_management_service import UserManagementService


def test_search_users_loads_page_profiles_without_per_user_queries(db_session):
    expected_ids = set()
    for index in range(6):
        user = User(
            username=f"synthetic_user_{index}",
            email=f"synthetic_{index}@example.invalid",
            hashed_password="unused-in-this-test",
            role="Admin",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()
        expected_ids.add(user.id)
        db_session.add(UserProfile(user_id=user.id, full_name=f"SYNTHETIC-{index}"))

    user_without_profile = User(
        username="synthetic_user_without_profile",
        email="synthetic_without_profile@example.invalid",
        hashed_password="unused-in-this-test",
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user_without_profile)
    db_session.flush()
    expected_ids.add(user_without_profile.id)
    db_session.expunge_all()

    statements = []
    engine = db_session.get_bind().engine

    def count_selects(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        users, total = UserManagementService().search_users(
            db_session, UserSearchRequest(page=1, per_page=20)
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert total == 7
    assert {user["id"] for user in users} == expected_ids
    users_with_profiles = [user for user in users if "full_name" in user]
    assert {user["full_name"] for user in users_with_profiles} == {
        f"SYNTHETIC-{index}" for index in range(6)
    }
    assert next(user for user in users if user["id"] == user_without_profile.id) == {
        "id": user_without_profile.id,
        "username": "synthetic_user_without_profile",
        "email": "synthetic_without_profile@example.invalid",
        "role": "Admin",
        "is_active": True,
        "is_superuser": False,
        "created_at": user_without_profile.created_at,
        "updated_at": user_without_profile.updated_at,
    }
    assert len(statements) == 3
