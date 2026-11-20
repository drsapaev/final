"""PostgreSQL HTTP regressions for admin user mutation authorization races."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.user import User
from app.models.user_profile import UserProfile

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_engine():
    ci = os.environ.get("CI", "").lower() == "true"
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires a disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL")
        pytest.skip("requires PostgreSQL")
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")

    schema = "test_admin_actor_race_" + uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=12,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
    try:
        import app.db.base  # noqa: F401

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.fixture
def pg_http_client(pg_engine):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    previous_override = app.dependency_overrides.get(get_db)

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


def _create_user(pg_engine, *, role="Patient", full_name=None, is_superuser=False):
    username = f"race_{uuid4().hex}"
    email = f"{uuid4().hex}@example.test"
    name = full_name or f"Name {username}"
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(
            username=username,
            email=email,
            full_name=name,
            hashed_password="not-used-by-these-tests",
            role=role,
            is_active=True,
            is_superuser=is_superuser,
            auth_epoch=0,
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id, full_name=name))
        db.commit()
        return {
            "id": user.id,
            "username": username,
            "role": role,
            "is_superuser": is_superuser,
            "auth_epoch": 0,
        }


def _authorization(user):
    from app.services.authentication_service import authentication_service

    token = authentication_service.create_access_token(
        {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "is_active": True,
            "is_superuser": user["is_superuser"],
            "auth_epoch": user["auth_epoch"],
        }
    )
    return {"Authorization": f"Bearer {token}"}, token


def _isolated_http_request(method, path, *, headers, json=None):
    """Use a separate TestClient portal for requests that must overlap."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        return getattr(client, method)(path, headers=headers, json=json)


def _assert_waiting(engine, backend_pids):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            blocked = [
                connection.execute(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
                ).scalar_one()
                for pid in backend_pids
            ]
        if all(count > 0 for count in blocked):
            return
        time.sleep(0.02)
    raise AssertionError("HTTP worker did not block on the orchestrating row lock")


def _run_behind_user_lock(pg_engine, user_id, calls, *, before_release=None):
    """Run HTTP calls only after proving their real PG sessions hit a row lock."""
    from sqlalchemy import event

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    main_thread = threading.get_ident()
    pids = Queue()
    seen = set()
    seen_lock = threading.Lock()

    def capture_user_lock(connection, _cursor, statement, _params, _context, _many):
        sql = statement.lower()
        if (
            threading.get_ident() == main_thread
            or "from users" not in sql
            or "for no key update" not in sql
        ):
            return
        driver_connection = connection.connection.driver_connection
        pid = (
            driver_connection.info.backend_pid
            if hasattr(driver_connection, "info")
            else driver_connection.get_backend_pid()
        )
        with seen_lock:
            if pid not in seen:
                seen.add(pid)
                pids.put(pid)

    event.listen(pg_engine, "before_cursor_execute", capture_user_lock)
    try:
        with factory() as gate, ThreadPoolExecutor(max_workers=len(calls)) as executor:
            gate.query(User).filter_by(id=user_id).with_for_update(key_share=True).one()
            futures = [executor.submit(call) for call in calls]
            backend_pids = [pids.get(timeout=10) for _ in calls]
            _assert_waiting(pg_engine, backend_pids)
            if before_release is not None:
                before_release(gate)
            gate.commit()
            return [future.result(timeout=20) for future in futures]
    finally:
        event.remove(pg_engine, "before_cursor_execute", capture_user_lock)


@pytest.mark.parametrize("revocation", ["inactive", "epoch"])
def test_create_rejects_admin_state_changed_after_dependency_check(
    pg_engine, pg_http_client, revocation
):
    actor = _create_user(pg_engine, role="Admin")
    headers, _token = _authorization(actor)
    payload = {
        "username": f"created_{uuid4().hex}",
        "email": f"{uuid4().hex}@example.test",
        "".join(('pass', 'word')): "ValidPassword123",
        "role": "Patient",
        "full_name": "Must not be created",
    }

    def change_actor_before_lock(gate):
        live_actor = gate.query(User).filter_by(id=actor["id"]).one()
        if revocation == "inactive":
            live_actor.is_active = False
        else:
            live_actor.auth_epoch += 1
        gate.flush()

    (response,) = _run_behind_user_lock(
        pg_engine,
        actor["id"],
        [
            lambda: pg_http_client.post(
                "/api/v1/users/users", headers=headers, json=payload
            )
        ],
        before_release=change_actor_before_lock,
    )

    assert response.status_code == 401
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(username=payload["username"]).first() is None


def test_update_rejects_exact_bearer_jti_logged_out_while_waiting(
    pg_engine, pg_http_client
):
    target = _create_user(pg_engine, role="Patient", full_name="Before update")
    actor = _create_user(pg_engine, role="Admin")
    headers, _token = _authorization(actor)

    def logout_actor(_gate):
        response = _isolated_http_request(
            "post", "/api/v1/authentication/logout", headers=headers, json={}
        )
        assert response.status_code == 200

    (response,) = _run_behind_user_lock(
        pg_engine,
        target["id"],
        [
            lambda: pg_http_client.put(
                f"/api/v1/users/users/{target['id']}",
                headers=headers,
                json={"full_name": "Should not commit"},
            )
        ],
        before_release=logout_actor,
    )

    assert response.status_code == 401
    with Session(pg_engine) as db:
        live_target = db.query(User).filter_by(id=target["id"]).one()
        assert live_target.full_name == "Before update"


def test_delete_locks_transfer_recipient_and_rejects_deactivated_actor(
    pg_engine, pg_http_client
):
    recipient = _create_user(pg_engine, role="Patient")
    target = _create_user(pg_engine, role="Patient")
    actor = _create_user(pg_engine, role="Admin")
    other_admin = _create_user(pg_engine, role="Admin")
    actor_headers, _token = _authorization(actor)
    other_headers, _token = _authorization(other_admin)

    def deactivate_actor(_gate):
        response = _isolated_http_request(
            "put",
            f"/api/v1/users/users/{actor['id']}",
            headers=other_headers,
            json={"is_active": False},
        )
        assert response.status_code == 200

    (response,) = _run_behind_user_lock(
        pg_engine,
        recipient["id"],
        [
            lambda: pg_http_client.delete(
                f"/api/v1/users/users/{target['id']}?transfer_to={recipient['id']}",
                headers=actor_headers,
            )
        ],
        before_release=deactivate_actor,
    )

    assert response.status_code == 401
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(id=target["id"]).one_or_none() is not None
        live_actor = db.query(User).filter_by(id=actor["id"]).one()
        assert live_actor.is_active is False


def test_update_rechecks_live_admin_role_after_wait(pg_engine, pg_http_client):
    target = _create_user(pg_engine, role="Patient", full_name="Before role check")
    actor = _create_user(pg_engine, role="Admin")
    headers, _token = _authorization(actor)

    def remove_admin_role(gate):
        live_actor = gate.query(User).filter_by(id=actor["id"]).one()
        # Keep the signed epoch unchanged to exercise the separate RBAC check.
        live_actor.role = "Nurse"
        gate.flush()

    (response,) = _run_behind_user_lock(
        pg_engine,
        target["id"],
        [
            lambda: pg_http_client.put(
                f"/api/v1/users/users/{target['id']}",
                headers=headers,
                json={"full_name": "Should not commit"},
            )
        ],
        before_release=remove_admin_role,
    )

    assert response.status_code == 403
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(id=target["id"]).one().full_name == "Before role check"


def test_superadmin_role_without_flag_is_denied_after_wait(
    pg_engine, pg_http_client
):
    target = _create_user(pg_engine, role="Patient", full_name="Before SuperAdmin edit")
    actor = _create_user(pg_engine, role="Admin")
    headers, _token = _authorization(actor)

    def change_role_without_superuser(gate):
        live_actor = gate.query(User).filter_by(id=actor["id"]).one()
        # Keep auth_epoch unchanged to exercise the separate RBAC recheck.
        live_actor.role = "SuperAdmin"
        gate.flush()

    (response,) = _run_behind_user_lock(
        pg_engine,
        target["id"],
        [
            lambda: pg_http_client.put(
                f"/api/v1/users/users/{target['id']}",
                headers=headers,
                json={"full_name": "Must remain unchanged"},
            )
        ],
        before_release=change_role_without_superuser,
    )

    assert response.status_code == 403
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(id=target["id"]).one().full_name == "Before SuperAdmin edit"


def test_update_rechecks_bearer_expiry_after_wait(pg_engine, pg_http_client, monkeypatch):
    import app.services.profile_contact_security as bearer_security

    target = _create_user(pg_engine, role="Patient", full_name="Before expiry check")
    actor = _create_user(pg_engine, role="Admin")
    headers, token = _authorization(actor)
    import jwt
    from app.core.config import settings

    claims = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    fake_clock = {"now": time.time()}
    monkeypatch.setattr(
        bearer_security,
        "time",
        type("Clock", (), {"time": staticmethod(lambda: fake_clock["now"])})(),
    )

    def expire_after_dependency(_gate):
        fake_clock["now"] = claims["exp"] + 1

    (response,) = _run_behind_user_lock(
        pg_engine,
        target["id"],
        [
            lambda: pg_http_client.put(
                f"/api/v1/users/users/{target['id']}",
                headers=headers,
                json={"full_name": "Should not commit"},
            )
        ],
        before_release=expire_after_dependency,
    )

    assert response.status_code == 401
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(id=target["id"]).one().full_name == "Before expiry check"


def test_update_rolls_back_if_bearer_expires_before_commit(
    pg_engine, pg_http_client, monkeypatch
):
    import jwt

    import app.services.profile_contact_security as bearer_security
    import app.api.v1.endpoints.user_management._users as user_routes
    from app.core.config import settings

    target = _create_user(pg_engine, role="Patient", full_name="Before commit expiry")
    actor = _create_user(pg_engine, role="Admin")
    headers, token = _authorization(actor)
    claims = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    fake_clock = {"now": time.time()}
    monkeypatch.setattr(
        bearer_security,
        "time",
        type("Clock", (), {"time": staticmethod(lambda: fake_clock["now"])})(),
    )

    service = user_routes.get_user_management_service()
    original_update = service.update_user

    def expire_before_commit(db, user_id, user_data, updated_by, *, before_commit=None):
        def guarded_commit():
            fake_clock["now"] = claims["exp"] + 1
            before_commit()

        return original_update(
            db,
            user_id,
            user_data,
            updated_by,
            before_commit=guarded_commit,
        )

    monkeypatch.setattr(service, "update_user", expire_before_commit)
    monkeypatch.setattr(user_routes, "get_user_management_service", lambda: service)

    response = pg_http_client.put(
        f"/api/v1/users/users/{target['id']}",
        headers=headers,
        json={"full_name": "Must roll back"},
    )

    assert response.status_code == 401
    with Session(pg_engine) as db:
        assert db.query(User).filter_by(id=target["id"]).one().full_name == "Before commit expiry"


def test_admin_can_edit_self_and_mutually_edit_admins_without_deadlock(
    pg_engine, pg_http_client
):
    first = _create_user(pg_engine, role="Admin", full_name="First admin")
    second = _create_user(pg_engine, role="Admin", full_name="Second admin")
    first_headers, _first_token = _authorization(first)
    second_headers, _second_token = _authorization(second)

    self_edit = pg_http_client.put(
        f"/api/v1/users/users/{first['id']}",
        headers=first_headers,
        json={"full_name": "First self edit"},
    )
    assert self_edit.status_code == 200

    calls = [
        lambda: _isolated_http_request(
            "put",
            f"/api/v1/users/users/{second['id']}",
            headers=first_headers,
            json={"full_name": "Edited by first"},
        ),
        lambda: _isolated_http_request(
            "put",
            f"/api/v1/users/users/{first['id']}",
            headers=second_headers,
            json={"full_name": "Edited by second"},
        ),
    ]
    responses = _run_behind_user_lock(pg_engine, first["id"], calls)
    assert [response.status_code for response in responses] == [200, 200]


def test_superuser_with_non_admin_role_keeps_dependency_access(
    pg_engine, pg_http_client
):
    target = _create_user(pg_engine, role="Patient", full_name="Before superuser edit")
    superuser = _create_user(
        pg_engine, role="Nurse", is_superuser=True
    )
    headers, _token = _authorization(superuser)

    response = pg_http_client.put(
        f"/api/v1/users/users/{target['id']}",
        headers=headers,
        json={"full_name": "Edited by superuser"},
    )

    assert response.status_code == 200


def test_lowercase_admin_role_keeps_case_insensitive_dependency_access(
    pg_engine, pg_http_client
):
    target = _create_user(pg_engine, role="Patient", full_name="Before lowercase edit")
    actor = _create_user(pg_engine, role="admin")
    headers, _token = _authorization(actor)

    response = pg_http_client.put(
        f"/api/v1/users/users/{target['id']}",
        headers=headers,
        json={"full_name": "Edited by lowercase admin"},
    )

    assert response.status_code == 200
