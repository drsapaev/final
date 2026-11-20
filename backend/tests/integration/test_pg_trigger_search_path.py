"""Runtime trigger relations must not follow an attacker-controlled path."""

import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from tests.integration.test_encounter_migration_pg import _migration, _setup_0103


@pytest.mark.integration
def test_repeat_and_encounter_triggers_ignore_shadow_relations():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex
    trusted, shadow, role = "trigger_real_" + suffix, "trigger_shadow_" + suffix, "trigger_role_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(trusted))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={trusted} -clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            _setup_0103(conn)
            migration = _migration("0104_encounters.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(text("INSERT INTO users (id) VALUES (2)"))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT CREATE ON SCHEMA "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{trusted}" TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{trusted}" TO "{role}"'))
            conn.execute(text(f'CREATE POLICY trigger_test_runtime ON "{trusted}".encounters TO "{role}" USING (true) WITH CHECK (true)'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text(f'CREATE TABLE "{shadow}".doctors AS SELECT * FROM "{trusted}".doctors'))
            conn.execute(text(f'UPDATE "{shadow}".doctors SET user_id=2'))
            conn.execute(text(f'CREATE TABLE "{shadow}".visits AS SELECT * FROM "{trusted}".visits'))
            conn.execute(text(f'CREATE TABLE "{shadow}".queue_entries AS SELECT * FROM "{trusted}".queue_entries'))
            conn.execute(text(f'CREATE FUNCTION "{shadow}".random() RETURNS double precision LANGUAGE sql IMMUTABLE AS $$ SELECT 0::double precision $$'))
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{trusted}", pg_catalog'))

            # The owner snapshot must come from the real Doctor, not shadow.
            conn.execute(text(f"INSERT INTO \"{trusted}\".visits (id,patient_id,doctor_id,visit_date,status) VALUES (6,1,10,'2031-04-01','open')"))
            assigned = conn.execute(text(f'SELECT repeat_assigned_doctor_user_id FROM "{trusted}".visits WHERE id=6')).scalar_one()
            assert assigned == 1
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET repeat_proof_generation=repeat_evidence_generation, repeat_proof_consultation=true, repeat_proof_doctor_user_id=1 WHERE id=1"))
            conn.execute(text(f"INSERT INTO \"{trusted}\".visit_services (id,visit_id,service_id,qty,price) VALUES (20,1,11,1,1)"))
            assert conn.execute(text(f'SELECT repeat_proof_generation FROM "{trusted}".visits WHERE id=1')).scalar_one() is None

            # Rebinding the real doctor must clear the real in-flight Visit.
            conn.execute(text(f'UPDATE "{trusted}".doctors SET user_id=2 WHERE id=10'))
            assert conn.execute(text(f'SELECT repeat_assigned_doctor_user_id FROM "{trusted}".visits WHERE id=6')).scalar_one() is None

            # Anonymous queue-only patient: detachment must affect the real
            # queue, even while a shadow queue_entries is first in the path.
            encounter = conn.execute(text(f"INSERT INTO \"{trusted}\".encounters (patient_id,provenance) VALUES (3,'new') RETURNING id")).scalar_one()
            conn.execute(text(f'UPDATE "{trusted}".queue_entries SET encounter_id=:id WHERE id=4'), {"id": encounter})
            conn.execute(text(f'UPDATE "{trusted}".encounters SET patient_id=NULL WHERE id=:id'), {"id": encounter})
            assert conn.execute(text(f'SELECT encounter_id FROM "{trusted}".queue_entries WHERE id=4')).scalar_one() is None
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            conn.execute(text("RESET ROLE"))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(trusted, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()
