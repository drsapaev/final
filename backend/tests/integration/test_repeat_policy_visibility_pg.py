"""Synthetic feasibility only: this is not the final 0132 migration test."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.services.repeat_policy_visibility import (
    RepeatPolicyBusy,
    RepeatPolicyUnavailable,
    read_postgresql_repeat_policy,
    repeat_policy_lock_function_body,
    repeat_policy_read_function_body,
)


@pytest.fixture
def pg_capability(monkeypatch, request):
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test PostgreSQL database")
    admin = create_engine(url)
    suffix = uuid4().hex[:12]
    app_schema = ('rp"; SELECT 1; --_' if getattr(request, "param", None) == "quoted" else "rp_app_") + suffix
    private = capability_schema_name(app_schema)
    capability, runtime = "rp_cap_" + suffix, "rp_rt_" + suffix
    password = uuid4().hex + uuid4().hex
    quote = admin.dialect.identifier_preparer.quote_identifier
    app_q, private_q, cap_q, runtime_q = map(quote, (app_schema, private, capability, runtime))
    created = False
    try:
        with admin.begin() as db:
            db.execute(text(f"CREATE ROLE {cap_q} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
            db.execute(text(f"CREATE ROLE {runtime_q} LOGIN NOSUPERUSER NOBYPASSRLS"))
            db.execute(text("SELECT pg_catalog.set_config('clinic.test_role', :role, true)"), {"role": runtime})
            db.execute(text("SELECT pg_catalog.set_config('clinic.test_password', :password, true)"), {"password": password})
            db.execute(text("""DO $$ BEGIN EXECUTE pg_catalog.format('ALTER ROLE %I PASSWORD %L',
                pg_catalog.current_setting('clinic.test_role'), pg_catalog.current_setting('clinic.test_password')); END $$"""))
            db.execute(text(f"CREATE SCHEMA {app_q}"))
            db.execute(text(f"CREATE SCHEMA {private_q}"))
            schema_owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": app_schema}).scalar_one()
            db.execute(text(f"CREATE TABLE {app_q}.users (id integer PRIMARY KEY)"))
            db.execute(text(f"CREATE TABLE {app_q}.token_blacklist (id integer PRIMARY KEY)"))
            db.execute(text(f"CREATE TABLE {app_q}.clinic_settings (key varchar(100) PRIMARY KEY, value json)"))
            db.execute(text(f"ALTER TABLE {app_q}.clinic_settings ENABLE ROW LEVEL SECURITY"))
            db.execute(text(f"GRANT USAGE ON SCHEMA {app_q}, {private_q} TO {cap_q}"))
            db.execute(text(f"GRANT USAGE ON SCHEMA {app_q} TO {runtime_q}"))
            db.execute(text(f"GRANT USAGE ON SCHEMA {private_q} TO {runtime_q}"))
            db.execute(text(f"GRANT SELECT ON {app_q}.users, {app_q}.token_blacklist TO {runtime_q}"))
            db.execute(text(f"GRANT SELECT (key,value), UPDATE ON {app_q}.clinic_settings TO {cap_q}"))
            db.execute(text(f"CREATE POLICY repeat_select ON {app_q}.clinic_settings FOR SELECT TO {cap_q} USING (true)"))
            db.execute(text(f"CREATE POLICY repeat_no_update ON {app_q}.clinic_settings FOR UPDATE TO {cap_q} USING (false) WITH CHECK (false)"))
            lock_body = repeat_policy_lock_function_body(app_schema)
            read_body = repeat_policy_read_function_body(app_schema)
            db.execute(text(f"""CREATE FUNCTION {private_q}.repeat_policy_lock()
              RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
              SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
              AS $function${lock_body}$function$"""))
            db.execute(text(f"""CREATE FUNCTION {private_q}.repeat_policy_read()
              RETURNS TABLE(key text, value_text text) LANGUAGE plpgsql SECURITY DEFINER
              SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
              AS $function${read_body}$function$"""))
            db.execute(text(f"GRANT CREATE ON SCHEMA {private_q} TO {cap_q}"))
            db.execute(text(f"ALTER FUNCTION {private_q}.repeat_policy_lock() OWNER TO {cap_q}"))
            db.execute(text(f"ALTER FUNCTION {private_q}.repeat_policy_read() OWNER TO {cap_q}"))
            db.execute(text(f"REVOKE CREATE ON SCHEMA {private_q} FROM {cap_q}"))
            db.execute(text(f"REVOKE ALL ON FUNCTION {private_q}.repeat_policy_lock() FROM PUBLIC"))
            db.execute(text(f"REVOKE ALL ON FUNCTION {private_q}.repeat_policy_read() FROM PUBLIC"))
            db.execute(text(f"GRANT EXECUTE ON FUNCTION {private_q}.repeat_policy_lock() TO {runtime_q}"))
            db.execute(text(f"GRANT EXECUTE ON FUNCTION {private_q}.repeat_policy_read() TO {runtime_q}"))
            db.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_discount','20'),('unrelated','1')"))
        created = True
        login = create_engine(url.set(username=runtime, password=password))
        with login.connect() as db:
            assert db.execute(text("SELECT SESSION_USER")).scalar_one() == runtime
        for name, value in {
            "TRUSTED_DB_SCHEMA": app_schema, "TRUSTED_DB_SCHEMA_OWNER": schema_owner,
            "TRUSTED_DB_RUNTIME_ROLE": runtime, "TRUSTED_DB_OWNER_MEMBERS": (),
            "TRUSTED_AUTH_TABLE_OWNER": schema_owner, "TRUSTED_AUTH_OWNER_MEMBERS": (),
            "TRUSTED_AUTH_READ_ROLES": (), "TRUSTED_AUTH_WRITE_ROLES": (),
            "TRUSTED_AUTH_USERS_OWNER": schema_owner, "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (),
            "TRUSTED_AUTH_USERS_WRITE_ROLES": (),
        }.items():
            monkeypatch.setattr(settings, name, value)
        arguments = {"schema": app_schema, "schema_owner": schema_owner, "runtime_role": runtime,
            "trusted_schema_owner_members": (), "capability_role": capability, "settings_owner": schema_owner,
            "trusted_settings_owner_members": (), "trusted_settings_writers": ()}
        yield admin, login, app_q, private_q, cap_q, runtime_q, arguments
    finally:
        if "login" in locals():
            login.dispose()
        if created:
            with admin.begin() as db:
                db.execute(text(f"DROP SCHEMA {private_q} CASCADE"))
                db.execute(text(f"DROP SCHEMA {app_q} CASCADE"))
                db.execute(text(f"DROP ROLE {runtime_q}"))
                db.execute(text(f"DROP ROLE {cap_q}"))
        admin.dispose()


def test_physical_login_capability_preserves_json_and_lock_after_return(pg_capability):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with login.connect() as reader, admin.connect() as writer:
        session = Session(bind=reader)
        assert read_postgresql_repeat_policy(session, **arguments) == {
            "repeat_visit_days": 21, "repeat_visit_discount": 20}
        writer.execute(text("SET LOCAL lock_timeout='100ms'"))
        with pytest.raises(DBAPIError) as error:
            writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))
        assert (getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)) == "55P03"
        writer.rollback()
        session.rollback()
        writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))
        writer.commit()


def test_rollback_to_prior_savepoint_releases_capability_lock(pg_capability):
    admin, login, app_q, private_q, _, _, _ = pg_capability
    with login.connect() as reader, admin.connect() as writer:
        transaction = reader.begin()
        savepoint = reader.begin_nested()
        reader.execute(text(f"SELECT {private_q}.repeat_policy_lock()" )).scalar_one()
        savepoint.rollback()
        writer.execute(text("SET LOCAL lock_timeout='100ms'"))
        writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))
        writer.commit()
        transaction.rollback()


@pytest.mark.parametrize("tamper", ["hidden_select", "restrictive_select", "public_insert", "public_select", "cap_extra", "second_definer", "body", "lock_body", "lock_acl", "read_acl", "read_language", "lock_language"])
def test_runtime_preflight_rejects_unsafe_policy_acl_or_function(pg_capability, tamper):
    admin, login, app_q, private_q, cap_q, _, arguments = pg_capability
    with admin.begin() as db:
        if tamper == "hidden_select":
            db.execute(text(f"ALTER POLICY repeat_select ON {app_q}.clinic_settings USING (false)"))
        elif tamper == "restrictive_select":
            db.execute(text(f"CREATE POLICY hidden_restriction ON {app_q}.clinic_settings AS RESTRICTIVE FOR SELECT TO {cap_q} USING (true)"))
        elif tamper == "public_insert":
            db.execute(text(f"GRANT INSERT ON {app_q}.clinic_settings TO PUBLIC"))
        elif tamper == "public_select":
            db.execute(text(f"GRANT SELECT (key,value) ON {app_q}.clinic_settings TO PUBLIC"))
        elif tamper == "cap_extra":
            db.execute(text(f"GRANT DELETE ON {app_q}.clinic_settings TO {cap_q}"))
        elif tamper == "second_definer":
            db.execute(text(f"CREATE FUNCTION {private_q}.extra() RETURNS integer LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'"))
            db.execute(text(f"GRANT CREATE ON SCHEMA {private_q} TO {cap_q}"))
            db.execute(text(f"ALTER FUNCTION {private_q}.extra() OWNER TO {cap_q}"))
            db.execute(text(f"REVOKE CREATE ON SCHEMA {private_q} FROM {cap_q}"))
        elif tamper == "lock_acl":
            db.execute(text(f"GRANT EXECUTE ON FUNCTION {private_q}.repeat_policy_lock() TO PUBLIC"))
        elif tamper == "read_acl":
            db.execute(text(f"GRANT EXECUTE ON FUNCTION {private_q}.repeat_policy_read() TO PUBLIC"))
        elif tamper == "lock_body":
            body = repeat_policy_lock_function_body(arguments["schema"]) + "\n-- unexpected change\n"
            db.execute(text(f"""CREATE OR REPLACE FUNCTION {private_q}.repeat_policy_lock()
              RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
              SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
              AS $function${body}$function$"""))
        elif tamper in {"read_language", "lock_language"}:
            db.execute(text("SET LOCAL check_function_bodies=off"))
            if tamper == "read_language":
                body = repeat_policy_read_function_body(arguments["schema"])
                db.execute(text(f"""CREATE OR REPLACE FUNCTION {private_q}.repeat_policy_read()
                  RETURNS TABLE(key text, value_text text) LANGUAGE sql SECURITY DEFINER
                  SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
                  AS $function${body}$function$"""))
            else:
                body = repeat_policy_lock_function_body(arguments["schema"])
                db.execute(text(f"""CREATE OR REPLACE FUNCTION {private_q}.repeat_policy_lock()
                  RETURNS boolean LANGUAGE sql SECURITY DEFINER
                  SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
                  AS $function${body}$function$"""))
        else:
            body = repeat_policy_read_function_body(arguments["schema"]) + "\n-- unexpected change\n"
            db.execute(text(f"""CREATE OR REPLACE FUNCTION {private_q}.repeat_policy_read()
              RETURNS TABLE(key text, value_text text) LANGUAGE plpgsql SECURITY DEFINER
              SET search_path=pg_catalog SET row_security=on SET standard_conforming_strings=on
              AS $function${body}$function$"""))
    with Session(login) as db, pytest.raises(RepeatPolicyUnavailable):
        read_postgresql_repeat_policy(db, **arguments)


def test_runtime_preserves_json_lexical_precision_and_rolls_back_on_bad_policy(pg_capability):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with admin.begin() as db:
        db.execute(text(f"UPDATE {app_q}.clinic_settings SET value='0.99999999999999999999' WHERE key='repeat_visit_discount'"))
    with Session(login) as reader:
        with pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(reader, **arguments)
        # The rejected snapshot releases its SHARE lock immediately.
        with admin.begin() as writer:
            writer.execute(text("SET LOCAL lock_timeout='100ms'"))
            writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))


@pytest.mark.parametrize("toxic", ["rls", "rls_extra", "rls_extra_all", "cast"])
def test_toxic_policy_and_cast_are_not_executed_before_validation(pg_capability, toxic):
    admin, login, app_q, private_q, _, _, arguments = pg_capability
    with admin.begin() as db:
        db.execute(text(f"CREATE SEQUENCE {app_q}.synthetic_effect"))
        # A public sequence grant is confined to this synthetic schema; a
        # sequence increment survives rollback and detects actual execution.
        db.execute(text(f"GRANT USAGE ON SEQUENCE {app_q}.synthetic_effect TO PUBLIC"))
        if toxic.startswith("rls"):
            db.execute(text(f"""CREATE FUNCTION {app_q}.toxic_policy() RETURNS boolean
              LANGUAGE plpgsql SECURITY INVOKER AS $$ BEGIN
                PERFORM pg_catalog.nextval('{app_q}.synthetic_effect'::pg_catalog.regclass);
                RETURN true;
              END $$"""))
            if toxic == "rls":
                db.execute(text(f"ALTER POLICY repeat_select ON {app_q}.clinic_settings USING ({app_q}.toxic_policy())"))
            else:
                command = "ALL" if toxic == "rls_extra_all" else "SELECT"
                db.execute(text(f"CREATE POLICY extra_toxic ON {app_q}.clinic_settings FOR {command} TO PUBLIC USING ({app_q}.toxic_policy())"))
        else:
            db.execute(text(f"CREATE TYPE {app_q}.toxic_value AS ENUM ('20')"))
            db.execute(text(f"""CREATE FUNCTION {app_q}.toxic_cast({app_q}.toxic_value) RETURNS text
              LANGUAGE plpgsql SECURITY INVOKER AS $$ BEGIN
                PERFORM pg_catalog.nextval('{app_q}.synthetic_effect'::pg_catalog.regclass);
                RETURN '20';
              END $$"""))
            db.execute(text(f"CREATE CAST ({app_q}.toxic_value AS text) WITH FUNCTION {app_q}.toxic_cast({app_q}.toxic_value)"))
            db.execute(text(f"ALTER TABLE {app_q}.clinic_settings ALTER COLUMN value TYPE {app_q}.toxic_value USING '20'::{app_q}.toxic_value"))
    with Session(login) as db, pytest.raises(RepeatPolicyUnavailable):
        read_postgresql_repeat_policy(db, **arguments)
    with admin.connect() as db:
        assert db.execute(text(f"SELECT is_called FROM {app_q}.synthetic_effect")).scalar_one() is False
    # Positive control: without the guard, the same real function executes
    # the synthetic RLS predicate/cast and advances the nontransactional sequence.
    # With an additional true policy, the planner may short-circuit its OR;
    # disable that policy only for the positive control.
    if toxic in {"rls_extra", "rls_extra_all"}:
        with admin.begin() as db:
            db.execute(text(f"ALTER POLICY repeat_select ON {app_q}.clinic_settings USING (false)"))
    with login.connect() as direct:
        direct.execute(text(f"SELECT * FROM {private_q}.repeat_policy_read()")).all()
        direct.rollback()
    with admin.connect() as db:
        assert db.execute(text(f"SELECT is_called FROM {app_q}.synthetic_effect")).scalar_one() is True


def test_duplicate_keys_fail_closed_and_capability_returns_at_most_three(pg_capability):
    admin, login, app_q, private_q, _, _, arguments = pg_capability
    with admin.begin() as db:
        db.execute(text(f"ALTER TABLE {app_q}.clinic_settings DROP CONSTRAINT clinic_settings_pkey"))
        db.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_discount','10'),"
                        "('repeat_visit_discount','15'),('repeat_visit_discount','17')"))
    with login.connect() as connection:
        # The bound lives inside the SECURITY DEFINER, not only in Python.
        rows = connection.execute(text(f"SELECT * FROM {private_q}.repeat_policy_read()")).all()
        assert len(rows) == 3
        connection.rollback()
        with Session(bind=connection) as db, pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(db, **arguments)


def test_runtime_rejects_tracked_savepoint_before_snapshot(pg_capability):
    _, login, _, _, _, _, arguments = pg_capability
    with Session(login) as db:
        with db.begin_nested(), pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(db, **arguments)


def test_runtime_rejects_connection_managed_savepoint(pg_capability):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with login.connect() as connection:
        outer = connection.begin()
        nested = connection.begin_nested()
        try:
            with Session(bind=connection, join_transaction_mode="rollback_only") as db:
                assert not db.in_nested_transaction()
                with pytest.raises(RepeatPolicyUnavailable):
                    read_postgresql_repeat_policy(db, **arguments)
                with admin.begin() as writer:
                    writer.execute(text("SET LOCAL lock_timeout='100ms'"))
                    writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))
        finally:
            nested.rollback()
            outer.rollback()


@pytest.mark.parametrize("raw", ["1e9999999999999999999", "1e-9999999999999999999"])
def test_extreme_json_policy_rejection_releases_pg_lock(pg_capability, raw):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with admin.begin() as connection:
        connection.execute(
            text(f"UPDATE {app_q}.clinic_settings SET value=CAST(:raw AS json) WHERE key='repeat_visit_discount'"),
            {"raw": raw},
        )
    with Session(login) as reader:
        with pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(reader, **arguments)
        assert not reader.in_transaction()
        with admin.begin() as writer:
            writer.execute(text("SET LOCAL lock_timeout='100ms'"))
            writer.execute(text(f"UPDATE {app_q}.clinic_settings SET value='0' WHERE key='repeat_visit_discount'"))


def test_runtime_retries_when_writer_already_holds_table_lock(pg_capability):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with Session(admin) as writer, Session(login) as reader:
        writer.execute(text(f"INSERT INTO {app_q}.clinic_settings VALUES ('repeat_visit_days','1')"))
        with pytest.raises(RepeatPolicyBusy):
            read_postgresql_repeat_policy(reader, **arguments)
        writer.commit()
        assert read_postgresql_repeat_policy(reader, **arguments) == {
            "repeat_visit_days": 1, "repeat_visit_discount": 20}


def test_runtime_rejects_repeatable_read_and_untracked_direct_table_access(pg_capability):
    _, login, app_q, _, _, _, arguments = pg_capability
    with login.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with Session(bind=connection) as db, pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(db, **arguments)
    with login.connect() as db, pytest.raises(DBAPIError) as error:
        db.execute(text(f"SELECT key,value FROM {app_q}.clinic_settings"))
    assert (getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)) == "42501"


def test_runtime_supports_preexisting_settings_table_without_rls(pg_capability):
    admin, login, app_q, _, _, _, arguments = pg_capability
    with admin.begin() as db:
        db.execute(text(f"ALTER TABLE {app_q}.clinic_settings DISABLE ROW LEVEL SECURITY"))
    with Session(login) as db:
        assert read_postgresql_repeat_policy(db, **arguments) == {
            "repeat_visit_days": 21, "repeat_visit_discount": 20}


def test_runtime_ignores_temporary_settings_shadow(pg_capability):
    _, login, _, _, _, _, arguments = pg_capability
    with login.connect() as connection:
        connection.execute(text("CREATE TEMP TABLE clinic_settings (key text,value json)"))
        connection.execute(text("INSERT INTO pg_temp.clinic_settings VALUES ('repeat_visit_days','1')"))
        connection.commit()
        try:
            with Session(bind=connection) as db:
                assert read_postgresql_repeat_policy(db, **arguments) == {
                    "repeat_visit_days": 21, "repeat_visit_discount": 20}
        finally:
            connection.rollback()
            connection.execute(text("DROP TABLE pg_temp.clinic_settings"))
            connection.commit()


def test_capability_membership_in_runtime_is_rejected(pg_capability):
    admin, login, _, _, cap_q, runtime_q, arguments = pg_capability
    with admin.begin() as db:
        db.execute(text(f"GRANT {cap_q} TO {runtime_q}"))
    try:
        with Session(login) as db, pytest.raises(RepeatPolicyUnavailable):
            read_postgresql_repeat_policy(db, **arguments)
    finally:
        with admin.begin() as db:
            db.execute(text(f"REVOKE {cap_q} FROM {runtime_q}"))


@pytest.mark.parametrize("pg_capability", ["quoted"], indirect=True)
def test_quoted_schema_is_identifier_not_sql(pg_capability):
    _, login, _, _, _, _, arguments = pg_capability
    with Session(login) as db:
        assert read_postgresql_repeat_policy(db, **arguments) == {
            "repeat_visit_days": 21, "repeat_visit_discount": 20}
