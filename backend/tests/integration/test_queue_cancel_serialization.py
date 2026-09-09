"""W2-PR3 — сериализация отмены записи с платёжным потоком (PostgreSQL).

Runtime-доказательство (зеркало Gate D): cancel_entry держит цепочку
блокировок entry → visit → invoice и РЕВАЛИДИРУЕТ платежи ПОСЛЕ ожидания
блокировки визита. Гонка, закрытая фикс:

  - сессия A (платёжный поток) держит блокировку строки Visit и коммитит
    канонический Payment (paid) в окне, пока отмена ещё не дошла до гварда;
  - сессия B (отмена записи) блокируется на Visit FOR UPDATE, после коммита
    A видит закоммиченный платёж (READ COMMITTED — свежий снапшот на каждый
    стейтмент) и ОТКАЗЫВАЕТ вместо отмены записи поверх полученных денег.

Требует PostgreSQL: SQLite не воспроизводит FOR UPDATE / блокировки строк.
Данные синтетические; production DB не используется.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic_test:clinic_test@localhost:5432/clinic_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-cancel-serialization-32ch")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.visit import Visit  # noqa: E402
from app.services.online_queue_new_service import (  # noqa: E402
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)

pytestmark = pytest.mark.gate_d


@pytest.fixture(scope="module")
def db_engine():
    db_url = os.environ["DATABASE_URL"]
    if "sqlite" in db_url:
        pytest.fail(
            "Сериализационный тест требует PostgreSQL, NOT SQLite. "
            "Задайте DATABASE_URL=postgresql+psycopg://..."
        )
    engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    from app.db.base_class import Base
    from app.models import (  # noqa: F401
        appointment,
        audit,
        clinic,
        emr_v2,
        lab,
        online_queue,
        patient,
        payment,
        payment_invoice,
        payment_webhook,
        user,
        visit,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    Session = sessionmaker(bind=db_engine)
    return Session


def _seed_world(session) -> tuple[Patient, Visit, OnlineQueueEntry]:
    patient = Patient(
        last_name="Гонка",
        first_name="Отмена",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone="+998900000779",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()
    # PostgreSQL enforcing FK: DailyQueue.specialist_id → doctors.id.
    doctor = Doctor(specialty="laboratory_general")
    session.add(doctor)
    session.flush()
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="laboratory_general",
        active=True,
    )
    session.add(queue)
    session.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=None,
        visit_date=date.today(),
        department="laboratory_general",
        discount_mode="none",
        approval_status="approved",
        status="open",
        source="desk",
    )
    session.add(visit)
    session.flush()
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=3,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        visit_id=visit.id,
        source="desk",
        status="waiting",
        queue_time=datetime.now(UTC).replace(microsecond=0),
        services=[],
        service_codes=[],
        total_amount=500,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return patient, visit, entry


def test_cancel_yields_to_committed_payment_and_refuses(db_engine, session_factory):
    """Отмена записи поверх закоммиченного платежа отказывает: сессия A
    коммитит Payment в окне блокировки визита, сессия B (отмена) ревалидирует
    ПОСЛЕ ожидания и возвращает 409, состояние записи не изменено."""
    seed_session = session_factory()
    try:
        _, visit, entry = _seed_world(seed_session)
        visit_id, entry_id = visit.id, entry.id
    finally:
        seed_session.close()

    visit_locked = threading.Event()
    payment_committed = threading.Event()
    cancel_result: dict[str, object] = {}

    def payment_flow() -> None:
        session_a = session_factory()
        try:
            # Платёжный поток: блокировка строки визита (та же блокировка,
            # которую держит PaymentInvariantService при создании платежа).
            locked = (
                session_a.execute(
                    select(Visit).where(Visit.id == visit_id).with_for_update()
                )
                .scalars()
                .one()
            )
            assert locked.id == visit_id
            visit_locked.set()
            # Окно гонки: отмена уже идёт параллельно и ждёт эту блокировку.
            time.sleep(0.4)
            session_a.add(
                Payment(
                    visit_id=visit_id,
                    amount=Decimal(500),
                    currency="UZS",
                    method="cash",
                    status="paid",
                    created_at=datetime.now(UTC),
                )
            )
            session_a.commit()
        finally:
            payment_committed.set()
            session_a.close()

    def cancel_flow() -> None:
        session_b = session_factory()
        try:
            # READ COMMITTED — дефолт PostgreSQL: каждый стейтмент видит
            # свежий снапшот, поэтому гвард платежей ПОСЛЕ ожидания
            # блокировки обязан увидеть закоммиченный платёж сессии A.
            service = OnlineQueueNewService(session_b)
            try:
                service.cancel_entry(entry_id=entry_id)
                cancel_result["outcome"] = "canceled"
            except OnlineQueueNewDomainError as exc:
                cancel_result["outcome"] = "refused"
                cancel_result["detail"] = exc.detail
                session_b.rollback()
        finally:
            session_b.close()

    thread_a = threading.Thread(target=payment_flow)
    thread_b = threading.Thread(target=cancel_flow)
    thread_a.start()
    assert visit_locked.wait(timeout=5), "платёжный поток не взял блокировку визита"
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)
    assert not thread_b.is_alive(), "отмена записи зависла на блокировке визита"

    # Отмена дождалась коммита платежа, увидела деньги и ОТКАЗАЛА.
    assert cancel_result.get("outcome") == "refused", cancel_result
    assert "оплата" in str(cancel_result.get("detail", ""))

    # Состояние не изменено: запись ждёт, визит открыт, платёж на месте.
    verify = session_factory()
    try:
        refreshed_entry = (
            verify.execute(select(OnlineQueueEntry).where(OnlineQueueEntry.id == entry_id))
            .scalars()
            .one()
        )
        refreshed_visit = (
            verify.execute(select(Visit).where(Visit.id == visit_id)).scalars().one()
        )
        payments = (
            verify.execute(select(Payment).where(Payment.visit_id == visit_id)).scalars().all()
        )
        assert refreshed_entry.status == "waiting"
        assert refreshed_visit.status == "open"
        assert [p.status for p in payments] == ["paid"]
    finally:
        verify.close()
