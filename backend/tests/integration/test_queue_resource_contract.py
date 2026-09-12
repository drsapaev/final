"""QD-2D (queue resource contract) — XOR CHECK + partial active uniqueness.

Stage D of the QD-2 staged rollout (architecture FINAL, 2026-09-07,
ADR-001 addendum stage table). Stages A (0058: registry + dual-owner
columns), B (0059: lab/ecg seeds + deterministic backfill) and C (the
runtime switch) landed; this suite pins the stage-D CONTRACT that
migration 0063_queue_resource_contract writes into the schema:

- the XOR: exactly one owner per queue (specialist_id XOR
  queue_resource_id) — both-set (the 0059 dual-ownership bridge) and
  neither-set (orphan) shapes are rejected at the ORM level;
- the partial active uniqueness: one ACTIVE (day, queue_resource_id)
  row — the ADR predicate verbatim, with inactive and NULL-resource
  duplicates staying legal;
- the migration data logic (0059 scratch-SQLite pattern): the bridge
  conversion consumes the specialist link on canonical bridges and the
  four loud-abort categories (orphan rows, ACTIVE duplicates, corrupt
  tag<->resource links, non-synthetic bridge owners);
- the offline PG DDL (QF-1 pattern): the CHECK and the partial unique
  render exactly, the downgrade reverses them, the chain stays
  single-headed with 0063 as the head and the revision id fits the
  alembic_version.version_num VARCHAR(32) limit (the 0059 CI lesson);
- parity: the ORM model and the migration carry the byte-identical
  XOR expression and predicate so the two surfaces cannot drift.
"""

from __future__ import annotations

import importlib.util
import io
import re
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import _OWNER_XOR_CHECK as MODEL_XOR_CHECK
from app.models.online_queue import DailyQueue, QueueResource
from app.models.user import User

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0063 = (
    BACKEND_ROOT / "alembic" / "versions" / "0063_queue_resource_contract.py"
)
ADR_001 = (
    REPO_ROOT / "docs" / "adr" / "ADR-001-queue-ownership-and-specialty-architecture.md"
)

# non-secret placeholder mirroring the 0055 seed marker — this suite
# performs no password verification
_DISABLED_HASH = "!disabled:queue-resource"

_DAY = date(2026, 9, 7)


# ===================== helpers =====================


def _make_user(db_session: Session, *, username: str, role: str) -> User:
    user = User(
        username=username, hashed_password=_DISABLED_HASH, role=role, is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(db_session: Session, *, user_id: int, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_resource(db_session: Session, *, code: str, queue_tag: str) -> QueueResource:
    resource = QueueResource(code=code, queue_tag=queue_tag, display_name=code)
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def _raw_owners(db_session: Session, queue_id: int) -> tuple[int | None, int | None]:
    row = db_session.execute(
        sa.text(
            "SELECT specialist_id, queue_resource_id FROM daily_queues"
            " WHERE id = :qid"
        ),
        {"qid": queue_id},
    ).fetchone()
    return (row[0], row[1])


# ===================== A. ORM-level contract =====================


def test_xor_rejects_both_owners(db_session: Session) -> None:
    """The 0059 dual-ownership bridge (both owners set) is closed: the
    ORM insert fails on ck_daily_queues_owner_xor — post-0063 the
    shape cannot re-enter through any writer."""
    user = _make_user(db_session, username="dr_contract", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")

    queue = DailyQueue(
        day=_DAY,
        specialist_id=doctor.id,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )
    db_session.add(queue)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_xor_rejects_neither_owner(db_session: Session) -> None:
    """An orphan queue (both owners NULL) is rejected — the migration
    aborts on pre-existing orphans and the contract keeps new ones
    out (the QD-2A backup-restore P1 shape)."""
    queue = DailyQueue(day=_DAY, queue_tag="lab")
    db_session.add(queue)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_xor_update_path_cannot_recreate_a_bridge(db_session: Session) -> None:
    """The constraint is re-evaluated on UPDATE: setting
    queue_resource_id on an existing specialist-owned row (the ORM
    twin of the 0059 backfill write) fails the same way an INSERT
    would."""
    user = _make_user(db_session, username="dr_update", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = DailyQueue(day=_DAY, specialist_id=doctor.id, queue_tag="lab")
    db_session.add(queue)
    db_session.commit()

    queue.queue_resource_id = resource.id
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_partial_unique_rejects_active_duplicate(db_session: Session) -> None:
    """One ACTIVE (day, queue_resource_id) row — the partial unique
    index is the DB-level twin of the QD-2C advisory locks (the
    check-then-insert race becomes an IntegrityError)."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    first = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )
    db_session.add(first)
    db_session.commit()

    second = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_partial_unique_allows_inactive_and_null_resource_duplicates(
    db_session: Session,
) -> None:
    """The predicate is ACTIVE-only (the ADR stage-table wording
    verbatim): inactive rows and NULL-resource rows stay
    duplicate-legal — history preservation first."""
    user = _make_user(db_session, username="dr_dup", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    active = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )
    inactive = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=False,
    )
    db_session.add(active)
    db_session.add(inactive)
    db_session.commit()

    # a second inactive row on the same (day, resource) is still legal
    inactive_again = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=False,
    )
    db_session.add(inactive_again)
    db_session.commit()

    # NULL-resource rows never conflict (NULLs are distinct in unique
    # indexes — the 0053 users.email precedent): the doctor axis keeps
    # its per-doctor rows untouched by the resource index
    doctor_queue_a = DailyQueue(day=_DAY, specialist_id=doctor.id, queue_tag="lab")
    doctor_queue_b = DailyQueue(day=_DAY, specialist_id=doctor.id, queue_tag="lab")
    db_session.add(doctor_queue_a)
    db_session.add(doctor_queue_b)
    db_session.commit()

    rows = db_session.execute(
        sa.text(
            "SELECT COUNT(*) FROM daily_queues"
            " WHERE day = :day AND queue_resource_id = :rid"
        ),
        {"day": _DAY.isoformat(), "rid": resource.id},
    ).scalar()
    assert rows == 3


# ===================== B. migration data logic (scratch SQLite) =====================


def _load_migration_0063():
    spec = importlib.util.spec_from_file_location(
        "migration_0063_queue_resource_contract", MIGRATION_0063
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch():
    """Minimal tables mirroring the shapes 0055/0058 provisioned (the
    0059 scratch pattern): the bridge conversion joins
    queue_resources/doctors/users and counts queue_entries."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
    )
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("specialty", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("start_number_online", sa.Integer, nullable=False),
        sa.Column("max_online_per_day", sa.Integer, nullable=False),
    )
    sa.Table(
        "queue_resources",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("specialist_id", sa.Integer, nullable=True),
        sa.Column("queue_resource_id", sa.Integer, nullable=True),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("cabinet_number", sa.String(20), nullable=True),
    )
    sa.Table(
        "queue_entries",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Integer, nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="waiting"),
    )
    metadata.create_all(engine)
    return engine.connect()


def _seed_user(conn, username: str) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO users (username, role, is_active, hashed_password)"
            " VALUES (:u, 'Resource', 1, :p)"
        ),
        {"u": username, "p": _DISABLED_HASH},
    )
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    return user_id


def _seed_doctor(conn, user_id: int | None, *, specialty: str) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active,"
            " start_number_online, max_online_per_day)"
            " VALUES (:u, :s, 1, 1, 15)"
        ),
        {"u": user_id, "s": specialty},
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors ORDER BY id DESC")
    ).fetchone()
    return doctor_id


def _seed_resource(conn, *, code: str, queue_tag: str) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
            " VALUES (:c, :t, :d, 1)"
        ),
        {"c": code, "t": queue_tag, "d": code},
    )
    (rid,) = conn.execute(
        sa.text("SELECT id FROM queue_resources WHERE code = :c"), {"c": code}
    ).fetchone()
    return rid


def _seed_queue(
    conn,
    *,
    day: str,
    specialist_id: int | None,
    queue_resource_id: int | None = None,
    queue_tag: str | None = None,
    active: bool = True,
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_resource_id,"
            " queue_tag, active) VALUES (:d, :s, :r, :t, :a)"
        ),
        {
            "d": day,
            "s": specialist_id,
            "r": queue_resource_id,
            "t": queue_tag,
            "a": 1 if active else 0,
        },
    )
    (qid,) = conn.execute(
        sa.text("SELECT id FROM daily_queues ORDER BY id DESC")
    ).fetchone()
    return qid


def _queue_state(conn, queue_id: int) -> tuple:
    return tuple(
        conn.execute(
            sa.text(
                "SELECT day, queue_tag, specialist_id, queue_resource_id, active"
                " FROM daily_queues WHERE id = :qid"
            ),
            {"qid": queue_id},
        ).fetchone()
    )


def test_bridge_conversion_dedicated_synthetic() -> None:
    """The canonical lab bridge (dedicated synthetic owner, tag matching
    the linked resource) converts: specialist_id consumed, everything
    else byte-identical."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "lab_resource")
        doctor_id = _seed_doctor(conn, user_id, specialty="lab")
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        qid = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="lab",
        )

        report = module._convert_bridges(conn)

        assert report == {"bridges_converted": 1}
        assert _queue_state(conn, qid) == (
            "2026-09-07",
            "lab",
            None,
            rid,
            1,
        )
    finally:
        conn.close()


def test_bridge_conversion_general_resource_cross_owner() -> None:
    """A general_resource-owned lab queue bridged onto the lab resource
    (the 0059 exact-tag-wins cross-owner shape) converts too."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "general_resource")
        doctor_id = _seed_doctor(conn, user_id, specialty="general")
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        qid = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="lab",
        )

        report = module._convert_bridges(conn)

        assert report == {"bridges_converted": 1}
        assert _queue_state(conn, qid) == (
            "2026-09-07",
            "lab",
            None,
            rid,
            1,
        )
    finally:
        conn.close()


def test_bridge_conversion_covers_inactive_rows() -> None:
    """Inactive bridges convert as well — the XOR CHECK applies to
    every row, not only the routing surface."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "ecg_resource")
        doctor_id = _seed_doctor(conn, user_id, specialty="ecg")
        rid = _seed_resource(conn, code="ecg", queue_tag="ecg")
        active_qid = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="ecg",
        )
        inactive_qid = _seed_queue(
            conn,
            day="2026-09-06",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="ecg",
            active=False,
        )

        report = module._convert_bridges(conn)

        assert report == {"bridges_converted": 2}
        assert _queue_state(conn, active_qid) == (
            "2026-09-07",
            "ecg",
            None,
            rid,
            1,
        )
        assert _queue_state(conn, inactive_qid) == (
            "2026-09-06",
            "ecg",
            None,
            rid,
            0,
        )
    finally:
        conn.close()


def test_bridge_conversion_noop_without_bridges() -> None:
    """A clean post-0059 database (no bridges — the CI
    alembic-upgrade-head path and a fresh installation) converts
    nothing: the data step is a no-op, only the DDL lands."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "dr_plain")
        doctor_id = _seed_doctor(conn, user_id, specialty="cardio")
        _seed_queue(conn, day="2026-09-07", specialist_id=doctor_id, queue_tag="cardio")

        assert module._convert_bridges(conn) == {"bridges_converted": 0}
    finally:
        conn.close()


def test_preflight_aborts_on_orphans() -> None:
    """Orphan rows (both owners NULL) abort with the inventory — the
    XOR needs exactly one owner and the migration never invents one."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        _seed_queue(conn, day="2026-09-07", specialist_id=None, queue_tag="lab")

        with pytest.raises(RuntimeError, match="ownerless daily_queues"):
            module._assert_no_orphans(conn)
    finally:
        conn.close()


def test_preflight_aborts_on_active_duplicates() -> None:
    """ACTIVE (day, resource) duplicates abort with the full per-row
    inventory — the partial unique would reject them and no dedup ever
    happens in a migration (the 0059 contract)."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=None,
            queue_resource_id=rid,
            queue_tag="lab",
        )
        _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=None,
            queue_resource_id=rid,
            queue_tag="lab",
        )

        with pytest.raises(RuntimeError, match="more than one ACTIVE queue"):
            module._assert_no_active_duplicates(conn)
    finally:
        conn.close()


def test_preflight_allows_inactive_duplicates() -> None:
    """The abort scope mirrors the index predicate: inactive
    duplicates do not abort (only the ACTIVE surface is stage-D's
    business)."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=None,
            queue_resource_id=rid,
            queue_tag="lab",
            active=False,
        )
        _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=None,
            queue_resource_id=rid,
            queue_tag="lab",
            active=False,
        )

        module._assert_no_active_duplicates(conn)  # no abort
    finally:
        conn.close()


def test_conversion_aborts_on_corrupt_tag_link() -> None:
    """A bridge whose queue_tag does not match its linked resource's
    queue_tag (including the NULL tag) is a corrupt reference — the
    0059 exact-tag-wins contract, never silently adopted."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "lab_resource")
        doctor_id = _seed_doctor(conn, user_id, specialty="lab")
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        foreign = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="laboratory",
        )
        null_tag = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag=None,
        )

        with pytest.raises(RuntimeError, match="corrupt bridge reference"):
            module._convert_bridges(conn)

        # no rows changed
        assert _queue_state(conn, foreign)[2] == doctor_id
        assert _queue_state(conn, null_tag)[2] == doctor_id
    finally:
        conn.close()


def test_conversion_aborts_on_human_doctor_bridge() -> None:
    """A bridge carrying a human doctor's specialist link never gets
    severed by the migration — which axis the row belongs to is an
    operator decision."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        user_id = _seed_user(conn, "dr_human")
        doctor_id = _seed_doctor(conn, user_id, specialty="cardio")
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        qid = _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=doctor_id,
            queue_resource_id=rid,
            queue_tag="lab",
        )

        with pytest.raises(RuntimeError, match="non-canonical owner"):
            module._convert_bridges(conn)

        assert _queue_state(conn, qid)[2] == doctor_id
    finally:
        conn.close()


def test_conversion_aborts_on_unlinked_doctor_bridge() -> None:
    """A bridge whose specialist has no user linkage cannot be
    classified as synthetic — operator decides."""
    module = _load_migration_0063()
    conn = _scratch()
    try:
        unlinked_doctor_id = _seed_doctor(conn, None, specialty="lab")
        rid = _seed_resource(conn, code="lab", queue_tag="lab")
        _seed_queue(
            conn,
            day="2026-09-07",
            specialist_id=unlinked_doctor_id,
            queue_resource_id=rid,
            queue_tag="lab",
        )

        with pytest.raises(RuntimeError, match="non-canonical owner"):
            module._convert_bridges(conn)
    finally:
        conn.close()


# ===================== C. offline PG DDL (QF-1) =====================


def _offline_pg_sql(fn) -> str:
    """Render a migration function as PG-dialect SQL offline (the QF-1
    0054/0058 validation pattern — the sqlite chain cannot host the
    DDL; CI runs the authoritative alembic upgrade head on real
    PostgreSQL)."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        fn()
    return buffer.getvalue()


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


def test_migration_module_chain_ids() -> None:
    module = _load_migration_0063()
    assert module.revision == "0063_queue_resource_contract"
    assert module.down_revision == "0062_telegram_webhook_dedup"
    # alembic_version.version_num is VARCHAR(32) — the 0059 CI lesson
    assert len(module.revision) <= 32


def test_migration_upgrade_ddl_renders_the_contract() -> None:
    module = _load_migration_0063()
    sql = _normalize(_offline_pg_sql(module._emit_contract_ddl))

    # the XOR CHECK — the exact portable CASE expression, identical to
    # the ORM model declaration (no drift between the surfaces)
    assert (
        "ALTER TABLE daily_queues ADD CONSTRAINT ck_daily_queues_owner_xor"
        " CHECK ((CASE WHEN specialist_id IS NULL THEN 0 ELSE 1 END)"
        " + (CASE WHEN queue_resource_id IS NULL THEN 0 ELSE 1 END) = 1)" in sql
    )
    # the partial active uniqueness — the ADR stage-table predicate
    assert (
        "CREATE UNIQUE INDEX uq_daily_queues_active_resource_day"
        " ON daily_queues (day, queue_resource_id)"
        " WHERE active AND queue_resource_id IS NOT NULL" in sql
    )
    # the DDL emit is pure contract: no data statements (the guarded
    # conversion UPDATE lives in the data functions)
    assert "INSERT" not in sql
    assert "UPDATE" not in sql
    assert "DELETE" not in sql


def test_migration_downgrade_ddl_renders_reverse() -> None:
    module = _load_migration_0063()
    sql = _normalize(_offline_pg_sql(module.downgrade))

    assert "DROP INDEX uq_daily_queues_active_resource_day" in sql
    assert "ALTER TABLE daily_queues DROP CONSTRAINT ck_daily_queues_owner_xor" in sql


def test_migration_data_statements_never_delete_or_invent() -> None:
    """Source pin (the 0059 NOTE convention): the revision carries no
    DELETE and no owner-assigning INSERT — the only data write is the
    specialist_id NULL-ing bridge conversion, executed through the
    single _UPDATE_BRIDGE site."""
    source = MIGRATION_0063.read_text(encoding="utf-8")
    assert "DELETE" not in source
    assert "INSERT" not in source
    # the single data write is the bridge conversion: one definition
    # plus one execution site
    assert source.count("_UPDATE_BRIDGE") == 2
    assert "UPDATE daily_queues SET specialist_id = NULL" in source


def test_alembic_chain_single_head_0063() -> None:
    """The chain stays single-headed with 0063 as the head (the
    sentinel-suite graph pattern)."""
    graph: dict[str, tuple[str, ...]] = {}
    for path in sorted((BACKEND_ROOT / "alembic" / "versions").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        revision_match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.M)
        if not revision_match:
            continue
        down_match = re.search(r"^down_revision\s*=\s*(.+)$", source, re.M)
        parents = (
            tuple(re.findall(r'["\']([^"\']+)["\']', down_match.group(1)))
            if down_match
            else ()
        )
        graph[revision_match.group(1)] = parents

    assert graph["0063_queue_resource_contract"] == ("0062_telegram_webhook_dedup",)
    # QD-2E (RQ-15.b): the chain head moved to 0064 — the `general`
    # retirement catalog cutover (operator-map application, data-only).
    assert graph["0064_general_retirement_cutover"] == (
        "0063_queue_resource_contract",
    )
    assert len("0064_general_retirement_cutover") <= 32
    referenced = {parent for parents in graph.values() for parent in parents}
    heads = sorted(revision for revision in graph if revision not in referenced)
    assert heads == ["0064_general_retirement_cutover"]


# ===================== D. parity + ADR =====================


def test_model_and_migration_xor_expressions_are_identical() -> None:
    """The ORM model constant and the migration constant carry the
    byte-identical expression — the surfaces cannot drift."""
    module = _load_migration_0063()
    assert MODEL_XOR_CHECK == module._OWNER_XOR_CHECK


def test_adr_001_documents_stage_d_contract() -> None:
    """The canonical ownership ADR carries the stage-D landing note
    (the A-suite round-1 P2 honesty pattern: an engineer following a
    stale ADR must not reintroduce the bridge)."""
    text = ADR_001.read_text(encoding="utf-8")
    assert "Stage D landing note" in text
    # the ADR stage-table predicate is the contract this suite pins
    assert (
        "UNIQUE(day, queue_resource_id) WHERE active AND queue_resource_id"
        " IS NOT NULL" in text
    )
    # the bridge closure is explicit: D consumes the specialist link
    assert "specialist_id" in text
