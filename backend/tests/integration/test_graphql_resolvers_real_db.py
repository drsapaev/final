"""GQL-AUDIT-28 follow-up: GraphQL резолверы/мутации против РЕАЛЬНОЙ сессии БД.

Регрессия: 15 из 16 резолверов делали ``db = get_db_session()`` без ``with``,
поэтому ``db`` был _GeneratorContextManager без .query → каждый Query-резолвер
падал с AttributeError в рантайме, а мутации тихо возвращали INTERNAL_ERROR.
Старый smoke-тест проверял только ``__typename`` и баг не ловил.

Эти тесты патчат ``app.db.session.SessionLocal`` на фабрику, привязанную к
тестовой SQLite-БД, и гоняют схему целиком: seeded данные -> schema.execute_sync.
"""

import asyncio
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session_module
from app.graphql.schema import GraphQLContext, schema
from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor
from app.models.notification import (
    NotificationDelivery,
    NotificationSettings,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.user_profile import UserAuditLog
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


gql_data_ctx: dict = {}


@pytest.fixture
def gql_data(test_db, gql_session_factory):
    """Seed реальных строк в тестовую БД; очистка в finally."""
    session = gql_session_factory()
    suffix = uuid.uuid4().hex[:8]
    created: dict = {}
    try:
        admin_user = User(
            username=f"synthetic-gql-admin-{suffix}",
            hashed_password="x",
            full_name="SYNTHETIC GQL Admin",
            role="Admin",
            is_active=True,
        )
        session.add(admin_user)
        session.flush()

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

        # Codex P1 (раунд 5): канонический прайсинг применяется только к
        # is_consultation=True (benefit/repeat) — нужна консультация.
        consult_service = Service(
            name=f"Приём GQL {suffix}",
            code=f"GQLC-{suffix}",
            price=100000,
            active=True,
            is_consultation=True,
        )
        session.add(consult_service)
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
            admin_user=admin_user,
            user=user,
            doctor=doctor,
            patient=patient,
            service=service,
            consult_service=consult_service,
            appointment=appointment,
            visit=visit,
            queue=queue,
            entry=entry,
            suffix=suffix,
        )
        gql_data_ctx.clear()
        gql_data_ctx.update(created)
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
                    User.username.like(f"synthetic-gql-%{suffix}%")
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
            # строки, ссылающиеся на users (FK на postgres CI), — до юзеров
            if user_ids:
                cleanup.query(UserAuditLog).filter(
                    UserAuditLog.user_id.in_(user_ids)
                ).delete(synchronize_session=False)
                cleanup.query(NotificationDelivery).filter(
                    NotificationDelivery.recipient_id.in_(user_ids)
                ).delete(synchronize_session=False)
                cleanup.query(NotificationSettings).filter(
                    NotificationSettings.user_id.in_(user_ids)
                ).delete(synchronize_session=False)
            cleanup.query(User).filter(User.id.in_(user_ids)).delete(
                synchronize_session=False
            )
            cleanup.commit()
        finally:
            cleanup.close()


def _execute(query: str, variables: dict | None = None):
    """execute через event loop: callNextPatient — async-мутация."""
    admin = gql_data_ctx["admin_user"]
    context = GraphQLContext(
        user=SimpleNamespace(
            id=admin.id,
            username=admin.username,
            full_name=admin.full_name,
            role="Admin",
            is_active=True,
        )
    )

    async def _run():
        return await schema.execute(
            query, variable_values=variables, context_value=context
        )

    result = asyncio.run(_run())
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
                # форматно-валидный (+998XXXXXXXXX), но синтетический номер
                # (цифры из hex-суффикса; нули в середине) — каноническая
                # валидация PatientService пропускает, а фейковость видна
                # в репо (codex round-1: никаких реалистичных +998-фикстур).
                "phone": f"+99890{str(int(suffix, 16) % 10**7).zfill(7)}",
                "email": f"petrov-{suffix}@example.com",
            }
        },
    )
    created = data["createPatient"]
    assert created["success"] is True, created
    linked_patient_id = created["patient"]["id"]
    assert created["patient"]["fullName"].startswith(f"SYNTHETIC-Petrov-{suffix}")

    # --- updatePatient: частичное обновление ТОЛЬКО address ---
    # Codex P1 (раунд 5): опущенные поля (UNSET) не должны затирать
    # существующие телефон/email — раньше они уходили в PatientUpdate как
    # None и CRUDBase.update обнулял их.
    created_phone = created["patient"]["phone"]
    data = _execute(
        """
        mutation($id: Int!, $input: PatientUpdateInput!) {
          updatePatient(id: $id, input: $input) {
            success patient { id address phone email }
          }
        }
        """,
        {"id": linked_patient_id, "input": {"address": "ул. Тестовая, 1"}},
    )
    assert data["updatePatient"]["success"] is True
    assert data["updatePatient"]["patient"]["address"] == "ул. Тестовая, 1"
    # опущенные поля выжили (не затёрты None)
    assert data["updatePatient"]["patient"]["phone"] == created_phone
    assert data["updatePatient"]["patient"]["email"] == f"petrov-{suffix}@example.com"

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
        "mutation($id: Int!) { updateVisitStatus(id: $id, status: \"confirmed\") "
        "{ success visit { status } } }",
        {"id": visit_id},
    )
    assert data["updateVisitStatus"]["success"] is True, data["updateVisitStatus"]
    assert data["updateVisitStatus"]["visit"]["status"] == "confirmed"

    # --- Codex P1 (раунд 5): repeat-guard — канонический guard корзины.
    # seed-пациент: фикстурный визит без visit_date → не eligible.
    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success message errors }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "discountMode": "repeat",
                "serviceIds": [d["consult_service"].id],
            }
        },
    )
    repeat_guard = data["createVisit"]
    assert repeat_guard["success"] is False, repeat_guard
    assert "REPEAT_VISIT_NOT_ELIGIBLE" in repeat_guard["errors"]

    # --- Codex P1 (раунд 5): канонический прайсинг ДО персистенса.
    # repeat: repeat_visit_discount=20 (ClinicSettings) → 80% от 100000.
    # benefit: benefit_consultation_free=True (дефолт) → 0.
    settings_owned = False
    # gql_session_factory уже пропатчил SessionLocal на тестовую БД —
    # саму фикстуру вызывать напрямую нельзя (pytest forbids).
    from app.db import session as db_session_module

    with db_session_module.SessionLocal() as s:
        row = (
            s.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_discount")
            .first()
        )
        if row is None:
            s.add(ClinicSettings(key="repeat_visit_discount", value="20"))
            settings_owned = True
        else:
            row.value = "20"
        s.commit()

    try:
        data = _execute(
            """
            mutation($input: VisitInput!) {
              createVisit(input: $input) { success visit { id } }
            }
            """,
            {
                "input": {
                    "patientId": linked_patient_id,
                    "doctorId": d["doctor"].id,
                    "discountMode": "repeat",
                    "serviceIds": [d["consult_service"].id],
                }
            },
        )
        assert data["createVisit"]["success"] is True, data["createVisit"]
        repeat_visit_id = data["createVisit"]["visit"]["id"]

        data = _execute(
            """
            mutation($input: VisitInput!) {
              createVisit(input: $input) { success visit { id } }
            }
            """,
            {
                "input": {
                    "patientId": linked_patient_id,
                    "doctorId": d["doctor"].id,
                    "discountMode": "benefit",
                    "serviceIds": [d["consult_service"].id],
                }
            },
        )
        assert data["createVisit"]["success"] is True, data["createVisit"]
        benefit_visit_id = data["createVisit"]["visit"]["id"]

        with db_session_module.SessionLocal() as s:
            repeat_vs = (
                s.query(VisitService)
                .filter(VisitService.visit_id == repeat_visit_id)
                .first()
            )
            assert repeat_vs is not None
            assert float(repeat_vs.price) == 80000.0  # 100000 - 20%
            benefit_vs = (
                s.query(VisitService)
                .filter(VisitService.visit_id == benefit_visit_id)
                .first()
            )
            assert benefit_vs is not None
            assert float(benefit_vs.price) == 0.0  # льгота: консультация 0
    finally:
        # не контаминировать общую session-scoped БД
        with db_session_module.SessionLocal() as s:
            row = (
                s.query(ClinicSettings)
                .filter(ClinicSettings.key == "repeat_visit_discount")
                .first()
            )
            if row is not None:
                if settings_owned:
                    s.delete(row)
                else:
                    row.value = None
                s.commit()

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


def test_join_queue_broadcasts_to_display_and_ws(gql_data, monkeypatch):
    """Codex P2 (раунд 5): успешный joinQueue broadcast-ит queue.created
    на TV-табло и entry_added в админский /ws/queue — как канонический
    REST /queue/join."""
    import app.ws.queue_ws as queue_ws_module
    from app.graphql import mutations as gql_mutations

    # Time-of-day gotcha (#2992): фиксируем окно онлайн-набора.
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    display_calls: list[dict] = []
    ws_calls: list[dict] = []

    class _StubDisplayManager:
        async def broadcast_queue_update(self, *, queue_entry, event_type):
            display_calls.append({"entry_id": queue_entry.id, "event_type": event_type})

    monkeypatch.setattr(
        gql_mutations, "get_display_manager", lambda: _StubDisplayManager()
    )

    def _fake_ws_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws_module, "broadcast_queue_update", _fake_ws_broadcast)

    d = gql_data
    suffix = d["suffix"]

    # свежий пациент (seed уже waiting — словили бы ALREADY_IN_QUEUE)
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-Broadcast-{suffix}",
                "firstName": "SYNTHETIC",
            }
        },
    )
    patient_id = data["createPatient"]["patient"]["id"]

    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) { success queueEntry { id number } }
        }
        """,
        {"input": {"patientId": patient_id, "doctorId": d["doctor"].id}},
    )
    join = data["joinQueue"]
    assert join["success"] is True, join
    entry_id = join["queueEntry"]["id"]

    # 1) TV-табло получила queue.created для новой записи
    assert display_calls == [{"entry_id": entry_id, "event_type": "queue.created"}]
    # 2) админский WS получил entry_added в комнату врача
    assert len(ws_calls) == 1, ws_calls
    ws = ws_calls[0]
    assert ws["department"] == f"specialist_{d['doctor'].id}"
    assert ws["date"] == date.today().strftime("%Y-%m-%d")
    assert ws["event_type"] == "queue_update"
    assert ws["data"]["action"] == "entry_added"
    assert ws["data"]["entry_id"] == entry_id
    assert ws["data"]["number"] == join["queueEntry"]["number"]


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
