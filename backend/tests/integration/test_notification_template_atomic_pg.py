"""Exercise template writes with independent, blocked PostgreSQL sessions."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.notification import crud_notification_template as crud
from app.models.notification import NotificationTemplate
from app.schemas.notification import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    raw = os.getenv("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if os.getenv("CI", "").lower() != "true" and not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.skip("requires disposable clinic_test database")
    schema = "test_notify_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        pool_size=8,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
    NotificationTemplate.__table__.create(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def create(db, name, pair=("reminder", "email"), active=True):
    return crud.create_atomic(
        db,
        obj_in=NotificationTemplateCreate(
            name=name, type=pair[0], channel=pair[1], template="hello", is_active=active
        ),
    )


def blocked(engine, pair, operations):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    pids = Queue()
    start = threading.Event()

    def worker(operation):
        with factory() as db:
            pids.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            assert start.wait(10)
            return operation(db)

    with factory() as gate, ThreadPoolExecutor(max_workers=len(operations)) as pool:
        crud._lock_pairs(gate, {pair})
        futures = [pool.submit(worker, op) for op in operations]
        worker_pids = [pids.get(timeout=10) for _ in operations]
        start.set()
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    if all(
                        conn.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid))"),
                            {"pid": pid},
                        ).scalar_one()
                        > 0
                        for pid in worker_pids
                    ):
                        break
                time.sleep(0.02)
            else:
                pytest.fail("workers did not reach the PostgreSQL lock")
        finally:
            gate.commit()
        return [future.result(timeout=20) for future in futures]


def update(db, template_id, **fields):
    return crud.update_atomic(
        db, template_id=template_id, obj_in=NotificationTemplateUpdate(**fields)
    )


@pytest.mark.parametrize(
    "case", ["create_create", "update_update", "create_update", "move_move"]
)
def test_competing_writers_serialize(engine, case):
    with Session(engine, expire_on_commit=False) as db:
        a = create(db, "a", ("old-a", "email"), False).id
        b = create(db, "b", ("old-b", "email"), False).id
    pair = ("reminder", "email")
    if case == "create_create":
        operations = [lambda db: create(db, "c"), lambda db: create(db, "d")]
    elif case == "update_update":
        with Session(engine) as db:
            update(db, a, type=pair[0])
            update(db, b, type=pair[0])
        operations = [
            lambda db: update(db, a, is_active=True),
            lambda db: update(db, b, is_active=True),
        ]
    elif case == "create_update":
        with Session(engine) as db:
            update(db, a, type=pair[0])
        operations = [
            lambda db: create(db, "c"),
            lambda db: update(db, a, is_active=True),
        ]
    else:
        with Session(engine) as db:
            update(db, a, is_active=True)
            update(db, b, is_active=True)
        operations = [
            lambda db: update(db, a, type=pair[0]),
            lambda db: update(db, b, type=pair[0]),
        ]
    blocked(engine, pair, operations)
    with Session(engine) as db:
        assert (
            db.query(NotificationTemplate)
            .filter_by(type=pair[0], channel=pair[1], is_active=True)
            .count()
            == 1
        )


def test_error_rolls_back_deactivation(engine):
    with Session(engine, expire_on_commit=False) as db:
        old = create(db, "old").id
        create(db, "taken", ("other", "email"))
        inactive = create(db, "inactive", active=False).id
        with pytest.raises(IntegrityError):
            create(db, "taken")
        assert db.get(NotificationTemplate, old).is_active
        with pytest.raises(IntegrityError):
            update(db, inactive, name="taken", is_active=True)
        assert db.get(NotificationTemplate, old).is_active
        assert not db.get(NotificationTemplate, inactive).is_active


def test_migration_refuses_duplicates_without_changing_rows_and_round_trips(engine):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0098_notification_template_active_unique.py"
    )
    spec = importlib.util.spec_from_file_location("notify_0098", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX uq_notification_templates_active_type_channel"))
        conn.execute(
            text(
                "INSERT INTO notification_templates (name, type, channel, template, is_active, created_at, updated_at) VALUES ('duplicate-1','legacy','email','first',true,now(),now()), ('duplicate-2','legacy','email','second',true,now(),now())"
            )
        )
    with pytest.raises(RuntimeError, match="1 duplicate active template groups"):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT name, template, is_active FROM notification_templates ORDER BY name"
            )
        ).all()
        assert rows == [("duplicate-1", "first", True), ("duplicate-2", "second", True)]
        conn.execute(
            text(
                "UPDATE notification_templates SET is_active=false WHERE name='duplicate-2'"
            )
        )
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.downgrade()
            migration.upgrade()
        indexes = conn.execute(
            text(
                "SELECT count(*) FROM pg_indexes WHERE schemaname=current_schema() AND indexname='uq_notification_templates_active_type_channel'"
            )
        ).scalar_one()
        assert indexes == 1


def test_http_post_and_put_compete_under_real_pg_lock(engine):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.endpoints.notifications import router

    with Session(engine, expire_on_commit=False) as db:
        target_id = create(db, "http-existing", active=False).id
    pids = Queue()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role="Admin", is_superuser=True
    )

    def db_override():
        with Session(engine, expire_on_commit=False) as db:
            pids.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            yield db

    app.dependency_overrides[get_db] = db_override

    def request(method):
        with TestClient(app) as client:
            if method == "post":
                return client.post(
                    "/templates",
                    json={
                        "name": "http-new",
                        "type": "reminder",
                        "channel": "email",
                        "template": "hello",
                    },
                )
            return client.put(f"/templates/{target_id}", json={"is_active": True})

    with Session(engine) as gate, ThreadPoolExecutor(max_workers=2) as pool:
        crud._lock_pairs(gate, {("reminder", "email")})
        futures = [pool.submit(request, method) for method in ("post", "put")]
        worker_pids = [pids.get(timeout=10) for _ in futures]
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    if all(
                        conn.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid))"),
                            {"pid": pid},
                        ).scalar_one()
                        for pid in worker_pids
                    ):
                        break
                time.sleep(0.02)
            else:
                pytest.fail("HTTP requests did not reach the PostgreSQL lock")
        finally:
            gate.commit()
        assert [future.result(timeout=20).status_code for future in futures] == [
            200,
            200,
        ]
    with Session(engine) as db:
        assert (
            db.query(NotificationTemplate)
            .filter_by(type="reminder", channel="email", is_active=True)
            .count()
            == 1
        )


def test_offline_sql_generation_enforces_uniqueness_on_apply(engine):
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "0097_two_factor_sensitive_totp:head",
            "--sql",
        ],
        cwd=backend,
        capture_output=True,
        text=True,
        check=True,
    )
    statements = result.stdout.split(";")
    index_sql = next(
        statement[statement.index("CREATE UNIQUE INDEX") :].strip()
        for statement in statements
        if "CREATE UNIQUE INDEX uq_notification_templates_active_type_channel"
        in statement
    )
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX uq_notification_templates_active_type_channel"))
        conn.execute(
            text(
                "INSERT INTO notification_templates (name,type,channel,template,is_active,created_at,updated_at) VALUES ('offline-1','legacy','email','first',true,now(),now()),('offline-2','legacy','email','second',true,now(),now())"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(index_sql)
    with engine.begin() as conn:
        assert conn.execute(
            text(
                "SELECT name,template,is_active FROM notification_templates ORDER BY name"
            )
        ).all() == [("offline-1", "first", True), ("offline-2", "second", True)]
        conn.execute(
            text(
                "UPDATE notification_templates SET is_active=false WHERE name='offline-2'"
            )
        )
        conn.exec_driver_sql(index_sql)
