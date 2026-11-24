"""Verify legacy clinical writes against the retained PostgreSQL schema."""

import io
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema

from tests._pg_admin_guard import is_local_admin_dsn

pytestmark = [pytest.mark.integration, pytest.mark.migration]

_MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic/versions/0108_emr_rollback_compat.py"
)


def _migrate(conn, action, offline):
    spec = spec_from_file_location("emr_rollback_compat_migration", _MIGRATION)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    if offline:
        sql = io.StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": sql}
        )
    else:
        context = MigrationContext.configure(conn)
    with Operations.context(context):
        getattr(migration, action)()
    if offline:
        conn.exec_driver_sql(sql.getvalue())


@pytest.mark.parametrize("offline", [False, True], ids=["online", "offline"])
def test_legacy_writes_invalidate_attribution_after_code_rollback(offline):
    dsn = os.environ.get("DATABASE_URL", "")
    if not is_local_admin_dsn(dsn):
        pytest.skip("requires a disposable local PostgreSQL database")
    url = make_url(dsn)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI") != "true":
        pytest.skip("requires an explicitly disposable PostgreSQL clinic_test database")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            schema = "test_emr_rollback_" + uuid4().hex
            conn.execute(CreateSchema(schema))
            conn.exec_driver_sql(f"SET LOCAL search_path TO {schema}")
            sql = conn.exec_driver_sql
            sql("""
                CREATE TABLE doctor_section_templates (
                    template_text text NOT NULL,
                    reviewed_at timestamptz,
                    template_revision integer NOT NULL DEFAULT 1,
                    shortcut varchar(16)
                )
            """)
            sql("""
                CREATE TABLE prescriptions (
                    medications json,
                    instructions text,
                    doctor_notes text,
                    visit_id integer,
                    emr_record_id integer,
                    emr_revision_id integer,
                    printed_at timestamptz
                )
            """)
            sql(
                "INSERT INTO doctor_section_templates "
                "VALUES ('Synthetic approved text', now(), 4, NULL)"
            )
            _migrate(conn, "upgrade", offline)

            def template_edit(change):
                return sql(
                    f"UPDATE doctor_section_templates SET {change} "
                    "RETURNING template_revision, reviewed_at IS NOT NULL"
                ).one()

            assert template_edit(
                "template_text = template_text, shortcut = 'synthetic'"
            ) == (4, True)
            assert template_edit("template_text = 'Legacy edit'") == (5, False)
            assert template_edit("reviewed_at = now()") == (5, True)
            assert template_edit(
                "template_text = 'Current edit', reviewed_at = NULL, template_revision = 6"
            ) == (6, False)

            sql("""INSERT INTO prescriptions (medications, visit_id, emr_record_id)
                   VALUES ('[{"name":"Synthetic A"}]', 8, 2)""")

            def prescription_edit(change):
                return sql(
                    f"UPDATE prescriptions SET {change} RETURNING emr_revision_id"
                ).scalar_one()

            assert prescription_edit("emr_revision_id = 10") == 10
            assert prescription_edit("printed_at = now()") == 10
            assert prescription_edit("""medications = '[ { "name": "Synthetic A" } ]'""") == 10
            assert prescription_edit("""medications = '[{"name":"Synthetic B"}]'""") is None
            assert prescription_edit(
                """medications = '[{"name":"Synthetic A"}]', emr_revision_id = 10"""
            ) == 10
            assert prescription_edit(
                """medications = '[{"name":"Synthetic C"}]', emr_revision_id = 11"""
            ) == 11
            assert prescription_edit("instructions = 'Legacy instructions'") is None
            assert prescription_edit("emr_revision_id = 12") == 12
            assert prescription_edit("doctor_notes = 'Legacy note'") is None
            assert prescription_edit("emr_revision_id = 13") == 13
            assert prescription_edit("visit_id = 9") is None

            _migrate(conn, "downgrade", offline)
            assert template_edit("reviewed_at = now()") == (6, True)
            assert template_edit("template_text = 'After downgrade'") == (6, True)
            assert prescription_edit("emr_revision_id = 13") == 13
            assert prescription_edit("instructions = 'After downgrade'") == 13
            # Closing the uncommitted transaction removes the scratch schema.
    finally:
        engine.dispose()
