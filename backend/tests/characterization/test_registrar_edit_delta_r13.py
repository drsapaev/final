"""Codex R13 PR 3118 — находки ревизии LIFO-представления и агрегации.

Находки:
  - P1 :1297 — matcher слоёв считал ОТМЕНЁННУЮ строку (cancelled=true от
    per-service cancellation-эндпоинта) активным слоем: повторное добавление
    той же услуги квотировалось и применялось как no-op, рост мог вернуть
    отменённые единицы в visit-представление. Фикс: отменённые строки
    исключаются из количеств и маршрутизации.
  - P1 :772 — легаси full-update слой хранит price как СУММУ строки
    ({quantity: 3, price: 300}): LIFO-списание брало записанную цену за
    единицу (100) корректно, но строка оставалась с price=300 — зеркало
    _sync_visit_service_rows читало остаток qty=1 как цену ЗА ЕДИНИЦУ 300:
    VisitService 300 при entry/invoice 100. Фикс: потреблённый слой
    ренормализуется до зеркала (unit_price каноничен, price сохраняет
    конвенцию строки).
  - Квота edit_delta зеркалит оба поведения (billable = ПОЛНОЕ количество
    при отменённом слое; amount снижения = точная сумма потреблённых слоёв).

Каждый сохраняющий кейс проверяет СОСТОЯНИЕ повторным чтением DB.
Данные синтетические; production DB не используется.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token

TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R13 {code}",
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


def _create_queue(db_session, *, specialist_id: int, queue_tag: str) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(), specialist_id=specialist_id, queue_tag=queue_tag, active=True
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_entry(
    db_session,
    *,
    queue: DailyQueue,
    patient,
    services_payload: list[dict],
    total_amount: int,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="desk",
        status="waiting",
        queue_time=datetime.now(TZ).replace(microsecond=0),
        services=services_payload,
        service_codes=[p.get("code") for p in services_payload if p.get("code")],
        total_amount=total_amount,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _post_edit_delta(
    client, registrar_auth_headers, *, patient_id, services, entry_ids
):
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": patient_id,
            "target_date": date.today().isoformat(),
            "payment_method": "cash",
            "discount_mode": "none",
            "all_free": False,
            "services": services,
            "existing_queue_entry_ids": entry_ids,
        },
    )


def _payload(db_session, entry_id: int) -> list[dict]:
    db_session.expire_all()
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).one()
    raw = entry.services
    return json.loads(raw) if isinstance(raw, str) else list(raw)


# ===================== P1: отменённые строки — не активные слои =====================


@pytest.mark.integration
@pytest.mark.queue
def test_readd_after_per_service_cancel_is_full_growth(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Услуга отменена per-service cancellation (строка осталась с
    cancelled=true, total пересчитан до 0). Повторное добавление той же
    услуги — ПОЛНЫЙ рост (новый активный слой, total = цена), а не no-op."""
    service = _create_service(db_session, code="R13-CXL-1", price=25000)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general")
    cancelled_row = {
        "id": service.id,
        "service_id": service.id,
        "code": service.service_code,
        "name": service.name,
        "quantity": 1,
        "price": 25000,
        "unit_price": 25000,
        "cancelled": True,
        "cancel_reason": "отменено регистратором",
    }
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, services_payload=[cancelled_row],
        total_amount=0,
    )

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )
    assert response.status_code == 200, response.text

    rows = [r for r in _payload(db_session, entry.id) if r.get("service_id") == service.id]
    active = [r for r in rows if not r.get("cancelled")]
    assert len(active) == 1, "a NEW active layer must be added on top of the cancelled one"
    assert active[0]["quantity"] == 1
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 25000, (
        "re-adding a cancelled service must bill the FULL quantity (no-op was the defect)"
    )


@pytest.mark.integration
@pytest.mark.queue
def test_quote_billable_ignores_cancelled_layer(
    client, db_session, registrar_auth_headers, admin_user, test_patient, test_doctor
):
    """Квота edit_delta зеркалит команду: отменённый слой НЕ уменьшает
    биллейбл-количество — квота подтверждает ПОЛНОЕ количество."""
    service = _create_service(db_session, code="R13-CXL-Q", price=25000)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general")
    cancelled_row = {
        "id": service.id,
        "service_id": service.id,
        "code": service.service_code,
        "name": service.name,
        "quantity": 2,
        "price": 50000,
        "unit_price": 25000,
        "cancelled": True,
    }
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, services_payload=[cancelled_row],
        total_amount=0,
    )

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers={"Authorization": f"Bearer {mint_access_token(admin_user)}"},
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "preferred_entry_ids": [entry.id],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["quantity"] == 1, (
        "cancelled layers must not reduce the billable quantity (old code quoted 0)"
    )
    assert float(body["total_amount"]) == 25000


# ===================== P1: ренормализация легаси line-total слоя =====================


@pytest.mark.integration
@pytest.mark.queue
def test_partial_decrease_renormalizes_legacy_line_total_layer(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Легаси full-update слой {quantity: 3, price: 300} (price = СУММА
    строки, unit_price отсутствует): снижение до 1 списывает 200
    (300/3 = 100 за единицу), но строка оставалась с price=300 — зеркало
    читало остаток как цену ЗА ЕДИНИЦУ 300. Фикс: слой ренормализуется
    (unit_price=100, price=100 — line-total остатка), VisitService ==
    entry.total_amount == invoice."""
    service = _create_service(db_session, code="R13-LTOT-1", price=30000)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general")
    legacy_row = {
        "id": service.id,
        "service_id": service.id,
        "code": service.service_code,
        "name": service.name,
        "quantity": 3,
        "price": 90000,  # line-total: 3 × 30000; НЕТ unit_price
        "cancelled": False,
    }
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time=None,
        department="laboratory",
        discount_mode="none",
        approval_status="approved",
        status="open",
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
            qty=3,
            price=Decimal("90000"),
            currency="UZS",
        )
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, services_payload=[legacy_row],
        total_amount=90000,
    )
    entry.visit_id = visit.id
    db_session.commit()
    db_session.refresh(entry)

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )
    assert response.status_code == 200, response.text

    rows = [r for r in _payload(db_session, entry.id) if r.get("service_id") == service.id]
    assert len(rows) == 1
    assert rows[0]["quantity"] == 1
    assert rows[0]["unit_price"] == 30000, "recorded unit charge must be explicit after consumption"
    assert rows[0]["price"] == 30000, "line-total convention: remaining × unit charge"
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 30000

    db_session.expire_all()
    vs = (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
        .one()
    )
    assert vs.qty == 1
    assert float(vs.price) == 30000, (
        "VisitService must mirror the renormalized layer, not the stale line total"
    )
    assert entry.total_amount == int(Decimal(str(vs.price)) * vs.qty)
