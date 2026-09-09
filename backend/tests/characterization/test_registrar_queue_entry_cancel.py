"""W2-PR3 — согласованное удаление/отмена записи очереди.

Дефект (воспроизведён на актуальном коде): POST
/online-queue/entries/{id}/cancel (OnlineQueueNewService.cancel_entry)
менял ТОЛЬКО entry.status='canceled'. Связанные сущности оставались в
противоречивом состоянии:

  - Visit (entry.visit_id) оставался open — «отменённая» запись продолжала
    светиться в рабочих списках врача и в EMR;
  - PENDING-счёт (PaymentInvoice → PaymentInvoiceVisit.visit_amount)
    оставался на прежнюю сумму — пациент обязан заплатить за отменённую
    услугу;
  - не было ни гварда статуса записи (отменить можно было даже served),
    ни блокировки строки (гонка с платёжными потоками), ни идемпотентности.

Контракт W2-PR3: отмена записи — атомарный согласованный каскад
(entry → visit → pending-счёт) под блокировками строк; потреблённые и
оплаченные позиции отвергаются с явной причиной (возврат — отдельный
финансовый контракт, см. W2-PR1 docstring _assert_decrease_allowed).

Каждый сохраняющий кейс проверяет СОСТОЯНИЕ повторным чтением DB.
Данные синтетические; production DB не используется.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.online_queue_new_service import (
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)

TZ = ZoneInfo("Asia/Tashkent")


def _create_patient(db_session) -> Patient:
    """Codex R14 PR 3121 (P1): санкционированная synthetic-фикстура —
    метка SYNTHETIC- в фамилии и DEV-DEMO-телефон вместо реалистичной
    пары «имя + узбекский номер» (политика AGENTS.md Synthetic data
    policy: только synthetic_seed.py/dev_seed.py или явная метка)."""
    patient = Patient(
        last_name="SYNTHETIC-W2PR3-Cancel",
        first_name="Тест",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone="DEV-DEMO-W2PR3-1",
        created_at=datetime.now(TZ),
        is_deleted=False,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"W2PR3 {code}",
        price=Decimal(price),
        active=True,
        requires_doctor=False,
        queue_tag="laboratory_general",
        department_key="laboratory_general",
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_queue(db_session, *, specialist_id: int, queue_tag: str, day: date) -> DailyQueue:
    queue = DailyQueue(day=day, specialist_id=specialist_id, queue_tag=queue_tag, active=True)
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_visit(
    db_session,
    *,
    patient: Patient,
    service: Service,
    status: str = "open",
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=None,
        visit_date=date.today(),
        visit_time=None,
        department="laboratory_general",
        discount_mode="none",
        approval_status="approved",
        status=status,
        source="desk",
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.service_code,
            name=service.name,
            qty=1,
            price=service.price,
            currency="UZS",
        )
    )
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _create_entry(
    db_session,
    *,
    queue: DailyQueue,
    patient: Patient,
    visit: Visit | None,
    status: str = "waiting",
    total_amount: int = 500,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        visit_id=visit.id if visit else None,
        source="desk",
        status=status,
        queue_time=datetime.now(TZ).replace(microsecond=0),
        services=[],
        service_codes=[],
        total_amount=total_amount,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _create_invoice(
    db_session,
    *,
    patient: Patient,
    visit: Visit,
    amount: int,
    status: str = "pending",
) -> PaymentInvoice:
    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=Decimal(amount),
        currency="UZS",
        status=status,
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=visit.id,
            visit_amount=Decimal(amount),
        )
    )
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


@pytest.fixture
def cancel_world(db_session):
    """Пациент + услуга + очередь лаборатории — общая база кейсов."""
    patient = _create_patient(db_session)
    service = _create_service(db_session, code="W2PR3CAN", price=500)
    queue = _create_queue(
        db_session, specialist_id=4242, queue_tag="laboratory_general", day=date.today()
    )
    return {"patient": patient, "service": service, "queue": queue}


# ─── Основной каскад ───────────────────────────────────────────────────


def test_cancel_cascades_to_open_visit_and_pending_invoice(db_session, cancel_world):
    """Отмена записи со связанным open-визитом и pending-счётом каскадно
    отменяет визит и аннулирует счёт (ссылка визит↔счёт исчезла, счёт
    без оставшихся позиций → cancelled). Состояние проверяется повторным
    чтением."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    invoice = _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.expire_all()

    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    # Каноническое написание статуса ЗАПИСИ — «cancelled» (тот же, что
    # пишут queue_svc/force majeure и ждёт queue position API и FE-тип
    # QueueEntryStatus); статус ВИЗИТА остаётся «canceled» (SSOT
    # visit lifecycle).
    assert refreshed_entry.status == "cancelled"
    assert refreshed_visit.status == "canceled"
    assert refreshed_invoice.status == "cancelled"
    assert (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
        .count()
        == 0
    )


def test_cancel_reduces_multi_visit_invoice_and_keeps_other_links(db_session, cancel_world):
    """Счёт на два визита: отмена записи одного визита уменьшает total_amount
    на его долю и сохраняет позицию другого визита; счёт остаётся pending."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit_a = _create_visit(db_session, patient=patient, service=service, status="open")
    visit_b = _create_visit(db_session, patient=patient, service=service, status="open")
    entry_a = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit_a
    )
    invoice = _create_invoice(db_session, patient=patient, visit=visit_a, amount=500)
    db_session.add(
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit_b.id, visit_amount=Decimal(700))
    )
    # Реалистичная фикстура: total счёта = сумма позиций (500 + 700),
    # как это делает /registrar/cart для мультвизитной корзины.
    invoice.total_amount = Decimal(1200)
    db_session.commit()

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry_a.id)
    db_session.expire_all()

    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_invoice.status == "pending"
    assert Decimal(str(refreshed_invoice.total_amount)) == Decimal(700)
    link_b = (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
        .filter(PaymentInvoiceVisit.visit_id == visit_b.id)
        .one()
    )
    assert Decimal(str(link_b.visit_amount)) == Decimal(700)
    link_a = (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
        .filter(PaymentInvoiceVisit.visit_id == visit_a.id)
        .count()
    )
    assert link_a == 0


# ─── Гварды: потреблённые/оплаченные позиции ──────────────────────────


def test_cancel_rejects_consumed_entry(db_session, cancel_world):
    """Уже обслуженная запись (served) не отменяется из корзины: явный отказ,
    состояние не изменено."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit, status="served"
    )
    invoice = _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    with pytest.raises(OnlineQueueNewDomainError) as exc:
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    assert "served" in getattr(exc.value, "detail", "")

    db_session.expire_all()
    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "served"
    assert refreshed_visit.status == "open"
    assert refreshed_invoice.status == "pending"


def test_cancel_rejects_when_invoice_processing(db_session, cancel_world):
    """Счёт в processing — платёж уходит провайдеру: отмена записи отвергается,
    состояние не изменено (зеркало гарда снижения W2-PR1)."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    invoice = _create_invoice(
        db_session, patient=patient, visit=visit, amount=500, status="processing"
    )

    with pytest.raises(OnlineQueueNewDomainError):
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "waiting"
    assert refreshed_visit.status == "open"
    assert refreshed_invoice.status == "processing"


def test_cancel_rejects_when_invoice_paid(db_session, cancel_world):
    """Оплаченный счёт — снижение/отмена это возврат, отдельный финансовый
    контракт: явный отказ, состояние не изменено."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    invoice = _create_invoice(
        db_session, patient=patient, visit=visit, amount=500, status="paid"
    )

    with pytest.raises(OnlineQueueNewDomainError):
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "waiting"
    assert refreshed_visit.status == "open"
    assert refreshed_invoice.status == "paid"


def test_cancel_rejects_when_provider_payment_pending(db_session, cancel_world):
    """Инициализированный провайдерский платёж (pending + payment_url):
    сумма у ссылки фиксирована — отмена записи сделала бы ссылку нечитаемой
    для пациента. Явный отказ, состояние не изменено (зеркало R10 PR 3118)."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    _create_invoice(db_session, patient=patient, visit=visit, amount=500)
    db_session.add(
        Payment(
            visit_id=visit.id,
            amount=Decimal(500),
            currency="UZS",
            method="online",
            provider="click",
            status="pending",
            payment_url="https://provider.test/pay/123",
        )
    )
    db_session.commit()

    with pytest.raises(OnlineQueueNewDomainError):
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    assert refreshed_entry.status == "waiting"
    assert refreshed_visit.status == "open"


# ─── Гварды стейт-машины визита ────────────────────────────────────────


def test_cancel_rejects_closed_visit(db_session, cancel_world):
    """Закрытый визит (день закрыт, EMR подписан) не отменяется через корзину:
    отказ из стейт-машины визита, состояние не изменено."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="closed")
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit, status="served"
    )

    with pytest.raises(OnlineQueueNewDomainError):
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    assert refreshed_visit.status == "closed"


def test_cancel_cascades_to_confirmed_visit_wizard_case(db_session, cancel_world):
    """Каноничный случай мастера: /registrar/cart создаёт визиты в статусе
    confirmed (сразу в очереди). Отмена записи переводит confirmed-визит в
    canceled и аннулирует pending-счёт."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="confirmed")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    invoice = _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.expire_all()

    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_visit.status == "canceled"
    assert refreshed_invoice.status == "cancelled"


def test_cancel_skips_already_canceled_visit(db_session, cancel_world):
    """Легаси-состояние «запись активна, визит уже отменён»: отмена записи
    успешна, повторная отмена визита не запускается (стейт-машина не даёт
    canceled → canceled), финансовый хвост отсутствует."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="canceled")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.expire_all()

    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    assert refreshed_entry.status == "cancelled"
    assert refreshed_visit.status == "canceled"


# ─── Идемпотентность и легаси-поведение ───────────────────────────────


def test_cancel_is_idempotent(db_session, cancel_world):
    """Повторная отмена уже отменённой записи — успешный no-op (двойной клик
    регистратора, параллельные вызовы трёх путей мастера)."""
    patient = cancel_world["patient"]
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=None, status="waiting"
    )
    service = OnlineQueueNewService(db_session)
    service.cancel_entry(entry_id=entry.id)
    service.cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    assert refreshed.status == "cancelled"


def test_cancel_entry_without_visit_keeps_legacy_behavior(db_session, cancel_world):
    """Запись без визита (online-запись до подтверждения) отменяется как
    раньше — каскад нечего каскадировать."""
    patient = cancel_world["patient"]
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=None, status="waiting"
    )

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    db_session.expire_all()
    refreshed = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    assert refreshed.status == "cancelled"


# ─── Codex R14 PR 3121: ремонт легаси-строк и владелец визита ─────────


def test_cancel_repairs_legacy_flip_with_open_visit_and_invoice(db_session, cancel_world):
    """R14 (P1): легаси-строка «canceled» от прежней реализации («тихий»
    флип только entry.status) с ОТКРЫТЫМ визитом и pending-счётом.
    Повторная отмена не просто возвращает запись — она дозавершает
    каскад: визит отменяется, счёт аннулируется, ссылка исчезает."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit,
        status="canceled",  # легаси-флип: визит и счёт НЕ тронуты
    )
    invoice = _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.expire_all()

    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "cancelled"
    assert refreshed_visit.status == "canceled"
    assert refreshed_invoice.status == "cancelled"
    assert (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
        .count()
        == 0
    )


def test_cancel_legacy_double_l_spelling_is_terminal_and_reconciles(db_session, cancel_world):
    """R14 (P1): легаси-написание «cancelled» (queue_svc/force majeure/
    batch) — терминальный статус, а НЕ 409-гард «уже в статусе …».
    Отмена идемпотентна и так же дозавершает каскад."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit,
        status="cancelled",  # легаси-писатели очереди
    )
    invoice = _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.expire_all()

    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "cancelled"
    assert refreshed_visit.status == "canceled"
    assert refreshed_invoice.status == "cancelled"


def test_cancel_rejects_foreign_visit_owner(db_session, cancel_world):
    """R14 (P2): легаси/битая строка с visit_id ЧУЖОГО пациента — отказ
    под блокировкой ДО любых мутаций (зеркало гарда владельца в
    full_update _online_entries.py). Состояние не изменено."""
    patient = cancel_world["patient"]
    foreign_patient = _create_patient(db_session)
    service = cancel_world["service"]
    foreign_visit = _create_visit(
        db_session, patient=foreign_patient, service=service, status="open"
    )
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=foreign_visit
    )
    invoice = _create_invoice(
        db_session, patient=foreign_patient, visit=foreign_visit, amount=500
    )

    with pytest.raises(OnlineQueueNewDomainError) as exc:
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    assert "не принадлежит пациенту записи" in getattr(exc.value, "detail", "")

    db_session.expire_all()
    refreshed_entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == foreign_visit.id).one()
    refreshed_invoice = (
        db_session.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).one()
    )
    assert refreshed_entry.status == "waiting"
    assert refreshed_visit.status == "open"
    assert refreshed_invoice.status == "pending"


def test_cancel_unknown_entry_raises_404(db_session):
    with pytest.raises(Exception) as exc:
        OnlineQueueNewService(db_session).cancel_entry(entry_id=999_999)
    assert getattr(exc.value, "detail", "") == "Запись очереди не найдена"


# ─── API-контракт эндпоинта ────────────────────────────────────────────


@pytest.fixture
def auth_headers(registrar_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {registrar_token}"}


def test_api_cancel_cascades_and_keeps_legacy_payload(
    db_session, client, auth_headers, cancel_world
):
    """POST /api/v1/online-queue/entries/{id}/cancel: 200 + легаси-payload
    (message/status) для фронта; согласованный каскад виден в БД."""
    from fastapi.testclient import TestClient  # noqa: F401

    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="confirmed")
    entry = _create_entry(db_session, queue=cancel_world["queue"], patient=patient, visit=visit)
    _create_invoice(db_session, patient=patient, visit=visit, amount=500)

    response = client.post(
        f"/api/v1/online-queue/entries/{entry.id}/cancel", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"

    db_session.expire_all()
    refreshed_visit = db_session.query(Visit).filter(Visit.id == visit.id).one()
    refreshed_entry = (
        db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    )
    assert refreshed_visit.status == "canceled"
    assert refreshed_entry.status == "cancelled"


def test_api_cancel_consumed_entry_returns_409(
    db_session, client, auth_headers, cancel_world
):
    """Потреблённая запись: 409 с явной причиной вместо тихого успеха."""
    patient = cancel_world["patient"]
    service = cancel_world["service"]
    visit = _create_visit(db_session, patient=patient, service=service, status="open")
    entry = _create_entry(
        db_session, queue=cancel_world["queue"], patient=patient, visit=visit, status="served"
    )

    response = client.post(
        f"/api/v1/online-queue/entries/{entry.id}/cancel", headers=auth_headers
    )
    assert response.status_code == 409
    assert "served" in response.json()["detail"]


def test_api_cancel_unknown_entry_returns_404(db_session, client, auth_headers):
    response = client.post(
        "/api/v1/online-queue/entries/999999/cancel", headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Запись очереди не найдена"
