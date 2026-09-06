"""QD-2A (queue resource entity) — EXPAND stage regression pins.

Migration 0058_queue_resource_expand is the additive-only first stage of
the QD-2 staged rollout (owner FINAL D-spec 2026-09-06): the
queue_resources routing table + the nullable daily_queues.queue_resource_id
FK + the relaxed daily_queues.specialist_id NULL. Nothing else changes —
no XOR, no uniqueness, no seeds, no synthetic identity deletion, no
runtime switch. Every pre-QD-2 daily_queues row is doctor-owned exactly
as before, and the old production code paths are pinned untouched.

Pins:

- migration contract (scratch SQLite, module-level functions bound via
  Operations/MigrationContext): exact queue_resources shape (columns /
  nullability / server defaults / UNIQUE code + queue_tag), daily_queues
  expansion (nullable FK column + index + relaxed specialist_id),
  loud abort when daily_queues is missing (before any DDL), idempotent
  re-run (already-migrated pass — the 0056/0057 contract), strict
  downgrade (shape restored, doctor data preserved, loud abort when
  doctorless rows exist), PG-only RLS guard is a no-op on SQLite (CI
  proves the statement on the disposable Postgres);
- model world (create_all): QueueResource CRUD + uniqueness + defaults,
  DailyQueue dual-owner persistence with RAW-SQL proofs (identity-map
  proof per QF-1), relationship loading, pre-XOR permissiveness pinned
  DELIBERATELY (both owners / no owner are allowed at this stage — the
  XOR CHECK lands in QD-2D, tightening these pins);
- read schema surface: DailyQueueOut keeps serializing doctor-owned
  queues unchanged (specialist_id int, queue_resource_id None) and
  carries queue_resource_id for resource-owned rows; QueueResourceOut
  round-trips the ORM entity;
- compatibility: get_or_create_daily_queue keeps the doctor-owned
  get-or-create semantics untouched (PR-26 per-doctor ownership).
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.queue_resource import QueueResource
from app.schemas.online_queue import DailyQueueOut, QueueResourceOut
from app.services.queue_service import queue_service

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0058 = (
    BACKEND_ROOT / "alembic" / "versions" / "0058_queue_resource_expand.py"
)

EXPECTED_QUEUE_RESOURCES_COLUMNS = {
    "id",
    "code",
    "queue_tag",
    "display_name",
    "active",
    "start_number_online",
    "max_online_per_day",
    "default_cabinet",
    "created_at",
    "updated_at",
}


# ===================== migration 0058 logic (scratch SQLite) =====================


def _load_migration_0058():
    spec = importlib.util.spec_from_file_location(
        "migration_0058_queue_resource_expand", MIGRATION_0058
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_connection():
    """daily_queues mirroring the baseline-0001 shape for the columns 0058
    touches (day/specialist_id NOT NULL/queue_tag/active) + a doctors
    table behind the specialist FK."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("specialty", sa.String(100), nullable=False),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column(
            "specialist_id", sa.Integer, sa.ForeignKey("doctors.id"), nullable=False
        ),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    metadata.create_all(engine)
    return engine.connect()


def _ops(conn) -> Operations:
    return Operations(MigrationContext.configure(conn))


def _run_upgrade_steps(module, conn) -> None:
    module._create_queue_resources_table(_ops(conn), conn)
    module._enable_queue_resources_rls(_ops(conn), conn)
    module._expand_daily_queues(_ops(conn), conn)


def _queue_namespace(queue: DailyQueue) -> SimpleNamespace:
    """DailyQueueOut-style read validation input: column attributes only.
    The schema's ``specialist: dict | None`` field is fed by endpoints as a
    pre-serialized dict (the ORM relationship object is not a dict) — the
    namespace mirrors that contract while pinning the nullable owner
    columns, which is what QD-2A changes."""
    return SimpleNamespace(
        id=queue.id,
        day=queue.day,
        specialist_id=queue.specialist_id,
        queue_resource_id=queue.queue_resource_id,
        active=queue.active,
        opened_at=queue.opened_at,
        created_at=queue.created_at,
        specialist=None,
        entries=[],
        total_entries=0,
        waiting_count=0,
        served_count=0,
    )


def _seed_doctor(conn) -> int:
    conn.execute(sa.text("INSERT INTO doctors (specialty) VALUES ('cardiology')"))
    return conn.execute(sa.text("SELECT MAX(id) FROM doctors")).scalar_one()


def _seed_daily_queue(conn, doctor_id: int) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_tag, active) "
            "VALUES ('2026-09-06', :sid, 'cardiology_common', 1)"
        ),
        {"sid": doctor_id},
    )
    return conn.execute(sa.text("SELECT MAX(id) FROM daily_queues")).scalar_one()


def _columns(conn, table: str) -> dict[str, dict]:
    return {col["name"]: col for col in sa.inspect(conn).get_columns(table)}


def _insert_resource_row(conn, *, code: str, queue_tag: str) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name) "
            "VALUES (:code, :tag, :name)"
        ),
        {"code": code, "tag": queue_tag, "name": f"Resource {code}"},
    )


# ===================== migration contract =====================


def test_upgrade_creates_queue_resources_table_shape() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        _run_upgrade_steps(module, conn)

        assert sa.inspect(conn).has_table("queue_resources")
        cols = _columns(conn, "queue_resources")
        assert set(cols) == EXPECTED_QUEUE_RESOURCES_COLUMNS
        # NOT NULL contract
        for name in (
            "code",
            "queue_tag",
            "display_name",
            "active",
            "start_number_online",
            "max_online_per_day",
        ):
            assert cols[name]["nullable"] is False, name
        for name in ("default_cabinet", "created_at", "updated_at"):
            assert cols[name]["nullable"] is True, name
        # id index (model index=True parity, baseline convention)
        index_names = {idx["name"] for idx in sa.inspect(conn).get_indexes("queue_resources")}
        assert "ix_queue_resources_id" in index_names


def test_queue_resources_unique_code_and_queue_tag() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        _run_upgrade_steps(module, conn)
        _insert_resource_row(conn, code="lab", queue_tag="lab")

        with pytest.raises(sa.exc.IntegrityError):
            _insert_resource_row(conn, code="lab2", queue_tag="lab")
        with pytest.raises(sa.exc.IntegrityError):
            _insert_resource_row(conn, code="lab", queue_tag="lab2")
        conn.rollback()


def test_queue_resources_server_defaults() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        _run_upgrade_steps(module, conn)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, display_name) "
                "VALUES ('ecg', 'ecg', 'ЭКГ')"
            )
        )
        row = conn.execute(
            sa.text(
                "SELECT active, start_number_online, max_online_per_day, "
                "default_cabinet, created_at FROM queue_resources WHERE code = 'ecg'"
            )
        ).one()
        # 0055 seeded the synthetic Doctors with 1/15 — the carried contract
        assert row[0] == 1 and row[1] == 1 and row[2] == 15
        assert row[3] is None
        assert row[4] is not None  # created_at server default fired


def test_upgrade_adds_nullable_fk_column_and_index() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        doctor_id = _seed_doctor(conn)
        queue_id = _seed_daily_queue(conn, doctor_id)
        _run_upgrade_steps(module, conn)
        _insert_resource_row(conn, code="lab", queue_tag="lab")
        resource_id = conn.execute(
            sa.text("SELECT id FROM queue_resources WHERE code = 'lab'")
        ).scalar_one()

        cols = _columns(conn, "daily_queues")
        assert "queue_resource_id" in cols
        assert cols["queue_resource_id"]["nullable"] is True
        assert cols["specialist_id"]["nullable"] is True

        index_names = {
            idx["name"] for idx in sa.inspect(conn).get_indexes("daily_queues")
        }
        assert "ix_daily_queues_queue_resource_id" in index_names

        # resource-owned row round-trips (SQLite: FK is structural, not enforced)
        conn.execute(
            sa.text(
                "INSERT INTO daily_queues (day, queue_resource_id, queue_tag, active) "
                "VALUES ('2026-09-06', :rid, 'lab', 1)"
            ),
            {"rid": resource_id},
        )
        row = conn.execute(
            sa.text("SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"),
            {"qid": queue_id + 1},
        ).one()
        assert row == (None, resource_id)

        # doctor-owned row untouched by the migration
        legacy = conn.execute(
            sa.text("SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"),
            {"qid": queue_id},
        ).one()
        assert legacy == (doctor_id, None)


def test_upgrade_fk_naming_contract() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        _run_upgrade_steps(module, conn)
        fks = [
            fk
            for fk in sa.inspect(conn).get_foreign_keys("daily_queues")
            if fk.get("referred_table") == "queue_resources"
        ]
        assert len(fks) == 1
        # QD-2D partial-unique/XOR follow-ups + drop_constraint reference these
        assert fks[0]["name"] == "fk_daily_queues_queue_resource_id"
        assert fks[0]["constrained_columns"] == ["queue_resource_id"]
        assert fks[0]["referred_columns"] == ["id"]


def test_upgrade_relaxes_specialist_id_not_null() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        # BEFORE: doctorless insert is impossible (baseline NOT NULL).
        # Savepoint keeps the outer transaction intact — SQLite DDL is
        # transactional, a plain rollback would wipe the whole fixture.
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin_nested():
                conn.execute(
                    sa.text(
                        "INSERT INTO daily_queues (day, queue_tag, active) "
                        "VALUES ('2026-09-06', 'lab', 1)"
                    )
                )

        _run_upgrade_steps(module, conn)

        # AFTER: the QD-2B backfill shape is writable
        conn.execute(
            sa.text(
                "INSERT INTO daily_queues (day, queue_tag, active) "
                "VALUES ('2026-09-06', 'lab', 1)"
            )
        )
        row = conn.execute(
            sa.text("SELECT specialist_id FROM daily_queues WHERE queue_tag = 'lab'")
        ).scalar_one()
        assert row is None


def test_require_daily_queues_loud_abort() -> None:
    module = _load_migration_0058()
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    with engine.connect() as conn:
        with pytest.raises(RuntimeError, match="daily_queues table not found"):
            module._require_daily_queues(conn)


def test_upgrade_idempotent_rerun() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        doctor_id = _seed_doctor(conn)
        _seed_daily_queue(conn, doctor_id)
        _run_upgrade_steps(module, conn)
        _insert_resource_row(conn, code="lab", queue_tag="lab")

        # re-run on the already-migrated shape = no-op, no error, no data loss
        _run_upgrade_steps(module, conn)

        assert sa.inspect(conn).has_table("queue_resources")
        assert _columns(conn, "daily_queues")["queue_resource_id"]["nullable"] is True
        count = conn.execute(sa.text("SELECT COUNT(*) FROM daily_queues")).scalar_one()
        assert count == 1
        assert (
            conn.execute(sa.text("SELECT COUNT(*) FROM queue_resources")).scalar_one()
            == 1
        )


def test_rls_statement_is_postgresql_only_noop_on_sqlite() -> None:
    """ALTER TABLE ... ENABLE ROW LEVEL SECURITY is PG syntax; the module
    guard must skip it on SQLite (CI's disposable Postgres + RLS guard
    step prove the real statement runs there)."""
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        module._create_queue_resources_table(_ops(conn), conn)
        # must not raise on the sqlite dialect
        module._enable_queue_resources_rls(_ops(conn), conn)


def test_downgrade_restores_pre_0058_shape() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        doctor_id = _seed_doctor(conn)
        queue_id = _seed_daily_queue(conn, doctor_id)
        _run_upgrade_steps(module, conn)

        module._revert_daily_queues(_ops(conn), conn)
        module._drop_queue_resources(_ops(conn), conn)

        # shape restored
        assert not sa.inspect(conn).has_table("queue_resources")
        cols = _columns(conn, "daily_queues")
        assert "queue_resource_id" not in cols
        assert cols["specialist_id"]["nullable"] is False
        index_names = {
            idx["name"] for idx in sa.inspect(conn).get_indexes("daily_queues")
        }
        assert "ix_daily_queues_queue_resource_id" not in index_names
        fks = [
            fk
            for fk in sa.inspect(conn).get_foreign_keys("daily_queues")
            if fk.get("referred_table") == "queue_resources"
        ]
        assert fks == []

        # doctorless insert impossible again (savepoint — see above)
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin_nested():
                conn.execute(
                    sa.text(
                        "INSERT INTO daily_queues (day, queue_tag, active) "
                        "VALUES ('2026-09-06', 'lab', 1)"
                    )
                )

        # doctor-owned data preserved across the full cycle (SQLite stores
        # the DATE column as its ISO string)
        row = conn.execute(
            sa.text("SELECT day, specialist_id, queue_tag, active FROM daily_queues WHERE id = :qid"),
            {"qid": queue_id},
        ).one()
        assert row == ("2026-09-06", doctor_id, "cardiology_common", 1)


def test_downgrade_aborts_when_doctorless_rows_exist() -> None:
    module = _load_migration_0058()
    with _scratch_connection() as conn:
        _run_upgrade_steps(module, conn)
        conn.execute(
            sa.text(
                "INSERT INTO daily_queues (day, queue_resource_id, queue_tag, active) "
                "VALUES ('2026-09-06', NULL, 'lab', 1)"
            )
        )

        with pytest.raises(RuntimeError, match="specialist_id IS NULL"):
            module._revert_daily_queues(_ops(conn), conn)

        # abort happened BEFORE any mutation: the expanded shape is intact
        assert _columns(conn, "daily_queues")["queue_resource_id"] is not None
        assert _columns(conn, "daily_queues")["specialist_id"]["nullable"] is True


# ===================== Codex round-1: adoption + FK drift pins =====================


def _scratch_with_precreated_queue_resources(*, drift: str) -> sa.engine.Connection:
    """Scratch world where queue_resources ALREADY exists (manual or
    interrupted rollout). ``drift`` selects the contract violation:
    'missing_column' | 'nullable_drift' | 'missing_unique' | 'clean'.
    """
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("specialty", sa.String(100), nullable=False),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column(
            "specialist_id", sa.Integer, sa.ForeignKey("doctors.id"), nullable=False
        ),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    columns = [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=(drift == "nullable_drift")),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("start_number_online", sa.Integer, nullable=False, default=1),
        sa.Column("max_online_per_day", sa.Integer, nullable=False, default=15),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    ]
    if drift != "missing_column":
        columns.append(sa.Column("default_cabinet", sa.String(20), nullable=True))
    table_args = []
    if drift != "missing_unique":
        table_args = [
            sa.UniqueConstraint("code", name="uq_queue_resources_code"),
            sa.UniqueConstraint("queue_tag", name="uq_queue_resources_queue_tag"),
        ]
    sa.Table("queue_resources", metadata, *columns, *table_args)
    metadata.create_all(engine)
    return engine.connect()


def test_upgrade_aborts_on_drifted_precreated_queue_resources() -> None:
    """Codex round-1 P1: a pre-existing queue_resources table is adopted
    ONLY on a full contract match — any drift aborts BEFORE any DDL, so
    daily_queues stays untouched and the chain is never stamped against
    an incompatible registry."""
    module = _load_migration_0058()
    for drift, needle in (
        ("missing_column", "missing=\\['default_cabinet'\\]"),
        ("nullable_drift", "nullable=True"),
        ("missing_unique", "UNIQUE contract"),
    ):
        with _scratch_with_precreated_queue_resources(drift=drift) as conn:
            with pytest.raises(RuntimeError, match=needle):
                _run_upgrade_steps(module, conn)

            # abort BEFORE any DDL: daily_queues never expanded
            assert "queue_resource_id" not in _columns(conn, "daily_queues")
            assert _columns(conn, "daily_queues")["specialist_id"]["nullable"] is False


def test_upgrade_adopts_clean_precreated_queue_resources() -> None:
    """Codex round-1 P1 (positive side): a shape-identical pre-existing
    table IS adopted — the idempotent already-migrated pass, and the
    missing id index is ensured even on the adoption path."""
    module = _load_migration_0058()
    with _scratch_with_precreated_queue_resources(drift="clean") as conn:
        _run_upgrade_steps(module, conn)

        # adoption: table kept, index ensured, daily_queues expanded
        assert "ix_queue_resources_id" in {
            idx["name"] for idx in sa.inspect(conn).get_indexes("queue_resources")
        }
        assert _columns(conn, "daily_queues")["queue_resource_id"]["nullable"] is True
        assert _columns(conn, "daily_queues")["specialist_id"]["nullable"] is True
        assert module._canonical_resource_fk_present(conn)


def test_upgrade_aborts_on_unexpected_resource_fk() -> None:
    """Codex round-1 P2: a foreign key to queue_resources that is NOT the
    canonical constraint (different name here) is drift — abort instead of
    skipping the canonical create (a wrong FK would leave the owner
    unenforced or break the name-based downgrade)."""
    module = _load_migration_0058()
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    )
    sa.Table(
        "queue_resources",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("specialist_id", sa.Integer, nullable=False),
        sa.Column(
            "queue_resource_id",
            sa.Integer,
            sa.ForeignKey("queue_resources.id", name="fk_daily_queues_resource_drift"),
            nullable=True,
        ),
    )
    metadata.create_all(engine)
    with engine.connect() as conn:
        with pytest.raises(RuntimeError, match="unexpected foreign key"):
            module._expand_daily_queues(_ops(conn), conn)

        # abort BEFORE any mutation: specialist_id never relaxed
        assert _columns(conn, "daily_queues")["specialist_id"]["nullable"] is False


# ===================== model world (create_all) =====================


def test_queue_resource_defaults_and_raw_sql_persistence(
    db_session: Session,
) -> None:
    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    db_session.flush()

    # RAW-SQL proof (identity-map proof per QF-1: read back through SQL,
    # not the ORM instance)
    row = db_session.execute(
        sa.text(
            "SELECT id, code, queue_tag, display_name, active, "
            "start_number_online, max_online_per_day, default_cabinet "
            "FROM queue_resources WHERE code = 'lab'"
        )
    ).one()
    assert row[0] == resource.id
    assert row[1] == "lab" and row[2] == "lab" and row[3] == "Лаборатория"
    assert bool(row[4]) is True
    assert row[5] == 1 and row[6] == 15  # carried from the 0055 Doctor config
    assert row[7] is None


def test_queue_resource_unique_code(db_session: Session) -> None:
    db_session.add(QueueResource(code="ecg", queue_tag="ecg", display_name="ЭКГ"))
    db_session.flush()
    db_session.add(QueueResource(code="ecg", queue_tag="ecg2", display_name="ЭКГ 2"))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_queue_resource_unique_queue_tag(db_session: Session) -> None:
    db_session.add(QueueResource(code="ecg", queue_tag="ecg", display_name="ЭКГ"))
    db_session.flush()
    db_session.add(QueueResource(code="ecg2", queue_tag="ecg", display_name="ЭКГ 2"))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_daily_queue_resource_owned_persists_raw_sql(
    db_session: Session,
) -> None:
    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    db_session.flush()

    queue = DailyQueue(
        day=date(2026, 9, 6),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    row = db_session.execute(
        sa.text(
            "SELECT specialist_id, queue_resource_id, queue_tag FROM daily_queues "
            "WHERE id = :qid"
        ),
        {"qid": queue.id},
    ).one()
    assert row == (None, resource.id, "lab")


def test_daily_queue_relationship_loads_resource(db_session: Session) -> None:
    resource = QueueResource(code="ecg", queue_tag="ecg", display_name="ЭКГ")
    db_session.add(resource)
    db_session.flush()
    queue = DailyQueue(
        day=date(2026, 9, 6),
        queue_resource_id=resource.id,
        queue_tag="ecg",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    loaded = db_session.get(DailyQueue, queue.id)
    assert loaded.queue_resource is not None
    assert loaded.queue_resource.code == "ecg"
    assert loaded.specialist is None


def test_pre_xor_permissive_both_owners(db_session: Session) -> None:
    """QD-2A reality pin: NO XOR constraint yet — a row with BOTH owners
    persists. QD-2D tightens this (its CHECK makes the same insert fail);
    until then this pin protects the staged plan from an accidental early
    constraint."""
    doctor = Doctor(specialty="cardiology", active=True)
    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add_all([doctor, resource])
    db_session.flush()

    queue = DailyQueue(
        day=date(2026, 9, 6),
        specialist_id=doctor.id,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()
    row = db_session.execute(
        sa.text("SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"),
        {"qid": queue.id},
    ).one()
    assert row == (doctor.id, resource.id)


def test_pre_xor_permissive_no_owner(db_session: Session) -> None:
    """QD-2A reality pin: no-owner rows also persist (the XOR CHECK of
    QD-2D will reject them). Pinned so the tightening stage has a
    deliberate, visible target."""
    queue = DailyQueue(day=date(2026, 9, 6), queue_tag="lab", active=True)
    db_session.add(queue)
    db_session.flush()
    row = db_session.execute(
        sa.text("SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"),
        {"qid": queue.id},
    ).one()
    assert row == (None, None)


def test_doctor_owned_daily_queue_unchanged(db_session: Session) -> None:
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.flush()

    queue = DailyQueue(
        day=date(2026, 9, 6),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    row = db_session.execute(
        sa.text("SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"),
        {"qid": queue.id},
    ).one()
    assert row == (doctor.id, None)


def test_get_or_create_daily_queue_doctor_owned_unchanged(
    db_session: Session,
) -> None:
    """PR-26 per-doctor ownership semantics untouched by the EXPAND stage:
    the canonical creator still resolves/creates doctor-owned queues and
    never touches queue_resource_id."""
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.flush()

    first = queue_service.get_or_create_daily_queue(
        db_session,
        day=date(2026, 9, 6),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
    )
    assert first is not None
    assert first.specialist_id == doctor.id
    assert first.queue_resource_id is None

    second = queue_service.get_or_create_daily_queue(
        db_session,
        day=date(2026, 9, 6),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
    )
    assert second.id == first.id


# ===================== read schema surface =====================


def test_daily_queue_out_doctor_owned_serialization(db_session: Session) -> None:
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(
        day=date(2026, 9, 6),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    payload = DailyQueueOut.model_validate(_queue_namespace(queue))
    assert payload.specialist_id == doctor.id
    assert payload.queue_resource_id is None


def test_daily_queue_out_resource_owned_serialization(db_session: Session) -> None:
    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    db_session.flush()
    queue = DailyQueue(
        day=date(2026, 9, 6),
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()

    payload = DailyQueueOut.model_validate(_queue_namespace(queue))
    assert payload.specialist_id is None
    assert payload.queue_resource_id == resource.id


def test_queue_resource_out_roundtrip(db_session: Session) -> None:
    resource = QueueResource(
        code="lab",
        queue_tag="lab",
        display_name="Лаборатория",
        default_cabinet="405",
    )
    db_session.add(resource)
    db_session.flush()

    payload = QueueResourceOut.model_validate(resource)
    assert payload.id == resource.id
    assert payload.code == "lab"
    assert payload.queue_tag == "lab"
    assert payload.display_name == "Лаборатория"
    assert payload.active is True
    assert payload.start_number_online == 1
    assert payload.max_online_per_day == 15
    assert payload.default_cabinet == "405"
