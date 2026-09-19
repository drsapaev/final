"""NURSE-V2 N2-2 — ServiceExecution model pins (SQLite).

Owner's required list (design-GO 2026-09-19):
- ServiceExecution performer fields reference real users (FK shape;
  the PG-level enforcement is proven by the migration test);
- one attempt ordinal per VisitService (UNIQUE — plain constraint,
  works on SQLite);
- completed/incomplete history is never overwritten — a retry creates a
  NEW attempt row, the old row keeps its terminal state;
- creating/completing a ServiceExecution does NOT close the Visit
  ("выполнить услугу" != "закрыть визит");
- defaults: attempt_no = 1, status = 'in_progress';
- review P2-2: the D1 FINAL status vocabulary and the 1-based attempt
  ordinal are enforced by portable CHECK constraints in the ORM —
  invalid statuses / non-positive attempt numbers are rejected at
  flush time on SQLite too (mirrored in migration 0072).
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest
from sqlalchemy import CheckConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.service_execution import (
    SERVICE_EXECUTION_STATUSES,
    ServiceExecution,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
)
from app.models.visit import Visit, VisitService


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


def _visit_with_service(session, name: str = "Услуга") -> tuple[Visit, VisitService]:
    visit = Visit(patient_id=1, status="open", source="desk")
    session.add(visit)
    session.flush()
    # service_id is NOT NULL on the table; the id value itself is
    # irrelevant for these model-level tests (SQLite does not enforce
    # the FK by default)
    visit_service = VisitService(visit_id=visit.id, service_id=101, name=name, qty=1)
    session.add(visit_service)
    session.flush()
    return visit, visit_service


def _execution(
    session,
    visit_service: VisitService,
    *,
    attempt_no: int = 1,
    status: str = STATUS_IN_PROGRESS,
    started_by: int = 10,
) -> ServiceExecution:
    execution = ServiceExecution(
        visit_service_id=visit_service.id,
        queue_entry_id=None,
        attempt_no=attempt_no,
        status=status,
        started_by_user_id=started_by,
        started_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )
    session.add(execution)
    session.flush()
    return execution


def test_status_vocabulary_first_stage() -> None:
    assert set(SERVICE_EXECUTION_STATUSES) == {
        "in_progress",
        "completed",
        "incomplete",
        "cancelled",
    }
    # 'no_show' stays a queue-level state — deliberately absent here
    assert "no_show" not in SERVICE_EXECUTION_STATUSES


# ---------------- review P2-2: DB-level vocabulary / ordinal CHECKs ----------------


@pytest.mark.parametrize(
    "bad_status",
    ["foo", "started", "in-progress", "IN_PROGRESS", "no_show", ""],
)
def test_status_outside_d1_vocabulary_rejected_by_check(session, bad_status) -> None:
    """A typo'd or unknown status must not be insertable — the CHECK
    constraint is what stops it from bypassing the one-active-execution
    model (the partial unique index guards only the literal
    'in_progress')."""
    visit, visit_service = _visit_with_service(session)
    with pytest.raises(IntegrityError):
        _execution(session, visit_service, status=bad_status)
    session.rollback()


@pytest.mark.parametrize("bad_attempt_no", [0, -1, -5])
def test_non_positive_attempt_no_rejected_by_check(session, bad_attempt_no) -> None:
    """Attempts are 1-based ordinals (D1 FINAL: a retry after 'incomplete'
    creates attempt_no = previous + 1); zero and negatives are invalid."""
    visit, visit_service = _visit_with_service(session)
    with pytest.raises(IntegrityError):
        _execution(session, visit_service, attempt_no=bad_attempt_no)
    session.rollback()


def test_check_constraints_declared_in_table_args() -> None:
    """The vocabulary/ordinal CHECKs are portable table-level constraints
    (mirrored in migration 0072 — the 0068 CHECK precedent)."""
    checks = {
        c.name: c.sqltext.text if hasattr(c.sqltext, "text") else str(c.sqltext)
        for c in ServiceExecution.__table__.constraints
        if isinstance(c, CheckConstraint)
    }
    assert "ck_service_executions_status" in checks
    assert "ck_service_executions_attempt_no" in checks


def test_defaults_attempt_and_status(session) -> None:
    visit, visit_service = _visit_with_service(session)
    execution = ServiceExecution(
        visit_service_id=visit_service.id,
        started_by_user_id=10,
        started_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )
    session.add(execution)
    session.flush()
    assert execution.attempt_no == 1
    assert execution.status == STATUS_IN_PROGRESS
    assert execution.queue_entry_id is None
    assert execution.performed_by_user_id is None
    assert execution.completed_at is None


def test_performer_columns_exist_with_user_fks() -> None:
    columns = {c.name for c in ServiceExecution.__table__.columns}
    assert {
        "visit_service_id",
        "queue_entry_id",
        "attempt_no",
        "status",
        "started_by_user_id",
        "started_at",
        "performed_by_user_id",
        "completed_at",
        "incomplete_reason",
    } <= columns
    fk_targets = {
        (fk.parent.name, fk.column.table.name)
        for fk in ServiceExecution.__table__.foreign_keys
    }
    assert ("visit_service_id", "visit_services") in fk_targets
    assert ("queue_entry_id", "queue_entries") in fk_targets
    assert ("started_by_user_id", "users") in fk_targets
    assert ("performed_by_user_id", "users") in fk_targets


def test_duplicate_attempt_no_rejected(session) -> None:
    visit, visit_service = _visit_with_service(session)
    _execution(session, visit_service, attempt_no=1)
    with pytest.raises(IntegrityError):
        _execution(session, visit_service, attempt_no=1)
    session.rollback()


def test_retry_after_incomplete_creates_new_attempt_and_keeps_history(
    session,
) -> None:
    visit, visit_service = _visit_with_service(session)
    first = _execution(session, visit_service, attempt_no=1)
    # first attempt ends incomplete, performed by nurse 10
    first.status = "incomplete"
    first.incomplete_reason = "пациент прервал процедуру"
    session.flush()

    # retry: NEW row, attempt 2 — the old row is never overwritten
    second = _execution(session, visit_service, attempt_no=2)
    session.flush()

    rows = (
        session.query(ServiceExecution)
        .filter(ServiceExecution.visit_service_id == visit_service.id)
        .order_by(ServiceExecution.attempt_no)
        .all()
    )
    assert [r.attempt_no for r in rows] == [1, 2]
    assert rows[0].status == "incomplete"
    assert rows[0].incomplete_reason == "пациент прервал процедуру"
    assert rows[1].status == STATUS_IN_PROGRESS
    assert rows[1] is second and rows[0] is first


def test_completion_does_not_close_the_visit(session) -> None:
    visit, visit_service = _visit_with_service(session)
    execution = _execution(session, visit_service)
    execution.status = STATUS_COMPLETED
    execution.performed_by_user_id = 11
    execution.completed_at = datetime(2026, 9, 19, 12, 30, tzinfo=UTC)
    session.commit()

    session.refresh(visit)
    assert visit.status == "open", (
        "completing a ServiceExecution must NOT close the Visit — "
        "'выполнить услугу' != 'закрыть визит' (owner contract)"
    )


def test_qty_is_not_the_execution_count(session) -> None:
    """qty=5 does NOT mean five executions — executions are created by
    actual serving, never derived from the billed quantity (D1 FINAL)."""
    visit = Visit(patient_id=1, status="open", source="desk")
    session.add(visit)
    session.flush()
    visit_service = VisitService(
        visit_id=visit.id, service_id=101, name="Процедура", qty=5
    )
    session.add(visit_service)
    session.flush()

    _execution(session, visit_service)

    count = (
        session.query(ServiceExecution)
        .filter(ServiceExecution.visit_service_id == visit_service.id)
        .count()
    )
    assert count == 1, "execution rows are never auto-derived from qty"
