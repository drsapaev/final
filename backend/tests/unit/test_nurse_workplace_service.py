"""NURSE-V2 N2-2 — NurseWorkplaceApiService boundary tests (SQLite).

Owner's required list (design-GO 2026-09-19):
- assignment foreign keys / referential sanity;
- several Nurses -> one QueueResource allowed;
- one Nurse -> several QueueResources allowed;
- a second ACTIVE assignment of the same pair is rejected (the DB-level
  partial unique is proven on PostgreSQL by the migration test; here the
  boundary check gives the API its deterministic 409);
- an inactive assignment can be replaced by a new active one;
- invalid/inactive QueueResource is rejected at the assignment boundary;
- review P2-1: deactivation is an atomic guarded UPDATE — under an
  interleaved concurrent flip exactly ONE request wins, the loser gets
  409 (not a second 200).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import QueueResource
from app.models.user import User
from app.services.nurse_workplace_api_service import (
    NurseWorkplaceApiDomainError,
    NurseWorkplaceApiService,
)


@pytest.fixture()
def session():
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()
    try:
        os.unlink(path)
    except OSError:
        pass


def _user(session, username: str, role: str = "Nurse", active: bool = True) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
        role=role,
        is_active=active,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    return user


def _resource(session, code: str, active: bool = True) -> QueueResource:
    resource = QueueResource(
        code=code,
        queue_tag=f"tag_{code}",
        display_name=f"Resource {code}",
        active=active,
        start_number_online=1,
        max_online_per_day=15,
        default_cabinet=f"c{code[-1]}",
    )
    session.add(resource)
    session.commit()
    return resource


def _svc(session) -> NurseWorkplaceApiService:
    return NurseWorkplaceApiService(session)


# ---------------- creation boundary ----------------


def test_create_assignment_happy_path(session) -> None:
    nurse = _user(session, "nurse_a")
    resource = _resource(session, "procedures")
    data = _svc(session).create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="5"
    )
    assert data["user_id"] == nurse.id
    assert data["queue_resource_id"] == resource.id
    assert data["is_active"] is True
    assert data["cabinet_override"] == "5"
    assert data["effective_cabinet"] == "5"
    assert data["user_username"] == "nurse_a"
    assert data["resource_code"] == "procedures"
    row = session.query(NurseWorkplaceAssignment).one()
    assert row.user_id == nurse.id and row.queue_resource_id == resource.id


def test_cabinet_override_null_falls_back_to_resource_default(session) -> None:
    nurse = _user(session, "nurse_b")
    resource = _resource(session, "ecg")  # default_cabinet "c"
    data = _svc(session).create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override=None
    )
    assert data["effective_cabinet"] == resource.default_cabinet


def test_create_rejects_unknown_user_with_404(session) -> None:
    resource = _resource(session, "procedures")
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).create_assignment(
            user_id=999999, queue_resource_id=resource.id, cabinet_override=None
        )
    assert exc.value.status_code == 404


def test_create_rejects_unknown_resource_with_404(session) -> None:
    nurse = _user(session, "nurse_c")
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).create_assignment(
            user_id=nurse.id, queue_resource_id=999999, cabinet_override=None
        )
    assert exc.value.status_code == 404


def test_create_rejects_non_nurse_role_with_400(session) -> None:
    registrar = _user(session, "reg_1", role="Registrar")
    resource = _resource(session, "procedures")
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).create_assignment(
            user_id=registrar.id, queue_resource_id=resource.id, cabinet_override=None
        )
    assert exc.value.status_code == 400


def test_create_rejects_deactivated_user_with_400(session) -> None:
    inactive_nurse = _user(session, "nurse_off", active=False)
    resource = _resource(session, "procedures")
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).create_assignment(
            user_id=inactive_nurse.id,
            queue_resource_id=resource.id,
            cabinet_override=None,
        )
    assert exc.value.status_code == 400


def test_create_rejects_inactive_resource_with_400(session) -> None:
    nurse = _user(session, "nurse_d")
    resource = _resource(session, "dead", active=False)
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).create_assignment(
            user_id=nurse.id, queue_resource_id=resource.id, cabinet_override=None
        )
    assert exc.value.status_code == 400


# ---------------- D2 multiplicity ----------------


def test_several_nurses_one_resource_allowed(session) -> None:
    nurse_a = _user(session, "nurse_a")
    nurse_b = _user(session, "nurse_b")
    resource = _resource(session, "procedures")
    svc = _svc(session)
    svc.create_assignment(
        user_id=nurse_a.id, queue_resource_id=resource.id, cabinet_override="5"
    )
    svc.create_assignment(
        user_id=nurse_b.id, queue_resource_id=resource.id, cabinet_override="6"
    )
    assert session.query(NurseWorkplaceAssignment).count() == 2


def test_one_nurse_several_resources_allowed(session) -> None:
    nurse = _user(session, "nurse_a")
    procedures = _resource(session, "procedures")
    ecg = _resource(session, "ecg")
    svc = _svc(session)
    svc.create_assignment(
        user_id=nurse.id, queue_resource_id=procedures.id, cabinet_override="5"
    )
    svc.create_assignment(
        user_id=nurse.id, queue_resource_id=ecg.id, cabinet_override="3"
    )
    assert session.query(NurseWorkplaceAssignment).count() == 2


def test_second_active_assignment_of_same_pair_rejected_with_409(session) -> None:
    nurse = _user(session, "nurse_a")
    resource = _resource(session, "procedures")
    svc = _svc(session)
    svc.create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="5"
    )
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        svc.create_assignment(
            user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="7"
        )
    assert exc.value.status_code == 409


def test_inactive_assignment_can_be_replaced_by_new_active(session) -> None:
    nurse = _user(session, "nurse_a")
    resource = _resource(session, "procedures")
    svc = _svc(session)
    first = svc.create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="5"
    )
    svc.deactivate_assignment(first["id"])
    # same pair, new active row — allowed (the DB partial unique is
    # WHERE is_active; the history row stays)
    second = svc.create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="7"
    )
    assert second["is_active"] is True
    rows = (
        session.query(NurseWorkplaceAssignment)
        .order_by(NurseWorkplaceAssignment.id)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].is_active is False
    assert rows[1].is_active is True


# ---------------- read / deactivate ----------------


def test_get_assignment_404_for_missing(session) -> None:
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).get_assignment(424242)
    assert exc.value.status_code == 404


def test_deactivate_assignment_404_for_missing(session) -> None:
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        _svc(session).deactivate_assignment(424242)
    assert exc.value.status_code == 404


def test_deactivate_twice_returns_409(session) -> None:
    nurse = _user(session, "nurse_a")
    resource = _resource(session, "procedures")
    svc = _svc(session)
    data = svc.create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override=None
    )
    deactivated = svc.deactivate_assignment(data["id"])
    assert deactivated["is_active"] is False
    with pytest.raises(NurseWorkplaceApiDomainError) as exc:
        svc.deactivate_assignment(data["id"])
    assert exc.value.status_code == 409


def test_deactivate_atomic_under_interleaved_concurrent_flip(session) -> None:
    """Review P2-1: exactly ONE deactivate may win; the loser gets 409.

    Race simulation — the interleave where the previous read-check-write
    version answered a second 200: a second writer flips the row in the
    window between this request's observation and its write. The hook
    fires right before the service's UPDATE reaches the DB and flips
    the row through a SEPARATE raw connection (the "concurrent winner").
    The guarded atomic UPDATE must then match 0 rows and answer 409.
    """
    import sqlite3

    from sqlalchemy import event

    nurse = _user(session, "nurse_race")
    resource = _resource(session, "procedures")
    svc = _svc(session)
    data = svc.create_assignment(
        user_id=nurse.id, queue_resource_id=resource.id, cabinet_override="5"
    )
    assignment_id = data["id"]

    engine = session.get_bind()
    db_path = engine.url.database
    flipped: list[bool] = []

    @event.listens_for(engine, "before_cursor_execute")
    def concurrent_winner(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.upper().startswith("UPDATE")
            and "nurse_workplace_assignments" in statement
            and not flipped
        ):
            flipped.append(True)
            raw = sqlite3.connect(db_path)
            try:
                raw.execute(
                    "UPDATE nurse_workplace_assignments SET is_active = 0 "
                    "WHERE id = ?",
                    (assignment_id,),
                )
                raw.commit()
            finally:
                raw.close()

    try:
        with pytest.raises(NurseWorkplaceApiDomainError) as exc:
            svc.deactivate_assignment(assignment_id)
    finally:
        event.remove(engine, "before_cursor_execute", concurrent_winner)

    assert flipped, "race hook never fired — interleave not exercised"
    assert (
        exc.value.status_code == 409
    ), "the loser of a concurrent deactivate must observe 409, not 200"
    row = session.get(NurseWorkplaceAssignment, assignment_id)
    assert row is not None and row.is_active is False
    assert session.query(NurseWorkplaceAssignment).count() == 1


def test_list_filters_and_total(session) -> None:
    nurse_a = _user(session, "nurse_a")
    nurse_b = _user(session, "nurse_b")
    procedures = _resource(session, "procedures")
    ecg = _resource(session, "ecg")
    svc = _svc(session)
    svc.create_assignment(
        user_id=nurse_a.id, queue_resource_id=procedures.id, cabinet_override="5"
    )
    svc.create_assignment(
        user_id=nurse_a.id, queue_resource_id=ecg.id, cabinet_override="3"
    )
    svc.create_assignment(
        user_id=nurse_b.id, queue_resource_id=procedures.id, cabinet_override="6"
    )
    items, total = svc.list_assignments()
    assert total == 3
    items, total = svc.list_assignments(user_id=nurse_a.id)
    assert total == 2 and all(i["user_id"] == nurse_a.id for i in items)
    items, total = svc.list_assignments(queue_resource_id=procedures.id)
    assert total == 2
    items, total = svc.list_assignments(active=True)
    assert total == 3
    svc.deactivate_assignment(items[0]["id"])
    items, total = svc.list_assignments(active=False)
    assert total == 1 and items[0]["is_active"] is False
