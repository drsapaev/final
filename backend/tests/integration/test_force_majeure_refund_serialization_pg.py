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

3808 round 4 (#3809 P1) — два дополнения:

  * Изоляция мира теста: модуль больше НЕ трогает схему ``public`` и НЕ
    делает ``DROP SCHEMA public CASCADE`` по произвольному
    ``DATABASE_URL``. Мир живёт в собственной одноразовой схеме
    ``fm_gate_d_<uuid>``: создаётся фикстурой, удаляется teardown-ом, и
    только она; цель подключения строго валидируется до любой DDL.
  * Кросс-канальная идемпотентность возврата: один оплаченный визит в
    записях ДВУХ очередей. Отмены разных очередей в разных каналах
    (deposit / bank_transfer) — и последовательные, и одновременные —
    дают ровно ОДИН возврат платежа: единый claim по ``payment_id``
    (миграция 0088), а не два независимых канала 0087.

Требует PostgreSQL: SQLite не воспроизводит FOR UPDATE / блокировки строк.
Данные синтетические; production DB не используется (см. валидацию цели).
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic_test:clinic_test@localhost:5432/clinic_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-fm-serialization-32ch")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

import app.db.base  # noqa: F401,E402 - registers every model on Base
from app.db.base_class import Base  # noqa: E402
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.refund_deposit import (  # noqa: E402
    DepositTransaction,
    PatientDeposit,
    PaymentRefundClaim,
    RefundRequest,
)
from app.models.visit import Visit  # noqa: E402
from app.services.force_majeure_api_service import (  # noqa: E402
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)

pytestmark = pytest.mark.gate_d

# 3808 round 4 (P1 destructive teardown): мир модуля — одноразовая схема с
# этим префиксом. teardown удаляет ТОЛЬКО схему, сгенерированную этим
# процессом; public / системные схемы недостижимы в принципе.
_SCHEMA_PREFIX = "fm_gate_d_"


def _one_off_schema() -> str:
    return f"{_SCHEMA_PREFIX}{uuid.uuid4().hex[:12]}"


def _target_is_disposable(db_url: str) -> bool:
    """Строгая валидация ЦЕЛИ подключения (3808 round 4, P1).

    Одноразовая схема ограничивает взрыв радиуса даже при ошибке, но
    модуль отказывается работать с базой, которая не выглядит одноразовой,
    ВООБЩЕ: имя базы должно содержать test/ci/gate/dev/local, либо дано
    явное согласие FM_GATE_D_ALLOW_ANY_TARGET=1 (CI использует его для
    своего сервис-контейнера clinicdb, который одноразовый по построению).
    """
    if os.environ.get("FM_GATE_D_ALLOW_ANY_TARGET") == "1":
        return True
    try:
        from sqlalchemy.engine import make_url

        database = (make_url(db_url).database or "").lower()
    except Exception:  # noqa: BLE001 - невалидируемый URL == не-одноразовая цель
        return False
    return bool(re.search(r"test|ci|gate|dev|local", database))


def _refuse_nondisposable_target(db_url: str) -> None:
    if _target_is_disposable(db_url):
        return
    message = (
        "gate_d отказывается работать с DATABASE_URL, который не выглядит "
        "одноразовым (в имени базы нет test/ci/gate/dev/local). Укажите "
        "одноразовую базу (например clinic_test) или выразите явное согласие "
        "FM_GATE_D_ALLOW_ANY_TARGET=1."
    )
    if os.environ.get("CI") == "true":
        # В CI покрытие gate_d не должно молча исчезать: только громкий fail.
        pytest.fail(message)
    pytest.skip(message)


def _assert_drop_safe(schema: str) -> None:
    """Ремень поверх ремня прямо перед ЕДИНСТВЕННОЙ деструктивной DDL
    модуля: удаляться может только схема, сгенерированная этим процессом."""
    assert schema.startswith(_SCHEMA_PREFIX), schema
    assert len(schema) == len(_SCHEMA_PREFIX) + 12, schema
    assert schema not in ("public", "information_schema"), schema
    assert not schema.startswith("pg_"), schema


@pytest.fixture(scope="module")
def db_engine():
    db_url = os.environ["DATABASE_URL"]
    if "postgres" not in db_url:
        pytest.skip("Сериализационный тест требует PostgreSQL, NOT SQLite/иной БД")
    # 3808 review round 4 (P1 destructive teardown): до любой DDL — строгая
    # проверка цели подключения (см. _refuse_nondisposable_target).
    _refuse_nondisposable_target(db_url)

    schema = _one_off_schema()
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    # Собственная одноразовая схема: не public, не то, что поднял alembic,
    # ничего общего ни с чем. Полный реестр моделей (app.db.base) — схема
    # самодостаточна по FK, как и в юнит-мире (conftest).
    with engine.begin() as setup:
        setup.execute(text(f'CREATE SCHEMA "{schema}"'))
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        # Строгий guard перед удалением: только своя схема этого прогона.
        _assert_drop_safe(schema)
        with engine.begin() as teardown:
            teardown.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
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


def _seed_two_queue_world(session) -> dict:
    """3808 round 4 (P1 cross-channel): ОДИН оплаченный визит в записях
    ДВУХ очередей (патологический дубликат-референс — именно он превращает
    два независимых канала 0087 в двойной возврат).

    Врач A владеет очередью A, врач B — очередью B; одна запись в каждой
    очереди ссылается на один и тот же visit (и его платёж)."""
    doctors = {}
    queues = {}
    for tag in ("a", "b"):
        doctor = Doctor(specialty="cardiology_common")
        session.add(doctor)
        session.flush()
        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag=f"fm_x_queue_{tag}",
            active=True,
        )
        session.add(queue)
        session.flush()
        doctors[tag] = doctor
        queues[tag] = queue

    patient = Patient(
        last_name="Кросс",
        first_name="Канал",
        birth_date=date(1991, 2, 2),
        sex="F",
        phone="+998900000771",
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
        amount=Decimal("220.00"),
        currency="UZS",
        method="cash",
        status="paid",
        created_at=datetime.now(UTC),
    )
    session.add(payment)
    session.flush()

    entries = {}
    for tag, number in (("a", 1), ("b", 1)):
        entry = OnlineQueueEntry(
            queue_id=queues[tag].id,
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
            total_amount=220,
        )
        session.add(entry)
        session.flush()
        entries[tag] = entry

    session.commit()
    return {
        "spec_a": doctors["a"].id,
        "spec_b": doctors["b"].id,
        "queue_a": queues["a"].id,
        "queue_b": queues["b"].id,
        "patient_id": patient.id,
        "visit_id": visit.id,
        "payment_id": payment.id,
        "payment_amount": payment.amount,
        "entry_a": entries["a"].id,
        "entry_b": entries["b"].id,
    }


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


def _cancel_once(session_factory, *, specialist_id, queue_id, snapshot, refund_type):
    """Последовательная (одиночная) отмена одной очереди; доменные ошибки
    всплывают наружу как исключения."""
    session = session_factory()
    try:
        service = ForceMajeureApiService(session)
        return service.cancel_queue_with_refund(
            request=_cancel_request(
                specialist_id, queue_id, snapshot, refund_type=refund_type
            ),
            current_user_id=None,
        )
    except ForceMajeureApiDomainError:
        session.rollback()
        raise
    finally:
        session.close()


def _run_cancel(session_factory, *, specialist_id, queue_id, snapshot, refund_type,
                outcomes, tag, barrier=None, done=None):
    # performed_by is NULL by design (DepositTransaction.performed_by is a
    # nullable audit axis): the synthetic world has no users row, and on
    # PostgreSQL (unlike the SQLite unit dialect) the FK to users.id is
    # enforced — a bogus performed_by_id would abort the whole mutation.
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
                current_user_id=None,
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


def test_cross_channel_two_queues_refund_payment_once(db_engine, session_factory):
    """3808 round 4 (P1 cross-channel), последовательно: ОДИН оплаченный
    визит в записях ДВУХ очередей. Отмена очереди A каналом deposit
    кредитует депозит; отмена очереди B каналом bank_transfer обязана НЕ
    создавать вторую автоматическую заявку — единый claim по payment_id
    (0088), а не два независимых канала 0087."""
    seed = session_factory()
    try:
        world = _seed_two_queue_world(seed)
    finally:
        seed.close()

    first = _cancel_once(
        session_factory,
        specialist_id=world["spec_a"],
        queue_id=world["queue_a"],
        snapshot=[world["entry_a"]],
        refund_type="deposit",
    )
    assert first["cancelled"] == 1, first
    assert not first["details"][0]["refund_info"].get("already_refunded"), first

    second = _cancel_once(
        session_factory,
        specialist_id=world["spec_b"],
        queue_id=world["queue_b"],
        snapshot=[world["entry_b"]],
        refund_type="bank_transfer",
    )
    assert second["cancelled"] == 1, second
    refund_info = second["details"][0]["refund_info"]
    assert refund_info["already_refunded"] is True, second
    assert refund_info["prior_channel"] == "deposit", second

    verify = session_factory()
    try:
        for entry_id in (world["entry_a"], world["entry_b"]):
            entry = verify.execute(
                select(OnlineQueueEntry).where(OnlineQueueEntry.id == entry_id)
            ).scalars().one()
            assert entry.status == "cancelled", entry_id

        credits = (
            verify.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == world["payment_id"])
            .count()
        )
        automatic_requests = (
            verify.query(RefundRequest)
            .filter(
                RefundRequest.payment_id == world["payment_id"],
                RefundRequest.is_automatic.is_(True),
            )
            .count()
        )
        claims = (
            verify.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == world["payment_id"])
            .all()
        )
        assert credits == 1, "ровно один депозитный кредит"
        assert automatic_requests == 0, "вторая (банковская) нога не создаётся"
        assert len(claims) == 1, claims
        assert claims[0].channel == "deposit", claims
        assert claims[0].deposit_transaction_id is not None, claims

        deposit = (
            verify.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == world["patient_id"])
            .one()
        )
        assert deposit.balance == world["payment_amount"], deposit.balance
    finally:
        verify.close()


def test_cross_channel_two_queues_concurrent_refund_once(
    db_engine, session_factory
):
    """3808 round 4 (P1 cross-channel), конкурентно: отмены ДВУХ очередей
    с одним платежом в РАЗНЫХ каналах стартуют одновременно. Обе отмены
    завершаются ok (записи обеих очередей отменены), но возврат ровно
    ОДИН: уникальный claim по payment_id решает победителя в БД,
    проигравший получает already_refunded (не ошибку и не второй возврат)."""
    seed = session_factory()
    try:
        world = _seed_two_queue_world(seed)
    finally:
        seed.close()

    outcomes: dict[str, tuple] = {}
    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(
            target=_run_cancel,
            kwargs={
                "session_factory": session_factory,
                "specialist_id": world["spec_a"],
                "queue_id": world["queue_a"],
                "snapshot": [world["entry_a"]],
                "refund_type": "deposit",
                "outcomes": outcomes,
                "tag": "deposit_leg",
                "barrier": barrier,
            },
        ),
        threading.Thread(
            target=_run_cancel,
            kwargs={
                "session_factory": session_factory,
                "specialist_id": world["spec_b"],
                "queue_id": world["queue_b"],
                "snapshot": [world["entry_b"]],
                "refund_type": "bank_transfer",
                "outcomes": outcomes,
                "tag": "bank_leg",
                "barrier": barrier,
            },
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "кросс-канальная отмена зависла"

    for tag in ("deposit_leg", "bank_leg"):
        assert outcomes[tag][0] == "ok", (tag, outcomes)

    fresh_legs = 0
    refunded_legs = 0
    for tag in ("deposit_leg", "bank_leg"):
        refund_info = outcomes[tag][1]["details"][0]["refund_info"]
        if refund_info.get("already_refunded"):
            refunded_legs += 1
            assert refund_info["prior_channel"] in ("deposit", "refund_request")
        else:
            fresh_legs += 1
    assert fresh_legs == 1, outcomes
    assert refunded_legs == 1, outcomes

    verify = session_factory()
    try:
        for entry_id in (world["entry_a"], world["entry_b"]):
            entry = verify.execute(
                select(OnlineQueueEntry).where(OnlineQueueEntry.id == entry_id)
            ).scalars().one()
            assert entry.status == "cancelled", entry_id

        credits = (
            verify.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == world["payment_id"])
            .count()
        )
        automatic_requests = (
            verify.query(RefundRequest)
            .filter(
                RefundRequest.payment_id == world["payment_id"],
                RefundRequest.is_automatic.is_(True),
            )
            .count()
        )
        claims = (
            verify.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == world["payment_id"])
            .all()
        )
        # Ровно один возврат любым из каналов — и ровно один claim.
        assert credits + automatic_requests == 1, (credits, automatic_requests)
        assert len(claims) == 1, claims
        assert claims[0].channel in ("deposit", "refund_request"), claims

        if credits == 1:
            deposit = (
                verify.query(PatientDeposit)
                .filter(PatientDeposit.patient_id == world["patient_id"])
                .one()
            )
            assert deposit.balance == world["payment_amount"], deposit.balance
            assert claims[0].deposit_transaction_id is not None, claims
        else:
            assert claims[0].refund_request_id is not None, claims
    finally:
        verify.close()


def test_payment_refund_claim_unique_is_the_db_backstop(db_engine, session_factory):
    """3808 round 4: единый guard существует и НА УРОВНЕ БД — вторая строка
    claim по тому же payment_id невозможна, что бы ни делал код
    (uq_payment_refund_claims_payment, миграция 0088)."""
    from sqlalchemy.exc import IntegrityError

    seed = session_factory()
    try:
        _, _, facts = _seed_world(seed, queue_tag="fm_claim_backstop")
    finally:
        seed.close()
    payment_id = facts[0]["payment_id"]

    verify = session_factory()
    try:
        first = PaymentRefundClaim(
            payment_id=payment_id,
            channel="deposit",
            reason="db backstop probe",
        )
        verify.add(first)
        verify.flush()

        duplicate = PaymentRefundClaim(
            payment_id=payment_id,
            channel="refund_request",
            reason="must never persist",
        )
        verify.add(duplicate)
        with pytest.raises(IntegrityError):
            verify.flush()
        # rollback откатывает ОБЕ вставки этой сессии (дубликат отравил
        # транзакцию) — заново вставляем ровно одну строку и фиксируем.
        verify.rollback()

        survivor = PaymentRefundClaim(
            payment_id=payment_id,
            channel="deposit",
            reason="db backstop probe (replay)",
        )
        verify.add(survivor)
        verify.flush()

        persisted = (
            verify.query(PaymentRefundClaim)
            .filter(PaymentRefundClaim.payment_id == payment_id)
            .count()
        )
        assert persisted == 1
    finally:
        verify.close()
