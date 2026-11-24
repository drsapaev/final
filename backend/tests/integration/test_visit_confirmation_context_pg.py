"""Exercise the actual Alembic trigger on SQLite and disposable PostgreSQL."""

import importlib.util
import io
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

_MIGRATION = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"


def _migration():
    spec = importlib.util.spec_from_file_location("visit_confirmation_context_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_table(conn):
    conn.execute(text("""
        CREATE TABLE visits (
          id integer PRIMARY KEY, patient_id integer NOT NULL, doctor_id integer,
          visit_date date, visit_time varchar(8), department varchar(64), department_id integer,
          discount_mode varchar(32),
          confirmation_channel varchar(16), status varchar(32) NOT NULL,
          confirmation_token varchar(128), confirmation_expires_at timestamp,
          reminder_sent_at timestamp, reminder_generation integer NOT NULL DEFAULT 0,
          reminder_claimed_at timestamp
        )
    """))
    conn.execute(text("CREATE TABLE patients (id integer PRIMARY KEY, phone varchar(64))"))
    conn.execute(text("INSERT INTO patients (id, phone) VALUES (1, 'synthetic-old')"))
    conn.execute(text("""
        CREATE TABLE visit_services (
          id integer PRIMARY KEY, visit_id integer NOT NULL, service_id integer,
          code varchar(64), name varchar(255), duration_minutes_snapshot integer,
          qty integer, price numeric(12,2), currency varchar(8)
        )
    """))
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, visit_time,
          department, department_id, confirmation_channel, status, confirmation_token,
          confirmation_expires_at, reminder_sent_at, reminder_generation, reminder_claimed_at)
        VALUES (1, 1, 10, '2031-04-01', '10:00', 'lab', 20, 'auto',
          'pending_confirmation', 'original-token', '2031-04-02 12:00:00',
          '2031-03-01 12:00:00', 4, '2031-03-01 11:00:00')
    """))


def _row(conn):
    return conn.execute(text("SELECT * FROM visits WHERE id = 1")).mappings().one()


def _issue(conn, token):
    conn.execute(text("UPDATE visits SET confirmation_token=:token, confirmation_expires_at='2031-04-02 12:00:00' WHERE id=1"), {"token": token})


def _exercise(conn):
    migration = _migration()
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    initial_epoch = _row(conn)["confirmation_context_epoch"]
    assert 0 < initial_epoch <= 2**52
    assert _row(conn)["confirmation_token"] == "original-token"  # upgrade preserves PWA links
    if conn.dialect.name == "postgresql":
        conn.execute(text("UPDATE visits SET confirmation_context_epoch=1 WHERE id=1"))
        assert _row(conn)["confirmation_context_epoch"] == initial_epoch
    # Same-value updates, including the worker's blank-to-auto normalization,
    # must preserve an already issued PWA token and the in-flight lease.
    conn.execute(text("UPDATE visits SET patient_id=patient_id, doctor_id=doctor_id, visit_date=visit_date, visit_time=visit_time, department=department, department_id=department_id, discount_mode=discount_mode WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "original-token"
    conn.execute(text("UPDATE visits SET confirmation_channel=NULL WHERE id=1"))
    conn.execute(text("UPDATE visits SET confirmation_channel='auto' WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "original-token"
    assert _row(conn)["reminder_generation"] == 4
    assert _row(conn)["confirmation_context_epoch"] == initial_epoch
    # Patient transfer and return cannot revive the previous capability.
    conn.execute(text("UPDATE visits SET patient_id=2 WHERE id=1"))
    row = _row(conn)
    assert row["confirmation_token"] is None and row["confirmation_expires_at"] is None
    assert row["reminder_sent_at"] is None and row["reminder_generation"] == 5
    assert row["confirmation_context_epoch"] != initial_epoch
    assert row["reminder_claimed_at"] is not None
    conn.execute(text("UPDATE visits SET patient_id=1 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    assert _row(conn)["reminder_generation"] == 6
    # A newly issued separate token works until a schedule change; reusing the
    # original token in the same context-changing write is rejected.
    _issue(conn, "separate-reissue")
    conn.execute(text("UPDATE visits SET visit_date='2031-04-03', confirmation_token='original-token', confirmation_expires_at='2031-04-02 12:00:00', reminder_generation=reminder_generation+1 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    assert _row(conn)["reminder_generation"] == 7  # writer's bump not doubled
    conn.execute(text("UPDATE visits SET visit_date='2031-04-01' WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    assert _row(conn)["reminder_generation"] == 8
    for column, value in (("visit_time", "11:00"), ("doctor_id", 11),
                          ("department", "cardiology"), ("department_id", 21),
                          ("discount_mode", "all_free"),
                          ("confirmation_channel", "telegram")):
        _issue(conn, f"token-{column}")
        conn.execute(text(f"UPDATE visits SET {column}=:value WHERE id=1"), {"value": value})
        assert _row(conn)["confirmation_token"] is None
    # A patient's phone is a bearer delivery identity: bulk changes and ABA
    # must fence both the token and an in-flight worker claim; no-op/rollback
    # must preserve both. A subsequent issuance remains possible.
    _issue(conn, "phone-before")
    before_phone = _row(conn)
    conn.execute(text("UPDATE patients SET phone=phone WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "phone-before"
    assert _row(conn)["confirmation_context_epoch"] == before_phone["confirmation_context_epoch"]
    saved = conn.begin_nested()
    conn.execute(text("UPDATE patients SET phone='synthetic-new' WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    assert _row(conn)["confirmation_context_epoch"] != before_phone["confirmation_context_epoch"]
    assert _row(conn)["reminder_generation"] == before_phone["reminder_generation"] + 1
    assert _row(conn)["reminder_claimed_at"] == before_phone["reminder_claimed_at"]
    saved.rollback()
    assert _row(conn)["confirmation_token"] == "phone-before"
    conn.execute(text("UPDATE patients SET phone='synthetic-new' WHERE id=1"))
    conn.execute(text("UPDATE patients SET phone='synthetic-old' WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    _issue(conn, "phone-reissued")
    assert _row(conn)["confirmation_token"] == "phone-reissued"
    # Service insertion, meaningful update and deletion revoke capabilities,
    # including A→B→A; same-value updates do not cause a spurious revocation.
    _issue(conn, "before-service-add")
    conn.execute(text("INSERT INTO visit_services (id, visit_id, service_id, name, qty) VALUES (1, 1, 9, 'SYNTHETIC', 1)"))
    assert _row(conn)["confirmation_token"] is None
    _issue(conn, "before-service-noop")
    conn.execute(text("UPDATE visit_services SET service_id=service_id, qty=qty WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "before-service-noop"
    conn.execute(text("UPDATE visit_services SET service_id=10 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    conn.execute(text("UPDATE visit_services SET service_id=9 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    _issue(conn, "before-service-delete")
    conn.execute(text("DELETE FROM visit_services WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    # Moving a service between visits revokes both contexts atomically.
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, status, confirmation_token,
          confirmation_expires_at, reminder_generation)
        VALUES (2, 2, 'pending_confirmation', 'target-token', '2031-04-02 12:00:00', 0)
    """))
    conn.execute(text("INSERT INTO visit_services (id, visit_id, service_id, name, qty) VALUES (2, 1, 9, 'SYNTHETIC', 1)"))
    _issue(conn, "source-token")
    move_savepoint = conn.begin_nested()
    conn.execute(text("UPDATE visit_services SET visit_id=2 WHERE id=2"))
    assert _row(conn)["confirmation_token"] is None
    assert conn.execute(text("SELECT confirmation_token FROM visits WHERE id=2")).scalar_one() is None
    move_savepoint.rollback()
    assert _row(conn)["confirmation_token"] == "source-token"
    assert conn.execute(text("SELECT confirmation_token FROM visits WHERE id=2")).scalar_one() == "target-token"
    # Savepoint rollback preserves the pre-change credential and schedule.
    _issue(conn, "rollback-token")
    nested = conn.begin_nested()
    conn.execute(text("UPDATE visits SET patient_id=3 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    nested.rollback()
    assert _row(conn)["confirmation_token"] == "rollback-token"
    # Internal processing does not invalidate the current claim. Terminal
    # departure/reopening must not resurrect the earlier bearer.
    conn.execute(text("UPDATE visits SET status='confirmation_processing' WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "rollback-token"
    conn.execute(text("UPDATE visits SET status='confirmed' WHERE id=1"))
    conn.execute(text("UPDATE visits SET status='pending_confirmation' WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    _issue(conn, "fresh-after-reopen")
    conn.execute(text("UPDATE visits SET status='canceled' WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None
    previous_epoch = _row(conn)["confirmation_context_epoch"]
    from app.services.visit_confirmation_service import (
        build_telegram_visit_action_token,
    )

    def capability(epoch):
        return build_telegram_visit_action_token(
            visit_id=1, confirmation_token="same-synthetic-token", link_id=1,
            chat_id=12345, patient_id=1, link_epoch=2, visit_context_epoch=epoch,
        )

    original_capability = capability(previous_epoch)
    migration.downgrade()
    _issue(conn, "downgrade-token")
    conn.execute(text("UPDATE visits SET patient_id=4 WHERE id=1"))
    assert _row(conn)["confirmation_token"] == "downgrade-token"
    migration.upgrade()
    assert _row(conn)["confirmation_context_epoch"] != previous_epoch
    assert capability(_row(conn)["confirmation_context_epoch"]) != original_capability
    # Normal upgrade does not mass-revoke an unchanged PWA bearer.
    assert _row(conn)["confirmation_token"] == "downgrade-token"
    conn.execute(text("UPDATE visits SET patient_id=1 WHERE id=1"))
    assert _row(conn)["confirmation_token"] is None


def test_sqlite_trigger_context_and_channel_normalization():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            _create_table(conn)
            _exercise(conn)
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_trigger_context_and_channel_normalization():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL clinic_test database")
    schema = "test_visit_context_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as conn:
            _create_table(conn)
            _exercise(conn)
            # Apply SQL generated by offline Alembic (not only inspect text).
            online = _migration()
            online.op = Operations(MigrationContext.configure(conn))
            online.downgrade()
            output = io.StringIO()
            offline = _migration()
            offline.op = Operations(MigrationContext.configure(
                dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
            ))
            offline.upgrade()
            conn.exec_driver_sql(output.getvalue())
            _issue(conn, "offline-token")
            conn.execute(text("UPDATE visits SET visit_time='12:00' WHERE id=1"))
            assert _row(conn)["confirmation_token"] is None
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_offline_postgres_sql_contains_reversible_trigger():
    output = io.StringIO()
    migration = _migration()
    migration.op = Operations(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    ))
    migration.upgrade()
    migration.downgrade()
    sql = output.getvalue()
    assert "CREATE TRIGGER trg_visit_confirmation_context" in sql
    assert "DROP TRIGGER trg_visit_confirmation_context" in sql


@pytest.mark.integration
def test_real_postgres_pwa_and_telegram_tokens_after_context_change():
    """Use the fully migrated schema and real confirmation service, not a fake DB."""
    from datetime import UTC, date, datetime, timedelta

    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.models.telegram_config import TelegramUser
    from app.models.visit import Visit, VisitService
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
        build_telegram_visit_action_token,
    )

    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a fully migrated disposable PostgreSQL clinic_test database")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    first = Patient(first_name="SYNTHETIC", last_name="FIRST", phone="synthetic-phone-a")
                    second = Patient(first_name="SYNTHETIC", last_name="SECOND")
                    db.add_all([first, second])
                    db.flush()
                    expires = datetime.now(UTC) + timedelta(hours=1)
                    visit_day = date.today() + timedelta(days=7)
                    pwa_token = "synthetic-pwa-" + uuid.uuid4().hex
                    moved_token = "synthetic-moved-" + uuid.uuid4().hex
                    telegram_token = "synthetic-tg-" + uuid.uuid4().hex
                    phone_token = "synthetic-phone-" + uuid.uuid4().hex
                    pwa = Visit(patient_id=first.id, visit_date=visit_day, visit_time="09:00",
                                status="pending_confirmation", confirmation_channel="auto",
                                confirmation_token=pwa_token, confirmation_expires_at=expires)
                    moved = Visit(patient_id=first.id, visit_date=visit_day, visit_time="10:00",
                                  status="pending_confirmation", confirmation_channel="pwa",
                                  confirmation_token=moved_token, confirmation_expires_at=expires)
                    telegram = Visit(patient_id=first.id, visit_date=visit_day, visit_time="11:00",
                                     status="pending_confirmation", confirmation_channel="telegram",
                                     confirmation_token=telegram_token, confirmation_expires_at=expires)
                    phone_visit = Visit(patient_id=first.id, visit_date=visit_day, visit_time="13:00",
                                        status="pending_confirmation", confirmation_channel="pwa",
                                        confirmation_token=phone_token, confirmation_expires_at=expires)
                    link = TelegramUser(patient_id=first.id, chat_id=int(uuid.uuid4().hex[:12], 16),
                                        active=True, blocked=False, notifications_enabled=True,
                                        appointment_reminders=True)
                    db.add_all([pwa, moved, telegram, phone_visit, link])
                    db.commit()
                    capability = build_telegram_visit_action_token(
                        visit_id=telegram.id, confirmation_token=telegram_token,
                        link_id=link.id, chat_id=link.chat_id, patient_id=first.id,
                        link_epoch=link.patient_link_epoch,
                        visit_context_epoch=telegram.confirmation_context_epoch,
                    )
                    # The booking writer inserts child services before issuing its
                    # initial bearer. The real DB trigger must not erase that bearer.
                    initial = Visit(patient_id=first.id, visit_date=visit_day,
                                    visit_time="12:00", status="pending_confirmation",
                                    confirmation_channel="pwa")
                    db.add(initial)
                    db.flush()
                    db.add(VisitService(visit_id=initial.id, service_id=99,
                                        name="SYNTHETIC", qty=1))
                    db.flush()
                    initial_token = "synthetic-initial-" + uuid.uuid4().hex
                    initial.confirmation_token = initial_token
                    initial.confirmation_expires_at = expires
                    db.commit()
                    db.refresh(initial)
                    assert initial.confirmation_token == initial_token
                    assert VisitConfirmationService(db).confirm_by_pwa(
                        token=initial_token, patient_phone=None, source_ip=None,
                        user_agent="synthetic",
                    )["success"] is True
                    # Legitimate same-value updates preserve the working PWA token.
                    db.execute(text("UPDATE visits SET visit_date=visit_date WHERE id=:id"), {"id": pwa.id})
                    db.commit()
                    result = VisitConfirmationService(db).confirm_by_pwa(
                        token=pwa_token, patient_phone=None, source_ip=None, user_agent="synthetic",
                    )
                    assert result["success"] is True
                    # Old PWA link is not valid for a new date, including A→B→A.
                    db.execute(text("UPDATE visits SET visit_date=visit_date+1 WHERE id=:id"), {"id": moved.id})
                    db.execute(text("UPDATE visits SET visit_date=visit_date-1 WHERE id=:id"), {"id": moved.id})
                    db.commit()
                    with pytest.raises(VisitConfirmationDomainError):
                        VisitConfirmationService(db).confirm_by_pwa(
                            token=moved_token, patient_phone=None, source_ip=None, user_agent="synthetic",
                        )
                    # Changing ordered services fences even an intentionally reused
                    # raw token: the old Telegram MAC no longer matches the epoch.
                    db.execute(text("INSERT INTO visit_services (visit_id, service_id, name, qty, created_at) VALUES (:id, 99, 'SYNTHETIC', 1, CURRENT_TIMESTAMP)"), {"id": telegram.id})
                    db.commit()
                    db.refresh(telegram)
                    assert telegram.confirmation_token is None
                    telegram.confirmation_token = telegram_token
                    telegram.confirmation_expires_at = expires
                    db.commit()
                    with pytest.raises(VisitConfirmationDomainError):
                        VisitConfirmationService(db).confirm_by_telegram(
                            token=capability, telegram_user_id=str(link.chat_id), source_ip=None,
                            user_agent="synthetic",
                        )
                    # A→B→A ownership transfer cannot revive a fresh signed button.
                    db.refresh(telegram)
                    capability = build_telegram_visit_action_token(
                        visit_id=telegram.id, confirmation_token=telegram_token,
                        link_id=link.id, chat_id=link.chat_id, patient_id=first.id,
                        link_epoch=link.patient_link_epoch,
                        visit_context_epoch=telegram.confirmation_context_epoch,
                    )
                    db.execute(text("UPDATE visits SET patient_id=:patient WHERE id=:id"),
                               {"patient": second.id, "id": telegram.id})
                    db.execute(text("UPDATE visits SET patient_id=:patient WHERE id=:id"),
                               {"patient": first.id, "id": telegram.id})
                    db.commit()
                    with pytest.raises(VisitConfirmationDomainError):
                        VisitConfirmationService(db).confirm_by_telegram(
                            token=capability, telegram_user_id=str(link.chat_id), source_ip=None,
                            user_agent="synthetic",
                        )
                    # Canonical contact identity A→B→A revokes the actual
                    # PWA credential; a later fresh issue continues to work.
                    db.execute(text("UPDATE patients SET phone='synthetic-phone-b' WHERE id=:id"), {"id": first.id})
                    db.execute(text("UPDATE patients SET phone='synthetic-phone-a' WHERE id=:id"), {"id": first.id})
                    db.commit()
                    with pytest.raises(VisitConfirmationDomainError):
                        VisitConfirmationService(db).confirm_by_pwa(
                            token=phone_token, patient_phone=None, source_ip=None, user_agent="synthetic",
                        )
                    fresh_phone_token = "synthetic-phone-fresh-" + uuid.uuid4().hex
                    db.refresh(phone_visit)
                    phone_visit.confirmation_token = fresh_phone_token
                    phone_visit.confirmation_expires_at = expires
                    db.commit()
                    assert VisitConfirmationService(db).confirm_by_pwa(
                        token=fresh_phone_token, patient_phone=None, source_ip=None, user_agent="synthetic",
                    )["success"] is True
            finally:
                outer.rollback()
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("replay", [False, True])
def test_schedule_next_pg_never_returns_transferred_patients_token(monkeypatch, replay):
    """Transfer at the response boundary; only the old, revoked bearer may escape."""
    import asyncio
    from datetime import UTC, date, datetime, timedelta

    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.doctor_integration import _visits
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit, VisitService
    from app.services.notification_service import NotificationService
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a fully migrated disposable PostgreSQL clinic_test database")
    engine = create_engine(url)
    suffix = uuid.uuid4().hex[:10]
    with Session(engine, expire_on_commit=False) as db:
        user = User(username=f"race_{suffix}", email=f"race_{suffix}@test.invalid",
                    full_name="SYNTHETIC", hashed_password="test", role="Doctor",
                    is_active=True, is_superuser=False)
        patient_a = Patient(first_name="SYNTHETIC", last_name="A")
        patient_b = Patient(first_name="SYNTHETIC", last_name="B")
        db.add_all([user, patient_a, patient_b])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty="cardiology", active=True)
        db.add(doctor)
        db.flush()
        service = Service(code=f"T{suffix}", name="SYNTHETIC", price=100,
                          duration_minutes=30, active=True, requires_doctor=True,
                          queue_tag="cardiology_common", is_consultation=False)
        db.add(service)
        db.flush()
        day = date.today() + timedelta(days=4)
        db.add(Visit(patient_id=patient_a.id, doctor_id=doctor.id,
                     visit_date=day, visit_time="09:00", status="open",
                     discount_mode="none", source="desk"))
        if replay:
            replay_visit = Visit(patient_id=patient_a.id, doctor_id=doctor.id,
                                 visit_date=day, visit_time="10:00", status="pending_confirmation",
                                 discount_mode="none", source="desk", confirmation_channel="pwa")
            db.add(replay_visit)
            db.flush()
            db.add(VisitService(visit_id=replay_visit.id, service_id=service.id,
                                name="SYNTHETIC", qty=1, price=100))
            db.flush()
            replay_visit.confirmation_token = "replay-old-" + suffix
            replay_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        request = _visits.ScheduleNextVisitRequest(patient_id=patient_a.id, services=[{"service_id": service.id}],
                                                    visit_date=day, visit_time="10:00",
                                                    confirmation_channel="pwa")
        new_token = "new-owner-" + suffix
        captured = {}

        def transfer(visit_id):
            with engine.begin() as conn:
                conn.execute(text("UPDATE visits SET patient_id=:patient WHERE id=:visit"),
                             {"patient": patient_b.id, "visit": visit_id})
                assert conn.execute(text("SELECT confirmation_token FROM visits WHERE id=:visit"),
                                    {"visit": visit_id}).scalar_one() is None
                conn.execute(text("UPDATE visits SET confirmation_token=:token, confirmation_expires_at=:expires WHERE id=:visit"),
                             {"token": new_token, "expires": datetime.now(UTC) + timedelta(hours=1),
                              "visit": visit_id})
            captured["visit_id"] = visit_id

        async def fake_send(self, db, visit_id, channel="auto", expected_context=None):
            captured["expected_context"] = expected_context
            return {"success": False, "channel": channel}

        monkeypatch.setattr(NotificationService, "send_visit_confirmation_invitation", fake_send)
        if replay:
            original = _visits._schedule_next_confirmation_data

            def transfer_before_replay_response(**kwargs):
                transfer(kwargs["visit"].id)
                return original(**kwargs)

            monkeypatch.setattr(_visits, "_schedule_next_confirmation_data", transfer_before_replay_response)
        else:
            commit = db.commit

            def transfer_after_commit():
                commit()
                visit_id = db.execute(text("SELECT id FROM visits WHERE patient_id=:patient AND status='pending_confirmation'"),
                                      {"patient": patient_a.id}).scalar_one()
                db.rollback()
                transfer(visit_id)

            monkeypatch.setattr(db, "commit", transfer_after_commit)
        response = asyncio.run(_visits.schedule_next_visit(request, db, user))
        assert response.idempotent_replay is replay
        assert response.confirmation["token"] != new_token
        assert response.confirmation["token"]
        if not replay:
            assert captured["expected_context"]["patient_id"] == patient_a.id
            assert captured["expected_context"]["confirmation_token"] == response.confirmation["token"]
        with Session(engine) as verify:
            current = verify.get(Visit, captured["visit_id"])
            assert current.patient_id == patient_b.id and current.confirmation_token == new_token
            with pytest.raises(VisitConfirmationDomainError):
                VisitConfirmationService(verify).confirm_by_pwa(
                    token=response.confirmation["token"], patient_phone=None,
                    source_ip=None, user_agent="synthetic",
                )
    engine.dispose()
