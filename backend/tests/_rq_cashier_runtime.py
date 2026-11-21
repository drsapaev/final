"""Run a cashier acceptance request under an isolated PostgreSQL login."""

from __future__ import annotations

import importlib.util
import re
import secrets
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from tests._pg_admin_guard import is_local_admin_dsn


def _provisioner(name: str):
    path = Path(__file__).resolve().parents[2] / "scripts" / f"provision_{name}_role.py"
    spec = importlib.util.spec_from_file_location(f"rq_provision_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision


@contextmanager
def cashier_request(client, owner_session):
    """Use the application's normal financial fence and separate committed sessions."""
    engine = owner_session.get_bind()
    url = engine.url
    db_name = url.database or ""
    if not re.fullmatch(r"rq(?:24b|29)_check_[0-9a-f]{12}", db_name) or not is_local_admin_dsn(
        url.render_as_string(hide_password=False)
    ):
        raise RuntimeError("The cashier fixture requires its own local scratch database")

    owner_session.commit()
    backend, capability = f"{db_name}_cashier", f"{db_name}_finance"
    password = secrets.token_hex(24)
    quote = engine.dialect.identifier_preparer.quote_identifier
    runtime_role, finance_role = quote(backend), quote(capability)
    runtime = None
    with engine.begin() as db:
        assert db.scalar(text("SELECT current_database()")) == db_name
        owner = db.scalar(text("SELECT CURRENT_USER"))
        ddl = db.scalar(text("""
          SELECT pg_catalog.format('CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L',
            CAST(:role AS text), CAST(:password AS text))
        """), {"role": backend, "password": password})
        db.exec_driver_sql(ddl)
        db.exec_driver_sql(f"CREATE ROLE {finance_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")

    try:
        _provisioner("all_free_backend")(engine, "public", backend, expected_owner=owner)
        for name in ("encounter_financial", "encounter_benefit", "reconciliation_fence"):
            _provisioner(name)(
                engine, schema="public", backend_role=backend, capability_role=capability,
                expected_owner=owner,
            )
        with engine.begin() as db:
            for table in ("users", "token_blacklist", "patients", "services", "payments", "payment_client_requests"):
                db.exec_driver_sql(f"GRANT SELECT ON public.{table} TO {runtime_role}")
                db.exec_driver_sql(
                    f"CREATE POLICY rq_cashier_read ON public.{table} FOR SELECT TO {runtime_role} USING (true)"
                )
            for table in ("payments", "payment_client_requests"):
                db.exec_driver_sql(f"GRANT INSERT ON public.{table} TO {runtime_role}")
                db.exec_driver_sql(
                    f"CREATE POLICY rq_cashier_insert ON public.{table} FOR INSERT TO {runtime_role} WITH CHECK (true)"
                )
            db.exec_driver_sql(f"GRANT UPDATE (id) ON public.visits TO {runtime_role}")
            db.exec_driver_sql(f"GRANT UPDATE (client_request_id,updated_at) ON public.payments TO {runtime_role}")
            db.exec_driver_sql(f"GRANT SELECT (created_at) ON public.payment_visits TO {runtime_role}")
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE public.payments_id_seq TO {runtime_role}")
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE public.payment_client_requests_id_seq TO {runtime_role}")
            db.exec_driver_sql(
                f"CREATE POLICY rq_cashier_visit_lock ON public.visits FOR UPDATE TO {runtime_role} "
                "USING (true) WITH CHECK (false)"
            )

        runtime = create_engine(url.set(username=backend, password=password), hide_parameters=True)

        def request_db():
            with Session(runtime) as db:
                yield db

        with pytest.MonkeyPatch.context() as fixture:
            for key, value in {
                "TRUSTED_DB_SCHEMA": "public",
                "TRUSTED_DB_SCHEMA_OWNER": owner,
                "TRUSTED_DB_RUNTIME_ROLE": backend,
                "TRUSTED_DB_OWNER_MEMBERS": (),
            }.items():
                fixture.setattr(settings, key, value)
            fixture.setitem(client.app.dependency_overrides, get_db, request_db)
            yield client
    finally:
        if runtime is not None:
            runtime.dispose()
        with engine.begin() as db:
            roles = f"{runtime_role}, {finance_role}"
            db.exec_driver_sql(f"REASSIGN OWNED BY {roles} TO {quote(owner)}")
            db.exec_driver_sql(f"DROP OWNED BY {roles}")
            db.exec_driver_sql(f"DROP ROLE {roles}")
        owner_session.expire_all()
