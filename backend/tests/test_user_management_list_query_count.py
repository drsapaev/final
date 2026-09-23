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

    db_session.flush()
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

    assert total == 6
    assert {user["id"] for user in users} == expected_ids
    assert {user["full_name"] for user in users} == {
        f"SYNTHETIC-{index}" for index in range(6)
    }
    assert len(statements) <= 4
