"""REG-FE-022 (issue 3822): the registrar today read model must never
fabricate ticket numbers from list ordinals.

`_resolve_queue_entry_metadata` initialized ``queue_entry_number = idx`` and
kept the ordinal whenever no real queue entry could be proven for a row;
``_serialize_queue_entry`` then sent it as BOTH ``number`` and
``queue_position``. A list ordinal like ``idx=3`` therefore masqueraded as
ticket #3 for unlinked appointments/visits, and the appointment heuristic
(patient, day, doctor) silently took the latest matching unlinked entry even
when several candidates existed.

Fail-first contract (issue 3822 acceptance):
1. A real allocated ``OnlineQueueEntry`` ticket is preserved (number and
   queue_position equal the stored number) regardless of its list position
   and on historical dates.
2. An unlinked appointment/visit amid other rows returns ``number=None`` and
   ``queue_position=None`` — never the list ordinal.
3. Two queues owned by different doctors may both hold ticket #7 without
   cross-association.
4. Multiple unlinked queue entries matching the same (patient, day, doctor)
   heuristic are ambiguous: the appointment gets NO ticket.
5. A unique heuristic match still attaches the ticket.
"""

from datetime import date, timedelta

from app.crud.clinic import clinic_today
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


def _rows_for(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    return [row for queue in payload["queues"] for row in queue["entries"]]


def _find(rows, kind, record_id):
    matches = [
        row
        for row in rows
        if row["record_kind"] == kind and row["id"] == record_id
    ]
    assert matches, f"row {kind}/{record_id} not found in today queues payload"
    return matches[0]


def test_real_allocated_ticket_is_preserved_at_any_position_and_date(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    yesterday = today - timedelta(days=1)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    history_queue = DailyQueue(day=yesterday, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add_all([queue, history_queue])
    db_session.flush()

    patients = [Patient(first_name="Тест", last_name=f"Пациент{i}") for i in range(3)]
    db_session.add_all(patients)
    db_session.flush()

    # Three allocated tickets; the #17 one must not depend on list position.
    entries = [
        OnlineQueueEntry(
            queue_id=queue.id, number=1, patient_id=patients[0].id,
            source="online", status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=queue.id, number=2, patient_id=patients[1].id,
            source="online", status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=queue.id, number=17, patient_id=patients[2].id,
            source="online", status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=history_queue.id, number=8, patient_id=patients[0].id,
            source="online", status="waiting",
        ),
    ]
    db_session.add_all(entries)
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    ticket_row = _find(rows, "online_queue", entries[2].id)
    assert ticket_row["number"] == 17
    assert ticket_row["queue_position"] == 17

    history_rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={yesterday.isoformat()}",
        headers=auth_headers,
    ))
    history_row = _find(history_rows, "online_queue", entries[3].id)
    assert history_row["number"] == 8
    assert history_row["queue_position"] == 8


def test_unlinked_appointment_amid_other_rows_has_no_ticket_number(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add(queue)
    db_session.flush()

    patients = [Patient(first_name="Тест", last_name=f"Пациент{i}") for i in range(4)]
    db_session.add_all(patients)
    db_session.flush()

    other_entries = [
        OnlineQueueEntry(
            queue_id=queue.id, number=1, patient_id=patients[0].id,
            source="online", status="waiting",
        ),
        OnlineQueueEntry(
            queue_id=queue.id, number=2, patient_id=patients[1].id,
            source="online", status="waiting",
        ),
    ]
    # The appointment has NO queue entry: no allocation was ever made.
    appointment = Appointment(
        patient_id=patients[2].id,
        doctor_id=test_doctor.id,
        appointment_date=today,
        status="scheduled",
        services=[test_service.name],
    )
    other_appointment = Appointment(
        patient_id=patients[3].id,
        appointment_date=today,
        status="scheduled",
        services=[],
    )
    db_session.add_all([*other_entries, appointment, other_appointment])
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    appointment_row = _find(rows, "appointment", appointment.id)
    # REG-FE-022: absent allocation must be null, never the list ordinal
    # (a positive ordinal masquerading as an issued ticket).
    assert appointment_row["number"] is None
    assert appointment_row["queue_position"] is None


def test_unlinked_visit_has_no_ticket_number(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add(queue)
    db_session.flush()

    patient = Patient(first_name="Тест", last_name="Пациент Без Связи")
    db_session.add(patient)
    db_session.flush()

    # A visit with NO OnlineQueueEntry link: no ticket was allocated.
    visit = Visit(
        patient_id=patient.id,
        doctor_id=test_doctor.id,
        visit_date=today,
        department="cardiology",
        status="open",
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add(VisitService(
        visit_id=visit.id, service_id=test_service.id, name=test_service.name,
    ))
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    visit_row = _find(rows, "visit", visit.id)
    assert visit_row["number"] is None
    assert visit_row["queue_position"] is None


def test_two_doctor_queues_with_same_ticket_number_keep_own_values(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    second_user = User(
        username="reg_fe_022_second_doctor",
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
    db_session.flush()

    queue_a = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    queue_b = DailyQueue(day=today, specialist_id=second_doctor.id, queue_tag="cardiology_common")
    db_session.add_all([queue_a, queue_b])
    db_session.flush()

    patients = [Patient(first_name="Тест", last_name=f"Пациент{i}") for i in range(2)]
    db_session.add_all(patients)
    db_session.flush()

    # Both independent queues legitimately hold ticket #7: the numbers must
    # not cross-associate, and both stay real sevens.
    entry_a = OnlineQueueEntry(
        queue_id=queue_a.id, number=7, patient_id=patients[0].id,
        source="online", status="waiting",
    )
    entry_b = OnlineQueueEntry(
        queue_id=queue_b.id, number=7, patient_id=patients[1].id,
        source="online", status="waiting",
    )
    db_session.add_all([entry_a, entry_b])
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    row_a = _find(rows, "online_queue", entry_a.id)
    row_b = _find(rows, "online_queue", entry_b.id)
    assert row_a["number"] == 7
    assert row_a["queue_position"] == 7
    assert row_b["number"] == 7
    assert row_b["queue_position"] == 7
    assert row_a["patient_id"] == patients[0].id
    assert row_b["patient_id"] == patients[1].id


def test_ambiguous_multi_entry_match_attaches_no_ticket_to_appointment(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add(queue)
    db_session.flush()

    patient = Patient(first_name="Тест", last_name="Пациент Двух Записей")
    db_session.add(patient)
    db_session.flush()

    # Two unlinked queue entries for the SAME (patient, day, doctor): the
    # heuristic cannot prove which one belongs to the appointment, so no
    # ticket may be attached (previously it silently took the latest).
    earlier = OnlineQueueEntry(
        queue_id=queue.id, number=5, patient_id=patient.id,
        visit_id=None, source="online", status="waiting",
    )
    later = OnlineQueueEntry(
        queue_id=queue.id, number=6, patient_id=patient.id,
        visit_id=None, source="online", status="waiting",
    )
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=test_doctor.id,
        appointment_date=today,
        status="scheduled",
        services=[test_service.name],
    )
    db_session.add_all([earlier, later, appointment])
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    appointment_row = _find(rows, "appointment", appointment.id)
    assert appointment_row["number"] is None
    assert appointment_row["queue_position"] is None
    # The queue entries themselves keep their real numbers.
    assert _find(rows, "online_queue", earlier.id)["number"] == 5
    assert _find(rows, "online_queue", later.id)["number"] == 6


def test_unique_appointment_match_attaches_ticket(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add(queue)
    db_session.flush()

    patient = Patient(first_name="Тест", last_name="Пациент Одной Записи")
    db_session.add(patient)
    db_session.flush()

    # Exactly one unlinked entry matches (patient, day, doctor): the match
    # is unambiguous and the appointment carries that ticket.
    entry = OnlineQueueEntry(
        queue_id=queue.id, number=9, patient_id=patient.id,
        visit_id=None, source="online", status="waiting",
    )
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=test_doctor.id,
        appointment_date=today,
        status="scheduled",
        services=[test_service.name],
    )
    db_session.add_all([entry, appointment])
    db_session.commit()

    rows = _rows_for(client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}",
        headers=auth_headers,
    ))
    appointment_row = _find(rows, "appointment", appointment.id)
    assert appointment_row["number"] == 9
    assert appointment_row["queue_position"] == 9


def test_ticket_identity_is_stable_across_pagination_pages(
    client, db_session, auth_headers, admin_user, test_doctor, test_service
):
    today = clinic_today(db_session)
    queue = DailyQueue(day=today, specialist_id=test_doctor.id, queue_tag="cardiology_common")
    db_session.add(queue)
    db_session.flush()

    patients = [Patient(first_name="Тест", last_name=f"Пациент{i}") for i in range(4)]
    db_session.add_all(patients)
    db_session.flush()

    entries = [
        OnlineQueueEntry(
            queue_id=queue.id, number=number, patient_id=patients[i].id,
            source="online", status="waiting",
        )
        for i, number in enumerate([11, 12, 13, 14], start=0)
    ]
    db_session.add_all(entries)
    db_session.commit()

    first_page = client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}&limit=2&offset=0",
        headers=auth_headers,
    )
    second_page = client.get(
        f"/api/v1/registrar/queues/today?target_date={today.isoformat()}&limit=2&offset=2",
        headers=auth_headers,
    )
    first_rows = _rows_for(first_page)
    second_rows = _rows_for(second_page)

    all_by_id = {row["id"]: row for row in [*first_rows, *second_rows]}
    for entry in entries:
        row = all_by_id[entry.id]
        assert row["record_kind"] == "online_queue"
        assert row["number"] == entry.number
        assert row["queue_position"] == entry.number
