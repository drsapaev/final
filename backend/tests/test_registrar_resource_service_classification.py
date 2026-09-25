"""PR #3438 review P1-1/P2: resource-vs-doctor service classification.

The catalog flag ``requires_doctor``/``is_consultation`` says a service is
clinician-performed; it says NOTHING about queue ownership. The canonical
seed carries K10 «ЭКГ» with ``requires_doctor=True`` while its ``ecg`` tag
is a registry QueueResource — three defects followed:

- the catalog emitted ``doctor_selection_required=true`` for it, the wizard
  removed it from the regular list, and no doctor card matched (no clinician
  carries the ``echokg`` specialty) → the service DISAPPEARED from the
  booking surface in the standard configuration;
- the write gate did not resource-check non-consultation doctor-selection
  services → a doctor_id on the visit was decorative: the assignment pass
  nulls the specialist for registry tags, so the queue entry landed in the
  resource queue and the per-doctor worklist never counted it;
- the catalog's ``doctor_booking_available`` used a dateless registry
  snapshot while the write gate uses the deactivation-proof day surface
  (``tag_routes_to_resource``) → after a mid-day registry deactivation with
  an existing resource queue the catalog promised a doctor booking that the
  save-time gate 409-rejected.

Pins in this file:

- K10-like resource service: no doctor selection, not doctor-bookable,
  bookable WITHOUT a doctor into the resource-owned queue;
- the same service with a doctor: 409, zero visits/invoices/entries;
- doctor-owned services keep requiring a doctor (byte-identical contract);
- consultation on a resource tag: ambiguous class — selection required and
  booking unavailable (fail-closed, unchanged);
- date-aware catalog: the day's existing resource surface keeps the
  resource classification after a registry deactivation (default booking
  day = today), while a later day re-classifies the service doctor-owned.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration


def _headers(admin_user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _resource_service(
    db_session,
    *,
    code: str,
    queue_tag: str,
    resource_active: bool = True,
    department_key: str = "echokg",
) -> tuple[Service, QueueResource]:
    """A K10-shaped service: requires_doctor, NOT a consultation, resource tag."""
    service = Service(
        code=code,
        service_code=code,
        name="ЭКГ",
        department_key=department_key,
        queue_tag=queue_tag,
        price=25000,
        active=True,
        requires_doctor=True,
        is_consultation=False,
    )
    resource = QueueResource(
        code=queue_tag,
        queue_tag=queue_tag,
        display_name="Тестовый ресурс",
        active=resource_active,
    )
    db_session.add_all([service, resource])
    db_session.commit()
    db_session.refresh(service)
    db_session.refresh(resource)
    return service, resource


def _doctor(db_session, *, username: str, specialty: str = "cardiology") -> Doctor:
    user = User(
        username=username,
        full_name="Тестовый Кардиолог",
        hashed_password="unused-test-hash",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _cart(patient_id: int, service_id: int, doctor_id: int | None) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": [
            {
                "doctor_id": doctor_id,
                "visit_date": date.today().isoformat(),
                "department": "echokg",
                "services": [{"service_id": service_id, "quantity": 1}],
            }
        ],
    }


def _rows(
    client, headers: dict[str, str], target_date: str | None = None
) -> dict[int, dict]:
    url = "/api/v1/registrar/services"
    if target_date:
        url += f"?target_date={target_date}"
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    return {
        row["id"]: row
        for group in response.json()["services_by_group"].values()
        for row in group
    }


# ── K10: the resource-owned class ─────────────────────────────────────────


def test_k10_resource_service_is_not_doctor_selection_required(
    client, db_session, admin_user
):
    service, _ = _resource_service(db_session, code="RRC01", queue_tag="rrc_ecg")

    row = _rows(client, _headers(admin_user))[service.id]
    # raw catalog flag is preserved...
    assert row["requires_doctor"] is True
    # ...but the surface decision accounts for queue ownership:
    assert row["doctor_selection_required"] is False
    # and the service is NOT doctor-bookable (the resource owns the queue)
    assert row["doctor_booking_available"] is False


def test_k10_resource_service_books_without_doctor_into_resource_queue(
    client, db_session, admin_user, test_patient
):
    service, resource = _resource_service(db_session, code="RRC02", queue_tag="rrc_ecg")

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, None),
    )
    assert response.status_code == 200, response.text

    visit = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).one()
    assert visit.doctor_id is None
    queue = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == date.today(),
            DailyQueue.queue_tag == service.queue_tag,
        )
        .one()
    )
    assert queue.queue_resource_id == resource.id
    assert queue.specialist_id is None
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit.id)
        .one()
    )
    assert entry.queue_id == queue.id


def test_k10_resource_service_with_doctor_fails_closed(
    client, db_session, admin_user, test_patient
):
    service, _ = _resource_service(db_session, code="RRC03", queue_tag="rrc_ecg")
    doctor = _doctor(db_session, username="rrc_ecg_doc")

    before_visits = db_session.query(Visit).count()
    before_entries = db_session.query(OnlineQueueEntry).count()
    before_invoices = db_session.query(PaymentInvoice).count()

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert response.status_code == 409, response.text
    assert "ресурсная" in response.json()["detail"]
    assert db_session.query(Visit).count() == before_visits
    assert db_session.query(OnlineQueueEntry).count() == before_entries
    assert db_session.query(PaymentInvoice).count() == before_invoices


def test_k10_resource_service_specialty_never_blocks_the_resource_surface(
    client, db_session, admin_user, test_patient
):
    """The old UI loss: the echokg department key matched no doctor.

    The resource class must not depend on specialty matching at all — the
    service stays bookable even when NO doctor shares its department.
    """
    service, _ = _resource_service(
        db_session, code="RRC04", queue_tag="rrc_ecg", department_key="echokg"
    )
    # a dentist exists — nobody matches "echokg"
    _doctor(db_session, username="rrc_mismatch_doc", specialty="dentistry")

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, None),
    )
    assert response.status_code == 200, response.text


# ── doctor-owned class: byte-identical contract ────────────────────────────


def test_doctor_owned_requires_doctor_service_still_requires_a_doctor(
    client, db_session, admin_user, test_patient
):
    service = Service(
        code="RRC05",
        service_code="RRC05",
        name="Врачебная процедура",
        department_key="cardiology",
        queue_tag="rrc_cardio",
        price=50000,
        active=True,
        requires_doctor=True,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    row = _rows(client, _headers(admin_user))[service.id]
    assert row["doctor_selection_required"] is True
    assert row["doctor_booking_available"] is True

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, None),
    )
    assert response.status_code == 400, response.text
    assert "требует выбора врача" in response.json()["detail"]


def test_inactive_registry_without_day_queue_returns_service_to_doctor_class(
    client, db_session, admin_user
):
    """Deactivated registry + no existing resource queue → doctor-owned again.

    The deactivation-proof surface only preserves the resource axis while
    the day's queue exists; with no queue, the tag is legacy doctor routing.
    """
    service, _ = _resource_service(
        db_session, code="RRC06", queue_tag="rrc_ecg", resource_active=False
    )

    row = _rows(client, _headers(admin_user))[service.id]
    assert row["doctor_selection_required"] is True
    assert row["doctor_booking_available"] is True


# ── ambiguous class: consultation on a resource tag ────────────────────────


def test_consultation_on_resource_tag_stays_selection_required_and_unbookable(
    client, db_session, admin_user
):
    service = Service(
        code="RRC07",
        service_code="RRC07",
        name="Консультация ресурсного тега",
        department_key="cardiology",
        queue_tag="rrc_consult_resource",
        price=50000,
        active=True,
        requires_doctor=True,
        is_consultation=True,
    )
    db_session.add_all(
        [
            service,
            QueueResource(
                code="rrc_consult_resource",
                queue_tag="rrc_consult_resource",
                display_name="Тестовый ресурс",
                active=True,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(service)

    row = _rows(client, _headers(admin_user))[service.id]
    # mixed semantics fail closed: the consult cannot silently book into
    # a staff-served resource queue without its clinician
    assert row["doctor_selection_required"] is True
    assert row["doctor_booking_available"] is False


# ── P2: date-aware catalog availability ───────────────────────────────────


def test_deactivated_registry_with_existing_day_queue_keeps_resource_class(
    client, db_session, admin_user
):
    """The P2 read/write drift: mid-day deactivation + existing queue.

    Old catalog logic: the deactivated tag left ``active_resource_tags`` →
    ``doctor_booking_available=true`` → the registrar picked a doctor and
    the save-time gate 409-rejected (the day's resource queue IS the
    surface). The catalog now uses the same deactivation-proof routing
    truth for the default booking day (today).
    """
    service, resource = _resource_service(db_session, code="RRC08", queue_tag="rrc_ecg")
    db_session.add(
        DailyQueue(
            day=date.today(),
            queue_tag=service.queue_tag,
            queue_resource_id=resource.id,
            active=True,
        )
    )
    db_session.commit()
    # the mid-day deactivation
    resource.active = False
    db_session.commit()

    row = _rows(client, _headers(admin_user))[service.id]
    assert row["doctor_selection_required"] is False
    assert row["doctor_booking_available"] is False


def test_target_date_reclassifies_service_for_another_day(
    client, db_session, admin_user
):
    """An explicit ``target_date`` computes the surface for THAT day.

    Today: deactivated registry + existing resource queue → resource class.
    Tomorrow: no queue and no active registry row → the tag is legacy
    doctor routing again → doctor-owned.
    """
    service, resource = _resource_service(db_session, code="RRC09", queue_tag="rrc_ecg")
    db_session.add(
        DailyQueue(
            day=date.today(),
            queue_tag=service.queue_tag,
            queue_resource_id=resource.id,
            active=True,
        )
    )
    db_session.commit()
    resource.active = False
    db_session.commit()

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    row = _rows(client, _headers(admin_user), target_date=tomorrow)[service.id]
    assert row["doctor_selection_required"] is True
    assert row["doctor_booking_available"] is True


def test_active_registry_without_day_queue_is_resource_class_for_any_day(
    client, db_session, admin_user
):
    """An ACTIVE registry row routes the tag regardless of a live queue.

    The first booking of the day will create the resource queue (the stage-C
    switch), so the catalog must classify the service resource-owned BEFORE
    any queue exists.
    """
    service, _ = _resource_service(db_session, code="RRC10", queue_tag="rrc_ecg")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    row = _rows(client, _headers(admin_user), target_date=tomorrow)[service.id]
    assert row["doctor_selection_required"] is False
    assert row["doctor_booking_available"] is False
