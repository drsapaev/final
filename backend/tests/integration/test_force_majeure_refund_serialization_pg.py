"""3808 round 3 (#3809 P1) — сериализация отмены с возвратом (PostgreSQL).

Runtime-доказательство (зеркало Gate D): связанная (bound) мутация
cancel-with-refund берёт блокировку строки DailyQueue FOR UPDATE ДО
чтения набора записей и сравнивает живой набор со снимком предпросмотра
(``expected_entry_ids``). Гонка, закрытая фиксом:

  - сессия A и сессия B одновременно подтверждают ОДНУ и ту же очередь с
    одним и тем же снимком предпросмотра;
  - A выигрывает блокировку строки очереди, отменяет записи и коммитит
    возвраты (deposit credit / automatic refund request);
  - B блокируется на строке очереди; после коммита A перечитывает
    (READ COMMITTED — свежий снапшот на каждый стейтмент) живой
    pending-набор: он пуст → дрейф против снимка → 409 вместо второго
    возврата того же платежа.

До фикса обе сессии одновременно читали один и тот же pending-набор
(без блокировки и без привязки к снимку) и выполняли возврат ДВАЖДЫ.

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
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-fm-serialization-32ch")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.refund_deposit import (  # noqa: E402
    DepositTransaction,
    PatientDeposit,
    RefundRequest,
)
from app.models.visit import Visit  # noqa: E402
from app.services.force_majeure_api_service import (  # noqa: E402
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
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
        refund_deposit,
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


def _seed_world(session, *, queue_tag: str) -> tuple[int, int, list[dict]]:
    """Врач + очередь (владелец-врач) + 2 пациента с записью и оплаченным
    визитом. Возвращает (specialist_id, queue_id, per-entry facts)."""
    doctor = Doctor(specialty="cardiology_common")
    session.add(doctor)
    session.flush()

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag=queue_tag,
        active=True,
    )
    session.add(queue)
    session.flush()

    facts = []
    for number in (1, 2):
        patient = Patient(
            last_name="Гонка",
            first_name=f"Возврат-{number}",
            birth_date=date(1990, 1, number),
            sex="M",
            phone=f"+99890000088{number}",
            created_at=datetime.now(UTC),
            is_deleted=False,
        )
        session.add(patient)
        session.flush()

        visit = Visit(
            patient_id=patient.id,
            doctor_id=None,
            visit_date=date.today(),
            department="cardiology_common",
            discount_mode="none",
            approval_status="approved",
            status="open",
            source="desk",
        )
        session.add(visit)
        session.flush()

        payment = Payment(
            visit_id=visit.id,
            amount=Decimal(f"{150 + number}.00"),
            currency="UZS",
            method="cash",
            status="paid",
            created_at=datetime.now(UTC),
        )
        session.add(payment)
        session.flush()

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=number,
            patient_id=patient.id,
            patient_name=patient.short_name(),
            phone=patient.phone,
            visit_id=visit.id,
            source="desk",
            status="waiting",
            queue_time=datetime.now(UTC).replace(microsecond=0),
            services=[],
            service_codes=[],
            total_amount=150 + number,
        )
        session.add(entry)
        session.flush()

        facts.append(
            {
                "patient_id": patient.id,
                "visit_id": visit.id,
                "payment_id": payment.id,
                "payment_amount": payment.amount,
                "entry_id": entry.id,
            }
        )

    session.commit()
    return doctor.id, queue.id, facts


def _cancel_request(specialist_id, queue_id, snapshot, *, refund_type):
    from types import SimpleNamespace

    return SimpleNamespace(
        specialist_id=specialist_id,
        target_date=date.today(),
        daily_queue_id=queue_id,
        entry_ids=None,
        expected_entry_ids=snapshot,
        reason="doctor emergency serialization probe",
        refund_type=refund_type,
        send_notifications=False,
    )


def _run_cancel(session_factory, *, specialist_id, queue_id, snapshot, refund_type,
                outcomes, tag, barrier=None, done=None):
    session = session_factory()
    try:
        service = ForceMajeureApiService(session)
        if barrier is not None:
            barrier.wait(timeout=10)
        try:
            result = service.cancel_queue_with_refund(
                request=_cancel_request(
                    specialist_id, queue_id, snapshot, refund_type=refund_type
                ),
                current_user_id=1,
            )
            outcomes[tag] = ("ok", result)
        except ForceMajeureApiDomainError as exc:
            outcomes[tag] = ("domain_error", exc.status_code)
            session.rollback()
    finally:
        if done is not None:
            done.set()
        session.close()


def test_concurrent_deposit_cancel_refunds_each_payment_once(
    db_engine, session_factory
):
    """Deposit leg: exactly ONE credit per payment, one deposit balance
    per patient, exactly one winner + one 409 drift refusal."""
    seed = session_factory()
    try:
        specialist_id, queue_id, facts = _seed_world(seed, queue_tag="fm_ser_deposit")
    finally:
        seed.close()
    snapshot = [fact["entry_id"] for fact in facts]

    outcomes: dict[str, tuple] = {}
    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(
            target=_run_cancel,
            kwargs=dict(
                session_factory=session_factory,
                specialist_id=specialist_id,
                queue_id=queue_id,
                snapshot=snapshot,
                refund_type="deposit",
                outcomes=outcomes,
                tag=tag,
                barrier=barrier,
            ),
        )
        for tag in ("A", "B")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive(), "cancel-with-refund завис на блокировке"

    kinds = sorted(outcomes[tag][0] for tag in ("A", "B"))
    assert kinds == ["domain_error", "ok"], outcomes
    loser_status = [
        outcomes[tag][1] for tag in outcomes if outcomes[tag][0] == "domain_error"
    ]
    assert loser_status == [409], outcomes

    verify = session_factory()
    try:
        for fact in facts:
            entry = verify.execute(
                select(OnlineQueueEntry).where(
                    OnlineQueueEntry.id == fact["entry_id"]
                )
            ).scalars().one()
            assert entry.status == "cancelled"

            credits = (
                verify.query(DepositTransaction)
                .filter(DepositTransaction.payment_id == fact["payment_id"])
                .count()
            )
            assert credits == 1, fact

            deposit = (
                verify.query(PatientDeposit)
                .filter(PatientDeposit.patient_id == fact["patient_id"])
                .one()
            )
            assert deposit.balance == fact["payment_amount"], fact
    finally:
        verify.close()


def test_concurrent_bank_transfer_cancel_creates_one_request_each(
    db_engine, session_factory
):
    """bank_transfer leg: exactly ONE automatic refund request per
    payment (the 0087 partial unique is the DB backstop), one 409."""
    seed = session_factory()
    try:
        specialist_id, queue_id, facts = _seed_world(seed, queue_tag="fm_ser_bank")
    finally:
        seed.close()
    snapshot = [fact["entry_id"] for fact in facts]

    outcomes: dict[str, tuple] = {}
    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(
            target=_run_cancel,
            kwargs=dict(
                session_factory=session_factory,
                specialist_id=specialist_id,
                queue_id=queue_id,
                snapshot=snapshot,
                refund_type="bank_transfer",
                outcomes=outcomes,
                tag=tag,
                barrier=barrier,
            ),
        )
        for tag in ("A", "B")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive(), "cancel-with-refund завис на блокировке"

    kinds = sorted(outcomes[tag][0] for tag in ("A", "B"))
    assert kinds == ["domain_error", "ok"], outcomes
    loser_status = [
        outcomes[tag][1] for tag in outcomes if outcomes[tag][0] == "domain_error"
    ]
    assert loser_status == [409], outcomes

    verify = session_factory()
    try:
        for fact in facts:
            automatic_requests = (
                verify.query(RefundRequest)
                .filter(
                    RefundRequest.payment_id == fact["payment_id"],
                    RefundRequest.is_automatic.is_(True),
                )
                .count()
            )
            assert automatic_requests == 1, fact
    finally:
        verify.close()


def test_cancel_waits_for_the_queue_row_lock(db_engine, session_factory):
    """Прямое доказательство блокировки: внешняя сессия держит FOR UPDATE
    на строке очереди — cancel-with-refund обязана ЖДАТЬ её освобождения
    и только затем выполниться (иначе конкурентный писатель читал бы
    незакоммиченный набор)."""
    seed = session_factory()
    try:
        specialist_id, queue_id, facts = _seed_world(seed, queue_tag="fm_ser_lock")
    finally:
        seed.close()
    snapshot = [fact["entry_id"] for fact in facts]

    holder = session_factory()
    holder_locked = threading.Event()
    holder_release = threading.Event()
    outcomes: dict[str, tuple] = {}
    cancel_done = threading.Event()

    def hold_lock() -> None:
        locked = holder.execute(
            select(DailyQueue).where(DailyQueue.id == queue_id).with_for_update()
        ).scalars().one()
        assert locked.id == queue_id
        holder_locked.set()
        # Cancel (thread B) must be stuck on this row lock meanwhile.
        holder_release.wait(timeout=10)
        holder.commit()

    holder_thread = threading.Thread(target=hold_lock)
    holder_thread.start()
    assert holder_locked.wait(timeout=10), "внешняя сессия не взяла блокировку"

    cancel_thread = threading.Thread(
        target=_run_cancel,
        kwargs=dict(
            session_factory=session_factory,
            specialist_id=specialist_id,
            queue_id=queue_id,
            snapshot=snapshot,
            refund_type="deposit",
            outcomes=outcomes,
            tag="B",
            done=cancel_done,
        ),
    )
    cancel_thread.start()
    time.sleep(0.5)
    assert not cancel_done.is_set(), "cancel не дождался блокировки строки очереди"

    holder_release.set()
    holder_thread.join(timeout=10)
    assert cancel_done.wait(timeout=15), "cancel не завершился после снятия блокировки"
    cancel_thread.join(timeout=10)

    assert outcomes.get("B", (None,))[0] == "ok", outcomes
    holder.close()

    verify = session_factory()
    try:
        for fact in facts:
            credits = (
                verify.query(DepositTransaction)
                .filter(DepositTransaction.payment_id == fact["payment_id"])
                .count()
            )
            assert credits == 1, fact
    finally:
        verify.close()
