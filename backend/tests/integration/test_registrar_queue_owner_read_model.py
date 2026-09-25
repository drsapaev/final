"""Per-row ownership contract for the registrar's specialty-grouped worklist."""

from types import SimpleNamespace

from app.api.v1.endpoints.registrar_integration._queue_ops import (
    _resolve_registrar_row_owner,
)
from app.api.v1.endpoints.registrar_integration._today_queues import (
    get_today_queues_page,
)
from app.crud.clinic import clinic_today
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


def test_today_queues_exposes_actual_owner_for_each_entry(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    second_user = User(
        username="queue_owner_second_doctor",
        full_name="Второй врач",
        hashed_password="disabled",
        role="Doctor",
        is_active=True,
    )
    db_session.add(second_user)
    db_session.flush()
    second_doctor = Doctor(
        user_id=second_user.id, specialty=test_doctor.specialty, active=True
    )
    db_session.add(second_doctor)

    ecg_service = Service(
        name="Синтетическая ЭКГ",
        queue_tag="ecg",
        department_key="echokg",
        requires_doctor=False,
        active=True,
    )
    resource = QueueResource(
        code="test_registrar_owner_ecg",
        queue_tag="ecg",
        display_name="ЭКГ",
        active=True,
    )
    db_session.add_all([ecg_service, resource])
    db_session.flush()

    doctor_queue_a = DailyQueue(
        day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common"
    )
    doctor_queue_b = DailyQueue(
        day=today, specialist_id=second_doctor.id, queue_tag="cardiology_common"
    )
    resource_queue = DailyQueue(
        day=today, queue_resource_id=resource.id, queue_tag="ecg"
    )
    db_session.add_all([doctor_queue_a, doctor_queue_b, resource_queue])
    db_session.flush()

    patients = [Patient(first_name="Тест", last_name=f"Пациент{i}") for i in range(10)]
    db_session.add_all(patients)
    db_session.flush()

    # The linked Visit points to doctor B and has both doctor and ECG
    # services, but its actual OQE queue belongs to doctor A. The worklist
    # must emit only the linked OQE row, without assigning its owner to a
    # second visit service slice.
    linked_visit = Visit(
        patient_id=patients[0].id,
        doctor_id=second_doctor.id,
        visit_date=today,
        department="cardiology",
        status="open",
    )
    doctor_visit = Visit(
        patient_id=patients[3].id,
        doctor_id=test_doctor.id,
        visit_date=today,
        department="cardiology",
        status="open",
    )
    resource_visit = Visit(
        patient_id=patients[4].id,
        doctor_id=second_doctor.id,
        visit_date=today,
        department="echokg",
        status="open",
    )
    mixed_unlinked_visit = Visit(
        patient_id=patients[9].id,
        doctor_id=second_doctor.id,
        visit_date=today,
        department="cardiology",
        status="open",
    )
    db_session.add_all(
        [linked_visit, doctor_visit, resource_visit, mixed_unlinked_visit]
    )
    db_session.flush()
    db_session.add_all(
        [
            VisitService(
                visit_id=linked_visit.id,
                service_id=test_service.id,
                name=test_service.name,
            ),
            VisitService(
                visit_id=linked_visit.id,
                service_id=ecg_service.id,
                name=ecg_service.name,
            ),
            VisitService(
                visit_id=doctor_visit.id,
                service_id=test_service.id,
                name=test_service.name,
            ),
            VisitService(
                visit_id=resource_visit.id,
                service_id=ecg_service.id,
                name=ecg_service.name,
            ),
            VisitService(
                visit_id=mixed_unlinked_visit.id,
                service_id=ecg_service.id,
                name=ecg_service.name,
            ),
            VisitService(
                visit_id=mixed_unlinked_visit.id,
                service_id=test_service.id,
                name=test_service.name,
            ),
        ]
    )

    entries = [
        OnlineQueueEntry(
            queue_id=doctor_queue_a.id,
            number=1,
            patient_id=patients[0].id,
            visit_id=linked_visit.id,
            source="online",
            status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=doctor_queue_b.id,
            number=1,
            patient_id=patients[1].id,
            source="online",
            status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=resource_queue.id,
            number=1,
            patient_id=patients[2].id,
            source="online",
            status="waiting",
        ),
    ]
    appointments = [
        Appointment(
            patient_id=patients[5].id,
            doctor_id=second_doctor.id,
            appointment_date=today,
            status="scheduled",
            services=[test_service.name],
        ),
        Appointment(
            patient_id=patients[6].id,
            appointment_date=today,
            status="scheduled",
            services=[ecg_service.name],
        ),
        Appointment(
            patient_id=patients[7].id,
            doctor_id=test_doctor.id,
            appointment_date=today,
            status="scheduled",
            services=[ecg_service.name, test_service.name],
        ),
        Appointment(
            patient_id=patients[8].id,
            appointment_date=today,
            status="scheduled",
            services=[],
        ),
    ]
    db_session.add_all([*entries, *appointments])
    db_session.commit()

    response = client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    all_rows = [row for queue in response.json()["queues"] for row in queue["entries"]]
    rows = {(row["record_kind"], row["id"]): row for row in all_rows}
    owner_keys = {"queue_owner_kind", "queue_owner_id", "daily_queue_id"}
    assert all(owner_keys <= row.keys() for row in all_rows)

    def owner(kind, row_id):
        row = rows[(kind, row_id)]
        return tuple(
            row[key] for key in ("queue_owner_kind", "queue_owner_id", "daily_queue_id")
        )

    assert owner("online_queue", entries[0].id) == (
        "doctor",
        test_doctor.id,
        doctor_queue_a.id,
    )
    assert rows[("online_queue", entries[0].id)]["visit_id"] == linked_visit.id
    assert ("visit", linked_visit.id) not in rows
    assert owner("online_queue", entries[1].id) == (
        "doctor",
        second_doctor.id,
        doctor_queue_b.id,
    )
    assert owner("online_queue", entries[2].id) == (
        "resource",
        resource.id,
        resource_queue.id,
    )
    assert owner("visit", doctor_visit.id) == ("doctor", test_doctor.id, None)
    assert owner("visit", resource_visit.id) == ("resource", resource.id, None)
    assert owner("appointment", appointments[0].id) == (
        "doctor",
        second_doctor.id,
        None,
    )
    assert owner("appointment", appointments[1].id) == ("resource", resource.id, None)
    assert owner("appointment", appointments[2].id) == (None, None, None)
    assert owner("appointment", appointments[3].id) == (None, None, None)

    mixed_rows = [
        row
        for row in all_rows
        if row["record_kind"] == "visit" and row["id"] == mixed_unlinked_visit.id
    ]
    assert len(mixed_rows) == 2
    assert {
        (
            row["queue_owner_kind"],
            row["queue_owner_id"],
            row["daily_queue_id"],
            tuple(detail["id"] for detail in row["service_details"]),
        )
        for row in mixed_rows
    } == {
        ("resource", resource.id, None, (ecg_service.id,)),
        ("doctor", second_doctor.id, None, (test_service.id,)),
    }

    page = get_today_queues_page(
        target_date=today.isoformat(),
        department=None,
        limit=100,
        offset=0,
        db=db_session,
        current_user=admin_user,
    )
    page_rows = [row for queue in page["queues"] for row in queue["entries"]]
    assert page["total_entries"] == len(all_rows)
    assert (
        sum(
            row["record_kind"] == "visit" and row["id"] == mixed_unlinked_visit.id
            for row in page_rows
        )
        == 2
    )


def test_owner_resolver_rejects_duplicate_service_names_and_inactive_resources(
    db_session,
):
    db_session.add_all(
        [
            Service(name="Одинаковое имя", queue_tag="ecg", active=True),
            Service(name="Одинаковое имя", queue_tag="cardiology", active=True),
            Service(name="Неактивный ресурс", queue_tag="inactive_tag", active=True),
            QueueResource(
                code="test_owner_duplicate_ecg",
                queue_tag="ecg",
                display_name="ЭКГ",
                active=True,
            ),
            QueueResource(
                code="test_owner_inactive",
                queue_tag="inactive_tag",
                display_name="Неактивен",
                active=False,
            ),
        ]
    )
    db_session.flush()

    duplicate_name = SimpleNamespace(doctor_id=42, services=["Одинаковое имя"])
    assert _resolve_registrar_row_owner(
        db=db_session,
        entry_type="appointment",
        entry_data=duplicate_name,
        service_details=[],
    ) == (None, None, None)

    inactive_resource = SimpleNamespace(doctor_id=42, services=["Неактивный ресурс"])
    assert _resolve_registrar_row_owner(
        db=db_session,
        entry_type="appointment",
        entry_data=inactive_resource,
        service_details=[],
    ) == ("doctor", 42, None)
