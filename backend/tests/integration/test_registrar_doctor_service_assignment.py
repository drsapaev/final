"""
Registrar doctor-services plan (Workstream A): exact service-to-doctor
assignment and the shared per-doctor queue.

Contract under test (Task 1 / Task 4):

- explicit assignment: a service pinned to a concrete doctor
  (``Service.doctor_id``) is bookable ONLY with that exact doctor on
  every registrar write surface that calls the canonical guard
  (``assert_doctor_eligible_for_service``): POST /registrar/cart (save),
  the edit-delta quote path, and the resource-routed write surfaces.
  Specialty eligibility stays in force for the pinned doctor;
- one doctor queue: services of the same doctor in one booking share
  the doctor's SINGLE queue of the day — one queue entry, one number —
  even when their queue_tags/categories differ (a dermatology consult
  «dermatology» + a cryodestruction procedure «procedures»). Each
  service's own code/name stays in the entry payload for reporting;
- ``get_or_create_daily_queue`` converges tag spellings for one doctor
  (cardio vs cardiology) instead of forking parallel queues;
- the edit-delta strict lookup finds the merged doctor entry by its
  read-model identity even when the service's queue_tag differs from
  the queue's tag (previously a false «entry is no longer active» 400).

Rejected carts leave no partial state (atomicity pin reused from
RQ-05.a: zero visits/invoices/queue entries).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.services.queue_service import queue_service
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _cart_payload(*, patient_id: int, visits: list[dict]) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": visits,
    }


def _visit(*, doctor_id: int | None, services: list[dict]) -> dict:
    return {
        "doctor_id": doctor_id,
        "visit_date": date.today().isoformat(),
        "department": "general",
        "services": services,
    }


def _make_service(
    db_session: Session,
    *,
    code: str,
    name: str,
    queue_tag: str,
    department_key: str | None = None,
    requires_doctor: bool = True,
    is_consultation: bool = False,
    doctor_id: int | None = None,
) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=name,
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=requires_doctor,
        is_consultation=is_consultation,
        department_key=department_key,
        queue_tag=queue_tag,
        doctor_id=doctor_id,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _make_doctor(db_session: Session, *, specialty: str) -> Doctor:
    user = User(
        username=f"asg_doctor_{uuid4().hex[:12]}",
        full_name=f"Тестовый Врач {uuid4().hex[:4]}",
        hashed_password="unused-test-hash",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _entry_services_payload(entry: OnlineQueueEntry) -> list[dict]:
    parsed = entry.services
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    return parsed if isinstance(parsed, list) else []


def _doctor_queue_entries(
    db_session: Session, doctor_id: int
) -> tuple[list[DailyQueue], list[OnlineQueueEntry]]:
    queues = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.specialist_id == doctor_id,
            DailyQueue.active.is_(True),
        )
        .all()
    )
    entries = (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.specialist_id == doctor_id,
        )
        .all()
    )
    return queues, entries


# ── Task 1: exact service-to-doctor assignment ────────────────────────────


def test_pinned_service_rejects_other_same_specialty_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Явное назначение: услуга с Service.doctor_id=X при submit врача Y
    (той же специальности) → 409, состояние не меняется."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    other_cardiologist = _make_doctor(db_session, specialty="cardiology")
    service = _make_service(
        db_session,
        code="ASG-PIN-K",
        name="ЭхоКГ закреплённая",
        queue_tag="cardio",
        department_key="cardiology",
        requires_doctor=True,
        doctor_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=other_cardiologist.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 409, response.text
    assert "назначена другому врачу" in response.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )
    assert _doctor_queue_entries(db_session, pinned_to.id)[1] == []
    assert _doctor_queue_entries(db_session, other_cardiologist.id)[1] == []


def test_pinned_service_books_with_assigned_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Контроль: закреплённая услуга + её врач → 200, визит и очередь врача."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_service(
        db_session,
        code="ASG-PIN-OK",
        name="ЭхоКГ закреплённая ок",
        queue_tag="cardio",
        department_key="cardiology",
        requires_doctor=True,
        doctor_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=pinned_to.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 200, response.text
    visit = db_session.query(Visit).get(response.json()["visit_ids"][0])
    assert visit.doctor_id == pinned_to.id
    queues, entries = _doctor_queue_entries(db_session, pinned_to.id)
    assert len(queues) == 1
    assert len(entries) == 1


def test_pinned_service_specialty_still_enforced_for_own_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Назначение не расширяет специальность: пин к стоматологу у кардио-
    услуги → 400 несовпадения специальности (fail-closed, не тихая запись)."""
    dentist = _make_doctor(db_session, specialty="dentistry")
    service = _make_service(
        db_session,
        code="ASG-PIN-SPEC",
        name="Кардио-услуга у стоматолога",
        queue_tag="cardio",
        department_key="cardiology",
        requires_doctor=True,
        doctor_id=dentist.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=dentist.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 400, response.text
    assert "не подходит для услуги" in response.json()["detail"]


def test_registrar_catalog_emits_doctor_id(
    client: TestClient, db_session: Session, admin_user
):
    """Read-side контракт: каталог регистратуры отдаёт Service.doctor_id,
    чтобы карточки врача фильтровались по точному назначению."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_service(
        db_session,
        code="ASG-CAT-PIN",
        name="Каталожная закреплённая",
        queue_tag="cardio",
        department_key="cardiology",
        requires_doctor=True,
        doctor_id=pinned_to.id,
    )

    response = client.get(
        "/api/v1/registrar/services", headers=_auth_headers(admin_user)
    )

    assert response.status_code == 200, response.text
    rows = [
        row
        for group in response.json()["services_by_group"].values()
        for row in group
        if row["id"] == service.id
    ]
    assert len(rows) == 1
    assert rows[0]["doctor_id"] == pinned_to.id


# ── Task 4: one doctor queue for services with different tags ─────────────


def test_same_doctor_different_tags_share_one_queue_entry(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Одна очередь врача: консультация (тег dermatology) + процедура
    (тег procedures) одного дерматолога в одном бронировании → ОДНА
    doctor-owned очередь, ОДНА запись, ОДИН номер, обе услуги в payload."""
    dermatologist = _make_doctor(db_session, specialty="derma")
    consult = _make_service(
        db_session,
        code="ASG-D01",
        name="Консультация дерматолога",
        queue_tag="dermatology",
        department_key="dermatology",
        requires_doctor=True,
        is_consultation=True,
    )
    procedure = _make_service(
        db_session,
        code="ASG-D06",
        name="Криодеструкция бородавок",
        queue_tag="procedures",
        department_key="dermatology",
        requires_doctor=True,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=dermatologist.id,
                    services=[
                        {"service_id": consult.id, "quantity": 1},
                        {"service_id": procedure.id, "quantity": 1},
                    ],
                )
            ],
        ),
    )

    assert response.status_code == 200, response.text
    queues, entries = _doctor_queue_entries(db_session, dermatologist.id)
    assert (
        len(queues) == 1
    ), "услуги одного врача не должны раскалывать его очередь по тегам"
    assert (
        len(entries) == 1
    ), "одно бронирование врача — одна запись очереди, один номер"
    entry = entries[0]
    assert entry.number is not None
    payload_codes = {str(row.get("code")) for row in _entry_services_payload(entry)}
    assert payload_codes == {
        "ASG-D01",
        "ASG-D06",
    }, "собственные коды услуг сохраняются в payload записи врача"
    assert (
        queues[0].queue_tag == "dermatology"
    ), "routing-тег записи — тег консультации (причина визита)"


def test_get_or_create_daily_queue_converges_doctor_tag_spellings(
    db_session: Session,
):
    """Канонический резолвер: разное написание тега одного врача/дня не
    форкает вторую очередь — переиспользуется существующая очередь врача."""
    doctor = _make_doctor(db_session, specialty="cardiology")

    first = queue_service.get_or_create_daily_queue(
        db_session, day=date.today(), specialist_id=doctor.id, queue_tag="cardio"
    )
    second = queue_service.get_or_create_daily_queue(
        db_session, day=date.today(), specialist_id=doctor.id, queue_tag="cardiology"
    )

    assert first.id == second.id
    assert (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.specialist_id == doctor.id,
        )
        .count()
        == 1
    )


def test_edit_delta_strict_lookup_finds_merged_entry_across_tags(
    db_session: Session, test_patient
):
    """Единая врачебная запись + edit-delta: строгий lookup по
    read-model идентичности находит живую запись врача, даже когда тег
    услуги (procedures) не совпадает с тегом очереди (dermatology)."""
    dermatologist = _make_doctor(db_session, specialty="derma")
    consult = _make_service(
        db_session,
        code="ASG-EQ-D01",
        name="Консультация дерматолога EQ",
        queue_tag="dermatology",
        department_key="dermatology",
        requires_doctor=True,
        is_consultation=True,
    )
    procedure = _make_service(
        db_session,
        code="ASG-EQ-D06",
        name="Криодеструкция EQ",
        queue_tag="procedures",
        department_key="dermatology",
        requires_doctor=True,
    )
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=dermatologist.id,
        visit_date=date.today(),
        status="confirmed",
    )
    db_session.add(visit)
    db_session.flush()
    from app.models.visit import VisitService

    for service, qty in ((consult, 1), (procedure, 1)):
        db_session.add(
            VisitService(
                visit_id=visit.id,
                service_id=service.id,
                code=service.service_code,
                name=service.name,
                qty=qty,
                price=100000.0,
            )
        )
    db_session.commit()

    service_obj = RegistrarEditDeltaService(db_session)
    # Канонический wizard-seam: единая запись врача создаётся тем же
    # контрактом, что и при сохранении корзины.
    from app.services.registrar_wizard_queue_assignment_service import (
        RegistrarWizardQueueAssignmentService,
    )

    wizard_seam = RegistrarWizardQueueAssignmentService(db_session)
    wizard_seam.assign_same_day_queue_numbers(
        [visit], target_day=date.today(), source="test"
    )

    queues, entries = _doctor_queue_entries(db_session, dermatologist.id)
    assert len(entries) == 1
    merged_entry = entries[0]

    found = service_obj._find_active_entry(
        patient_id=test_patient.id,
        queue_tag=procedure.queue_tag,
        target_date=date.today(),
        preferred_entry_ids={merged_entry.id},
        specialist_id=None,
        strict_entry_id=merged_entry.id,
    )
    assert found is not None and found.id == merged_entry.id


def test_edit_delta_quote_rejects_pinned_service_for_other_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Edit-delta квота: добавление закреплённой услуги (Service.doctor_id=X)
    к другому врачу → 409 того же контракта, что и сохранение корзины."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    other_cardiologist = _make_doctor(db_session, specialty="cardiology")
    service = _make_service(
        db_session,
        code="ASG-EQ-PIN",
        name="ЭхоКГ закреплённая квота",
        queue_tag="cardio",
        department_key="cardiology",
        requires_doctor=True,
        doctor_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": other_cardiologist.id,
                }
            ],
            "discount_mode": "none",
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 409, response.text
    assert "назначена другому врачу" in response.json()["detail"]


# ── PR #3511 review P1 (round 5): pin WITHOUT catalog flags ────────────────
#
# The admin catalog saves ``Service.doctor_id`` and ``requires_doctor``/
# ``is_consultation`` INDEPENDENTLY, so a service can arrive pinned with
# BOTH flags unset. Every historical gate keyed its early exit on the raw
# flags and the pin was silently bypassed: the cart pre-filter dropped the
# service before the guard, the guard returned before the exact-doctor
# check, the QR resolver/validation loop skipped the row, and the catalog
# answered ``doctor_selection_required=false`` — so the master wizard
# offered the service to every doctor (or doctorless) and the server
# accepted it. The pins below restore the exact-doctor contract for
# ``doctor_id задан, requires_doctor=false``:
#
# - doctor-queue tag: the service is offered ONLY on the assigned
#   doctor's card (catalog decision) and booking to another doctor is
#   rejected with the same 409 on every write surface;
# - resource-routed tag: queue ownership wins — the surface stays
#   resource/doctorless (no read/write drift) and the pin is surfaced to
#   the ADMIN readiness as a configuration error instead of being
#   enforced against the resource axis.


def _make_pinned_unflagged_service(
    db_session: Session,
    *,
    code: str,
    name: str,
    pinned_to_id: int,
    queue_tag: str = "cardio",
    department_key: str = "cardiology",
) -> Service:
    return _make_service(
        db_session,
        code=code,
        name=name,
        queue_tag=queue_tag,
        department_key=department_key,
        requires_doctor=False,
        is_consultation=False,
        doctor_id=pinned_to_id,
    )


def test_unflagged_pinned_service_rejects_other_doctor_on_cart_save(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """P1 (мастер, серверная запись): услуга с Service.doctor_id=X и
    requires_doctor=false при визите к врачу Y → 409 «назначена другому
    врачу», частичного состояния нет."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    other_cardiologist = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-K",
        name="ЭхоКГ закреплённая без флага",
        pinned_to_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=other_cardiologist.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 409, response.text
    assert "назначена другому врачу" in response.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )
    assert _doctor_queue_entries(db_session, pinned_to.id)[1] == []
    assert _doctor_queue_entries(db_session, other_cardiologist.id)[1] == []


def test_unflagged_pinned_service_rejects_doctorless_visit(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Закреплённая услуга без визита врача → 400 «требует выбора врача»
    (пин обязан выполняться, запись «без кого попало» недоступна)."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-ND",
        name="ЭхоКГ закреплённая без врача",
        pinned_to_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=None,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 400, response.text
    assert "требует выбора врача" in response.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )


def test_unflagged_pinned_service_books_with_assigned_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Контроль: закреплённая безфлажковая услуга + её врач → 200, единая
    запись в ОЧЕРЕДИ назначенного врача (пин не ломает happy path)."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-OK",
        name="ЭхоКГ закреплённая без флага ок",
        pinned_to_id=pinned_to.id,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=pinned_to.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )

    assert response.status_code == 200, response.text
    visit = db_session.query(Visit).get(response.json()["visit_ids"][0])
    assert visit.doctor_id == pinned_to.id
    queues, entries = _doctor_queue_entries(db_session, pinned_to.id)
    assert len(queues) == 1
    assert len(entries) == 1
    assert queues[0].queue_resource_id is None


def test_registrar_catalog_requires_doctor_selection_for_unflagged_pin(
    client: TestClient, db_session: Session, admin_user
):
    """Мастер-карточки (серверное решение каталога): закреплённая услуга
    без флагов на врачебном теге → doctor_selection_required=true и
    doctor_booking_available=true — карточки врачей показываются, фильтр
    wizardUtils.pin оставляет только назначенного врача."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-CAT",
        name="Каталожная закреплённая без флага",
        pinned_to_id=pinned_to.id,
    )

    response = client.get(
        "/api/v1/registrar/services", headers=_auth_headers(admin_user)
    )

    assert response.status_code == 200, response.text
    rows = [
        row
        for group in response.json()["services_by_group"].values()
        for row in group
        if row["id"] == service.id
    ]
    assert len(rows) == 1
    assert rows[0]["doctor_id"] == pinned_to.id
    assert rows[0]["doctor_selection_required"] is True
    assert rows[0]["doctor_booking_available"] is True


def test_registrar_catalog_keeps_resource_surface_for_pin_on_resource_tag(
    client: TestClient, db_session: Session, admin_user
):
    """Пин на теге АКТИВНОЙ ресурсной очереди: владелец очереди важнее —
    каталог держит ресурсную поверхность (doctor_selection_required=false,
    doctor_booking_available=false), закрепление видит админ-readiness,
    read/write дрейфа нет (сервер не предлагает то, что отвергнет)."""
    from app.models.online_queue import QueueResource

    pinned_to = _make_doctor(db_session, specialty="cardiology")
    suffix = uuid4().hex[:8]
    resource_tag = f"p1f_res_{suffix}"
    db_session.add(
        QueueResource(
            code=f"p1f_{suffix}",
            queue_tag=resource_tag,
            display_name="Тестовый ресурс P1F",
            active=True,
        )
    )
    db_session.commit()
    service = _make_pinned_unflagged_service(
        db_session,
        code=f"ASG-P1F-R_{suffix}".upper(),
        name=f"Закреплённая на ресурсном теге {suffix}",
        pinned_to_id=pinned_to.id,
        queue_tag=resource_tag,
    )

    response = client.get(
        "/api/v1/registrar/services", headers=_auth_headers(admin_user)
    )

    assert response.status_code == 200, response.text
    rows = [
        row
        for group in response.json()["services_by_group"].values()
        for row in group
        if row["id"] == service.id
    ]
    assert len(rows) == 1
    assert rows[0]["doctor_selection_required"] is False
    assert rows[0]["doctor_booking_available"] is False
    assert rows[0]["doctor_id"] == pinned_to.id


def test_unflagged_pin_on_resource_tag_cart_save_books_resource_queue(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """PR #3511 merge-gate e2e (owner verdict P1#1): write-нога cart-save
    для НОВОГО входа «unflagged pin на ресурсном теге».

    Read-нога запинена соседним
    ``test_registrar_catalog_keeps_resource_surface_for_pin_on_resource_tag``
    (doctor_selection_required=false, doctor_booking_available=false);
    флагованный вариант — ``test_k10_resource_service_books_without_doctor_
    into_resource_queue`` / ``..._with_doctor_fails_closed`` в
    test_registrar_resource_service_classification.py. Здесь — недостающее
    звено: пин (``Service.doctor_id``) без ``requires_doctor``/
    ``is_consultation`` на теге АКТИВНОГО ресурса проходит cart-save
    тем же контрактом ownership-wins:

    - без врача → 200, запись в ресурсной очереди (пин декоративен:
      specialist нет, вилки докторской очереди нет);
    - с врачом — даже с САМИМ закреплённым врачом — 409 «ресурсная»
      (fail-closed), частичного состояния нет. Второй пациент изолирует
      RED-подпись от дубль-клейм-гварда: до round-5 ранний выход гварда
      по сырым флагам обходил пин целиком и корзина принималась с любым
      врачом — воспроизводится именно как «success с декоративным
      врачом», а не как отказ по чужой причине.
    """
    from app.models.online_queue import QueueResource

    pinned_to = _make_doctor(db_session, specialty="cardiology")
    suffix = uuid4().hex[:8]
    resource_tag = f"asg_pin_res_{suffix}"
    resource = QueueResource(
        code=f"asg_pin_{suffix}",
        queue_tag=resource_tag,
        display_name="Тестовый ресурс пина",
        active=True,
    )
    db_session.add(resource)
    db_session.commit()
    service = _make_pinned_unflagged_service(
        db_session,
        code=f"ASG-P1F-CRT_{suffix}".upper(),
        name=f"Закреплённая на ресурсном теге запись {suffix}",
        pinned_to_id=pinned_to.id,
        queue_tag=resource_tag,
    )

    booked = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(
                    doctor_id=None,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )
    assert booked.status_code == 200, booked.text

    visit = db_session.query(Visit).get(booked.json()["visit_ids"][0])
    assert visit.doctor_id is None
    resource_queue = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.queue_tag == resource_tag,
        )
        .one()
    )
    assert resource_queue.queue_resource_id == resource.id
    assert resource_queue.specialist_id is None
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit.id)
        .one()
    )
    assert entry.queue_id == resource_queue.id
    assert _doctor_queue_entries(db_session, pinned_to.id) == ([], [])

    fresh_patient = Patient(
        first_name="Пётр",
        last_name="Петров",
        middle_name="Петрович",
        phone=f"+9989{uuid4().hex[:9]}",
        birth_date=date(1990, 1, 1),
        address="Тестовый адрес",
    )
    db_session.add(fresh_patient)
    db_session.commit()
    db_session.refresh(fresh_patient)

    rejected = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=fresh_patient.id,
            visits=[
                _visit(
                    doctor_id=pinned_to.id,
                    services=[{"service_id": service.id, "quantity": 1}],
                )
            ],
        ),
    )
    assert rejected.status_code == 409, rejected.text
    assert "ресурсная" in rejected.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == fresh_patient.id).count()
        == 0
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == fresh_patient.id)
        .count()
        == 0
    )


def test_unflagged_pinned_service_edit_delta_quote_rejects_other_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Edit-delta поверхность использует ту же проверку: квота добавления
    закреплённой безфлажковой услуги к другому врачу → 409 того же
    контракта; к назначенному врачу → 200 (контроль)."""
    pinned_to = _make_doctor(db_session, specialty="cardiology")
    other_cardiologist = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-EQ",
        name="ЭхоКГ закреплённая без флага квота",
        pinned_to_id=pinned_to.id,
    )

    rejected = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": other_cardiologist.id,
                }
            ],
            "discount_mode": "none",
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert "назначена другому врачу" in rejected.json()["detail"]

    accepted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": pinned_to.id,
                }
            ],
            "discount_mode": "none",
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert accepted.status_code == 200, accepted.text


def _qr_resource_entry(db_session: Session, *, patient, day) -> OnlineQueueEntry:
    from app.models.online_queue import QueueResource

    suffix = uuid4().hex[:8]
    resource = QueueResource(
        code=f"p1f_qr_{suffix}",
        queue_tag=f"p1f_lab_{suffix}",
        display_name="Тестовый ресурс QR",
        active=True,
    )
    db_session.add(resource)
    db_session.flush()
    resource_queue = DailyQueue(
        day=day,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
    )
    db_session.add(resource_queue)
    db_session.commit()
    return OnlineQueueEntry(
        queue_id=resource_queue.id,
        number=1,
        queue_time=datetime.now(UTC),
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="online",
        status="waiting",
        services="[]",
    )


def _persist_qr_entry(db_session: Session, entry: OnlineQueueEntry) -> OnlineQueueEntry:
    db_session.add(entry)
    db_session.commit()
    return entry


def _qr_full_update(client, headers, entry: OnlineQueueEntry, services: list[dict]):
    return client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=headers,
        json={
            "patient_data": {"patient_name": "Changed Test Patient"},
            "visit_type": "paid",
            "discount_mode": "none",
            "services": services,
            "all_free": False,
        },
    )


def test_qr_full_update_unflagged_pin_lands_on_pinned_doctor_queue(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """QR full-update из РЕСУРСНОЙ записи: добавление закреплённой
    безфлажковой услуги создаёт независимую запись в очереди НАЗНАЧЕННОГО
    врача (раньше услуга ехала по resource-ветке резолвера — пин
    обходился, тег мог привести в чужую очередь)."""
    from app.crud.clinic import clinic_today

    pinned_to = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-QR",
        name="ЭхоКГ закреплённая без флага QR",
        pinned_to_id=pinned_to.id,
    )
    day = clinic_today(db_session)
    entry = _persist_qr_entry(
        db_session, _qr_resource_entry(db_session, patient=test_patient, day=day)
    )

    response = _qr_full_update(
        client,
        _auth_headers(admin_user),
        entry,
        [{"service_id": service.id, "quantity": 1}],
    )

    assert response.status_code == 200, response.text
    added = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.id != entry.id,
        )
        .all()
    )
    assert len(added) == 1
    assert added[0].queue.specialist_id == pinned_to.id
    assert added[0].queue.queue_resource_id is None


def test_qr_full_update_unflagged_pin_rejects_other_doctors_entry(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """QR full-update из записи ДРУГОГО врача: закреплённая безфлажковая
    услуга → 409 «назначена другому врачу» ДО мутаций (валидационный
    прогон больше не пропускает строку мимо гварда)."""
    from app.crud.clinic import clinic_today

    pinned_to = _make_doctor(db_session, specialty="cardiology")
    other_cardiologist = _make_doctor(db_session, specialty="cardiology")
    service = _make_pinned_unflagged_service(
        db_session,
        code="ASG-P1F-QR2",
        name="ЭхоКГ закреплённая без флага QR2",
        pinned_to_id=pinned_to.id,
    )
    day = clinic_today(db_session)
    other_queue = DailyQueue(
        day=day, specialist_id=other_cardiologist.id, queue_tag="cardio", active=True
    )
    db_session.add(other_queue)
    db_session.commit()
    entry = _persist_qr_entry(
        db_session,
        OnlineQueueEntry(
            queue_id=other_queue.id,
            number=1,
            queue_time=datetime.now(UTC),
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="online",
            status="waiting",
            services="[]",
        ),
    )
    original_name = entry.patient_name

    response = _qr_full_update(
        client,
        _auth_headers(admin_user),
        entry,
        [{"service_id": service.id, "quantity": 1}],
    )

    assert response.status_code == 409, response.text
    assert "назначена другому врачу" in response.json()["detail"]
    db_session.refresh(entry)
    assert entry.patient_name == original_name
    assert entry.services == "[]"
    assert _doctor_queue_entries(db_session, pinned_to.id)[1] == []
