"""QD-2B (queue resource seed + backfill) — stage B regression pins.

Stage B of the QD-2 staged rollout (architecture FINAL, 2026-09-07;
stage A = 0058/PR #3093). Migration 0059 seeds the lab/ecg registry
rows from LIVE service-catalog proof and backfills synthetic-owned
queues onto the resource axis — no runtime switch, no XOR, no
dedup. The pins here protect every half of that contract:

- the SEED half: exactly lab/ecg, only from homogeneous doctorless
  tags, values transferred from the live synthetic Doctor (not the
  0055 constants), display names from the canonical 0055 vocabulary,
  default_cabinet NULL; general/procedures/cosmetology/stomatology
  never seeded; exact-identity idempotency; incompatible occupants
  abort;
- the GATE half: mixed requires_doctor semantics abort; doctor-only
  tags and alias spellings ('laboratory') are not converted;
- the BACKFILL half: dedicated synthetic and general_resource owners
  bridge onto the tag's resource (destination by queue_tag — the
  exact-tag-wins policy — never by owner username), specialist_id is
  preserved (the dual-ownership bridge), entries are never touched,
  every ambiguity aborts with the full row inventory (multiple active
  same-day queues, human/unlinked/NULL/foreign owners on active
  resource-tag queues, dedicated synthetics owning foreign or NULL
  tags, corrupt resource references);
- the PRESERVATION half: synthetic User/Doctor rows are byte-identical
  before and after (the old runtime resolves through them until
  QD-2C), and the migration's SQL never writes users / doctors /
  services / queue_entries and never emits DDL (data-only stage);
- the DOWNGRADE half: reverses the backfill (references nulled,
  specialist preserved) while refusing to orphan a resource-owned
  queue (specialist_id NULL + queue_resource_id set) and never
  deleting the registry rows — provenance cannot be proven, so
  possibly-pre-existing data always wins (the Codex round-1 P2
  ruling, pinned with the exact hand-applied-row scenario).

The migration logic runs against a scratch SQLite connection (the
0056/0057 pattern); CI runs the authoritative `alembic upgrade head`
on real PostgreSQL. Production today has daily_queues = 0 rows, so
the backfill there is a clean no-op — these rules are regression
pins for staging/dev databases that do carry history.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0059 = (
    BACKEND_ROOT / "alembic" / "versions" / "0059_resource_seed_backfill.py"
)

# non-secret placeholder mirroring the 0055 seed marker (the suite
# performs no password verification)
_DISABLED_HASH = "!disabled:queue-resource"

_DAY = "2026-09-07"
_DAY_2 = "2026-09-08"


# ===================== helpers =====================


def _load_migration_0059():
    spec = importlib.util.spec_from_file_location(
        "migration_0059_resource_seed_backfill", MIGRATION_0059
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_connection():
    """Minimal tables mirroring the shapes 0055/0058 provisioned.

    queue_resources carries the full 0058 column set plus its UNIQUE
    identity contract so conflicting-occupant aborts are realistic;
    daily_queues carries the dual-owner axis; queue_entries carries
    the status vocabulary used for the abort inventory.
    """
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
        sa.Column("cabinet", sa.String(20), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("start_number_online", sa.Integer, nullable=False),
        sa.Column("max_online_per_day", sa.Integer, nullable=False),
    )
    sa.Table(
        "services",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("requires_doctor", sa.Boolean, nullable=False, default=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "queue_resources",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        sa.Column("start_number_online", sa.Integer, nullable=False),
        sa.Column("max_online_per_day", sa.Integer, nullable=False),
        sa.Column("default_cabinet", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("code", name="uq_queue_resources_code"),
        sa.UniqueConstraint("queue_tag", name="uq_queue_resources_queue_tag"),
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


def _seed_user(
    conn,
    username: str,
    *,
    role: str = "Resource",
    is_active: bool = True,
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO users (username, role, is_active, hashed_password) "
            "VALUES (:u, :r, :a, :p)"
        ),
        {"u": username, "r": role, "a": is_active, "p": _DISABLED_HASH},
    )
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    return user_id


def _seed_doctor(
    conn,
    user_id: int,
    *,
    specialty: str,
    active: bool = True,
    start_number_online: int = 1,
    max_online_per_day: int = 15,
    cabinet: str | None = None,
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active, cabinet, "
            "start_number_online, max_online_per_day) "
            "VALUES (:u, :s, :a, :c, :sn, :mx)"
        ),
        {
            "u": user_id,
            "s": specialty,
            "a": active,
            "c": cabinet,
            "sn": start_number_online,
            "mx": max_online_per_day,
        },
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE user_id = :u ORDER BY id DESC"),
        {"u": user_id},
    ).fetchone()
    return doctor_id


def _seed_synthetic(
    conn,
    username: str,
    tag: str,
    *,
    role: str = "Resource",
    user_active: bool = True,
    doctor_active: bool = True,
    start_number_online: int = 1,
    max_online_per_day: int = 15,
    specialty: str | None = None,
) -> tuple[int, int]:
    """The 0055/0056/0057 synthetic pair shape for one queue tag."""
    user_id = _seed_user(conn, username, role=role, is_active=user_active)
    doctor_id = _seed_doctor(
        conn,
        user_id,
        specialty=specialty if specialty is not None else tag,
        active=doctor_active,
        start_number_online=start_number_online,
        max_online_per_day=max_online_per_day,
    )
    return user_id, doctor_id


def _seed_service(
    conn,
    queue_tag: str,
    *,
    requires_doctor: bool = False,
    active: bool = True,
    code: str = "X01",
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO services (code, name, queue_tag, requires_doctor, "
            "active) VALUES (:c, :n, :t, :rd, :a)"
        ),
        {
            "c": code,
            "n": f"Service {code}",
            "t": queue_tag,
            "rd": requires_doctor,
            "a": active,
        },
    )
    (service_id,) = conn.execute(
        sa.text("SELECT id FROM services WHERE code = :c"), {"c": code}
    ).fetchone()
    return service_id


def _seed_queue(
    conn,
    *,
    day: str = _DAY,
    specialist_id: int | None,
    queue_tag: str | None,
    active: bool = True,
    queue_resource_id: int | None = None,
    cabinet_number: str | None = None,
) -> int:
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, "
            "queue_resource_id, queue_tag, active, cabinet_number) "
            "VALUES (:d, :s, :r, :t, :a, :c)"
        ),
        {
            "d": day,
            "s": specialist_id,
            "r": queue_resource_id,
            "t": queue_tag,
            "a": active,
            "c": cabinet_number,
        },
    )
    (queue_id,) = conn.execute(
        sa.text("SELECT id FROM daily_queues ORDER BY id DESC")
    ).fetchone()
    return queue_id


def _seed_entry(conn, queue_id: int, *, status: str = "waiting") -> int:
    conn.execute(
        sa.text(
            "INSERT INTO queue_entries (queue_id, number, status) "
            "VALUES (:q, :n, :s)"
        ),
        {"q": queue_id, "n": 1, "s": status},
    )
    (entry_id,) = conn.execute(
        sa.text("SELECT id FROM queue_entries ORDER BY id DESC")
    ).fetchone()
    return entry_id


def _resource_rows(conn) -> list:
    return conn.execute(
        sa.text(
            "SELECT id, code, queue_tag, display_name, active, "
            "start_number_online, max_online_per_day, default_cabinet "
            "FROM queue_resources ORDER BY id"
        )
    ).fetchall()


def _queue_row(conn, queue_id: int):
    return conn.execute(
        sa.text(
            "SELECT id, day, specialist_id, queue_resource_id, queue_tag, "
            "active FROM daily_queues WHERE id = :q"
        ),
        {"q": queue_id},
    ).fetchone()


def _user_rows(conn) -> list:
    return conn.execute(
        sa.text(
            "SELECT id, username, role, is_active, hashed_password "
            "FROM users ORDER BY id"
        )
    ).fetchall()


def _doctor_rows(conn) -> list:
    return conn.execute(
        sa.text(
            "SELECT id, user_id, specialty, active, cabinet, "
            "start_number_online, max_online_per_day "
            "FROM doctors ORDER BY id"
        )
    ).fetchall()


def _entry_rows(conn, queue_id: int) -> list:
    return conn.execute(
        sa.text(
            "SELECT id, queue_id, number, status FROM queue_entries "
            "WHERE queue_id = :q ORDER BY id"
        ),
        {"q": queue_id},
    ).fetchall()


def _canonical_environment(conn, *, with_queues: bool = True):
    """Lab+ecg proven doctorless, all three synthetics present.

    Returns (lab_doctor_id, ecg_doctor_id, general_doctor_id,
    queue_ids_by_tag)."""
    _seed_service(conn, "lab", code="L01")
    _seed_service(conn, "ecg", code="K10")
    _, lab_doctor_id = _seed_synthetic(conn, "lab_resource", "lab")
    _, ecg_doctor_id = _seed_synthetic(conn, "ecg_resource", "ecg")
    _, general_doctor_id = _seed_synthetic(conn, "general_resource", "general")

    queue_ids: dict[str, list[int]] = {"lab": [], "ecg": []}
    if with_queues:
        queue_ids["lab"].append(
            _seed_queue(conn, specialist_id=lab_doctor_id, queue_tag="lab")
        )
        queue_ids["ecg"].append(
            _seed_queue(conn, specialist_id=ecg_doctor_id, queue_tag="ecg")
        )
    return lab_doctor_id, ecg_doctor_id, general_doctor_id, queue_ids


# ============ A. module structure / source contract ============


def test_migration_module_chain_ids() -> None:
    module = _load_migration_0059()
    assert module.revision == "0059_resource_seed_backfill"
    assert module.down_revision == "0058_queue_resource_expand"


def test_revision_id_fits_alembic_version_column() -> None:
    """alembic's auto-created alembic_version.version_num column is
    VARCHAR(32): a longer revision id passes every scratch-SQLite test
    (SQLite ignores VARCHAR widths) and explodes only on real
    PostgreSQL at the version stamp — exactly what PR #3101 CI
    round-1 caught. Both ends of the new link must fit."""
    module = _load_migration_0059()
    assert len(module.revision) <= 32
    assert len(module.down_revision) <= 32


_SQL_CONSTANT_RE = re.compile(r"^_(SELECT|INSERT|UPDATE|DELETE)_")


def _module_sql_statements(module) -> list[tuple[str, str]]:
    return [
        (name, str(getattr(module, name)))
        for name in sorted(vars(module))
        if _SQL_CONSTANT_RE.match(name)
    ]


def test_migration_is_data_only_no_ddl() -> None:
    """Stage B is a data migration: zero DDL anywhere in the module."""
    module = _load_migration_0059()
    for name, sql in _module_sql_statements(module):
        for pattern in (
            r"\bCREATE\s+(TABLE|INDEX|CONSTRAINT|VIEW|SEQUENCE)\b",
            r"\bALTER\s+TABLE\b",
            r"\bDROP\s+(TABLE|INDEX|CONSTRAINT|COLUMN|VIEW)\b",
            r"\bADD\s+CONSTRAINT\b",
            r"\bTRUNCATE\b",
        ):
            assert not re.search(pattern, sql, re.I), (name, pattern)


def test_migration_never_writes_protected_tables() -> None:
    """The only tables stage B may write are queue_resources and
    daily_queues.queue_resource_id — the synthetic identities
    (users/doctors), the service catalog and queue entries are
    read-only inputs (they carry the old runtime until QD-2C/E), and
    NOTHING is ever deleted (the Codex round-1 P2 ruling: the
    downgrade conserves registry rows because provenance cannot be
    proven)."""
    module = _load_migration_0059()
    writes = [
        sql
        for name, sql in _module_sql_statements(module)
        if re.match(r"^_(INSERT|UPDATE|DELETE)", name)
    ]
    assert writes, "expected the migration to carry write statements"
    for sql in writes:
        assert re.match(
            r"\s*(INSERT\s+INTO\s+queue_resources|UPDATE\s+daily_queues)\b",
            sql,
        ), sql


def test_migration_writes_registry_and_queue_axis() -> None:
    """Positive control: the migration writes exactly its two tables
    and never deletes anything (data-preserving by construction)."""
    module = _load_migration_0059()
    combined = "\n".join(sql for _, sql in _module_sql_statements(module))
    assert "INSERT INTO queue_resources" in combined
    assert "UPDATE daily_queues SET queue_resource_id" in combined
    assert "DELETE" not in combined.upper()


# ===================== B. resource seed =====================


def test_seed_creates_lab_resource_with_canonical_values() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)

        module._apply_seed_and_backfill(conn)

        rows = _resource_rows(conn)
        assert len(rows) == 2
        lab = next(row for row in rows if row.code == "lab")
        # exact-tag identity: code == queue_tag == 'lab' (never the
        # 'laboratory' alias spelling)
        assert lab.queue_tag == "lab"
        # canonical 0055 vocabulary (departments/queue_profiles)
        assert lab.display_name == "Лаборатория"
        assert bool(lab.active) is True
        # numbering TRANSFERRED from the live synthetic Doctor
        assert lab.start_number_online == 1
        assert lab.max_online_per_day == 15
        # no canonical cabinet source exists
        assert lab.default_cabinet is None
    finally:
        conn.close()


def test_seed_creates_ecg_resource_with_canonical_values() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)

        module._apply_seed_and_backfill(conn)

        ecg = next(row for row in _resource_rows(conn) if row.code == "ecg")
        assert ecg.queue_tag == "ecg"
        assert ecg.display_name == "ЭКГ"
        assert bool(ecg.active) is True
        assert ecg.start_number_online == 1
        assert ecg.max_online_per_day == 15
        assert ecg.default_cabinet is None
    finally:
        conn.close()


def test_seed_transfers_live_doctor_numbering_not_constants() -> None:
    """A drifted environment transfers ITS actually-used numbering —
    the queue machinery reads the Doctor row today, so the registry
    must mirror it, not the 0055 seed constants (1/15)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(
            conn,
            "lab_resource",
            "lab",
            start_number_online=5,
            max_online_per_day=40,
        )

        module._apply_seed_and_backfill(conn)

        lab = next(row for row in _resource_rows(conn) if row.code == "lab")
        assert lab.start_number_online == 5
        assert lab.max_online_per_day == 40
    finally:
        conn.close()


def test_no_general_seed_even_when_general_tag_is_doctorless() -> None:
    """general is deliberately conditional (ADR-001 addendum): live
    doctorless 'general' services + a healthy general_resource pair
    do NOT produce a registry row — that is an explicit operator
    decision that must land before stage E."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        _seed_service(conn, "general", code="G01")

        module._apply_seed_and_backfill(conn)

        codes = [row.code for row in _resource_rows(conn)]
        assert codes == ["lab", "ecg"]
    finally:
        conn.close()


def test_no_stomatology_seed_for_doctor_required_tag() -> None:
    """Stomatology requires an actual dentist (the 0055 contract) —
    the migration never converts a doctor-required tag."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        _seed_service(conn, "stomatology", code="S01", requires_doctor=True)

        module._apply_seed_and_backfill(conn)

        codes = [row.code for row in _resource_rows(conn)]
        assert codes == ["lab", "ecg"]
    finally:
        conn.close()


def test_no_procedures_or_cosmetology_inference() -> None:
    """procedures/cosmetology tags are never auto-converted without a
    proven doctorless contract (queue_profiles vocabulary alone is
    not evidence)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        _seed_service(conn, "procedures", code="P01")
        _seed_service(conn, "cosmetology", code="C01")

        module._apply_seed_and_backfill(conn)

        codes = [row.code for row in _resource_rows(conn)]
        assert codes == ["lab", "ecg"]
    finally:
        conn.close()


def test_doctor_required_tag_is_not_converted_to_resource() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01", requires_doctor=True)
        _seed_service(conn, "ecg", code="K10")
        _seed_synthetic(conn, "lab_resource", "lab")
        _seed_synthetic(conn, "ecg_resource", "ecg")

        module._apply_seed_and_backfill(conn)

        codes = [row.code for row in _resource_rows(conn)]
        assert codes == ["ecg"]
    finally:
        conn.close()


def test_no_services_no_seeds_clean_noop() -> None:
    """The CI postgres chain (empty catalog) is a clean no-op."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_synthetic(conn, "lab_resource", "lab")

        report = module._apply_seed_and_backfill(conn)

        assert _resource_rows(conn) == []
        assert report == {}
    finally:
        conn.close()


def test_inactive_services_do_not_prove_the_tag() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01", active=False)
        _seed_synthetic(conn, "lab_resource", "lab")

        module._apply_seed_and_backfill(conn)

        assert _resource_rows(conn) == []
    finally:
        conn.close()


def test_alias_spelling_does_not_seed_the_resource() -> None:
    """Exact-tag semantics: a 'laboratory' queue_tag is a DIFFERENT
    tag, not an alias of 'lab' — no seed, no abort."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "laboratory", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")

        module._apply_seed_and_backfill(conn)

        assert _resource_rows(conn) == []
    finally:
        conn.close()


def test_seed_idempotent_exact_state() -> None:
    """An exact-identity occupant (hand-applied incident fix) is a
    safe no-op — the row is never duplicated or overwritten."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)

        module._apply_seed_and_backfill(conn)
        first = _resource_rows(conn)
        assert len(first) == 2

        module._apply_seed_and_backfill(conn)  # must not raise
        second = _resource_rows(conn)
        assert second == first
    finally:
        conn.close()


def test_seed_abort_conflicting_existing_code_occupant() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория X', true, 1, 15, NULL)"
            )
        )

        with pytest.raises(RuntimeError, match="incompatible row"):
            module._apply_seed_and_backfill(conn)

        # the unexpected occupant is never overwritten
        (row,) = _resource_rows(conn)
        assert row.display_name == "Лаборатория X"
    finally:
        conn.close()


def test_seed_abort_conflicting_queue_tag_occupant() -> None:
    """A row holding queue_tag='lab' under a different code (e.g. an
    operator's own 'laboratory' registry row) blocks the seed."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('laboratory', 'lab', 'Лаборатория', true, 1, 15, "
                "NULL)"
            )
        )

        with pytest.raises(RuntimeError, match="incompatible row"):
            module._apply_seed_and_backfill(conn)

        (row,) = _resource_rows(conn)
        assert row.code == "laboratory"
    finally:
        conn.close()


def test_seed_abort_numbering_mismatch_occupant() -> None:
    """Incompatible numbering configuration aborts (the registry must
    mirror the live synthetic config)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', true, 2, 15, NULL)"
            )
        )

        with pytest.raises(RuntimeError, match="start_number_online"):
            module._apply_seed_and_backfill(conn)

        (row,) = _resource_rows(conn)
        assert row.start_number_online == 2
    finally:
        conn.close()


def test_seed_abort_inactive_occupant() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', false, 1, 15, NULL)"
            )
        )

        with pytest.raises(RuntimeError, match="active"):
            module._apply_seed_and_backfill(conn)

        (row,) = _resource_rows(conn)
        assert bool(row.active) is False
    finally:
        conn.close()


def test_seed_abort_default_cabinet_occupant() -> None:
    """A non-NULL default_cabinet is not the expected identity (no
    canonical cabinet source exists)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', true, 1, 15, '404')"
            )
        )

        with pytest.raises(RuntimeError, match="default_cabinet"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


# ===================== C. service gate =====================


def test_homogeneous_doctorless_tags_accepted() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_service(conn, "lab", code="L02")
        _seed_service(conn, "ecg", code="K10")
        _seed_synthetic(conn, "lab_resource", "lab")
        _seed_synthetic(conn, "ecg_resource", "ecg")

        module._apply_seed_and_backfill(conn)

        assert sorted(row.code for row in _resource_rows(conn)) == [
            "ecg",
            "lab",
        ]
    finally:
        conn.close()


def test_mixed_requires_doctor_semantics_abort() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_service(conn, "lab", code="L02", requires_doctor=True)
        _seed_synthetic(conn, "lab_resource", "lab")

        with pytest.raises(RuntimeError, match="mixed requires_doctor"):
            module._apply_seed_and_backfill(conn)

        assert _resource_rows(conn) == []
    finally:
        conn.close()


# ===================== D. synthetic pair validation =====================


def test_abort_when_synthetic_user_missing() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")

        with pytest.raises(RuntimeError, match="exactly one user row"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_when_synthetic_doctor_missing() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_user(conn, "lab_resource")

        with pytest.raises(RuntimeError, match="exactly one linked Doctor"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_when_specialty_mismatch() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab", specialty="general")

        with pytest.raises(RuntimeError, match="specialty"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_when_synthetic_user_inactive() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab", user_active=False)

        with pytest.raises(RuntimeError, match="inactive"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_when_synthetic_doctor_inactive() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab", doctor_active=False)

        with pytest.raises(RuntimeError, match="inactive"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_when_duplicate_doctor_linkage() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        user_id = _seed_user(conn, "lab_resource")
        _seed_doctor(conn, user_id, specialty="lab")
        _seed_doctor(conn, user_id, specialty="lab")

        with pytest.raises(RuntimeError, match="exactly one linked Doctor"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


# ===================== E. backfill =====================


def test_backfill_dedicated_lab_synthetic_queue() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, queues = _canonical_environment(conn)
        queue_id = queues["lab"][0]
        _seed_entry(conn, queue_id, status="waiting")
        _seed_entry(conn, queue_id, status="served")

        module._apply_seed_and_backfill(conn)

        row = _queue_row(conn, queue_id)
        (resource,) = [r for r in _resource_rows(conn) if r.code == "lab"]
        # the bridge: resource set, specialist PRESERVED
        assert row.queue_resource_id == resource.id
        assert row.specialist_id == lab_doctor_id
        assert row.queue_tag == "lab"
        assert bool(row.active) is True
    finally:
        conn.close()


def test_backfill_dedicated_ecg_synthetic_queue() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, ecg_doctor_id, _, queues = _canonical_environment(conn)
        queue_id = queues["ecg"][0]

        module._apply_seed_and_backfill(conn)

        row = _queue_row(conn, queue_id)
        (resource,) = [r for r in _resource_rows(conn) if r.code == "ecg"]
        assert row.queue_resource_id == resource.id
        assert row.specialist_id == ecg_doctor_id
    finally:
        conn.close()


def test_backfill_general_resource_lab_queue_lands_on_lab() -> None:
    """Destination is queue.queue_tag (exact-tag-wins), NEVER the
    owner username: a general_resource-owned lab queue bridges onto
    the LAB resource, and no general registry row appears."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, _, general_doctor_id, _ = _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(conn, specialist_id=general_doctor_id, queue_tag="lab")

        module._apply_seed_and_backfill(conn)

        row = _queue_row(conn, queue_id)
        (resource,) = [r for r in _resource_rows(conn) if r.code == "lab"]
        assert row.queue_resource_id == resource.id
        assert row.specialist_id == general_doctor_id
        assert all(r.code != "general" for r in _resource_rows(conn))
    finally:
        conn.close()


def test_backfill_general_resource_ecg_queue_lands_on_ecg() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, _, general_doctor_id, _ = _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(conn, specialist_id=general_doctor_id, queue_tag="ecg")

        module._apply_seed_and_backfill(conn)

        row = _queue_row(conn, queue_id)
        (resource,) = [r for r in _resource_rows(conn) if r.code == "ecg"]
        assert row.queue_resource_id == resource.id
    finally:
        conn.close()


def test_backfill_inactive_historical_queue() -> None:
    """Inactive dedicated/general-owned rows are history WITH a proven
    resource identity — they bridge too (abort scope is the active
    routing surface only)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(
            conn, specialist_id=lab_doctor_id, queue_tag="lab", active=False
        )

        module._apply_seed_and_backfill(conn)

        row = _queue_row(conn, queue_id)
        (resource,) = [r for r in _resource_rows(conn) if r.code == "lab"]
        assert row.queue_resource_id == resource.id
        assert bool(row.active) is False
    finally:
        conn.close()


def test_backfill_covers_multiple_days() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        day_1 = _seed_queue(
            conn, day=_DAY, specialist_id=lab_doctor_id, queue_tag="lab"
        )
        day_2 = _seed_queue(
            conn, day=_DAY_2, specialist_id=lab_doctor_id, queue_tag="lab"
        )

        module._apply_seed_and_backfill(conn)

        (resource,) = [r for r in _resource_rows(conn) if r.code == "lab"]
        assert _queue_row(conn, day_1).queue_resource_id == resource.id
        assert _queue_row(conn, day_2).queue_resource_id == resource.id
    finally:
        conn.close()


def test_abort_multiple_active_same_day_resource_queues() -> None:
    """NO dedup in stage B: two active lab queues on one day abort
    with the full inventory; the repair is explicit operator work."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, general_doctor_id, _ = _canonical_environment(
            conn, with_queues=False
        )
        first = _seed_queue(conn, specialist_id=lab_doctor_id, queue_tag="lab")
        _seed_entry(conn, first, status="waiting")
        second = _seed_queue(conn, specialist_id=general_doctor_id, queue_tag="lab")

        with pytest.raises(RuntimeError, match="multiple ACTIVE queues") as (exc_info):
            module._apply_seed_and_backfill(conn)

        message = str(exc_info.value)
        assert f"queue id={first}" in message
        assert f"queue id={second}" in message
        assert "entries=1/live=1" in message
        # nothing was mutated before the abort
        assert _queue_row(conn, first).queue_resource_id is None
        assert _queue_row(conn, second).queue_resource_id is None
    finally:
        conn.close()


def test_multiple_inactive_same_day_do_not_abort() -> None:
    """The duplicate policy is scoped to ACTIVE queues: inactive
    historical duplicates bridge without an abort (no uniqueness
    contract exists on inactive rows until QD-2D's partial index)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, general_doctor_id, _ = _canonical_environment(
            conn, with_queues=False
        )
        first = _seed_queue(
            conn, specialist_id=lab_doctor_id, queue_tag="lab", active=False
        )
        second = _seed_queue(
            conn,
            specialist_id=general_doctor_id,
            queue_tag="lab",
            active=False,
        )

        module._apply_seed_and_backfill(conn)  # must not raise

        (resource,) = [r for r in _resource_rows(conn) if r.code == "lab"]
        assert _queue_row(conn, first).queue_resource_id == resource.id
        assert _queue_row(conn, second).queue_resource_id == resource.id
    finally:
        conn.close()


def test_abort_unknown_owner_active_resource_tag_queue() -> None:
    """A human doctor owning an active lab-tag queue is a conflicting
    owner (the morning 'any active doctor' fallback drift) — loud
    abort, operator decides."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        human_user_id = _seed_user(conn, "dr_human", role="Doctor")
        human_doctor_id = _seed_doctor(conn, human_user_id, specialty="cardio")
        queue_id = _seed_queue(conn, specialist_id=human_doctor_id, queue_tag="lab")

        with pytest.raises(RuntimeError, match="unknown/conflicting owner"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id is None
    finally:
        conn.close()


def test_inactive_human_owned_queue_left_untouched() -> None:
    """Historical artifacts outside the routing surface are not
    backfilled and do not abort."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        human_user_id = _seed_user(conn, "dr_human", role="Doctor")
        human_doctor_id = _seed_doctor(conn, human_user_id, specialty="cardio")
        queue_id = _seed_queue(
            conn,
            specialist_id=human_doctor_id,
            queue_tag="lab",
            active=False,
        )

        module._apply_seed_and_backfill(conn)  # must not raise

        assert _queue_row(conn, queue_id).queue_resource_id is None
        assert _queue_row(conn, queue_id).specialist_id == human_doctor_id
    finally:
        conn.close()


def test_abort_unlinked_doctor_owner() -> None:
    """A doctor row without user linkage cannot be classified —
    active resource-tag queue aborts."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        # an orphan doctor row (no user linkage) owning a lab queue
        conn.execute(
            sa.text(
                "INSERT INTO doctors (user_id, specialty, active, "
                "start_number_online, max_online_per_day) "
                "VALUES (NULL, 'lab', 1, 1, 15)"
            )
        )
        (orphan_doctor_id,) = conn.execute(
            sa.text(
                "SELECT id FROM doctors WHERE user_id IS NULL " "AND specialty = 'lab'"
            )
        ).fetchone()
        queue_id = _seed_queue(conn, specialist_id=orphan_doctor_id, queue_tag="lab")

        with pytest.raises(RuntimeError, match="unknown/conflicting owner"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id is None
    finally:
        conn.close()


def test_abort_null_null_owner_active_queue() -> None:
    """specialist_id NULL + queue_resource_id NULL on an active
    resource-tag queue: neither owner axis is set — abort (the app
    never writes this shape pre-QD-2C; drift is loud)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(conn, specialist_id=None, queue_tag="lab")

        with pytest.raises(RuntimeError, match="unknown/conflicting owner"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id is None
    finally:
        conn.close()


def test_abort_foreign_synthetic_owner() -> None:
    """ecg_resource's doctor owning a lab-tag queue: neither the
    dedicated synthetic for the tag nor the general fallback."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, ecg_doctor_id, _, _ = _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(conn, specialist_id=ecg_doctor_id, queue_tag="lab")

        with pytest.raises(RuntimeError, match="unknown/conflicting owner"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id is None
    finally:
        conn.close()


def test_abort_dedicated_synthetic_owning_unknown_tag() -> None:
    """lab_resource must own only 'lab' queues: a foreign/unknown tag
    row under it is ownership drift (alias spellings are NOT silently
    adopted)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        queue_id = _seed_queue(
            conn, specialist_id=lab_doctor_id, queue_tag="procedures"
        )

        with pytest.raises(RuntimeError, match="not its own"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id is None
    finally:
        conn.close()


def test_abort_dedicated_synthetic_owning_null_tag_queue() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        _seed_queue(conn, specialist_id=lab_doctor_id, queue_tag=None)

        with pytest.raises(RuntimeError, match="not its own"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_dedicated_synthetic_owning_alias_tag_queue() -> None:
    """The 'laboratory' alias under lab_resource is a foreign tag —
    the migration does not adopt alias spellings implicitly."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        _seed_queue(conn, specialist_id=lab_doctor_id, queue_tag="laboratory")

        with pytest.raises(RuntimeError, match="not its own"):
            module._apply_seed_and_backfill(conn)
    finally:
        conn.close()


def test_abort_corrupt_resource_reference() -> None:
    """An ecg-tag queue pointing at the LAB registry row (any row
    other than the tag's own resource) is a corrupt reference —
    always loud."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, ecg_doctor_id, _, _ = _canonical_environment(conn, with_queues=False)
        # a hand-applied lab registry row with the exact expected
        # identity (accepted as a no-op by the lab pass)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', true, 1, 15, NULL)"
            )
        )
        (occupant_id,) = conn.execute(
            sa.text("SELECT id FROM queue_resources WHERE code = 'lab'")
        ).fetchone()
        # an ecg-tag queue owned by the ecg synthetic but pointing at
        # the LAB registry row — corrupt reference, not drift
        queue_id = _seed_queue(
            conn,
            specialist_id=ecg_doctor_id,
            queue_tag="ecg",
            queue_resource_id=occupant_id,
        )

        with pytest.raises(RuntimeError, match="corrupt reference"):
            module._apply_seed_and_backfill(conn)

        assert _queue_row(conn, queue_id).queue_resource_id == occupant_id
    finally:
        conn.close()


def test_backfill_idempotent_rerun() -> None:
    """A second pass over already-bridged rows is a no-op (the exact
    shape a hand-applied incident fix leaves behind)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn)
        lab_queue_id = conn.execute(
            sa.text("SELECT id FROM daily_queues WHERE queue_tag = 'lab'")
        ).scalar()
        ecg_queue_id = conn.execute(
            sa.text("SELECT id FROM daily_queues WHERE queue_tag = 'ecg'")
        ).scalar()

        module._apply_seed_and_backfill(conn)
        before = (
            _queue_row(conn, lab_queue_id),
            _queue_row(conn, ecg_queue_id),
        )

        module._apply_seed_and_backfill(conn)  # must not raise

        after = (
            _queue_row(conn, lab_queue_id),
            _queue_row(conn, ecg_queue_id),
        )
        assert after == before
    finally:
        conn.close()


def test_backfill_queue_entries_untouched() -> None:
    """Entries are never merged, moved or rewritten — only read for
    abort inventory counts."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, _, _, queues = _canonical_environment(conn)
        queue_id = queues["lab"][0]
        _seed_entry(conn, queue_id, status="waiting")
        _seed_entry(conn, queue_id, status="called")
        _seed_entry(conn, queue_id, status="served")
        before = _entry_rows(conn, queue_id)

        module._apply_seed_and_backfill(conn)

        assert _entry_rows(conn, queue_id) == before
        assert len(before) == 3
    finally:
        conn.close()


def test_no_queue_rows_clean_noop() -> None:
    """Production today: daily_queues = 0 — the backfill is a clean
    no-op, only the seeds land."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)

        report = module._apply_seed_and_backfill(conn)

        assert report == {"lab": 0, "ecg": 0}
        assert len(_resource_rows(conn)) == 2
    finally:
        conn.close()


# ===================== F. preservation =====================


def test_synthetic_rows_byte_identical() -> None:
    """The synthetic User+Doctor pairs carry the old runtime until
    QD-2C/QD-2E — every column is identical before and after."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn)

        users_before = _user_rows(conn)
        doctors_before = _doctor_rows(conn)

        module._apply_seed_and_backfill(conn)

        assert _user_rows(conn) == users_before
        assert _doctor_rows(conn) == doctors_before
    finally:
        conn.close()


def test_human_doctor_selector_rows_unchanged() -> None:
    """Human doctors (selectors, booking surfaces) are read-only
    inputs to stage B — nothing about them moves."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        human_user_id = _seed_user(conn, "dr_human", role="Doctor")
        human_doctor_id = _seed_doctor(
            conn, human_user_id, specialty="cardio", start_number_online=10
        )
        doctors_before = _doctor_rows(conn)

        module._apply_seed_and_backfill(conn)

        assert _doctor_rows(conn) == doctors_before
        assert len(doctors_before) == 4  # 3 synthetics + 1 human
        assert doctors_before[-1].id == human_doctor_id
    finally:
        conn.close()


def test_services_catalog_unchanged() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        services_before = conn.execute(
            sa.text(
                "SELECT id, code, name, queue_tag, requires_doctor, "
                "active FROM services ORDER BY id"
            )
        ).fetchall()

        module._apply_seed_and_backfill(conn)

        services_after = conn.execute(
            sa.text(
                "SELECT id, code, name, queue_tag, requires_doctor, "
                "active FROM services ORDER BY id"
            )
        ).fetchall()
        assert services_after == services_before
    finally:
        conn.close()


def test_lab_seed_role_agnostic() -> None:
    """QD-0 resolution is role-agnostic and roles legitimately moved
    Lab -> Resource across 0055-0057: the pair validation must not
    pin the role spelling (a pre-0057 'Lab' spelling seeds fine)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab", role="Lab")

        module._apply_seed_and_backfill(conn)  # must not raise

        (row,) = _resource_rows(conn)
        assert row.code == "lab"
    finally:
        conn.close()


def test_transaction_atomicity_rolls_back_earlier_seed() -> None:
    """The whole migration is one alembic transaction (spec order:
    lab first, ecg second): an abort in the LATER tag rolls back the
    EARLIER tag's seed (PG transactional DDL; pinned here with an
    explicit transaction + rollback)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        # lab is clean and would seed; ecg is proven doctorless but
        # its synthetic pair is missing — the second tag aborts
        _seed_service(conn, "lab", code="L01")
        _seed_synthetic(conn, "lab_resource", "lab")
        _seed_service(conn, "ecg", code="K10")
        conn.commit()  # settle the fixture, start a clean transaction

        tx = conn.begin()
        with pytest.raises(RuntimeError, match="exactly one user row"):
            module._apply_seed_and_backfill(conn)
        tx.rollback()

        assert _resource_rows(conn) == []
    finally:
        conn.close()


# ===================== G. downgrade =====================


def test_downgrade_conserves_references_and_registry_rows() -> None:
    """Downgrade CONSERVES both axes of what 0059 wrote: the registry
    rows AND the queue_resource_id references. No provenance marker
    can distinguish an exact-identity occupant (or a pre-existing
    link) from what this revision inserted/backfilled (Codex
    round-1 P2 for the rows, round-2 P2 for the references), so
    data wins: the dual-ownership bridge keeps both owners on every
    backfilled row, the references stay inert until QD-2C, and
    downgrading further drops the table and the column themselves."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, queues = _canonical_environment(conn)

        module._apply_seed_and_backfill(conn)
        seeded = _resource_rows(conn)
        assert len(seeded) == 2
        lab_resource = next(row for row in seeded if row.code == "lab")

        module._restore_pre_seed_state(conn)

        # the reference survives: provenance cannot be proven, so the
        # link stays (the specialist axis is untouched — both owners
        # remain set, nothing is orphaned)
        row = _queue_row(conn, queues["lab"][0])
        assert row.queue_resource_id == lab_resource.id
        assert row.specialist_id == lab_doctor_id
        assert row.queue_tag == "lab"
        assert bool(row.active) is True
        # ...and the registry rows survive unchanged
        assert _resource_rows(conn) == seeded
    finally:
        conn.close()


def test_downgrade_preserves_preexisting_exact_identity_row() -> None:
    """The Codex round-1 P2 scenario: a hand-applied lab registry row
    that PRE-DATES the migration (upgrade no-ops on it and only
    backfills the reference) must survive the downgrade — rolling
    back 0059 can never destroy data that existed before it."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        # the pre-existing hand-applied row (exact expected identity)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', true, 1, 15, NULL)"
            )
        )
        (preexisting_id,) = conn.execute(
            sa.text("SELECT id FROM queue_resources WHERE code = 'lab'")
        ).fetchone()
        queue_id = _seed_queue(conn, specialist_id=lab_doctor_id, queue_tag="lab")

        # upgrade: exact-identity no-op for lab, only the backfill runs
        module._apply_seed_and_backfill(conn)
        assert _queue_row(conn, queue_id).queue_resource_id == preexisting_id

        module._restore_pre_seed_state(conn)

        # the pre-existing row is intact — byte-identical (the ecg
        # seed also survives: the conservative contract deletes
        # nothing, ever)
        rows = _resource_rows(conn)
        assert sorted(row.code for row in rows) == ["ecg", "lab"]
        lab_row = next(row for row in rows if row.code == "lab")
        assert lab_row.id == preexisting_id
        assert lab_row.queue_tag == "lab"
        assert lab_row.display_name == "Лаборатория"
        assert bool(lab_row.active) is True
        assert lab_row.start_number_online == 1
        assert lab_row.max_online_per_day == 15
        assert lab_row.default_cabinet is None
        # and the backfill link also survives — the conservative
        # contract clears nothing, ever (round-2 P2: the link's
        # provenance is exactly as unprovable as the row's)
        assert _queue_row(conn, queue_id).queue_resource_id == preexisting_id
    finally:
        conn.close()


def test_downgrade_preserves_preexisting_hand_applied_link() -> None:
    """The Codex round-2 P2 scenario, pinned end-to-end: a 0058-era
    installation may already hold BOTH a hand-applied exact-identity
    registry row AND a queue linked to it (a state the upgrade's
    no-op path deliberately accepts — _seed_resource no-ops on the
    row, _backfill_tag no-ops on the link). The downgrade must not
    destroy that operator-owned link: _SELECT_REFERENCING_QUEUES
    cannot distinguish a reference 0059 backfilled from one that
    pre-dates it, so nulling "all references" was silently clearing
    operator data. The conservative contract (round-1 P2 for rows,
    round-2 P2 for references) conserves both — byte-identical."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        lab_doctor_id, _, _, _ = _canonical_environment(conn, with_queues=False)
        # the hand-applied 0058-era state: registry row + linked queue
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('lab', 'lab', 'Лаборатория', true, 1, 15, NULL)"
            )
        )
        (preexisting_id,) = conn.execute(
            sa.text("SELECT id FROM queue_resources WHERE code = 'lab'")
        ).fetchone()
        queue_id = _seed_queue(
            conn,
            specialist_id=lab_doctor_id,
            queue_tag="lab",
            queue_resource_id=preexisting_id,
        )

        # upgrade: exact-identity no-op for the row AND the link
        module._apply_seed_and_backfill(conn)
        assert _queue_row(conn, queue_id).queue_resource_id == preexisting_id

        module._restore_pre_seed_state(conn)

        # the operator-owned link survives byte-identical, the doctor
        # axis untouched — the downgrade wrote nothing at all
        row = _queue_row(conn, queue_id)
        assert row.queue_resource_id == preexisting_id
        assert row.specialist_id == lab_doctor_id
        assert row.queue_tag == "lab"
        assert bool(row.active) is True
        lab_row = next(r for r in _resource_rows(conn) if r.code == "lab")
        assert lab_row.id == preexisting_id
    finally:
        conn.close()


def test_downgrade_refuses_to_orphan_resource_owned_queue() -> None:
    """Stripping a reference that would leave BOTH owners NULL is the
    QD-2A backup-restore P1 shape — the downgrade never produces it
    silently (rows written by a later stage require downgrading that
    stage first)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        module._apply_seed_and_backfill(conn)
        lab_resource = next(row for row in _resource_rows(conn) if row.code == "lab")
        # simulate a LATER stage write: resource-owned, no specialist
        _seed_queue(
            conn,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=lab_resource.id,
        )

        with pytest.raises(RuntimeError, match="orphan"):
            module._restore_pre_seed_state(conn)

        # nothing was cleared or deleted
        assert len(_resource_rows(conn)) == 2
    finally:
        conn.close()


def test_downgrade_keeps_unrelated_registry_rows() -> None:
    """Reference clearing targets only the exact code+queue_tag pair:
    an operator-owned row sharing spelling but not the identity pair
    is never touched (and by the conservative contract, never deleted
    either)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _canonical_environment(conn, with_queues=False)
        module._apply_seed_and_backfill(conn)
        # a hand-made row holding code='laboratory' with queue_tag
        # 'laboratory' (neither matches the lab spec identity pair)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, "
                "display_name, active, start_number_online, "
                "max_online_per_day, default_cabinet) "
                "VALUES ('laboratory', 'laboratory', 'Лаборатория', "
                "true, 1, 15, NULL)"
            )
        )

        module._restore_pre_seed_state(conn)

        # everything survives; nothing is ever deleted
        codes = sorted(row.code for row in _resource_rows(conn))
        assert codes == ["ecg", "lab", "laboratory"]
    finally:
        conn.close()


def test_downgrade_noop_when_nothing_seeded() -> None:
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        module._restore_pre_seed_state(conn)  # must not raise
        assert _resource_rows(conn) == []
    finally:
        conn.close()


def test_downgrade_rerun_after_downgrade_is_still_clean() -> None:
    """Downgrade -> upgrade again is a clean exact-identity no-op for
    the seeds AND the links (the conservative contract keeps the rows
    and the references, so the re-upgrade path is the hand-applied
    state path twice over — rows and links)."""
    module = _load_migration_0059()
    conn = _scratch_connection()
    try:
        _, _, _, queues = _canonical_environment(conn)

        module._apply_seed_and_backfill(conn)
        module._restore_pre_seed_state(conn)
        module._apply_seed_and_backfill(conn)  # must not raise

        row = _queue_row(conn, queues["lab"][0])
        lab_resource = next(r for r in _resource_rows(conn) if r.code == "lab")
        assert row.queue_resource_id == lab_resource.id
        assert len(_resource_rows(conn)) == 2
    finally:
        conn.close()
