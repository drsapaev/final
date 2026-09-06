"""QD-2A (queue resource expand) — dual-owner EXPAND regression pins.

Stage A of the QD-2 staged rollout (architecture FINAL, 2026-09-07):
the doctorless-queue routing owner moves off synthetic User+Doctor
pairs onto a dedicated ``queue_resources`` registry, and
``daily_queues`` gains the ``queue_resource_id`` axis with
``specialist_id`` relaxed to NULLABLE. This revision is strictly
additive — no XOR, no uniqueness contract, no seed rows, no runtime
switch — so the pins here protect BOTH halves of that contract:

- the EXPAND half: the registry exists with its shape (code/queue_tag
  UNIQUE, numbering config equivalent to the Doctor columns, nullable
  default_cabinet), the dual-owner columns accept every stored shape
  (doctor-only — the only production shape today — resource-only,
  both, neither), and duplicates stay legal;
- the COMPAT half: old-shape rows behave exactly as before
  (specialist relationship, no resource leakage), the read schema
  serializes both shapes, and the doctor-queue mutation guard rejects
  a NULL specialist exactly like a foreign specialist (the QD-2
  inventory Q1 conclusion: no caller needs a non-null synthetic
  doctor id — RBAC guards fail closed on NULL).

Migration contract: 0058 renders as pure additive PG DDL (CREATE
TABLE + UNIQUE constraints + RLS, ADD COLUMN, FK, index, DROP NOT
NULL) with a strict symmetric downgrade; no INSERT/UPDATE/DELETE —
data (lab/ecg seeds, dedup) is QD-2B, the XOR/partial-unique
contract is QD-2D. The offline-SQL generation runs the real
migration functions through the PG dialect (the QF-1 0054 validation
pattern; the sqlite chain cannot host 0054+ DDL).

Codex round-1 pins (both findings fixed in this PR):

- P1 backup round-trip: MigrationService.backup_queue_data /
  restore_queue_data must carry queue_resource_id, or a future
  resource-owned queue (specialist_id NULL) restored from backup
  would come back with BOTH owners NULL — an unroutable queue with
  orphaned entries. Backward compatibility: pre-QD-2 backup files
  (no queue_resource_id key) still restore.
- P2 ADR honesty: ADR-001 documents the dual-owner staged contract
  (the doctor-ownership decision is unchanged for doctor queues).
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, QueueResource
from app.models.user import User
from app.schemas.online_queue import DailyQueueOut

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0058 = BACKEND_ROOT / "alembic" / "versions" / "0058_queue_resource_expand.py"
ADR_001 = (
    REPO_ROOT / "docs" / "adr" / "ADR-001-queue-ownership-and-specialty-architecture.md"
)

# non-secret placeholder mirroring the 0055 seed marker — this suite
# performs no password verification
_DISABLED_HASH = "!disabled:queue-resource"


# ===================== helpers =====================


def _make_user(db_session: Session, *, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=_DISABLED_HASH,
        role=role,
        is_active=True,
        is_superuser=False,
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


def _make_resource(
    db_session: Session,
    *,
    code: str,
    queue_tag: str,
    display_name: str = "Ресурс очереди",
) -> QueueResource:
    resource = QueueResource(code=code, queue_tag=queue_tag, display_name=display_name)
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def _make_queue(
    db_session: Session,
    *,
    day: date,
    specialist_id: int | None,
    queue_resource_id: int | None = None,
    queue_tag: str | None = None,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=specialist_id,
        queue_resource_id=queue_resource_id,
        queue_tag=queue_tag,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _raw_owners(db_session: Session, queue_id: int) -> tuple[int | None, int | None]:
    """Identity-map-proof persistence pin (QF-1 lesson): raw SQL, not
    the ORM session, is the honest witness of stored NULLs."""
    row = db_session.execute(
        sa.text(
            "SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = :qid"
        ),
        {"qid": queue_id},
    ).fetchone()
    assert row is not None
    return (row[0], row[1])


# ===================== A. registry shape (ORM layer) =====================


def test_queue_resources_table_shape(db_session: Session) -> None:
    inspector = sa.inspect(db_session.get_bind())
    assert "queue_resources" in inspector.get_table_names()

    columns = {col["name"]: col for col in inspector.get_columns("queue_resources")}
    assert set(columns) == {
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
    # nullable contract
    assert columns["code"]["nullable"] is False
    assert columns["queue_tag"]["nullable"] is False
    assert columns["display_name"]["nullable"] is False
    assert columns["start_number_online"]["nullable"] is False
    assert columns["max_online_per_day"]["nullable"] is False
    assert columns["default_cabinet"]["nullable"] is True
    # the numbering config mirrors the Doctor columns this entity replaces
    assert str(columns["start_number_online"]["type"]) == "INTEGER"
    assert str(columns["max_online_per_day"]["type"]) == "INTEGER"


def test_queue_resource_code_is_unique(db_session: Session) -> None:
    _make_resource(db_session, code="lab", queue_tag="lab")
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, display_name, active,"
                " start_number_online, max_online_per_day)"
                " VALUES ('lab', 'lab-other', 'Дубль кода', 1, 1, 15)"
            )
        )
    db_session.rollback()


def test_queue_resource_queue_tag_is_unique(db_session: Session) -> None:
    _make_resource(db_session, code="lab", queue_tag="lab")
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, display_name, active,"
                " start_number_online, max_online_per_day)"
                " VALUES ('lab-other', 'lab', 'Дубль тега', 1, 1, 15)"
            )
        )
    db_session.rollback()


def test_queue_resource_orm_defaults(db_session: Session) -> None:
    resource = _make_resource(db_session, code="ecg", queue_tag="ecg")
    assert resource.active is True
    assert resource.start_number_online == 1
    assert resource.max_online_per_day == 15
    assert resource.default_cabinet is None
    assert resource.created_at is not None


# ===================== B. dual-owner columns (ORM layer) =====================


def test_daily_queue_resource_relationship_resolves(db_session: Session) -> None:
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )

    assert _raw_owners(db_session, queue.id) == (None, resource.id)
    db_session.refresh(queue)
    assert queue.queue_resource is not None
    assert queue.queue_resource.code == "lab"
    assert queue.specialist is None


def test_daily_queue_specialist_id_stores_null(db_session: Session) -> None:
    """The core expand fact: NULL specialist_id is a legal stored
    state now (pre-0058 the column was NOT NULL)."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=None,
        queue_resource_id=resource.id,
    )
    assert _raw_owners(db_session, queue.id) == (None, resource.id)


def test_no_xor_in_expand_stage(db_session: Session) -> None:
    """DELIBERATE expand semantics: both owners AND neither owner are
    legal stored states. The XOR CHECK is the QD-2D contract step —
    pinning its absence here guards the staged rollout order (a
    premature constraint would break the QD-2B backfill)."""
    user = _make_user(db_session, username="dr_xor", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")

    both = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=doctor.id,
        queue_resource_id=resource.id,
    )
    neither = _make_queue(db_session, day=date(2026, 9, 7), specialist_id=None)

    assert _raw_owners(db_session, both.id) == (doctor.id, resource.id)
    assert _raw_owners(db_session, neither.id) == (None, None)


def test_no_active_uniqueness_in_expand_stage(db_session: Session) -> None:
    """DELIBERATE expand semantics: duplicate ACTIVE (day, resource)
    rows stay legal. The exact-tag-wins dedup is QD-2B and the partial
    unique index (`WHERE active AND queue_resource_id IS NOT NULL`)
    is QD-2D — this pin protects the historical duplicates until the
    operator-approved migration handles them."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    first = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )
    second = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )

    assert first.active and second.active
    assert _raw_owners(db_session, first.id) == (None, resource.id)
    assert _raw_owners(db_session, second.id) == (None, resource.id)


def test_old_shape_doctor_owned_row_unchanged(db_session: Session) -> None:
    """The ONLY production shape today: specialist-owned, no resource.
    Byte-compat pin — nothing about the expand may disturb it."""
    user = _make_user(db_session, username="dr_classic", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    queue = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
    )

    assert _raw_owners(db_session, queue.id) == (doctor.id, None)
    db_session.refresh(queue)
    assert queue.specialist is not None
    assert queue.specialist.id == doctor.id
    assert queue.queue_resource is None


# ===================== C. read schema relaxation =====================


def test_daily_queue_out_serializes_old_shape(db_session: Session) -> None:
    user = _make_user(db_session, username="dr_schema", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    queue = _make_queue(db_session, day=date(2026, 9, 7), specialist_id=doctor.id)

    payload = DailyQueueOut(
        id=queue.id,
        day=queue.day,
        specialist_id=queue.specialist_id,
        queue_resource_id=queue.queue_resource_id,
        active=queue.active,
        opened_at=queue.opened_at,
        created_at=queue.created_at or datetime.now(UTC),
    )
    assert payload.specialist_id == doctor.id
    assert payload.queue_resource_id is None


def test_daily_queue_out_serializes_resource_shape(db_session: Session) -> None:
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        day=date(2026, 9, 7),
        specialist_id=None,
        queue_resource_id=resource.id,
    )

    payload = DailyQueueOut(
        id=queue.id,
        day=queue.day,
        specialist_id=queue.specialist_id,
        queue_resource_id=queue.queue_resource_id,
        active=queue.active,
        opened_at=queue.opened_at,
        created_at=queue.created_at or datetime.now(UTC),
    )
    assert payload.specialist_id is None
    assert payload.queue_resource_id == resource.id


def test_daily_queue_out_new_field_defaults_to_none() -> None:
    """Old callers that never heard of queue_resource_id keep working
    — the new field is purely optional (additive contract)."""
    payload = DailyQueueOut(
        id=1,
        day=date(2026, 9, 7),
        specialist_id=42,
        active=True,
        created_at=datetime.now(UTC),
    )
    assert payload.queue_resource_id is None


# ===================== D. runtime compat (old production code) =====================


def _mutation_guard(db_session: Session, specialist_id: int | None, user: User) -> None:
    from app.api.v1.endpoints.qr_queue._helpers import (
        _ensure_doctor_can_mutate_specialist_queue,
    )

    _ensure_doctor_can_mutate_specialist_queue(
        db_session, specialist_id=specialist_id, current_user=user
    )


def test_doctor_mutation_guard_rejects_null_specialist(db_session: Session) -> None:
    """QD-2 inventory Q1 conclusion, pinned: the doctor-role mutation
    guard fails CLOSED on a NULL specialist (None != doctor.id) — a
    resource-owned queue is not doctor-mutable, exactly like a
    foreign-doctor queue. No caller needs a non-null synthetic id."""
    user = _make_user(db_session, username="dr_guard", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")

    with pytest.raises(HTTPException) as exc_info:
        _mutation_guard(db_session, None, user)
    assert exc_info.value.status_code == 403

    # positive control on the same guard: own queue still passes
    _mutation_guard(db_session, doctor.id, user)


def test_doctor_mutation_guard_still_rejects_foreign_specialist(
    db_session: Session,
) -> None:
    """Compat pin: the pre-QD-2 guard semantics are untouched."""
    owner = _make_user(db_session, username="dr_owner", role="doctor")
    owner_doctor = _make_doctor(db_session, user_id=owner.id, specialty="cardio")
    stranger = _make_user(db_session, username="dr_stranger", role="doctor")
    _make_doctor(db_session, user_id=stranger.id, specialty="derma")

    with pytest.raises(HTTPException) as exc_info:
        _mutation_guard(db_session, owner_doctor.id, stranger)
    assert exc_info.value.status_code == 403


# ===================== F. Codex round-1 P1: backup round-trip =====================


def test_backup_queue_data_includes_resource_owner(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex round-1 P1: the backup format must serialize the resource
    owner — otherwise a resource-owned queue (specialist_id NULL)
    restored from backup comes back with BOTH owners NULL, an
    unroutable queue with orphaned entries."""
    from app.services.migration_service import MigrationService

    user = _make_user(db_session, username="dr_backup", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    day = date(2026, 9, 7)
    _make_queue(db_session, day=day, specialist_id=doctor.id, queue_tag="cardio")
    _make_queue(
        db_session,
        day=day,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
    )

    # backup writes to a CWD-relative backups/ dir — isolate it
    monkeypatch.chdir(tmp_path)
    result = MigrationService(db_session).backup_queue_data(day)
    assert result["success"] is True, result
    assert result["queues_count"] == 2

    backup = json.loads((tmp_path / result["backup_file"]).read_text(encoding="utf-8"))
    by_tag = {q["queue_tag"]: q for q in backup["queues"]}
    assert by_tag["cardio"]["specialist_id"] == doctor.id
    assert by_tag["cardio"]["queue_resource_id"] is None
    assert by_tag["lab"]["specialist_id"] is None
    assert by_tag["lab"]["queue_resource_id"] == resource.id


def test_restore_queue_data_round_trips_resource_owner(
    db_session: Session, tmp_path: Path
) -> None:
    """The other half of the P1 fix: restore recreates the resource
    owner (raw-SQL pin — identity-map-proof)."""
    from app.services.migration_service import MigrationService

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    backup_file = tmp_path / "resource_owner_backup.json"
    backup_file.write_text(
        json.dumps(
            {
                "backup_date": "2026-09-07",
                "created_at": "2026-09-07T00:00:00+00:00",
                "queues": [
                    {
                        "id": 910001,
                        "day": "2026-09-07",
                        "specialist_id": None,
                        "queue_resource_id": resource.id,
                        "queue_tag": "lab",
                        "active": True,
                        "opened_at": None,
                        "entries": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = MigrationService(db_session).restore_queue_data(str(backup_file))
    assert result["success"] is True, result
    assert result["restored_queues"] == 1

    row = db_session.execute(
        sa.text(
            "SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = 910001"
        )
    ).fetchone()
    assert row == (None, resource.id)


def test_restore_queue_data_accepts_pre_qd2_backup_format(
    db_session: Session, tmp_path: Path
) -> None:
    """Backward compatibility: a pre-QD-2 backup file (no
    queue_resource_id key) still restores, with the resource axis
    simply NULL — exactly the pre-QD-2 behavior."""
    from app.services.migration_service import MigrationService

    backup_file = tmp_path / "pre_qd2_backup.json"
    backup_file.write_text(
        json.dumps(
            {
                "backup_date": "2026-09-07",
                "created_at": "2026-09-07T00:00:00+00:00",
                "queues": [
                    {
                        "id": 910002,
                        "day": "2026-09-07",
                        "specialist_id": 42,
                        "queue_tag": "cardio",
                        "active": True,
                        "opened_at": None,
                        "entries": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = MigrationService(db_session).restore_queue_data(str(backup_file))
    assert result["success"] is True, result

    row = db_session.execute(
        sa.text(
            "SELECT specialist_id, queue_resource_id FROM daily_queues WHERE id = 910002"
        )
    ).fetchone()
    assert row == (42, None)


# ===================== G. Codex round-1 P2: ADR honesty =====================


def test_adr_001_documents_dual_owner_axis() -> None:
    """Codex round-1 P2: the canonical ownership ADR must carry the
    dual-owner staged contract — engineers following a stale 'every
    DailyQueue belongs to a doctor' ADR would omit resource-owned
    queues from routing/authorization/reporting work."""
    text = ADR_001.read_text(encoding="utf-8")
    assert "Dual-Owner Axis for Doctorless Queues" in text
    assert "queue_resource_id" in text
    assert "queue_resources" in text
    # the staged contract is spelled out
    assert "XOR" in text
    assert "0058_queue_resource_expand" in text
    # the doctor-ownership decision itself is explicitly unchanged
    assert "decision itself is UNCHANGED" in text
    # Codex round-2 P2: the general resource's conditional fate is explicit —
    # stage E cannot retire general_resource before its destination decision
    # lands, so general queues are never left ownerless
    assert "deliberately conditional, not forgotten" in text


# ===================== E. migration 0058 (offline PG dialect) =====================


def _load_migration_0058():
    spec = importlib.util.spec_from_file_location(
        "migration_0058_queue_resource_expand", MIGRATION_0058
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_pg_sql(fn) -> str:
    """Render a migration function as PG-dialect SQL offline (the QF-1
    0054 validation pattern — the sqlite chain cannot host the DDL of
    0054+; CI runs the authoritative `alembic upgrade head` on real
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
    module = _load_migration_0058()
    assert module.revision == "0058_queue_resource_expand"
    assert module.down_revision == "0057_lab_resource_internal_role"


def test_migration_upgrade_renders_additive_pg_ddl() -> None:
    module = _load_migration_0058()
    sql = _normalize(_offline_pg_sql(module.upgrade))

    # registry table with its UNIQUE identity contract
    assert "CREATE TABLE queue_resources" in sql
    assert "id SERIAL NOT NULL" in sql
    assert "CONSTRAINT pk_queue_resources PRIMARY KEY (id)" in sql
    assert "CONSTRAINT uq_queue_resources_code UNIQUE (code)" in sql
    assert "CONSTRAINT uq_queue_resources_queue_tag UNIQUE (queue_tag)" in sql
    assert "start_number_online INTEGER NOT NULL" in sql
    assert "max_online_per_day INTEGER NOT NULL" in sql
    assert "default_cabinet VARCHAR(20)" in sql
    assert "active BOOLEAN DEFAULT true NOT NULL" in sql
    assert "created_at TIMESTAMP WITH TIME ZONE DEFAULT now()" in sql

    # RLS invariant for the new public table (0050/0051 convention)
    assert "ALTER TABLE public.queue_resources ENABLE ROW LEVEL SECURITY" in sql

    # daily_queues: additive column + FK + index + nullable relaxation
    assert "ALTER TABLE daily_queues ADD COLUMN queue_resource_id INTEGER" in sql
    assert (
        "ADD CONSTRAINT fk_daily_queues_queue_resource_id FOREIGN KEY(queue_resource_id)"
        " REFERENCES queue_resources (id)" in sql
    )
    assert (
        "CREATE INDEX ix_daily_queues_queue_resource_id"
        " ON daily_queues (queue_resource_id)" in sql
    )
    assert "ALTER TABLE daily_queues ALTER COLUMN specialist_id DROP NOT NULL" in sql

    # expand-only: no XOR CHECK, no daily_queues uniqueness contract,
    # no data statements (seeds/dedup are QD-2B, XOR is QD-2D)
    assert "CHECK" not in sql
    assert sql.count("UNIQUE") == 2
    assert "INSERT" not in sql
    assert "UPDATE" not in sql
    assert "DELETE" not in sql


def test_migration_downgrade_renders_reverse_ddl() -> None:
    module = _load_migration_0058()
    sql = _normalize(_offline_pg_sql(module.downgrade))

    # strict re-tighten first (fails loudly on resource-owned rows)
    assert "ALTER TABLE daily_queues ALTER COLUMN specialist_id SET NOT NULL" in sql
    assert (
        "ALTER TABLE daily_queues DROP CONSTRAINT fk_daily_queues_queue_resource_id"
        in sql
    )
    assert "ALTER TABLE daily_queues DROP COLUMN queue_resource_id" in sql
    assert "DROP INDEX ix_daily_queues_queue_resource_id" in sql
    assert "DROP TABLE queue_resources" in sql
    assert "DROP INDEX ix_queue_resources_queue_tag" in sql
    assert "DROP INDEX ix_queue_resources_code" in sql
    assert "DROP INDEX ix_queue_resources_id" in sql
