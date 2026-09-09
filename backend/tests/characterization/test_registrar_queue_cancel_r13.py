"""Codex R13 PR 3121 — находки ревизии согласованной отмены записи.

Находки:
  - P1 :133 — гонка статуса визита: разблокированный пре-чек + FOR UPDATE
    внутри cancel_visit возвращали уже загруженную SQLAlchemy identity БЕЗ
    перечитывания колонок — визит, параллельно переведённый
    open → completed, всё ещё оценивался как open и перезаписывался в
    canceled. Фикс: визит читается под FOR UPDATE с populate_existing.
  - P1 :111 — batch /registrar/records/actions: отклонённый record оставлял
    staged-изменения в сессии, следующий успешный record закоммитил бы
    чужой каскад. Фикс: rollback в обработчиках отказов _run_single +
    финансовые гарды ВНУТРИ cancel_entry ДО staging.
  - P2 :51 — record-action cancel не передавал current_user/reason.
  - P2 :111 — легаси «активная запись + уже отменённый визит»: доля
    pending-счёта не сверялась.

Каждый сохраняющий кейс проверяет СОСТОЯНИЕ повторным чтением DB.
Данные синтетические; production DB не используется.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit
from app.services.online_queue_new_service import OnlineQueueNewService

TZ = ZoneInfo("Asia/Tashkent")


def _create_patient(db_session, *, suffix: str = "") -> Patient:
    patient = Patient(
        last_name=f"Отмена{suffix}",
        first_name="Тест",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone="+998900000888",
        created_at=datetime.now(TZ),
        is_deleted=False,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_doctor(db_session, *, unique: str) -> int:
    """Реальный Doctor (FK daily_queues.specialist_id → doctors) — нужен для
    durable-БД (postgres race-протокол); в SQLite-savepoint мире сходит и 4242."""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    user = User(
        username=f"r13_race_{unique}",
        email=f"r13_race_{unique}@test.local",
        full_name="R13 Race Doctor",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty="general", active=True, cabinet="401")
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor.id


def _create_queue(db_session, *, tag: str, specialist_id: int = 4242) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(), specialist_id=specialist_id, queue_tag=tag, active=True
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_visit(db_session, *, patient, status: str = "open") -> Visit:
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
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _create_entry(db_session, *, queue, patient, visit=None, status: str = "waiting") -> OnlineQueueEntry:
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
        total_amount=500,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _create_pending_invoice(db_session, *, patient, visit, amount: int) -> PaymentInvoice:
    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=Decimal(amount),
        currency="UZS",
        status="pending",
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal(amount))
    )
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


# ─── P2: легаси «визит уже отменён» — счёт всё равно сверяется ────


def test_cancel_releases_pending_invoice_for_legacy_canceled_visit(db_session):
    """Активная запись + УЖЕ отменённый визит + pending-счёт на долю визита:
    отмена записи обязана освободить долю счёта (счёт без позиций →
    cancelled). Раньше каскад пропускал сверку — пациент оставался
    выставленным."""
    patient = _create_patient(db_session, suffix="Легаси")
    queue = _create_queue(db_session, tag="laboratory_general")
    visit = _create_visit(db_session, patient=patient, status="canceled")
    entry = _create_entry(db_session, queue=queue, patient=patient, visit=visit)
    invoice = _create_pending_invoice(db_session, patient=patient, visit=visit, amount=500)

    result = OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)

    assert result.status == "canceled"
    db_session.expire_all()
    db_session.refresh(invoice)
    assert invoice.status == "cancelled", (
        "legacy canceled visit must still reconcile the pending invoice share"
    )
    assert Decimal(str(invoice.total_amount)) == 0


# ─── P1: гонка статуса — завершённый визит не перезаписывается ────


@pytest.mark.gate_d
def test_concurrent_visit_completion_is_seen_under_lock():
    """Runtime-протокол гонки (детерминированный, Gate D-стиль — два
    НЕЗАВИСИМЫХ соединения):
    1. сессия A загружает визит (identity map: status='open');
    2. сессия B параллельно переводит визит в completed и коммитит;
    3. cancel_entry в A обязан увидеть СВЕЖИЙ статус (409), а не перезаписать
       completed → canceled по устаревшей identity-map копии."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or "sqlite" in db_url:
        pytest.skip("cross-connection race requires a server DB (PostgreSQL)")

    engine = create_engine(db_url, pool_pre_ping=True)
    from app.db.base_class import Base
    Base.metadata.create_all(engine)  # идемпотентно (checkfirst), как Gate D
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    setup = factory()
    unique = uuid4().hex[:6]
    doctor_id = _create_doctor(setup, unique=unique)
    patient = _create_patient(setup, suffix=f"Гонка{unique}")
    queue = _create_queue(setup, tag=f"laboratory_general_race_{unique}", specialist_id=doctor_id)
    visit = _create_visit(setup, patient=patient)
    entry = _create_entry(setup, queue=queue, patient=patient, visit=visit)
    visit_id, entry_id = visit.id, entry.id
    setup.commit()
    setup.close()

    # Шаг 1: сессия A держит визит в identity map (не-expired, статус open)
    session_a = factory()
    cached = session_a.query(Visit).filter(Visit.id == visit_id).first()
    assert cached.status == "open"

    # Шаг 2: независимая сессия B завершает визит и коммитит
    session_b = factory()
    try:
        row_b = session_b.query(Visit).filter(Visit.id == visit_id).first()
        row_b.status = "completed"
        session_b.commit()
    finally:
        session_b.close()

    # Шаг 3: отмена записи обязана отказать на свежем чтении
    try:
        with pytest.raises(Exception) as exc_info:
            OnlineQueueNewService(session_a).cancel_entry(entry_id=entry_id)
    finally:
        session_a.rollback()
        session_a.close()

    verify = factory()
    try:
        v = verify.query(Visit).filter(Visit.id == visit_id).first()
        e = verify.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        assert v.status == "completed", (
            "a concurrently completed visit must never be overwritten to canceled"
        )
        assert e.status == "waiting"
        assert exc_info.value.status_code == 409
    finally:
        verify.close()
        engine.dispose()


def test_cancel_rejects_completed_visit_under_lifecycle_lock(db_session):
    """Регрессия стейт-машины: visit 'completed' → отмена записи 409, визит
    остаётся completed; cancel_entry читает визит под FOR UPDATE с
    populate_existing (source-контракт)."""
    import inspect

    patient = _create_patient(db_session, suffix="Комплит")
    queue = _create_queue(db_session, tag="laboratory_general_lock")
    visit = _create_visit(db_session, patient=patient, status="completed")
    entry = _create_entry(db_session, queue=queue, patient=patient, visit=visit)

    source = inspect.getsource(OnlineQueueNewService.cancel_entry)
    assert "with_for_update" in source and "populate_existing" in source, (
        "the visit must be read under a row lock with forced re-population"
    )

    with pytest.raises(Exception) as exc_info:
        OnlineQueueNewService(db_session).cancel_entry(entry_id=entry.id)
    db_session.rollback()
    db_session.expire_all()
    db_session.refresh(visit)
    db_session.refresh(entry)
    assert visit.status == "completed"
    assert entry.status == "waiting"
    assert exc_info.value.status_code == 409


# ─── P2: actor/reason через record-action поверхность ────


def test_record_action_cancel_forwards_actor_and_reason(
    client, db_session, registrar_auth_headers, registrar_user
):
    """P2 :51: cancel через /registrar/records/actions передаёт
    current_user и reason — причина попадает в notes визита."""
    patient = _create_patient(db_session, suffix="Актёр")
    queue = _create_queue(db_session, tag="laboratory_general_actor")
    visit = _create_visit(db_session, patient=patient)
    entry = _create_entry(db_session, queue=queue, patient=patient, visit=visit)

    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "cancel",
            "records": [{"record_kind": "online_queue", "record_id": entry.id}],
            "reason": "пациент передумал",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success_count"] == 1, body

    db_session.expire_all()
    db_session.refresh(visit)
    db_session.refresh(entry)
    assert entry.status == "canceled"
    assert visit.status == "canceled"
    assert "Canceled: пациент передумал" in (visit.notes or ""), (
        "the record-action path must forward the reason to the visit notes"
    )


# ─── P1: batch-изоляция — отклонённый record не утекает ────


def test_batch_cancel_rejected_record_does_not_leak_staged_cascade(
    client, db_session, registrar_auth_headers
):
    """Batch из двух записей: первая отклоняется (оплаченный Payment),
    вторая успешна. Итог: визит ПЕРВОЙ записи остаётся open — раньше он
    staged как canceled ДО финансовых гардов и закоммитился бы вместе со
    второй записью."""
    patient = _create_patient(db_session, suffix="Батч")
    queue = _create_queue(db_session, tag="laboratory_general_batch")
    paid_visit = _create_visit(db_session, patient=patient)
    paid_entry = _create_entry(db_session, queue=queue, patient=patient, visit=paid_visit)
    db_session.add(
        Payment(visit_id=paid_visit.id, amount=Decimal("500"), status="paid", method="cash")
    )
    ok_visit = _create_visit(db_session, patient=patient)
    ok_entry = _create_entry(db_session, queue=queue, patient=patient, visit=ok_visit)
    db_session.commit()

    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "cancel",
            "records": [
                {"record_kind": "online_queue", "record_id": paid_entry.id},
                {"record_kind": "online_queue", "record_id": ok_entry.id},
            ],
            "reason": "batch",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["failed_count"] == 1
    assert body["success_count"] == 1

    db_session.expire_all()
    db_session.refresh(paid_visit)
    db_session.refresh(paid_entry)
    db_session.refresh(ok_visit)
    db_session.refresh(ok_entry)
    assert paid_visit.status == "open", (
        "the REJECTED record's visit must stay open (staged cascade leaked into the next commit)"
    )
    assert paid_entry.status == "waiting"
    assert ok_visit.status == "canceled"
    assert ok_entry.status == "canceled"
