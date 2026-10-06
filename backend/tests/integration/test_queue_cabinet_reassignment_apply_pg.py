"""Disposable PostgreSQL proof for safe same-day cabinet reassignment."""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models import (  # noqa: F401 - register all mapped tables
    AuditLog,
    Doctor,
    Patient,
    QueueResource,
    Service,
    ServiceExecution,
    User,
    Visit,
    VisitService,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)

_PG_TIMEOUT_MS = 12_000
_CLINIC_DAY = date(2026, 10, 6)


@pytest.fixture
def cabinet_apply_engine(monkeypatch):
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("cabinet reassignment proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_qcab_apply_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                f"-cstatement_timeout={_PG_TIMEOUT_MS} "
                f"-clock_timeout={_PG_TIMEOUT_MS} "
                "-cdeadlock_timeout=500ms"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: _CLINIC_DAY,
        )
        yield engine, schema
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def _seed_queues(
    engine,
    *,
    owner_types: tuple[str, ...] = ("doctor",),
    statuses: tuple[str, ...] | None = None,
    execution_index: int | None = None,
) -> list[dict]:
    """Seed synthetic owners, queues and optional blocker rows in one commit."""
    result = []
    suffix = uuid.uuid4().hex[:10]
    with Session(engine) as db:
        patient = Patient(
            last_name=f"SYNTHETIC-{suffix}",
            first_name="SYNTHETIC-Queue Patient",
        )
        db.add(patient)
        db.flush()
        service = Service(
            name=f"SYNTHETIC Cabinet Service {suffix}",
            code=f"cabinet-{suffix}",
            price=1,
            requires_doctor=False,
        )
        db.add(service)
        db.flush()

        for index, owner_type in enumerate(owner_types):
            owner_user_id = None
            if owner_type == "doctor":
                user = User(
                    username=f"cabinet_apply_{suffix}_{index}",
                    full_name=f"SYNTHETIC Doctor {index}",
                    hashed_password="!disabled:test",
                    role="Doctor",
                    is_active=True,
                )
                db.add(user)
                db.flush()
                owner_user_id = user.id
                doctor = Doctor(
                    user_id=user.id,
                    specialty="cardiology",
                    cabinet=f"90{index}",
                    active=True,
                )
                db.add(doctor)
                db.flush()
                queue = DailyQueue(
                    day=_CLINIC_DAY,
                    specialist_id=doctor.id,
                    cabinet_number=f"10{index}",
                    active=True,
                )
                owner_id = doctor.id
                queue_tag = None
                owner_default = doctor.cabinet
            elif owner_type == "resource":
                resource = QueueResource(
                    code=f"cabinet_resource_{suffix}_{index}",
                    queue_tag=f"cabinet_resource_{suffix}_{index}",
                    display_name=f"SYNTHETIC Resource {index}",
                    default_cabinet=f"80{index}",
                    active=True,
                )
                db.add(resource)
                db.flush()
                queue = DailyQueue(
                    day=_CLINIC_DAY,
                    queue_resource_id=resource.id,
                    queue_tag=resource.queue_tag,
                    cabinet_number=f"20{index}",
                    active=True,
                )
                owner_id = resource.id
                queue_tag = resource.queue_tag
                owner_default = resource.default_cabinet
            else:  # pragma: no cover - test construction guard
                raise AssertionError(f"unexpected owner type: {owner_type}")

            db.add(queue)
            db.flush()
            queue_entry = None
            if statuses is not None:
                queue_entry = OnlineQueueEntry(
                    queue_id=queue.id,
                    patient_id=patient.id,
                    number=index + 1,
                    status=statuses[index],
                )
                db.add(queue_entry)
                db.flush()
            if index == execution_index:
                assert queue_entry is not None
                visit = Visit(
                    patient_id=patient.id,
                    doctor_id=None,
                    visit_date=_CLINIC_DAY,
                    department=queue_tag or "cardiology",
                    status="in_progress",
                )
                db.add(visit)
                db.flush()
                queue_entry.visit_id = visit.id
                visit_service = VisitService(
                    visit_id=visit.id,
                    service_id=service.id,
                    name=service.name,
                    qty=1,
                )
                db.add(visit_service)
                db.flush()
                db.add(
                    ServiceExecution(
                        visit_service_id=visit_service.id,
                        queue_entry_id=queue_entry.id,
                        attempt_no=1,
                        status="in_progress",
                        started_by_user_id=owner_user_id,
                        started_at=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
                    )
                )
                db.flush()
            result.append(
                {
                    "queue_id": queue.id,
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "old_cabinet": queue.cabinet_number,
                    "default_cabinet": owner_default,
                    "entry_id": queue_entry.id if queue_entry is not None else None,
                }
            )
        db.commit()
    return result


def _target(queue: dict, *, expected_cabinet: str | None = None) -> dict:
    return {
        "queue_id": queue["queue_id"],
        "expected_owner_type": queue["owner_type"],
        "expected_owner_id": queue["owner_id"],
        "expected_cabinet_number": (
            queue["old_cabinet"] if expected_cabinet is None else expected_cabinet
        ),
    }


def _apply(db: Session, targets: list[dict], cabinet: str, request_id: str) -> dict:
    return QueueCabinetManagementApiService(db).apply_cabinet_reassignment(
        targets=targets,
        new_cabinet_number=cabinet,
        reason_code="room_unavailable",
        actor_user_id=1,
        actor_role="Admin",
        request_id=request_id,
    )


def test_preview_and_apply_update_doctor_and_resource_day_rows_only(
    cabinet_apply_engine,
):
    engine, _schema = cabinet_apply_engine
    queues = _seed_queues(engine, owner_types=("doctor", "resource"))
    with Session(engine) as db:
        preview = QueueCabinetManagementApiService(db).preview_cabinet_reassignment(
            queue_ids=[item["queue_id"] for item in queues],
            new_cabinet_number="305",
        )
        assert preview["can_apply"] is True
        assert [item["owner_type"] for item in preview["items"]] == [
            "doctor",
            "resource",
        ]
        result = _apply(
            db,
            [_target(item) for item in queues],
            "305",
            "synthetic-pg-apply-success",
        )

    assert result["changed_queue_ids"] == [item["queue_id"] for item in queues]
    with Session(engine) as verify:
        persisted = [verify.get(DailyQueue, item["queue_id"]) for item in queues]
        assert [item.cabinet_number for item in persisted] == ["305", "305"]
        assert [item.specialist_id for item in persisted] == [
            queues[0]["owner_id"],
            None,
        ]
        assert [item.queue_resource_id for item in persisted] == [
            None,
            queues[1]["owner_id"],
        ]
        assert [item.cabinet_number for item in persisted] != [
            item["default_cabinet"] for item in queues
        ]
        audits = (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .order_by(AuditLog.entity_id)
            .all()
        )
        assert [item.entity_id for item in audits] == [
            item["queue_id"] for item in queues
        ]


def test_stale_batch_returns_409_without_partial_update_or_audit(cabinet_apply_engine):
    engine, _schema = cabinet_apply_engine
    queues = _seed_queues(engine, owner_types=("doctor", "resource"))
    stale_targets = [_target(queues[0]), _target(queues[1], expected_cabinet="stale")]
    with Session(engine) as db, pytest.raises(QueueCabinetManagementDomainError) as exc:
        _apply(db, stale_targets, "306", "synthetic-pg-apply-stale")
    assert exc.value.status_code == 409

    with Session(engine) as verify:
        assert [
            verify.get(DailyQueue, item["queue_id"]).cabinet_number for item in queues
        ] == [item["old_cabinet"] for item in queues]
        assert (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 0
        )


def test_audit_insert_failure_rolls_back_every_target(cabinet_apply_engine):
    engine, schema = cabinet_apply_engine
    queues = _seed_queues(engine, owner_types=("doctor", "resource"))
    with engine.begin() as connection:
        connection.execute(
            text(
                f'CREATE FUNCTION "{schema}".fail_cabinet_audit() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION "
                "'synthetic cabinet audit failure'; END; $$"
            )
        )
        connection.execute(
            text(
                f'CREATE TRIGGER fail_cabinet_audit BEFORE INSERT ON "{schema}".audit_logs '
                f'FOR EACH ROW EXECUTE FUNCTION "{schema}".fail_cabinet_audit()'
            )
        )

    with Session(engine) as db, pytest.raises(QueueCabinetManagementDomainError) as exc:
        _apply(
            db,
            [_target(item) for item in queues],
            "307",
            "synthetic-pg-apply-audit-failure",
        )
    assert exc.value.status_code == 500

    with Session(engine) as verify:
        assert [
            verify.get(DailyQueue, item["queue_id"]).cabinet_number for item in queues
        ] == [item["old_cabinet"] for item in queues]
        assert (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 0
        )


@pytest.mark.parametrize(
    ("statuses", "execution_index"),
    [(("called",), None), (("in_progress",), None), (("waiting",), 0)],
)
def test_called_or_active_clinical_state_blocks_reassignment(
    cabinet_apply_engine, statuses, execution_index
):
    engine, _schema = cabinet_apply_engine
    [queue] = _seed_queues(
        engine,
        statuses=statuses,
        execution_index=execution_index,
    )
    with Session(engine) as db, pytest.raises(QueueCabinetManagementDomainError) as exc:
        _apply(db, [_target(queue)], "308", f"synthetic-pg-block-{statuses[0]}")
    assert exc.value.status_code == 409

    with Session(engine) as verify:
        assert (
            verify.get(DailyQueue, queue["queue_id"]).cabinet_number
            == queue["old_cabinet"]
        )
        assert (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 0
        )


def test_concurrent_stale_applications_commit_one_change_and_one_audit(
    cabinet_apply_engine,
):
    engine, _schema = cabinet_apply_engine
    [queue] = _seed_queues(engine)
    barrier = threading.Barrier(2)

    def attempt(cabinet: str, request_id: str):
        with Session(engine) as db:
            barrier.wait(timeout=5)
            try:
                _apply(db, [_target(queue)], cabinet, request_id)
                return "applied"
            except QueueCabinetManagementDomainError as exc:
                return f"rejected:{exc.status_code}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, "309", "synthetic-pg-race-a"),
            executor.submit(attempt, "310", "synthetic-pg-race-b"),
        ]
        outcomes = [future.result(timeout=20) for future in futures]

    assert outcomes.count("applied") == 1
    assert outcomes.count("rejected:409") == 1
    with Session(engine) as verify:
        assert verify.get(DailyQueue, queue["queue_id"]).cabinet_number in {
            "309",
            "310",
        }
        assert (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 1
        )


def test_apply_waits_for_concurrent_call_then_refuses_transfer(cabinet_apply_engine):
    engine, _schema = cabinet_apply_engine
    [queue] = _seed_queues(engine, statuses=("waiting",))
    writer_locked = threading.Event()
    writer_can_commit = threading.Event()
    apply_started = threading.Event()
    apply_backend_pid: list[int] = []
    writer_backend_pid: list[int] = []

    def call_entry():
        with Session(engine) as writer:
            writer_backend_pid.append(
                writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            writer.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.id == queue["entry_id"]
            ).update({OnlineQueueEntry.status: "called"}, synchronize_session=False)
            writer_locked.set()
            if not writer_can_commit.wait(timeout=8):
                raise TimeoutError("the test did not release the queue-entry row lock")
            writer.commit()

    def apply_command():
        with Session(engine) as command:
            apply_backend_pid.append(
                command.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            apply_started.set()
            try:
                _apply(
                    command,
                    [_target(queue)],
                    "311",
                    "synthetic-pg-called-race",
                )
                return "applied"
            except QueueCabinetManagementDomainError as exc:
                return f"rejected:{exc.status_code}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer_future = executor.submit(call_entry)
        assert writer_locked.wait(timeout=5)
        apply_future = executor.submit(apply_command)
        try:
            assert apply_started.wait(timeout=5)
            deadline = time.monotonic() + 6
            blocked_by_writer = False
            while time.monotonic() < deadline:
                with engine.connect() as connection:
                    blockers = connection.execute(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": apply_backend_pid[0]},
                    ).scalar_one()
                if writer_backend_pid[0] in blockers:
                    blocked_by_writer = True
                    break
                if apply_future.done():
                    break
                time.sleep(0.05)
            assert blocked_by_writer, "apply did not wait on the called-entry writer"
        finally:
            writer_can_commit.set()
        writer_future.result(timeout=10)
        assert apply_future.result(timeout=10) == "rejected:409"

    with Session(engine) as verify:
        assert (
            verify.get(DailyQueue, queue["queue_id"]).cabinet_number
            == queue["old_cabinet"]
        )
        assert verify.get(OnlineQueueEntry, queue["entry_id"]).status == "called"
        assert (
            verify.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 0
        )
