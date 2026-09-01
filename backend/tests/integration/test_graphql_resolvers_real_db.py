"""GQL-AUDIT-28 follow-up: GraphQL резолверы/мутации против РЕАЛЬНОЙ сессии БД.

Регрессия: 15 из 16 резолверов делали ``db = get_db_session()`` без ``with``,
поэтому ``db`` был _GeneratorContextManager без .query → каждый Query-резолвер
падал с AttributeError в рантайме, а мутации тихо возвращали INTERNAL_ERROR.
Старый smoke-тест проверял только ``__typename`` и баг не ловил.

Эти тесты патчат ``app.db.session.SessionLocal`` на фабрику, привязанную к
тестовой SQLite-БД, и гоняют схему целиком: seeded данные -> schema.execute_sync.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session_module
from app.graphql.schema import schema
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService

pytestmark = pytest.mark.integration


@pytest.fixture
def gql_session_factory(test_db, monkeypatch):
    """Привязывает SessionLocal (используемый get_db_session) к тестовой БД."""
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db,
        expire_on_commit=False,
    )
    monkeypatch.setattr(db_session_module, "SessionLocal", factory)
    return factory


@pytest.fixture
def gql_data(test_db, gql_session_factory):
    """Seed реальных строк в тестовую БД; очистка в finally."""
    session = gql_session_factory()
    suffix = uuid.uuid4().hex[:8]
    created: dict = {}
    try:
        user = User(
            username=f"synthetic-gql-doc-{suffix}",
            hashed_password="x",
            full_name="SYNTHETIC GQL Doctor",
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.flush()

        doctor = Doctor(
            user_id=user.id,
            specialty="dentistry",
            cabinet="101",
            start_number_online=1,
            max_online_per_day=15,
            active=True,
        )
        session.add(doctor)
        session.flush()

        patient = Patient(
            last_name=f"SYNTHETIC-Ivanov-{suffix}",
            first_name="SYNTHETIC",
            middle_name="SYNTHETIC",
            phone=f"DEV-DEMO-{suffix}-1",
            email=f"synthetic-{suffix}@example.com",
        )
        session.add(patient)
        session.flush()

        service = Service(
            name=f"Консультация GQL {suffix}",
            code=f"GQL-{suffix}",
            price=150000,
            active=True,
        )
        session.add(service)
        session.flush()

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=date.today(),
            status="scheduled",
        )
        session.add(appointment)
        visit = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            status="scheduled",
        )
        session.add(visit)
        session.flush()

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            active=True,
        )
        session.add(queue)
        session.flush()

        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=patient.id,
            status="waiting",
        )
        session.add(entry)
        session.commit()

        created.update(
            user=user,
            doctor=doctor,
            patient=patient,
            service=service,
            appointment=appointment,
            visit=visit,
            queue=queue,
            entry=entry,
            suffix=suffix,
        )
        yield created
    finally:
        session.close()
        # cleanup: мутационный тест создаёт доп. строки (пациенты с суффиксом,
        # услуги %suffix%, визиты + VisitService, записи очереди) — чистим всё
        # по суффиксу, чтобы не контаминировать общую session-scoped БД.
        cleanup = gql_session_factory()
        try:
            user_ids = [
                u.id
                for u in cleanup.query(User).filter(
                    User.username.like(f"synthetic-gql-doc-{suffix}%")
                )
            ]
            doctor_ids = [
                d.id for d in cleanup.query(Doctor).filter(Doctor.user_id.in_(user_ids))
            ]
            queue_ids = [
                q.id
                for q in cleanup.query(DailyQueue).filter(
                    DailyQueue.specialist_id.in_(doctor_ids)
                )
            ]
            patient_ids = [
                p.id
                for p in cleanup.query(Patient).filter(
                    Patient.last_name.like(f"%{suffix}%")
                )
            ]
            visit_ids = [
                v.id
                for v in cleanup.query(Visit).filter(Visit.patient_id.in_(patient_ids))
            ]
            if visit_ids:
                cleanup.query(VisitService).filter(
                    VisitService.visit_id.in_(visit_ids)
                ).delete(synchronize_session=False)
                cleanup.query(Visit).filter(Visit.id.in_(visit_ids)).delete(
                    synchronize_session=False
                )
            if queue_ids:
                cleanup.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id.in_(queue_ids)
                ).delete(synchronize_session=False)
                cleanup.query(DailyQueue).filter(DailyQueue.id.in_(queue_ids)).delete(
                    synchronize_session=False
                )
            cleanup.query(Appointment).filter(
                Appointment.patient_id.in_(patient_ids)
            ).delete(synchronize_session=False)
            cleanup.query(Service).filter(Service.code.like(f"%{suffix}%")).delete(
                synchronize_session=False
            )
            cleanup.query(Patient).filter(Patient.last_name.like(f"%{suffix}%")).delete(
                synchronize_session=False
            )
            cleanup.query(Doctor).filter(Doctor.id.in_(doctor_ids)).delete(
                synchronize_session=False
            )
            cleanup.query(User).filter(User.id.in_(user_ids)).delete(
                synchronize_session=False
            )
            cleanup.commit()
        finally:
            cleanup.close()


def _execute(query: str, variables: dict | None = None):
    result = schema.execute_sync(query, variable_values=variables)
    assert not result.errors, f"GraphQL errors: {result.errors}"
    return result.data


def test_graphql_query_resolvers_against_real_db(gql_data):
    """Все 15 Query-резолверов работают с реальной сессией (не __typename)."""
    d = gql_data
    query = f"""
        query {{
          patients(filter: {{ phone: "{d["patient"].phone}" }}) {{
            pagination {{ total }}
            items {{ id fullName docNumber }}
          }}
          patient(id: {d["patient"].id}) {{ id fullName }}
          doctors {{ pagination {{ total }} items {{ id specialty active }} }}
          doctor(id: {d["doctor"].id}) {{ id specialty }}
          services(filter: {{ code: "GQL-{d["suffix"]}" }}) {{
            pagination {{ total }}
            items {{ id name price }}
          }}
          service(id: {d["service"].id}) {{ id name }}
          appointments(filter: {{ patientId: {d["patient"].id} }}) {{
            pagination {{ total }}
            items {{ id status }}
          }}
          appointment(id: {d["appointment"].id}) {{
            id status patient {{ id }} doctor {{ id }}
          }}
          visits(filter: {{ patientId: {d["patient"].id} }}) {{
            pagination {{ total }}
            items {{ id status }}
          }}
          visit(id: {d["visit"].id}) {{ id status }}
          queueEntries(filter: {{ doctorId: {d["doctor"].id} }}) {{
            pagination {{ total }}
            items {{ id number status }}
          }}
          appointmentStats {{ total today }}
          visitStats {{ total }}
          queueStats {{ totalEntries activeQueues }}
          doctorStats(doctorId: {d["doctor"].id}) {{
            totalAppointments totalVisits
          }}
        }}
        """
    data = _execute(query)

    # Уникальные фильтры → ровно одна seeded-строка в каждом списке
    assert data["patients"]["pagination"]["total"] == 1
    assert data["patients"]["items"][0]["id"] == d["patient"].id
    assert data["patients"]["items"][0]["fullName"]
    assert data["patient"]["id"] == d["patient"].id
    assert data["doctors"]["pagination"]["total"] >= 1
    assert data["doctor"]["id"] == d["doctor"].id
    assert data["services"]["pagination"]["total"] == 1
    assert data["service"]["id"] == d["service"].id
    assert data["appointments"]["pagination"]["total"] == 1
    apt = data["appointment"]
    assert apt["patient"]["id"] == d["patient"].id
    assert apt["doctor"]["id"] == d["doctor"].id
    assert data["visits"]["pagination"]["total"] == 1
    assert data["visit"]["id"] == d["visit"].id
    assert data["queueEntries"]["pagination"]["total"] == 1
    entry = data["queueEntries"]["items"][0]
    assert entry["number"] == 1
    assert entry["status"] == "waiting"
    assert data["appointmentStats"]["total"] >= 1
    assert data["visitStats"]["total"] >= 1
    assert data["queueStats"]["totalEntries"] >= 1
    assert data["queueStats"]["activeQueues"] >= 1
    assert data["doctorStats"]["totalAppointments"] >= 1


def test_graphql_mutations_succeed_against_real_db(gql_data, monkeypatch):
    """Все 12 мутаций возвращают success=True (раньше — тихий INTERNAL_ERROR)."""
    from app.graphql import mutations as gql_mutations

    # Time-of-day gotcha (#2992): окно онлайн-набора queue_start_hour=7
    # роняет joinQueue ночью (CI/ночь по Ташкенту) — фиксируем окно.
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]

    # --- createPatient (раньше: success=False, INTERNAL_ERROR) ---
    data = _execute(
        """
        mutation Create($input: PatientInput!) {
          createPatient(input: $input) {
            success message errors
            patient { id fullName phone }
          }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-Petrov-{suffix}",
                "firstName": "SYNTHETIC",
                "phone": f"DEV-DEMO-{suffix}-2",
            }
        },
    )
    created = data["createPatient"]
    assert created["success"] is True, created
    linked_patient_id = created["patient"]["id"]
    assert created["patient"]["fullName"].startswith(f"SYNTHETIC-Petrov-{suffix}")

    # --- updatePatient ---
    data = _execute(
        """
        mutation($id: Int!, $input: PatientUpdateInput!) {
          updatePatient(id: $id, input: $input) {
            success patient { id address }
          }
        }
        """,
        {"id": linked_patient_id, "input": {"address": "ул. Тестовая, 1"}},
    )
    assert data["updatePatient"]["success"] is True
    assert data["updatePatient"]["patient"]["address"] == "ул. Тестовая, 1"

    # --- createService / updateServicePrice ---
    data = _execute(
        """
        mutation($input: ServiceInput!) {
          createService(input: $input) { success service { id code price } }
        }
        """,
        {
            "input": {
                "name": f"УЗИ GQL {suffix}",
                "code": f"UZI-{suffix}",
                "price": 200000,
            }
        },
    )
    assert data["createService"]["success"] is True
    service_id = data["createService"]["service"]["id"]

    data = _execute(
        "mutation($id: Int!) { updateServicePrice(id: $id, price: 250000) "
        "{ success service { price } } }",
        {"id": service_id},
    )
    assert data["updateServicePrice"]["success"] is True
    assert data["updateServicePrice"]["service"]["price"] == 250000.0

    # --- createAppointment ---
    data = _execute(
        """
        mutation($input: AppointmentInput!) {
          createAppointment(input: $input) {
            success appointment { id status patient { id } }
          }
        }
        """,
        {
            "input": {
                "patientId": linked_patient_id,
                "doctorId": d["doctor"].id,
                "appointmentDate": str(date.today()),
                "notes": "gql smoke",
            }
        },
    )
    assert data["createAppointment"]["success"] is True, data["createAppointment"]
    appointment_id = data["createAppointment"]["appointment"]["id"]

    # --- updateAppointmentStatus / cancelAppointment ---
    # (SSOT: канонический enum AppointmentStatus; 'confirmed' -> 'paid')
    data = _execute(
        "mutation($id: Int!) { updateAppointmentStatus(id: $id, status: \"paid\") "
        "{ success appointment { status } } }",
        {"id": appointment_id},
    )
    assert data["updateAppointmentStatus"]["success"] is True
    assert data["updateAppointmentStatus"]["appointment"]["status"] == "paid"

    data = _execute(
        "mutation($id: Int!) { cancelAppointment(id: $id, reason: \"gql\") "
        "{ success appointment { status notes } } }",
        {"id": appointment_id},
    )
    assert data["cancelAppointment"]["success"] is True
    assert "gql" in (data["cancelAppointment"]["appointment"]["notes"] or "")

    # --- createVisit / updateVisitStatus ---
    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success visit { id status discountMode } }
        }
        """,
        {
            "input": {
                "patientId": linked_patient_id,
                "doctorId": d["doctor"].id,
                "discountMode": "none",
                "serviceIds": [d["service"].id],
            }
        },
    )
    assert data["createVisit"]["success"] is True, data["createVisit"]
    visit_id = data["createVisit"]["visit"]["id"]

    data = _execute(
        "mutation($id: Int!) { updateVisitStatus(id: $id, status: \"completed\") "
        "{ success visit { status } } }",
        {"id": visit_id},
    )
    assert data["updateVisitStatus"]["success"] is True

    # --- joinQueue / callNextPatient (свежий пациент — seed-пациент
    # уже waiting, словили бы ALREADY_IN_QUEUE) ---
    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) {
            success message queueEntry { id number status }
          }
        }
        """,
        {"input": {"patientId": linked_patient_id, "doctorId": d["doctor"].id}},
    )
    join = data["joinQueue"]
    assert join["success"] is True, join
    assert join["queueEntry"]["number"] >= 2  # seed-запись #1 уже существует
    assert join["queueEntry"]["status"] == "waiting"

    data = _execute(
        "mutation($doctorId: Int!) { callNextPatient(doctorId: $doctorId) "
        "{ success queueEntry { id status calledAt } } }",
        {"doctorId": d["doctor"].id},
    )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    assert call["queueEntry"]["status"] == "called"

    # --- deletePatient (пациент без записей) ---
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-Sidorov-{suffix}",
                "firstName": "SYNTHETIC",
            }
        },
    )
    orphan_id = data["createPatient"]["patient"]["id"]

    data = _execute(
        "mutation($id: Int!) { deletePatient(id: $id) { success } }",
        {"id": orphan_id},
    )
    assert data["deletePatient"]["success"] is True


def test_delete_patient_blocked_when_related_records_exist(gql_data):
    """Пациент с записями/визитами не удаляется (guard HAS_RELATED_RECORDS)."""
    d = gql_data
    data = _execute(
        "mutation($id: Int!) { deletePatient(id: $id) { success errors } }",
        {"id": d["patient"].id},
    )
    assert data["deletePatient"]["success"] is False
    assert "HAS_RELATED_RECORDS" in data["deletePatient"]["errors"]


def test_sessions_are_closed_after_resolver(gql_session_factory):
    """with get_db_session() закрывает сессию: соединения не утекают."""
    _execute("{ patients { pagination { total } } }")
    engine = gql_session_factory.kw["bind"]
    # Утечка сессий (P0-1) оставляла checked-out соединения после запроса.
    assert engine.pool.checkedout() == 0, "pool leaked connections after resolver"
