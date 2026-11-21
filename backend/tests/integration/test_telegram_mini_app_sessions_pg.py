"""Migration and concurrency proof using a guarded disposable local PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
import os
import time
import uuid

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    create_engine,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.telegram_mini_app_session import TelegramMiniAppSession
from app.repositories.telegram_mini_app_session_repository import (
    TelegramMiniAppSessionRepository,
)
from app.services.telegram_mini_app_jwt import (
    TelegramMiniAppAuthExchangeError,
    authenticate_patient_session,
    exchange_init_data_for_jwt,
    list_patient_sessions,
    refresh_patient_session,
    revoke_patient_sessions,
    verify_patient_jwt,
)
from tests._pg_admin_guard import is_local_admin_dsn
from tests.unit.test_telegram_mini_app_jwt import BOT_TOKEN, signed_init_data

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pg_engine():
    admin_url = os.environ.get("TG_SESSION_PG_ADMIN_URL", "")
    if not admin_url:
        pytest.skip("Explicit TG_SESSION_PG_ADMIN_URL is required")
    if not is_local_admin_dsn(admin_url):
        pytest.fail("Refusing non-local PostgreSQL admin target")
    database = "clinic_test_tg_sessions_" + uuid.uuid4().hex[:12]
    engine = None
    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
            created = True
        target = make_url(admin_url).set(
            database=database, drivername="postgresql+psycopg"
        )
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
            command.upgrade(cfg, "0102_visit_confirm_context")
            engine = create_engine(target, pool_pre_ping=True)
            assert "telegram_mini_app_sessions" not in inspect(engine).get_table_names()
            command.upgrade(cfg, "head")
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            # Only this invocation's successfully-created random DB is removed.
            with psycopg.connect(admin_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(database)
                    )
                )


def seed(pg_engine, chat_id):
    with Session(pg_engine) as db:
        patient = Patient(last_name="SYNTHETIC-SESSION", first_name="SYNTHETIC")
        db.add(patient)
        db.flush()
        db.add(
            TelegramUser(
                patient_id=patient.id, chat_id=chat_id, active=True, blocked=False
            )
        )
        db.commit()
        return patient.id


def exchange(db, chat_id):
    return exchange_init_data_for_jwt(
        db, signed_init_data(chat_id), bot_token=BOT_TOKEN
    )


def test_migrated_table_matches_model_and_enables_rls(pg_engine):
    inspector = inspect(pg_engine)
    table = TelegramMiniAppSession.__table__
    columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    assert set(columns) == set(table.columns.keys())
    epoch_column = table.c.patient_link_epoch
    assert isinstance(epoch_column.type, BigInteger)
    assert epoch_column.nullable is False
    assert epoch_column.default is None
    assert epoch_column.server_default is None
    assert isinstance(columns["patient_link_epoch"]["type"], BigInteger)
    assert columns["patient_link_epoch"]["nullable"] is False
    assert columns["patient_link_epoch"]["default"] is None
    model_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert model_checks["ck_tg_mini_session_link_epoch"] == "patient_link_epoch >= 0"
    assert {
        row["name"]: row["sqltext"].strip("()")
        for row in inspector.get_check_constraints(table.name)
    } == model_checks
    assert columns["refresh_token_hash"]["type"].length == 64
    assert all(
        columns[key]["type"].timezone
        for key in (
            "created_at",
            "last_active_at",
            "expires_at",
            "revoked_at",
        )
    )
    assert {row["name"] for row in inspector.get_unique_constraints(table.name)} == {
        "uq_tg_mini_session_init_data",
        "uq_tg_mini_session_refresh",
    }
    assert {
        row["referred_table"] for row in inspector.get_foreign_keys(table.name)
    } == {
        "patients",
        "telegram_users",
    }
    assert all(
        row["options"]["ondelete"] == "CASCADE"
        for row in inspector.get_foreign_keys(table.name)
    )
    with pg_engine.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.telegram_mini_app_sessions'::regclass"
                )
            ).scalar_one()
            is True
        )
        assert conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == ("0103_telegram_mini_app_sessions")


@pytest.mark.parametrize(
    "field,chat_id,changed_value",
    [
        ("patient_id", 750010, None),
        ("chat_id", 750011, 850011),
        ("active", 750012, False),
        ("blocked", 750013, True),
        ("notifications_enabled", 750014, False),
        ("appointment_reminders", 750015, False),
    ],
)
def test_bulk_link_change_and_restore_do_not_revive_sessions(
    pg_engine, field, chat_id, changed_value
):
    patient_id = seed(pg_engine, chat_id)
    consumed_init_data = signed_init_data(chat_id)
    links = TelegramUser.__table__
    with Session(pg_engine) as db:
        pair = exchange_init_data_for_jwt(db, consumed_init_data, bot_token=BOT_TOKEN)
        original = authenticate_patient_session(db, pair["access_token"]).session
        stale_id = original.id
        link_id = original.telegram_user_id
        original_epoch = original.patient_link_epoch
        original_value, link_epoch = db.execute(
            select(links.c[field], links.c.patient_link_epoch).where(
                links.c.id == link_id
            )
        ).one()
        assert original_epoch == link_epoch
        assert original_value != changed_value

    epochs = {original_epoch}
    for value in (changed_value, original_value):
        # Core SQL bypasses ORM hooks: only the migrated PostgreSQL trigger
        # can fence a capability when the original link values are restored.
        with pg_engine.begin() as conn:
            current_epoch = conn.execute(
                update(links)
                .where(links.c.id == link_id)
                .values({field: value})
                .returning(links.c.patient_link_epoch)
            ).scalar_one()
        assert current_epoch not in epochs
        epochs.add(current_epoch)
        with Session(pg_engine) as db:
            assert verify_patient_jwt(pair["access_token"], db) is None
            with pytest.raises(
                TelegramMiniAppAuthExchangeError, match="session_invalid"
            ):
                refresh_patient_session(db, pair["refresh_token"])
            stale = db.get(TelegramMiniAppSession, stale_id)
            assert stale.patient_link_epoch == original_epoch
            assert stale.revoked_at is None

    with Session(pg_engine) as db:
        fresh = exchange(db, chat_id)
        auth, listing = list_patient_sessions(db, fresh["access_token"])
        assert auth.session.patient_id == patient_id
        assert auth.session.patient_link_epoch == current_epoch
        assert listing["total"] == 1
        assert {row["id"] for row in listing["sessions"]} == {auth.session.id}
        assert stale_id not in {row["id"] for row in listing["sessions"]}
        refreshed = refresh_patient_session(db, fresh["refresh_token"])
        authenticate_patient_session(db, refreshed["access_token"])
        with pytest.raises(
            TelegramMiniAppAuthExchangeError, match="init_data_replayed"
        ):
            exchange_init_data_for_jwt(db, consumed_init_data, bot_token=BOT_TOKEN)


def test_exchange_waits_for_relink_without_patient_fk_deadlock(pg_engine, monkeypatch):
    patient_id = seed(pg_engine, 750020)
    links = TelegramUser.__table__
    patient_locked = Event()
    exchange_pid = []
    lock_patient = TelegramMiniAppSessionRepository.lock_patient

    def observe_patient_lock(repo, locked_patient_id):
        lock_patient(repo, locked_patient_id)
        assert locked_patient_id == patient_id
        patient_locked.set()

    monkeypatch.setattr(
        TelegramMiniAppSessionRepository, "lock_patient", observe_patient_lock
    )

    def launch():
        with Session(pg_engine) as db:
            db.execute(text("SET LOCAL statement_timeout = '10000ms'"))
            db.execute(text("SET LOCAL lock_timeout = '8000ms'"))
            exchange_pid.append(
                db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            pair = exchange(db, 750020)
            auth = authenticate_patient_session(db, pair["access_token"])
            # Only safe database identifiers leave the worker thread.
            return auth.session.id, auth.session.patient_link_epoch

    with Session(pg_engine) as writer:
        writer.execute(text("SET LOCAL statement_timeout = '10000ms'"))
        writer.execute(text("SET LOCAL lock_timeout = '8000ms'"))
        writer_pid = writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
        link_id, original_epoch = writer.execute(
            select(links.c.id, links.c.patient_link_epoch)
            .where(links.c.chat_id == 750020)
            .with_for_update()
        ).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            launching = pool.submit(launch)
            try:
                assert patient_locked.wait(timeout=5), "exchange did not lock patient"
                deadline = time.monotonic() + 5
                waiting = False
                with pg_engine.connect() as observer:
                    while time.monotonic() < deadline:
                        blockers = observer.execute(
                            text("SELECT pg_blocking_pids(:pid)"),
                            {"pid": exchange_pid[0]},
                        ).scalar_one()
                        if writer_pid in blockers:
                            waiting = True
                            break
                        time.sleep(0.025)
                assert waiting, "exchange did not wait for the locked Telegram link"

                unlinked_epoch = writer.execute(
                    update(links)
                    .where(links.c.id == link_id)
                    .values(patient_id=None)
                    .returning(links.c.patient_link_epoch)
                ).scalar_one()
                restored_epoch = writer.execute(
                    update(links)
                    .where(links.c.id == link_id)
                    .values(patient_id=patient_id)
                    .returning(links.c.patient_link_epoch)
                ).scalar_one()
                # Restoring the FK takes Patient KEY SHARE while the exchange
                # waits on this link. Patient FOR UPDATE would form a cycle;
                # the credential lock must allow this unchanged patient key.
                assert restored_epoch not in (original_epoch, unlinked_epoch)
                writer.commit()
            finally:
                # Release the competing link even if an assertion or SQL fails.
                writer.rollback()
            session_id, captured_epoch = launching.result(timeout=15)

    assert captured_epoch == restored_epoch
    with Session(pg_engine) as db:
        session = db.get(TelegramMiniAppSession, session_id)
        assert session.patient_id == patient_id
        assert session.patient_link_epoch == restored_epoch
        assert session.revoked_at is None


def test_concurrent_exchange_has_exactly_one_winner(pg_engine):
    patient_id = seed(pg_engine, 750001)
    data = signed_init_data(750001)
    barrier = Barrier(2)

    def attempt():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            try:
                exchange_init_data_for_jwt(db, data, bot_token=BOT_TOKEN)
                return "issued"
            except TelegramMiniAppAuthExchangeError as exc:
                return exc.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["init_data_replayed", "issued"]
    with Session(pg_engine) as db:
        assert (
            len(
                db.scalars(
                    select(TelegramMiniAppSession).where(
                        TelegramMiniAppSession.patient_id == patient_id,
                    )
                ).all()
            )
            == 1
        )


def test_concurrent_refresh_detects_reuse_without_double_rotation(pg_engine):
    seed(pg_engine, 750002)
    with Session(pg_engine) as db:
        pair = exchange(db, 750002)
    barrier = Barrier(2)

    def attempt():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            try:
                return refresh_patient_session(db, pair["refresh_token"])
            except TelegramMiniAppAuthExchangeError as exc:
                return exc.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "session_invalid" in results
    with Session(pg_engine) as db:
        assert verify_patient_jwt(pair["access_token"], db) is None


def test_refresh_and_revoke_others_are_serialized(pg_engine):
    seed(pg_engine, 750003)
    with Session(pg_engine) as db:
        current = exchange(db, 750003)
        other = exchange(db, 750003)
    barrier = Barrier(2)

    def refresh():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            try:
                return refresh_patient_session(db, other["refresh_token"])
            except TelegramMiniAppAuthExchangeError:
                return None

    def revoke():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            return revoke_patient_sessions(db, current["access_token"])[1]

    with ThreadPoolExecutor(max_workers=2) as pool:
        refreshing = pool.submit(refresh)
        revoking = pool.submit(revoke)
        rotated = refreshing.result(timeout=20)
        assert revoking.result(timeout=20) == 1
    with Session(pg_engine) as db:
        authenticate_patient_session(db, current["access_token"])
        assert verify_patient_jwt(other["access_token"], db) is None
        if rotated is not None:
            assert verify_patient_jwt(rotated["access_token"], db) is None
