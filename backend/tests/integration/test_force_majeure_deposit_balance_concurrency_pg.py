"""3808 round 12 (#3809 P1) — гонка депозитного баланса ОДНОГО пациента.

Runtime-доказательство фикса ``_add_to_deposit``: идемпотентность ОДНОГО
платежа закрыта claim-ами (0087/0088), но баланс депозита — ОБЩАЯ строка
пациента, и ПАРАЛЛЕЛЬНЫЕ возвраты РАЗНЫХ платежей одного пациента должны
СУММИРОВАТЬСЯ, а не перезаписывать друг друга.

Производственный сценарий модуля: пациент записан в ДВЕ очереди (два
оплаченных визита — два РАЗНЫХ платежа); два регистратора одновременно
подтверждают форс-мажорную отмену СВОЕЙ очереди с возвратом на депозит.
Блокировка строки очереди (round 3) здесь не помогает — строки РАЗНЫЕ;
claim-ы не помогают — платежи РАЗНЫЕ. Гонка живёт ровно в окне
read-modify-write баланса.

Гонка, закрытая фиксом (READ COMMITTED, PostgreSQL):

  * существующий депозит: обе ноги берут строку FOR UPDATE — вторая ждёт
    коммита первой и читает уже пополненный balance (round 12);
  * конкурентное создание: обе ноги не находят депозита; INSERT-проигравший
    ловит unique(patient_id) на connection-level savepoint (паттерн
    ``_claim_payment_refund``) и зачисляет на строку победителя.

До фикса: обе ноги читали один balance и каждая писала СВОЮ сумму — одно
зачисление терялось (``balance_after`` аудита расходился с фактическими
credit-строками); при конкурентном создании необученный IntegrityError
ломал всю отмену (poisoned session -> 500).

Дополнительно пинирует счётчики round 12 (P2): каждая нога обязана
сообщить ``deposit_credits_created == 1`` — депозитные зачисления больше
не «невидимы» для ответа API.

Требует PostgreSQL: SQLite не воспроизводит FOR UPDATE и блокировки строк
(см. ``_validated_daily_queue``: «SQLite (unit tests) ignores FOR UPDATE»).
Мир — одноразовая схема ``fm_dep_race_<uuid12>`` (паттерн gate_d);
production DB не используется: строгая валидация цели до любой DDL.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic_test:clinic_test@localhost:5432/clinic_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-fm-deposit-race-32ch")
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
    DepositTransactionType,
    PatientDeposit,
    PaymentRefundClaim,
)
from app.models.visit import Visit  # noqa: E402
from app.services.force_majeure_api_service import (  # noqa: E402
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)

pytestmark = pytest.mark.gate_d

# 3808 round 12: мир модуля — одноразовая схема с этим префиксом; teardown
# удаляет ТОЛЬКО схему, сгенерированную этим процессом (паттерн gate_d).
_SCHEMA_PREFIX = "fm_dep_race_"

_AMOUNT_A = Decimal("150.00")
_AMOUNT_B = Decimal("200.00")
_TOTAL = _AMOUNT_A + _AMOUNT_B  # 350.00


def _one_off_schema() -> str:
    return f"{_SCHEMA_PREFIX}{uuid.uuid4().hex[:12]}"


def _target_is_disposable(db_url: str) -> bool:
    """Строгая валидация ЦЕЛИ подключения (паттерн gate_d round 4).

    Модуль отказывается работать с базой, которая не выглядит одноразовой:
    имя базы должно содержать test/ci/gate/dev/local, либо дано явное
    согласие FM_GATE_D_ALLOW_ANY_TARGET=1 (то же имя, что у FM
    serialization-модуля: CI использует его для своего одноразового
    сервис-контейнера clinicdb).
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
        "deposit-race отказывается работать с DATABASE_URL, который не"
        " выглядит одноразовым (в имени базы нет test/ci/gate/dev/local)."
        " Укажите одноразовую базу (например clinic_test) или выразите"
        " явное согласие FM_GATE_D_ALLOW_ANY_TARGET=1."
    )
    if os.environ.get("CI") == "true":
        pytest.fail(message)
    pytest.skip(message)


def _assert_drop_safe(schema: str) -> None:
    """Ремень поверх ремня перед ЕДИНСТВЕННОЙ деструктивной DDL модуля."""
    assert schema.startswith(_SCHEMA_PREFIX), schema
    assert len(schema) == len(_SCHEMA_PREFIX) + 12, schema
    assert schema not in ("public", "information_schema"), schema
    assert not schema.startswith("pg_"), schema


@pytest.fixture(scope="module")
def db_engine():
    db_url = os.environ["DATABASE_URL"]
    if "postgres" not in db_url:
        pytest.skip("Гонка депозитного баланса требует PostgreSQL, NOT SQLite")
    _refuse_nondisposable_target(db_url)

    schema = _one_off_schema()
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    with engine.begin() as setup:
        setup.execute(text(f'CREATE SCHEMA "{schema}"'))
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        _assert_drop_safe(schema)
        with engine.begin() as teardown:
            teardown.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    Session = sessionmaker(bind=db_engine)
    return Session


def _seed_round(session, *, with_deposit: bool) -> dict:
    """Мир одного раунда: врач A/очередь A + врач B/очередь B, ОДИН пациент
    с ДВУМЯ оплаченными визитами (платёж A — 150, платёж B — 200), запись
    каждого визита — в своей очереди. ``with_deposit`` — предсоздать
    депозиту строку (вариант «существующий депозит»)."""
    suffix = uuid.uuid4().hex[:8]
    world: dict = {}

    doctors = {}
    queues = {}
    for tag in ("a", "b"):
        doctor = Doctor(specialty="cardiology_common")
        session.add(doctor)
        session.flush()
        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag=f"fm_dep_race_{tag}_{suffix}",
            active=True,
        )
        session.add(queue)
        session.flush()
        doctors[tag] = doctor
        queues[tag] = queue

    patient = Patient(
        last_name="Депозитный",
        first_name=f"Баланс-{suffix[:4]}",
        birth_date=date(1992, 3, 3),
        sex="M",
        phone=f"+9989{suffix[:9]}",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()

    if with_deposit:
        session.add(PatientDeposit(patient_id=patient.id, balance=Decimal("50.00")))
        session.flush()

    amounts = {"a": _AMOUNT_A, "b": _AMOUNT_B}
    for tag in ("a", "b"):
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
            amount=amounts[tag],
            currency="UZS",
            method="cash",
            status="paid",
            created_at=datetime.now(UTC),
        )
        session.add(payment)
        session.flush()

        entry = OnlineQueueEntry(
            queue_id=queues[tag].id,
            number=1,
            patient_id=patient.id,
            patient_name=patient.short_name(),
            phone=patient.phone,
            visit_id=visit.id,
            source="desk",
            status="waiting",
            queue_time=datetime.now(UTC).replace(microsecond=0),
            services=[],
            service_codes=[],
            total_amount=int(amounts[tag]),
        )
        session.add(entry)
        session.flush()

        world[f"specialist_{tag}"] = doctors[tag].id
        world[f"queue_{tag}"] = queues[tag].id
        world[f"entry_{tag}"] = entry.id
        world[f"payment_{tag}"] = payment.id

    world["patient_id"] = patient.id
    session.commit()
    return world


def _cancel_request(specialist_id, queue_id, snapshot):
    return SimpleNamespace(
        specialist_id=specialist_id,
        target_date=date.today(),
        daily_queue_id=queue_id,
        entry_ids=None,
        expected_entry_ids=snapshot,
        reason="deposit balance race probe",
        refund_type="deposit",
        send_notifications=False,
    )


def _run_cancel(session_factory, *, specialist_id, queue_id, snapshot,
                outcomes, tag, barrier=None):
    # performed_by is NULL by design: DepositTransaction.performed_by —
    # nullable audit axis, синтетический мир без users (FK на PG строг).
    session = session_factory()
    try:
        service = ForceMajeureApiService(session)
        if barrier is not None:
            barrier.wait(timeout=10)
        try:
            result = service.cancel_queue_with_refund(
                request=_cancel_request(specialist_id, queue_id, snapshot),
                current_user_id=None,
            )
            outcomes[tag] = ("ok", result)
        except ForceMajeureApiDomainError as exc:
            session.rollback()
            outcomes[tag] = ("domain_error", exc.status_code)
    except Exception as exc:  # noqa: BLE001 - исход гонки целиком в outcomes
        session.rollback()
        outcomes[tag] = ("error", repr(exc))
    finally:
        session.close()


def _run_parallel_cancels(session_factory, world) -> dict:
    """Два потока, старт синхронизирован барьером: каждый отменяет СВОЮ
    очередь пациента с депозитным возвратом своего платежа."""
    outcomes: dict[str, tuple] = {}
    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(
            target=_run_cancel,
            kwargs=dict(
                session_factory=session_factory,
                specialist_id=world[f"specialist_{tag}"],
                queue_id=world[f"queue_{tag}"],
                snapshot=[world[f"entry_{tag}"]],
                outcomes=outcomes,
                tag=tag,
                barrier=barrier,
            ),
        )
        for tag in ("a", "b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "cancel-with-refund завис на блокировке"
    return outcomes


def _verify_patient_money(session, world, *, initial: Decimal) -> None:
    """Инварианты денег пациента после ОБЕИХ ног: ровно один депозит,
    баланс = старт + оба зачисления, обе credit-строки, корректный
    balance_after, оба claim-а."""
    deposits = (
        session.query(PatientDeposit)
        .filter(PatientDeposit.patient_id == world["patient_id"])
        .all()
    )
    assert len(deposits) == 1, deposits

    credits = (
        session.query(DepositTransaction)
        .filter(
            DepositTransaction.deposit_id == deposits[0].id,
            DepositTransaction.transaction_type
            == DepositTransactionType.CREDIT.value,
        )
        .all()
    )
    assert len(credits) == 2, credits

    credited = sum(credit.amount for credit in credits)
    assert credited == _TOTAL, credited
    assert deposits[0].balance == initial + _TOTAL, deposits[0].balance

    # Аудит: последний balance_after = итоговому балансу (не «своей» сумме
    # поверх устаревшего чтения — ровно то, что терялось в гонке). Первая
    # нога недетерминирована: после неё баланс = старт + ЕЁ сумма.
    after_values = sorted(credit.balance_after for credit in credits)
    assert after_values[-1] == initial + _TOTAL, after_values
    assert after_values[0] in (initial + _AMOUNT_A, initial + _AMOUNT_B), after_values

    claims = (
        session.query(PaymentRefundClaim)
        .filter(
            PaymentRefundClaim.payment_id.in_(
                [world["payment_a"], world["payment_b"]]
            )
        )
        .all()
    )
    assert len(claims) == 2, claims


def test_parallel_deposit_credits_same_patient_concurrent_creation(
    db_engine, session_factory
):
    """Конкурентное СОЗДАНИЕ депозита: до фикса — необученный IntegrityError
    (одна нога падает 500-й), после — обе ноги ок, баланс = сумма."""
    for _ in range(5):
        seed = session_factory()
        try:
            world = _seed_round(seed, with_deposit=False)
        finally:
            seed.close()

        outcomes = _run_parallel_cancels(session_factory, world)
        kinds = sorted(outcomes[tag][0] for tag in ("a", "b"))
        assert kinds == ["ok", "ok"], outcomes

        verify = session_factory()
        try:
            _verify_patient_money(verify, world, initial=Decimal("0.00"))
        finally:
            verify.close()


def test_parallel_deposit_credits_same_patient_existing_row(
    db_engine, session_factory
):
    """Существующий депозит (balance=50): до фикса — lost update (баланс
    200 или 250 вместо 400 — статистическая гонка, поэтому несколько
    раундов), после — FOR UPDATE сериализует, баланс точен."""
    for _ in range(15):
        seed = session_factory()
        try:
            world = _seed_round(seed, with_deposit=True)
        finally:
            seed.close()

        outcomes = _run_parallel_cancels(session_factory, world)
        kinds = sorted(outcomes[tag][0] for tag in ("a", "b"))
        assert kinds == ["ok", "ok"], outcomes

        verify = session_factory()
        try:
            _verify_patient_money(verify, world, initial=Decimal("50.00"))
        finally:
            verify.close()


def test_sequential_deposit_credits_same_patient(db_engine, session_factory):
    """Контроль без конкурентности: последовательные отмены обеих очередей
    суммируются (базовая семантика + счётчики P2 в ответе)."""
    seed = session_factory()
    try:
        world = _seed_round(seed, with_deposit=False)
    finally:
        seed.close()

    results = {}
    for tag in ("a", "b"):
        outcomes: dict[str, tuple] = {}
        _run_cancel(
            session_factory,
            specialist_id=world[f"specialist_{tag}"],
            queue_id=world[f"queue_{tag}"],
            snapshot=[world[f"entry_{tag}"]],
            outcomes=outcomes,
            tag=tag,
        )
        assert outcomes[tag][0] == "ok", outcomes
        results[tag] = outcomes[tag][1]

    # 3808 round 12 (P2): депозитные зачисления видны в ответе — прежде
    # ветка DEPOSIT не попадала ни в один счётчик.
    for tag in ("a", "b"):
        assert results[tag]["cancelled"] == 1, results[tag]
        assert results[tag]["deposit_credits_created"] == 1, results[tag]
        assert results[tag]["refund_requests_created"] == 0, results[tag]

    verify = session_factory()
    try:
        _verify_patient_money(verify, world, initial=Decimal("0.00"))
        # SELECT через select() — чтобы импорт не был «мертвым» и проверка
        # читала ту же строку, что и сервис.
        balance = verify.execute(
            select(PatientDeposit.balance).where(
                PatientDeposit.patient_id == world["patient_id"]
            )
        ).scalar_one()
        assert balance == _TOTAL, balance
    finally:
        verify.close()
