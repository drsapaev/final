"""DB invariant tests: doctors.user_id is UNIQUE (1 User = 1 Doctor).

Business invariant (see migration 0048_doctors_user_id_unique):

    1 physical doctor = 1 User account + 1 Doctor profile
    (doctors.user_id UNIQUE; multiple NULLs allowed for historical rows)

Covers:
- ORM/model level: inserting a second Doctor row for the same user_id raises
  IntegrityError (SQLite test DB enforces the column-level UNIQUE that is
  declared on the model and, in production, added by migration 0048).
- Multiple userless Doctor rows (user_id NULL) remain legal.
- Migration pre-condition logic: _duplicate_user_ids() detects duplicates and
  upgrade() aborts with RuntimeError before touching anything.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.clinic import Doctor
from app.models.user import User


def _make_user(db_session, username: str) -> User:
    user = User(username=username, hashed_password="x", role="Doctor")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_two_doctors_cannot_share_one_user(db_session) -> None:
    """Duplicate Doctor.user_id insert must fail at the DB level."""
    user = _make_user(db_session, "uq_dup_user")

    db_session.add(Doctor(user_id=user.id, specialty="stomatology", active=True))
    db_session.commit()

    db_session.add(Doctor(user_id=user.id, specialty="cardiology", active=True))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_multiple_userless_doctors_are_allowed(db_session) -> None:
    """NULL user_id rows (historical data) must NOT violate the constraint."""
    db_session.add_all(
        [
            Doctor(user_id=None, specialty="stomatology", active=True),
            Doctor(user_id=None, specialty="stomatology", active=True),
            Doctor(user_id=None, specialty="cardiology", active=False),
        ]
    )
    db_session.commit()

    count = (
        db_session.query(Doctor).filter(Doctor.user_id.is_(None)).count()
    )
    assert count == 3


def _load_migration():
    path = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "alembic"
        / "versions"
        / "0048_doctors_user_id_unique.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0048", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_doctors_table(engine: sa.Engine) -> sa.Connection:
    """Doctors table WITHOUT the unique constraint, mimicking pre-0048 state."""
    con = engine.connect()
    con.execute(
        sa.text(
            """
            CREATE TABLE doctors (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                specialty VARCHAR(100) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
    )
    con.commit()
    return con


def _scratch_doctors_table_drifted(
    engine: sa.Engine, constraint_sql: str
) -> sa.Connection:
    """Doctors table with schema drift: a constraint named uq_doctors_user_id
    on OTHER columns (not user_id), mimicking a drifted production DB."""
    con = engine.connect()
    con.execute(
        sa.text(
            f"""
            CREATE TABLE doctors (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                specialty VARCHAR(100) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1,
                {constraint_sql}
            )
            """
        )
    )
    con.commit()
    return con


def _seed(con: sa.Connection, sql: str) -> None:
    con.execute(sa.text(sql))
    con.commit()


def test_migration_upgrade_aborts_on_duplicates_and_touches_nothing(tmp_path) -> None:
    """Real upgrade() call: with duplicate links present it must raise
    RuntimeError BEFORE emitting any DDL (constraint must not appear)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'precheck.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (7, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (7, 'stomatology')")

        # Bind a real alembic Operations context to the scratch connection so
        # upgrade() executes for real (op.get_bind(), batch_alter_table, ...).
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))

        with pytest.raises(RuntimeError, match="MIGRATION ABORTED"):
            module.upgrade()

        # Nothing was touched: duplicates still there, no constraint created.
        assert module._duplicate_user_ids(con) == [(7, 2)]
        names = {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        assert "uq_doctors_user_id" not in names
    finally:
        con.close()


def test_migration_upgrade_creates_constraint_on_clean_data(tmp_path) -> None:
    """Real upgrade() call on clean data: constraint created (postcondition)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'clean.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        names = {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        assert "uq_doctors_user_id" in names

        # And the constraint actually enforces uniqueness now.
        with pytest.raises(IntegrityError):
            _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'lab')")
        con.rollback()
    finally:
        con.close()


def test_migration_downgrade_drops_constraint(tmp_path) -> None:
    """Real upgrade() then downgrade(): constraint removed, data preserved."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'down.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()
        assert "uq_doctors_user_id" in {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }

        module.downgrade()
        assert "uq_doctors_user_id" not in {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        # Data preserved by rollback.
        count = con.execute(sa.text("SELECT COUNT(*) FROM doctors")).scalar()
        assert count == 2
    finally:
        con.close()


def test_migration_precondition_passes_without_duplicates(tmp_path) -> None:
    """With clean data, _duplicate_user_ids() returns an empty list."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'clean.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        assert module._duplicate_user_ids(con) == []
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Schema-drift guard (Codex P2 on 0048): a constraint with the expected NAME
# but a DIFFERENT definition must abort the migration, never be silently
# accepted, and user_id must stay non-unique only via an explicit failure.
# ---------------------------------------------------------------------------


def test_migration_aborts_on_wrong_columns_same_name(tmp_path) -> None:
    """Drifted DB: UNIQUE(specialty) named uq_doctors_user_id must abort.

    The migration must NOT stamp the revision (user_id stays non-unique)
    and must NOT silently accept the drifted constraint by name."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'drift_single.db'}")
    con = _scratch_doctors_table_drifted(
        engine, "CONSTRAINT uq_doctors_user_id UNIQUE (specialty)"
    )
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))

        with pytest.raises(RuntimeError, match=r"MIGRATION ABORTED \(precondition\)"):
            module.upgrade()

        # Drift untouched: same-named constraint still on (specialty) only.
        uqs = [
            u
            for u in sa.inspect(con).get_unique_constraints("doctors")
            if u["name"] == "uq_doctors_user_id"
        ]
        assert [u["column_names"] for u in uqs] == [["specialty"]]

        # Revision was NOT stamped: user_id is still non-unique, so a
        # duplicate link insert succeeds (proof of no silent acceptance).
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'lab')")
    finally:
        con.close()


def test_migration_aborts_on_multicolumn_constraint_same_name(tmp_path) -> None:
    """Drifted DB: UNIQUE(user_id, specialty) under the expected name also
    allows duplicate user_id values (differing specialty) -> must abort."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'drift_multi.db'}")
    con = _scratch_doctors_table_drifted(
        engine, "CONSTRAINT uq_doctors_user_id UNIQUE (user_id, specialty)"
    )
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))

        # The abort message must name the offending reflected columns.
        with pytest.raises(RuntimeError, match=r"\['user_id', 'specialty'\]"):
            module.upgrade()
    finally:
        con.close()


def test_migration_upgrade_idempotent_with_correct_constraint(tmp_path) -> None:
    """Correct UNIQUE(user_id) under the expected name -> second upgrade()
    is a validated no-op success (idempotent re-run safety preserved)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'idempotent.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))

        module.upgrade()  # first run: creates the constraint
        module.upgrade()  # second run: must be accepted as a real no-op

        uqs = [
            u
            for u in sa.inspect(con).get_unique_constraints("doctors")
            if u["name"] == "uq_doctors_user_id"
        ]
        assert len(uqs) == 1
        assert uqs[0]["column_names"] == ["user_id"]

        # Uniqueness still enforced after the idempotent pass.
        with pytest.raises(IntegrityError):
            _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'lab')")
        con.rollback()
    finally:
        con.close()


def test_validator_rejects_nulls_not_distinct_variant() -> None:
    """PostgreSQL 15+ reflects UNIQUE NULLS NOT DISTINCT with the same
    column_names == ['user_id'] — the validator must reject it anyway: it
    would permit only ONE userless doctor row, contradicting the
    multiple-NULL semantics promised for historical userless doctors.

    (Unit-level: SQLite reflection cannot produce the PG dialect option,
    so the reflected dict is simulated; the same validator runs in the
    migration precondition/postcondition AND in the production pre-check
    script — single source of truth.)"""
    from alembic import op as alembic_op  # noqa: F401  (module import side effect)

    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic" / "versions" / "0048_doctors_user_id_unique.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0048_nnd", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._assert_valid_user_id_constraint(None, "test") is None
    # NULLS DISTINCT (absent / None / False) is accepted
    module._assert_valid_user_id_constraint(
        {"name": "uq_doctors_user_id", "column_names": ["user_id"]}, "test"
    )
    module._assert_valid_user_id_constraint(
        {
            "name": "uq_doctors_user_id",
            "column_names": ["user_id"],
            "postgresql_nulls_not_distinct": False,
        },
        "test",
    )
    # NULLS NOT DISTINCT must be rejected — in the REAL PostgreSQL
    # reflection shape, where the dialect option is NESTED inside
    # dialect_options (round-5 Codex: a top-level-only key is never produced
    # by actual reflection and would have hidden the regression):
    with pytest.raises(RuntimeError, match="NULLS NOT DISTINCT"):
        module._assert_valid_user_id_constraint(
            {
                "name": "uq_doctors_user_id",
                "column_names": ["user_id"],
                "dialect_options": {"postgresql_nulls_not_distinct": True},
            },
            "test",
        )
    # Defensive fallback: a top-level key (older/other reflection shapes)
    with pytest.raises(RuntimeError, match="NULLS NOT DISTINCT"):
        module._assert_valid_user_id_constraint(
            {
                "name": "uq_doctors_user_id",
                "column_names": ["user_id"],
                "postgresql_nulls_not_distinct": True,
            },
            "test",
        )
    # A NULLS DISTINCT constraint reflected with dialect_options present but
    # the option at its default must keep passing:
    module._assert_valid_user_id_constraint(
        {
            "name": "uq_doctors_user_id",
            "column_names": ["user_id"],
            "dialect_options": {"postgresql_nulls_not_distinct": False},
        },
        "test",
    )
