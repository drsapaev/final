"""Потерянные находки codex R7 #3095 (треды 3951581794/3951581800).

Находки:
  - P1 (_cart.py:637): команды получали ГОЛЫЙ булев флаг all_free, а квота
    резолвила эффективный режим из ПАРЫ (all_free, discount_mode).
    Агрегированная запись мастера несёт discount_mode="all_free" без булева
    флага (wizard инициализирует all_free=False) → квота подтверждала
    бесплатную корзину, а RegistrarEditDeltaService и full-update команда
    выставляли каталожные цены. Ревалидация токена повторяла логику квоты
    и пропускала расхождение. Фикс: команды получают РЕЗОЛВНУТЫЙ режим из
    того же SSOT (_resolve_effective_discount_mode), токен биндит
    резолвнутый режим.
  - P2 (_cart.py:654): дублирующие строки одной услуги в edit-delta квоте:
    каждая строка читала одну и ту же ДО-командную позицию, тогда как
    команда обрабатывает строки последовательно (вторая видит позицию,
    созданную первой) → токен покрывал две единицы, команда выставляла
    одну. Фикс: квота накапливает уже подтверждённые единицы внутри
    прохода — точное зеркало последовательного состояния команды.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.online_queue import OnlineQueueEntry
from app.models.service import Service
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _r7_service(db: Session, *, code: str, price: Decimal) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R7 {code}",
        price=price,
        active=True,
        requires_doctor=False,
        queue_tag="r7_lost_tag",
        department_key="r7_lost_tag",
        doctor_id=None,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


# ===================== P1: All Free строковый режим =====================


def test_edit_delta_all_free_string_mode_bills_free(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    admin_user,
    test_patient,
    test_doctor,
):
    """Edit-delta сохранение с discount_mode="all_free" и all_free=False
    обязано выставить 0 — тот же резолв, что подтвердила квота."""
    service = _r7_service(db_session, code="R7-AF-ED", price=Decimal("25000"))

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                }
            ],
            "discount_mode": "all_free",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert quoted.status_code == 200, quoted.text
    token = quoted.json()["quote_token"]
    assert token

    response = client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "payment_method": "cash",
            "discount_mode": "all_free",
            "all_free": False,
            "services": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                }
            ],
            "existing_queue_entry_ids": [],
            "quote_token": token,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert Decimal(str(body["total_amount"])) == 0, (
        "aggregated record carries discount_mode='all_free' without the "
        "boolean flag: the command must bill ZERO, not catalog prices"
    )
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.queue_time
            >= datetime.now(ZoneInfo("Asia/Tashkent")).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        )
        .order_by(OnlineQueueEntry.id.desc())
        .first()
    )
    assert entry is not None
    assert int(entry.total_amount or 0) == 0


def test_full_update_all_free_string_mode_bills_free(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    admin_user,
    test_daily_queue,
    test_patient,
    test_doctor,
):
    """Full-update сохранение с discount_mode="all_free" и all_free=False
    обязано выставить 0 — команды нормализуют режим как квота."""
    from app.models.online_queue import DailyQueue

    service = _r7_service(db_session, code="R7-AF-FU", price=Decimal("25000"))
    # Целевая очередь для queue_tag услуги существует → путь авто-создания
    # очереди (и его требования к врачу) не задействуется.
    db_session.add(
        DailyQueue(
            day=test_daily_queue.day,
            specialist_id=test_doctor.id,
            queue_tag="r7_lost_tag",
            active=True,
        )
    )
    db_session.commit()
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=21,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
        services=[],
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "all_free",
            "all_free": False,
            "pricing_mode": "full_update",
        },
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    token = body["quote_token"]
    assert token
    assert float(body["total_amount"]) == 0, (
        "the quote already prices the string all_free mode as free"
    )

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
            },
            "visit_type": "paid",
            "discount_mode": "all_free",
            "services": [{"service_id": service.id, "quantity": 1}],
            "all_free": False,
            "quote_token": token,
        },
    )
    assert response.status_code == 200, response.text

    created = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.id != entry.id,
        )
        .all()
    )
    assert len(created) == 1
    assert int(created[0].total_amount or 0) == 0, (
        "the full-update command must normalize discount_mode='all_free' "
        "the same way the quote does: total 0, not catalog 25000"
    )


# ===================== P2: дубликаты строк edit-delta =====================


def test_edit_delta_quote_duplicate_rows_cover_sequentially(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    admin_user,
    test_patient,
    test_doctor,
):
    """Квота edit_delta накапливает уже подтверждённые единицы внутри
    прохода: [X×1, X×1] без существующей позиции == одна биллинговая
    единица (точное зеркало последовательного состояния команды)."""
    service = _r7_service(db_session, code="R7-DUP-ED", price=Decimal("25000"))

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                },
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                },
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    assert float(body["total_amount"]) == 25000, (
        "the command processes duplicate rows sequentially: the second row "
        "sees the position created by the first and bills ZERO more — the "
        "quote must cover exactly one unit, not two"
    )
    token = body["quote_token"]

    saved = client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "payment_method": "cash",
            "discount_mode": "none",
            "all_free": False,
            "services": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                },
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                },
            ],
            "existing_queue_entry_ids": [],
            "quote_token": token,
        },
    )
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert saved_body["success"] is True
    assert Decimal(str(saved_body["total_amount"])) == Decimal("25000"), (
        "token parity: the save bills exactly what the quote confirmed"
    )


def test_edit_delta_quote_duplicate_rows_different_specialists_cover_by_service(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    admin_user,
    test_patient,
    test_doctor,
):
    """Codex R15 #3095: покрытие по УСЛУГЕ, без специалиста в ключе. Команда
    маршрутизирует строку по (patient, day, queue_tag), а количество внутри
    записи суммируется по сервису независимо от врача (_find_service_payload):
    дубликаты одного сервиса с РАЗНЫМИ врачами покрывают друг друга так же,
    как дубликаты с одним врачом."""
    service = _r7_service(db_session, code="R15-DUP-SPEC", price=Decimal("25000"))
    # Дефолтный врач услуги: строка со specialist_id=None проходит R11-гейт
    # («specialist_id is required») через service.doctor_id, как и в команде.
    service.doctor_id = test_doctor.id
    db_session.commit()

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": None,
                },
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                },
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    assert float(body["total_amount"]) == 25000, (
        "coverage is keyed by the routed entry's service identity: a second "
        "duplicate row with a different specialist must be priced as the "
        "sequential no-op it becomes in the command, not as a second unit"
    )
