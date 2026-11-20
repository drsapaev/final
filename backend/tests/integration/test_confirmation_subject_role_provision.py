"""Provision and exercise 0116 with a real nonowner LOGIN under forced RLS."""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_patient_owner_confirmation_migration import _setup


def _provision_module():
    path = Path(__file__).resolve().parents[3] / "scripts/provision_confirmation_subject_role.py"
    spec = importlib.util.spec_from_file_location("confirmation_subject_provision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_forced_rls_trigger_uses_isolated_nologin_capability():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    url = make_url(raw)
    suffix = uuid.uuid4().hex
    schema, shadow = "subject_cap_" + suffix, "subject_fake_" + suffix
    private = capability_schema_name(schema)
    cap, runtime, password = "subject_fn_" + suffix, "subject_app_" + suffix, uuid.uuid4().hex
    other_cap = "other_cap_" + suffix
    owner_member = "owner_member_" + suffix
    schema_owner = "subject_owner_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE ROLE "{schema_owner}" NOLOGIN'))
        conn.execute(text(f'CREATE SCHEMA "{schema}" AUTHORIZATION "{schema_owner}"'))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{cap}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{other_cap}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{owner_member}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{runtime}" LOGIN PASSWORD \'{password}\''))
    owner = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    login = create_engine(url.set(username=runtime, password=password), connect_args={"options": f"-csearch_path={shadow},{schema},pg_catalog"})
    try:
        with owner.begin() as conn:
            _setup(conn)
            conn.execute(text(f'ALTER TABLE "{schema}".visits ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".visits FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".patients ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".patients FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'CREATE TABLE "{shadow}".visits AS SELECT * FROM "{schema}".visits'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}","{shadow}" TO "{runtime}"'))
            conn.execute(text(f'GRANT CREATE ON SCHEMA "{shadow}" TO "{runtime}"'))
        provision = _provision_module().provision
        expected_owner = schema_owner
        provision(admin, schema, cap, runtime, expected_owner=expected_owner)
        with owner.begin() as conn:
            conn.execute(text(f'ALTER FUNCTION "{private}".invalidate_patient_owner_confirmations() SET search_path="{shadow}"'))
        with pytest.raises(RuntimeError, match="configuration differs"):
            provision(admin, schema, cap, runtime, expected_owner=expected_owner)
        with owner.begin() as conn:
            conn.execute(text(f'ALTER FUNCTION "{private}".invalidate_patient_owner_confirmations() SET search_path=pg_catalog'))
        with admin.begin() as conn:
            conn.execute(text(f'GRANT "{expected_owner}" TO "{owner_member}"'))
        with pytest.raises(RuntimeError, match="Owner membership"):
            provision(admin, schema, cap, runtime, expected_owner=expected_owner)
        approved_members = (owner_member,)
        helper = _provision_module()._namespace_helper()
        with admin.begin() as conn:
            helper.merge_namespace_roles(conn, schema, expected_owner=expected_owner,
                                         backend_roles=(), capability_owner_roles=(other_cap,),
                                         trusted_owner_members=approved_members)
        provision(admin, schema, cap, runtime, expected_owner=expected_owner, trusted_owner_members=approved_members)
        provision(admin, schema, cap, runtime, expected_owner=expected_owner, trusted_owner_members=approved_members)  # safe, idempotent replay
        with admin.begin() as conn:
            profile = dict(conn.execute(text(f'SELECT role_name,role_kind FROM "{private}".clinic_capability_role_profile')).all())
            assert profile == {other_cap: "capability_owner", cap: "capability_owner", runtime: "backend"}
            assert not conn.execute(text("SELECT pg_catalog.has_any_column_privilege(:role,:table,'UPDATE')"),
                                    {"role": runtime, "table": f'"{schema}".patients'}).scalar_one()
        with login.connect() as holder, owner.connect() as competitor:
            held = holder.begin()
            blocked = competitor.begin()
            try:
                assert holder.execute(text(f'SELECT "{private}".lock_confirmation_patient(1)')).scalar_one() is True
                competitor.execute(text("SET LOCAL lock_timeout='150ms'"))
                with pytest.raises(DBAPIError) as conflict:
                    competitor.execute(text(f'UPDATE "{schema}".patients SET user_id=2 WHERE id=1'))
                assert conflict.value.orig.sqlstate == "55P03"
            finally:
                blocked.rollback()
                held.rollback()
        with login.begin() as conn:
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text(f'UPDATE "{schema}".patients SET user_id=2 WHERE id=1'))
        with owner.begin() as conn:
            conn.execute(text(f'SET LOCAL ROLE "{cap}"'))
            with pytest.raises(DBAPIError) as forbidden, conn.begin_nested():
                conn.execute(text(f'UPDATE "{schema}".patients SET id=id WHERE id=1'))
            assert forbidden.value.orig.sqlstate == "42501"
        with owner.begin() as conn:
            conn.execute(text(f'CREATE POLICY synthetic_public_update ON "{schema}".patients FOR UPDATE TO PUBLIC USING (true) WITH CHECK (true)'))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'SELECT "{private}".lock_confirmation_patient(1)'))
        with pytest.raises(RuntimeError, match="Another patient UPDATE policy"):
            provision(admin, schema, cap, runtime, expected_owner=expected_owner, trusted_owner_members=approved_members)
        with owner.begin() as conn:
            conn.execute(text(f'DROP POLICY synthetic_public_update ON "{schema}".patients'))
        with owner.begin() as conn:
            conn.execute(text(f'ALTER POLICY owner_confirmation_patient_select ON "{schema}".patients USING (false)'))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'SELECT "{private}".lock_confirmation_patient(1)'))
        with owner.begin() as conn:
            conn.execute(text(f'ALTER POLICY owner_confirmation_patient_select ON "{schema}".patients USING (true)'))
            # The application has a separately authorized owner-change flow;
            # this synthetic grant is not part of subject provisioning.
            conn.execute(text(f'GRANT UPDATE(user_id) ON "{schema}".patients TO "{runtime}"'))
            conn.execute(text(f'CREATE POLICY synthetic_owner_update ON "{schema}".patients FOR UPDATE TO "{runtime}" USING (true) WITH CHECK (true)'))
        with login.begin() as conn:
            conn.execute(text(f'CREATE TABLE "{shadow}".forged_patient (id INTEGER, user_id INTEGER, is_deleted BOOLEAN)'))
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text(f'CREATE TRIGGER forged AFTER UPDATE ON "{shadow}".forged_patient FOR EACH ROW EXECUTE FUNCTION "{private}".invalidate_patient_owner_confirmations()'))
        with login.begin() as conn:
            conn.execute(text("CREATE TYPE pg_temp.oid AS ENUM ('SYNTHETIC')"))
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=2 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT confirmation_token FROM "{schema}".visits WHERE id=1')).scalar_one() is None
            assert conn.execute(text(f'SELECT confirmation_token FROM "{schema}".visits WHERE id=2')).scalar_one() == 'other-token'
            assert conn.execute(text(f'SELECT confirmation_token FROM "{shadow}".visits WHERE id=1')).scalar_one() == 'original-token'
            conn.execute(text(f'ALTER POLICY owner_confirmation_role_select ON "{schema}".visits USING (false)'))
            conn.execute(text(f"UPDATE \"{schema}\".visits SET confirmation_token='still-current' WHERE id=1"))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT user_id FROM "{schema}".patients WHERE id=1')).scalar_one() == 2
            assert conn.execute(text(f'SELECT confirmation_token FROM "{schema}".visits WHERE id=1')).scalar_one() == 'still-current'
            conn.execute(text(f'ALTER POLICY owner_confirmation_role_select ON "{schema}".visits USING (true)'))
            conn.execute(text(f'GRANT "{cap}" TO "{runtime}"'))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT user_id FROM "{schema}".patients WHERE id=1')).scalar_one() == 2
            conn.execute(text(f'REVOKE "{cap}" FROM "{runtime}"'))
            conn.execute(text(f'GRANT TRIGGER ON "{schema}".visits TO "{runtime}"'))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT user_id FROM "{schema}".patients WHERE id=1')).scalar_one() == 2
            conn.execute(text(f'REVOKE TRIGGER ON "{schema}".visits FROM "{runtime}"'))
            conn.execute(text(f'GRANT CREATE ON SCHEMA "{private}" TO "{runtime}"'))
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT user_id FROM "{schema}".patients WHERE id=1')).scalar_one() == 2
            conn.execute(text(f'REVOKE CREATE ON SCHEMA "{private}" FROM "{runtime}"'))
            conn.execute(text(f"UPDATE \"{schema}\".visits SET confirmation_token='before-reupgrade' WHERE id=1"))
            migration = _migration("0116_patient_owner_confirmation.py")
            migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
            migration.downgrade()
            migration.upgrade()
        # Re-upgrade returns the function to its reviewed invoker state. It
        # cannot silently skip hidden visits until the role is reprovisioned.
        with pytest.raises(DBAPIError), login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT confirmation_token FROM "{schema}".visits WHERE id=1')).scalar_one() == "before-reupgrade"
        provision(admin, schema, cap, runtime, expected_owner=expected_owner, trusted_owner_members=approved_members)
        with login.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=1 WHERE id=1'))
        with owner.begin() as conn:
            assert conn.execute(text(f'SELECT confirmation_token FROM "{schema}".visits WHERE id=1')).scalar_one() is None
    finally:
        login.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(private, cascade=True))
            conn.execute(text(f'REVOKE "{schema_owner}" FROM "{owner_member}"'))
            conn.execute(text(f'DROP ROLE "{runtime}"'))
            conn.execute(text(f'DROP ROLE "{cap}"'))
            conn.execute(text(f'DROP ROLE "{other_cap}"'))
            conn.execute(text(f'DROP ROLE "{owner_member}"'))
            conn.execute(text(f'DROP ROLE "{schema_owner}"'))
        admin.dispose()
