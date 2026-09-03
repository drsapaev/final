"""GQL-AUDIT-28 follow-up: GraphQL резолверы/мутации против РЕАЛЬНОЙ сессии БД.

Регрессия: 15 из 16 резолверов делали ``db = get_db_session()`` без ``with``,
поэтому ``db`` был _GeneratorContextManager без .query → каждый Query-резолвер
падал с AttributeError в рантайме, а мутации тихо возвращали INTERNAL_ERROR.
Старый smoke-тест проверял только ``__typename`` и баг не ловил.

Эти тесты патчат ``app.db.session.SessionLocal`` на фабрику, привязанную к
тестовой SQLite-БД, и гоняют схему целиком: seeded данные -> schema.execute_sync.
"""

import asyncio
import json
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


def _queue_day():
    """День очереди, который используют GraphQL-мутации (TZ из настроек).

    Asia/Tashkent = UTC+5: между 19:00 и 24:00 UTC день очереди уже
    СЛЕДУЮЩИЙ относительно host-даты. Тесты должны создавать очереди
    на тот же день, что и мутации, иначе ночные прогоны расходятся
    (мутация ищет очередь на TZ-день, тест создал на host-день).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


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
def gql_data(test_db, gql_session_factory, monkeypatch):
    """Seed реальных строк в тестовую БД; очистка в finally."""
    # Codex round-11 фикс: createPatient теперь ДОСТАВЛЯЕТ каноническую
    # нотификацию (worker-тред без event loop) — реальные deliveries
    # контаминировали общую session-scoped БД (contract-тесты считали
    # строки). Async-заглушка сохраняет механизм (asyncio.run в треде
    # работает, "skipped due runtime context" не появляется), но не пишет
    # deliveries.
    from app.services.notifications import notification_sender_service

    sent_notifications: list[dict] = []

    async def _stub_send_patient_registered(**kwargs):
        sent_notifications.append(kwargs)
        return True

    monkeypatch.setattr(
        notification_sender_service,
        "send_patient_registered_notification",
        _stub_send_patient_registered,
    )

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
            day=_queue_day(),
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
    # Codex P1 (round-12): 'confirmed' идёт через канонический
    # confirmation-workflow (expire-guard, confirmed_at/by, номера
    # очередей + активация) — сегодняшний визит активируется: open.
    assert data["updateVisitStatus"]["success"] is True, data["updateVisitStatus"]
    assert data["updateVisitStatus"]["visit"]["status"] == "open"

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
    assert ws["date"] == _queue_day().strftime("%Y-%m-%d")
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


def test_graphql_round6_guards(gql_data, monkeypatch):
    """Codex round-6: неактивная очередь, tagged-дубликаты, пагинация,
    аудит изменения цены — все 5 находок round-6."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.service_audit import ServiceAuditLog

    # Time-of-day gotcha (#2992): фиксируем окно онлайн-набора.
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) QUEUE_INACTIVE: деактивированная (active=False) очередь
    # без opened_at отклоняется ДО вставки (get_or_create_daily_queue
    # не фильтрует active).
    with S() as s:
        s.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == d["queue"].id
        ).update({"status": "waiting"}, synchronize_session=False)
        d["queue"].active = False
        s.merge(d["queue"])
        s.commit()

    try:
        data = _execute(
            """
            mutation($input: QueueEntryInput!) {
              joinQueue(input: $input) { success errors message }
            }
            """,
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                }
            },
        )
        join = data["joinQueue"]
        assert join["success"] is False, join
        assert "QUEUE_INACTIVE" in join["errors"], join
    finally:
        with S() as s:
            d["queue"].active = True
            s.merge(d["queue"])
            s.commit()

    # --- 2) дубликат скоупится к ВЫБРАННОЙ tagged-очереди: пациент,
    # waiting в базовой очереди, легитимно встаёт в tagged-очередь того же
    # врача (раньше находили ALREADY_IN_QUEUE по всем очередям врача).
    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) { success queueEntry { number } }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "queueTag": f"r6-{suffix}",
            }
        },
    )
    tagged_join = data["joinQueue"]
    assert tagged_join["success"] is True, tagged_join

    # а в самой tagged-очереди второй join того же пациента — дубликат
    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) { success errors }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "queueTag": f"r6-{suffix}",
            }
        },
    )
    dup = data["joinQueue"]
    assert dup["success"] is False, dup
    assert "ALREADY_IN_QUEUE" in dup["errors"], dup

    # --- 3) пагинация: per_page=0 больше не делит на ноль (clamp до 1),
    # гигантский per_page ограничен серверным максимумом 1000.
    data = _execute(
        "query { patients(pagination: { page: 1, perPage: 0 }) "
        "{ pagination { page perPage total pages } } }"
    )
    assert data["patients"]["pagination"]["perPage"] == 1

    data = _execute(
        "query { patients(pagination: { page: 0, perPage: 5000 }) "
        "{ pagination { page perPage } } }"
    )
    assert data["patients"]["pagination"]["page"] == 1
    assert data["patients"]["pagination"]["perPage"] == 1000

    # --- 4) updateServicePrice пишет ServiceAuditLog (канонический
    # ServicesApiService.update_service), а не молчаливое присваивание.
    data = _execute(
        """
        mutation($input: ServiceInput!) {
          createService(input: $input) { success service { id } }
        }
        """,
        {
            "input": {
                "name": f"Аудит-цена GQL {suffix}",
                "code": f"AUD-{suffix}",
                "price": 100000,
            }
        },
    )
    assert data["createService"]["success"] is True, data["createService"]
    audit_service_id = data["createService"]["service"]["id"]

    data = _execute(
        "mutation($id: Int!) { updateServicePrice(id: $id, price: 250000) "
        "{ success service { price } } }",
        {"id": audit_service_id},
    )
    assert data["updateServicePrice"]["success"] is True, data["updateServicePrice"]
    assert data["updateServicePrice"]["service"]["price"] == 250000.0

    with S() as s:
        audit_rows = (
            s.query(ServiceAuditLog)
            .filter(ServiceAuditLog.service_id == audit_service_id)
            .all()
        )
        assert audit_rows, "updateServicePrice must write ServiceAuditLog"
    # чистим аудит-строки (общая session-scoped БД)
    with S() as s:
        s.query(ServiceAuditLog).filter(
            ServiceAuditLog.service_id == audit_service_id
        ).delete(synchronize_session=False)
        s.commit()


def test_graphql_round7_guards(gql_data, monkeypatch):
    """Codex round-7: DOCTOR_INACTIVE, терминальные записи не съедают
    слоты, SOFT_DELETE-аудит, CALL_NEXT persistит вызывающего."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.user_profile import UserAuditLog

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) DOCTOR_INACTIVE: деактивированный врач отклоняется до
    # get_or_create_daily_queue (раньше — existence-only lookup).
    with S() as s:
        d["doctor"].active = False
        s.merge(d["doctor"])
        s.commit()
    try:
        data = _execute(
            """
            mutation($input: QueueEntryInput!) {
              joinQueue(input: $input) { success errors }
            }
            """,
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                }
            },
        )
        join = data["joinQueue"]
        assert join["success"] is False, join
        assert "DOCTOR_INACTIVE" in join["errors"], join
    finally:
        with S() as s:
            d["doctor"].active = True
            s.merge(d["doctor"])
            s.commit()

    # --- 2) ёмкость очереди считает только waiting/called: served-запись
    # не должна блокировать join при cap=1 (канонический check_queue_limits).
    with S() as s:
        d["entry"].status = "served"
        s.merge(d["entry"])
        d["queue"].max_online_entries = 1
        s.merge(d["queue"])
        s.commit()

    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R7-Cap-{suffix}",
                "firstName": "SYNTHETIC",
            }
        },
    )
    cap_patient_id = data["createPatient"]["patient"]["id"]

    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) { success errors queueEntry { number } }
        }
        """,
        {"input": {"patientId": cap_patient_id, "doctorId": d["doctor"].id}},
    )
    cap_join = data["joinQueue"]
    assert cap_join["success"] is True, cap_join  # served не съедает слот

    # восстанавливаем капу очереди (шаг 4 встаёт в ту же базовую очередь)
    with S() as s:
        d["queue"].max_online_entries = 15  # дефолт модели
        s.merge(d["queue"])
        s.commit()

    # --- 3) SOFT_DELETE-аудит: GraphQL deletePatient пишет log_critical_change
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R7-Del-{suffix}",
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

    with S() as s:
        soft_rows = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "SOFT_DELETE",
                UserAuditLog.resource_type == "patients",
                UserAuditLog.resource_id == orphan_id,
            )
            .all()
        )
        assert soft_rows, "deletePatient must write critical-change audit"

    # --- 4) CALL_NEXT persistит вызывающего через критичный аудит
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R7-Call-{suffix}",
                "firstName": "SYNTHETIC",
            }
        },
    )
    call_patient_id = data["createPatient"]["patient"]["id"]

    data = _execute(
        """
        mutation($input: QueueEntryInput!) {
          joinQueue(input: $input) { success queueEntry { id } }
        }
        """,
        {"input": {"patientId": call_patient_id, "doctorId": d["doctor"].id}},
    )
    call_join = data["joinQueue"]
    assert call_join["success"] is True, call_join
    call_entry_id = call_join["queueEntry"]["id"]

    data = _execute(
        "mutation($doctorId: Int!) { callNextPatient(doctorId: $doctorId) "
        "{ success queueEntry { id status } } }",
        {"doctorId": d["doctor"].id},
    )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    # вызывается САМАЯ ранняя waiting-запись (не обязательно call_patient —
    # cap-пациент из шага 2 тоже waiting) — берём id из ответа
    called_entry_id = call["queueEntry"]["id"]

    with S() as s:
        call_rows = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "CALL_NEXT",
                UserAuditLog.resource_type == "online_queue_entries",
                UserAuditLog.resource_id == called_entry_id,
            )
            .all()
        )
        assert call_rows, "callNextPatient must persist the caller via audit"
        assert call_rows[0].new_values.get("called_by_user_id")

    # чистим критичные аудит-строки (общая session-scoped БД)
    with S() as s:
        s.query(UserAuditLog).filter(
            UserAuditLog.action.in_(["SOFT_DELETE", "CALL_NEXT"]),
            UserAuditLog.resource_id.in_([orphan_id, called_entry_id, d["entry"].id]),
        ).delete(synchronize_session=False)
        s.commit()


def test_graphql_round8_guards(gql_data, monkeypatch):
    """Codex round-8: маскирование ФИО в аудите удаления, eligibility
    владельца врача, сидирование капы врача, CREATE-аудит визита."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.user_profile import UserAuditLog

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) описание SOFT_DELETE-аудита не содержит ФИО (initial-only)
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R8-Del-{suffix}",
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

    with S() as s:
        row = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "SOFT_DELETE",
                UserAuditLog.resource_type == "patients",
                UserAuditLog.resource_id == orphan_id,
            )
            .first()
        )
        assert row is not None
        assert f"SYNTHETIC-R8-Del-{suffix}" not in (row.description or "")
        assert f"#{orphan_id}" in (row.description or "")
        # чистим аудит-строку
        s.delete(row)
        s.commit()

    # --- 2) владелец врача неактивен -> DOCTOR_INACTIVE (канонический
    # eligibility: active Doctor + active User с doctor-ролью)
    with S() as s:
        d["user"].is_active = False
        s.merge(d["user"])
        s.commit()
    try:
        data = _execute(
            """
            mutation($input: QueueEntryInput!) {
              joinQueue(input: $input) { success errors }
            }
            """,
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r8-{suffix}",
                }
            },
        )
        join = data["joinQueue"]
        assert join["success"] is False, join
        assert "DOCTOR_INACTIVE" in join["errors"], join
    finally:
        with S() as s:
            d["user"].is_active = True
            s.merge(d["user"])
            s.commit()

    # --- 3) новая очередь получает капу ВРАЧА, а не дефолт модели 15
    with S() as s:
        d["doctor"].max_online_per_day = 7
        s.merge(d["doctor"])
        s.commit()
    try:
        data = _execute(
            """
            mutation($input: QueueEntryInput!) {
              joinQueue(input: $input) { success queueEntry { id } }
            }
            """,
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r8cap-{suffix}",
                }
            },
        )
        cap_join = data["joinQueue"]
        assert cap_join["success"] is True, cap_join
        with S() as s:
            q = (
                s.query(DailyQueue)
                .filter(
                    DailyQueue.queue_tag == f"r8cap-{suffix}",
                    DailyQueue.specialist_id == d["doctor"].id,
                )
                .first()
            )
            assert q is not None
            assert q.max_online_entries == 7  # doctor.max_online_per_day
    finally:
        with S() as s:
            d["doctor"].max_online_per_day = 15
            s.merge(d["doctor"])
            s.commit()

    # --- 4) createVisit пишет CREATE критичный аудит (как канонический
    # /visits writer)
    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success visit { id } }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "discountMode": "none",
                "serviceIds": [d["service"].id],
            }
        },
    )
    assert data["createVisit"]["success"] is True, data["createVisit"]
    r8_visit_id = data["createVisit"]["visit"]["id"]

    with S() as s:
        visit_rows = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "CREATE",
                UserAuditLog.resource_type == "visits",
                UserAuditLog.resource_id == r8_visit_id,
            )
            .all()
        )
        assert visit_rows, "createVisit must write critical-change audit"
        # чистим аудит-строку (визит удаляется фикстурной очисткой)
        for r in visit_rows:
            s.delete(r)
        s.commit()


def test_graphql_round9_masked_audits(gql_data):
    """Codex round-9: create/updatePatient аудит — initial-only, без ФИО
    в description (PatientService — канонический путь REST+GraphQL)."""
    from app.db import session as db_session_module
    from app.models.user_profile import UserAuditLog

    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R9-{suffix}",
                "firstName": "SYNTHETIC",
            }
        },
    )
    assert data["createPatient"]["success"] is True, data["createPatient"]
    pid = data["createPatient"]["patient"]["id"]

    data = _execute(
        """
        mutation($id: Int!, $input: PatientUpdateInput!) {
          updatePatient(id: $id, input: $input) { success }
        }
        """,
        {"id": pid, "input": {"address": "ул. R9, 1"}},
    )
    assert data["updatePatient"]["success"] is True, data["updatePatient"]

    with S() as s:
        rows = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.resource_type == "patients",
                UserAuditLog.resource_id == pid,
                UserAuditLog.action.in_(["CREATE", "UPDATE"]),
            )
            .all()
        )
        by_action = {r.action: r for r in rows}
        assert "CREATE" in by_action and "UPDATE" in by_action
        for action, row in by_action.items():
            desc = row.description or ""
            assert f"SYNTHETIC-R9-{suffix}" not in desc, (action, desc)
            assert f"#{pid}" in desc, (action, desc)
        # чистим аудит-строки (пациента удалит фикстурная очистка)
        for r in rows:
            s.delete(r)
        s.commit()


def test_graphql_round10(gql_data):
    """Codex round-10: PHI маскируется в JSON-снапшотах аудита;
    soft-deleted пациент не отдаёт PHI в nested-результатах."""
    from app.db import session as db_session_module
    from app.models.user_profile import UserAuditLog

    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) снапшоты new_values/old_values маскируются (pii_masker)
    data = _execute(
        """
        mutation($input: PatientInput!) {
          createPatient(input: $input) { success patient { id } }
        }
        """,
        {
            "input": {
                "lastName": f"SYNTHETIC-R10-{suffix}",
                "firstName": "SYNTHETIC",
                "phone": f"+99890{str(int(suffix, 16) % 10**7).zfill(7)}",
                "email": f"r10-{suffix}@example.com",
            }
        },
    )
    assert data["createPatient"]["success"] is True, data["createPatient"]
    pid = data["createPatient"]["patient"]["id"]

    with S() as s:
        row = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "CREATE",
                UserAuditLog.resource_type == "patients",
                UserAuditLog.resource_id == pid,
            )
            .first()
        )
        assert row is not None
        nv = row.new_values or {}
        # ФИО — инициалы, не plaintext
        assert nv.get("last_name") != f"SYNTHETIC-R10-{suffix}"
        assert nv.get("last_name", "").endswith(".")
        # телефон замаскирован (•••), не исходный
        assert "•" in (nv.get("phone") or "")
        assert nv.get("phone") != f"+99890{str(int(suffix, 16) % 10**7).zfill(7)}"
        # email маскирован
        assert (nv.get("email") or "").startswith("r")
        assert "•" in (nv.get("email") or "")
        # чистим аудит-строку
        s.delete(row)
        s.commit()

    # --- 2) soft-deleted пациент скрыт из nested (appointments.items.patient)
    with S() as s:
        d["patient"].is_deleted = True
        s.merge(d["patient"])
        s.commit()
    try:
        data = _execute(
            "query { appointments { items { id patient { id fullName phone } } } }"
        )
        items = data["appointments"]["items"]
        target = next((i for i in items if i["id"] == d["appointment"].id), None)
        assert target is not None
        # запись осталась (история), но PHI пациента подавлено
        assert target["patient"] is None
    finally:
        with S() as s:
            d["patient"].is_deleted = False
            s.merge(d["patient"])
            s.commit()


def test_graphql_round11(gql_data, caplog):
    """Codex round-11: регистрация-нотификация не скипается (worker-тред,
    без активного event loop); visit-снапшот аудита маскируется."""
    import logging

    from app.db import session as db_session_module
    from app.models.user_profile import UserAuditLog

    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) createPatient из async-резолвера: canonical delivery НЕ скипается
    with caplog.at_level(logging.WARNING, logger="app.services.patient_service"):
        data = _execute(
            """
            mutation($input: PatientInput!) {
              createPatient(input: $input) { success patient { id } }
            }
            """,
            {
                "input": {
                    "lastName": f"SYNTHETIC-R11-{suffix}",
                    "firstName": "SYNTHETIC",
                }
            },
        )
    assert data["createPatient"]["success"] is True, data["createPatient"]
    assert not any(
        "skipped due runtime context" in (r.getMessage() or "") for r in caplog.records
    ), "patient-registered delivery must not be skipped for GraphQL creates"

    # --- 2) visit-снапшот: clinical notes -> [REDACTED] в new_values
    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success visit { id } }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "discountMode": "none",
                "serviceIds": [d["service"].id],
                "notes": f"Жалобы R11 {suffix}: боль, тел +998901112233",
            }
        },
    )
    assert data["createVisit"]["success"] is True, data["createVisit"]
    r11_visit_id = data["createVisit"]["visit"]["id"]

    with S() as s:
        row = (
            s.query(UserAuditLog)
            .filter(
                UserAuditLog.action == "CREATE",
                UserAuditLog.resource_type == "visits",
                UserAuditLog.resource_id == r11_visit_id,
            )
            .first()
        )
        assert row is not None
        nv = row.new_values or {}
        # notes — full-redact; текст/телефон не в plaintext
        assert nv.get("notes") == "[REDACTED]", nv.get("notes")
        assert suffix not in json.dumps(nv, ensure_ascii=False, default=str)
        # чистим аудит-строку (визит удалит фикстурная очистка)
        s.delete(row)
        s.commit()


def test_graphql_round12(gql_data, monkeypatch):
    """Codex round-12: callNext без тега детерминированно берёт очередь
    с waiting-кандидатом; all_free-заявка шлёт нотификацию.
    Round-13 уточнение: порядок канонический (по времени прибытия),
    а не по локальному номеру очереди."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.services.notifications import notification_sender_service

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) две активные очереди врача: порядок по ВРЕМЕНИ ПРИБЫТИЯ,
    # а не по локальному номеру (round-13): #5, ждущий час, выигрывает
    # у свежего #1 соседней tagged-очереди.
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    with S() as s:
        q2 = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r12-{suffix}",
            active=True,
        )
        s.add(q2)
        s.flush()
        e2 = OnlineQueueEntry(
            queue_id=q2.id,
            number=1,
            patient_id=d["patient"].id,
            status="waiting",
            queue_time=now,  # свежий #1
        )
        s.add(e2)
        d["entry"].number = 5
        d["entry"].queue_time = now - timedelta(hours=1)  # #5 ждёт час
        s.merge(d["entry"])
        s.commit()
        base_entry_id = d["entry"].id

    data = _execute(
        "mutation($doctorId: Int!) { callNextPatient(doctorId: $doctorId) "
        "{ success queueEntry { id } } }",
        {"doctorId": d["doctor"].id},
    )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    # канонический порядок: самое раннее ПРИБЫТИЕ (queue_time) —
    # вызван #5 из базовой очереди, а не свежий #1 tagged-очереди
    assert call["queueEntry"]["id"] == base_entry_id

    # --- 2) all_free без автоаппрува -> approver-нотификация после коммита
    all_free_calls: list[dict] = []

    async def _stub_all_free(**kwargs):
        all_free_calls.append(kwargs)
        return True

    monkeypatch.setattr(
        notification_sender_service,
        "send_all_free_request_notification",
        _stub_all_free,
    )

    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success visit { id } }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "discountMode": "all_free",
                "serviceIds": [d["service"].id],
            }
        },
    )
    assert data["createVisit"]["success"] is True, data["createVisit"]
    created_visit_id = data["createVisit"]["visit"]["id"]
    assert len(all_free_calls) == 1, all_free_calls
    assert all_free_calls[0]["visit"].id == created_visit_id


def test_graphql_round13(gql_data, monkeypatch):
    """Codex round-13: (1) канонический порядок вызова без тега —
    priority DESC, затем coalesce(queue_time, created_at) ASC (номера
    локальны для очереди и НЕ отражают порядок прибытия); (2) joinQueue
    на пустой очереди врача со start_number_online != 1 выдаёт билет
    со стартового номера врача, а не всегда #1."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.patient import Patient as PatientModel

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)

    # --- 0) изоляция: терминальный статус всем waiting-записям врача
    # за сегодня (левые waiting от предыдущих тестов не должны влиять)
    with S() as s:
        doc_queue_ids = [
            q.id
            for q in s.query(DailyQueue).filter(
                DailyQueue.specialist_id == d["doctor"].id,
                DailyQueue.day == _queue_day(),
            )
        ]
        s.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id.in_(doc_queue_ids),
            OnlineQueueEntry.status == "waiting",
        ).update({"status": "cancelled"}, synchronize_session=False)
        s.commit()

    # --- 1) старое прибытие (большой локальный номер) против свежего #1:
    # выигрывает РАННЕЕ прибытие (e_old: ждёт час), не минимальный номер
    with S() as s:
        qa = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r13a-{suffix}",
            active=True,
        )
        qb = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r13b-{suffix}",
            active=True,
        )
        s.add_all([qa, qb])
        s.flush()
        e_old = OnlineQueueEntry(
            queue_id=qa.id,
            number=5,
            patient_id=d["patient"].id,
            status="waiting",
            queue_time=now - timedelta(hours=1),
        )
        e_fresh = OnlineQueueEntry(
            queue_id=qb.id,
            number=1,
            patient_id=d["patient"].id,
            status="waiting",
            queue_time=now,
        )
        s.add_all([e_old, e_fresh])
        s.commit()
        e_old_id = e_old.id

    data = _execute(
        "mutation($doctorId: Int!) { callNextPatient(doctorId: $doctorId) "
        "{ success queueEntry { id } } }",
        {"doctorId": d["doctor"].id},
    )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    assert (
        call["queueEntry"]["id"] == e_old_id
    ), "hour-old #5 must win over freshly joined #1 in another tag"

    # --- 2) priority-запись в соседней очереди обгоняет обычную (fresh) —
    # priority DESC доминирует над временем прибытия
    with S() as s:
        qc = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r13c-{suffix}",
            active=True,
        )
        s.add(qc)
        s.flush()
        e_vip = OnlineQueueEntry(
            queue_id=qc.id,
            number=10,
            patient_id=d["patient"].id,
            status="waiting",
            priority=2,  # VIP
            queue_time=now,
        )
        s.add(e_vip)
        s.commit()
        e_vip_id = e_vip.id

    data = _execute(
        "mutation($doctorId: Int!) { callNextPatient(doctorId: $doctorId) "
        "{ success queueEntry { id } } }",
        {"doctorId": d["doctor"].id},
    )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    assert (
        call["queueEntry"]["id"] == e_vip_id
    ), "priority entry must be called before regular waiting entries"

    # --- 3) joinQueue: пустая очередь врача со start_number_online=3
    # начинает с билета #3 (не #1), следующая — #4
    second_patient = None
    original_start = d["doctor"].start_number_online
    try:
        with S() as s:
            second_patient = PatientModel(
                last_name=f"SYNTHETIC-Petrov-{suffix}",
                first_name="SYNTHETIC",
                middle_name="SYNTHETIC",
                phone=f"DEV-DEMO-{suffix}-2",
                email=f"synthetic-{suffix}-2@example.com",
            )
            s.add(second_patient)
            d["doctor"].start_number_online = 3
            s.merge(d["doctor"])
            s.commit()

        data = _execute(
            """mutation($input: QueueEntryInput!) { joinQueue(input: $input) {
            success message queueEntry { id number } } }""",
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r13d-{suffix}",
                }
            },
        )
        join = data["joinQueue"]
        assert join["success"] is True, join
        assert join["queueEntry"]["number"] == 3, join

        data = _execute(
            """mutation($input: QueueEntryInput!) { joinQueue(input: $input) {
            success message queueEntry { id number } } }""",
            {
                "input": {
                    "patientId": second_patient.id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r13d-{suffix}",
                }
            },
        )
        join = data["joinQueue"]
        assert join["success"] is True, join
        assert join["queueEntry"]["number"] == 4, join
    finally:
        with S() as s:
            doc = s.query(Doctor).filter(Doctor.id == d["doctor"].id).first()
            if doc is not None:
                doc.start_number_online = original_start
                s.commit()


def test_sessions_are_closed_after_resolver(gql_session_factory):
    """with get_db_session() закрывает сессию: соединения не утекают."""
    _execute("{ patients { pagination { total } } }")
    engine = gql_session_factory.kw["bind"]
    # Утечка сессий (P0-1) оставляла checked-out соединения после запроса.
    assert engine.pool.checkedout() == 0, "pool leaked connections after resolver"


def test_graphql_round14(gql_data, monkeypatch):
    """Codex round-14: (1) лоченный re-fetch очереди перечитывает stale
    identity-map (populate_existing) — дезактивация между get_or_create и
    локом видна -> QUEUE_INACTIVE; (2) отказ пост-коммит аудита createVisit
    НЕ возвращает INTERNAL_ERROR (визит уже durable); (3) callNext: весь
    sync-DB флоу в одном worker-треде — notify через sync-обёртку,
    display-payload собирается в impl, отправка на event loop."""
    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.services.display_websocket import get_display_manager

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) populate_existing на лоченном re-fetch: дезактивация очереди
    # между get_or_create_daily_queue и with_for_update видна мутации.
    # Патч изолирован в context()-сабменеджере.
    with monkeypatch.context() as m:
        original_goc = gql_mutations.crud_queue.get_or_create_daily_queue

        def _goc_deactivate(db, **kwargs):
            queue = original_goc(db, **kwargs)
            with S() as s2:
                stale = s2.query(DailyQueue).filter(DailyQueue.id == queue.id).first()
                stale.active = False
                s2.commit()
            return queue

        m.setattr(
            gql_mutations.crud_queue, "get_or_create_daily_queue", _goc_deactivate
        )
        data = _execute(
            """mutation($input: QueueEntryInput!) { joinQueue(input: $input) {
            success message errors queueEntry { id } } }""",
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r14a-{suffix}",
                }
            },
        )
    join = data["joinQueue"]
    assert join["success"] is False, join
    assert join["errors"] == ["QUEUE_INACTIVE"], join

    # --- 2) отказ пост-коммит аудита createVisit не роняет мутацию
    def _raiser(**kwargs):
        raise RuntimeError("audit boom")

    with monkeypatch.context() as m:
        m.setattr(gql_mutations, "log_critical_change", _raiser)
        data = _execute(
            """
            mutation($input: VisitInput!) {
              createVisit(input: $input) { success message visit { id } }
            }
            """,
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "serviceIds": [d["service"].id],
                }
            },
        )
    created = data["createVisit"]
    assert created["success"] is True, created
    durable_visit_id = created["visit"]["id"]
    with S() as s:
        assert (
            s.query(Visit).filter(Visit.id == durable_visit_id).first() is not None
        ), "visit must be durable despite audit failure"

    # --- 3) callNext: sync-notify-обёртка + display payload из impl
    notify_calls: list = []

    def _notify_recorder(db, entry, cabinet_number=None):
        notify_calls.append((entry.id, cabinet_number))
        return {"sent": 0}

    manager = get_display_manager()
    sent_messages: list = []

    async def _send_recorder(self, call_message, board_ids=None):
        sent_messages.append(call_message)

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with S() as s:
        q14 = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r14b-{suffix}",
            active=True,
        )
        s.add(q14)
        s.flush()
        e14 = OnlineQueueEntry(
            queue_id=q14.id,
            number=7,
            patient_id=d["patient"].id,
            status="waiting",
            queue_time=now,
        )
        s.add(e14)
        s.commit()
        e14_id = e14.id

    with monkeypatch.context() as m3:
        m3.setattr(gql_mutations, "notify_patient_called_sync", _notify_recorder)
        m3.setattr(type(manager), "broadcast_patient_call_data", _send_recorder)
        data = _execute(
            "mutation($doctorId: Int!, $tag: String) { callNextPatient(doctorId: "
            "$doctorId, queueTag: $tag) { success message queueEntry { id number } "
            "} }",
            {"doctorId": d["doctor"].id, "tag": f"r14b-{suffix}"},
        )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    assert call["queueEntry"]["id"] == e14_id, call
    assert call["queueEntry"]["number"] == 7, call
    # sync-notify вызвана ровно один раз в worker-треде
    assert len(notify_calls) == 1, notify_calls
    assert notify_calls[0][0] == e14_id, notify_calls
    # display payload собран в impl и отправлен через новый метод
    assert len(sent_messages) == 1, sent_messages
    assert sent_messages[0]["data"]["queue_number"] == 7, sent_messages
    assert sent_messages[0]["type"] == "patient_call", sent_messages


def test_graphql_round15(gql_data, monkeypatch, caplog):
    """Codex round-15: (1) joinQueue повторно проверяет eligibility врача
    ПОСЛЕ коммита создания очереди (внутренний commit отпускает лок строки
    врача и advisory-лок); (2) отказ критичного аудита callNext после
    durably-закоммиченного перехода waiting->called НЕ возвращает
    INTERNAL_ERROR (retry клиента вызвал бы второго пациента); (3)
    createPatient: doc_number в debug-логе маскируется (full-redact);
    (4) updatePatient отклоняет дубликат doc_number другого пациента
    (unchanged value разрешён); (5) createVisit без visitDate дефолтит
    дату на день конфигурированной таймзоны, а не host-день; (6)
    updateServicePrice атрибутирует ServiceAuditLog аутентифицированному
    актору (user_id), а не None."""
    import logging
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.service_audit import ServiceAuditLog
    from app.services.display_websocket import get_display_manager

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) joinQueue: дезактивация врача в окне внутреннего коммита
    # get_or_create_daily_queue -> повторная eligibility-проверка видит
    # свежее состояние и отклоняет join (DOCTOR_INACTIVE).
    with monkeypatch.context() as m:
        original_goc = gql_mutations.crud_queue.get_or_create_daily_queue

        def _goc_deactivate_doctor(db, **kwargs):
            queue = original_goc(db, **kwargs)
            with S() as s2:
                d2 = s2.query(Doctor).filter(Doctor.id == d["doctor"].id).first()
                d2.active = False
                s2.commit()
            return queue

        m.setattr(
            gql_mutations.crud_queue,
            "get_or_create_daily_queue",
            _goc_deactivate_doctor,
        )
        data = _execute(
            """mutation($input: QueueEntryInput!) { joinQueue(input: $input) {
            success message errors queueEntry { id } } }""",
            {
                "input": {
                    "patientId": d["patient"].id,
                    "doctorId": d["doctor"].id,
                    "queueTag": f"r15a-{suffix}",
                }
            },
        )
    join = data["joinQueue"]
    assert join["success"] is False, join
    assert join["errors"] == ["DOCTOR_INACTIVE"], join
    with S() as s:
        queue_id = (
            s.query(DailyQueue)
            .filter(
                DailyQueue.day == _queue_day(),
                DailyQueue.queue_tag == f"r15a-{suffix}",
            )
            .first()
            .id
        )
        assert (
            s.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
            == 0
        ), "талон недоступному врачу выдан не должен быть"

    # --- 2) callNext: отказ пост-коммит аудита сохраняет success
    def _raiser(**kwargs):
        raise RuntimeError("audit boom")

    notify_calls: list = []

    def _notify_recorder(db, entry, cabinet_number=None):
        notify_calls.append(entry.id)
        return {"sent": 0}

    manager = get_display_manager()

    async def _send_recorder(self, call_message, board_ids=None):
        return None

    now = datetime.now(UTC)
    with S() as s:
        q15 = DailyQueue(
            day=_queue_day(),
            specialist_id=d["doctor"].id,
            queue_tag=f"r15b-{suffix}",
            active=True,
        )
        s.add(q15)
        s.flush()
        e15 = OnlineQueueEntry(
            queue_id=q15.id,
            number=11,
            patient_id=d["patient"].id,
            status="waiting",
            queue_time=now,
        )
        s.add(e15)
        s.commit()
        e15_id = e15.id

    with monkeypatch.context() as m:
        m.setattr(gql_mutations, "log_critical_change", _raiser)
        m.setattr(gql_mutations, "notify_patient_called_sync", _notify_recorder)
        m.setattr(type(manager), "broadcast_patient_call_data", _send_recorder)
        data = _execute(
            "mutation($doctorId: Int!, $tag: String) { callNextPatient(doctorId: "
            "$doctorId, queueTag: $tag) { success message queueEntry { id number } "
            "} }",
            {"doctorId": d["doctor"].id, "tag": f"r15b-{suffix}"},
        )
    call = data["callNextPatient"]
    assert call["success"] is True, call
    assert call["queueEntry"]["id"] == e15_id, call
    # уведомления не пропущены (durably вызванному пациенту они доставлены)
    assert notify_calls == [e15_id], notify_calls
    with S() as s:
        assert (
            s.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == e15_id).first()
            is not None
        )

    # --- 3) createPatient: doc_number в debug-логе маскируется
    doc_number = f"AA{int(suffix, 16) % 10**10:010d}"
    with caplog.at_level(logging.DEBUG, logger="app.services.patient_service"):
        data = _execute(
            """
            mutation($input: PatientInput!) {
              createPatient(input: $input) { success patient { id } }
            }
            """,
            {
                "input": {
                    "lastName": f"SYNTHETIC-R15-{suffix}",
                    "firstName": "SYNTHETIC",
                    "phone": f"+99877{str(int(suffix, 16) % 10**7).zfill(7)}",
                    "docType": "passport",
                    "docNumber": doc_number,
                }
            },
        )
    created = data["createPatient"]
    assert created["success"] is True, created
    r15_patient_id = created["patient"]["id"]
    doc_records = [r for r in caplog.records if "[FIX:ADM-05]" in r.getMessage()]
    assert doc_records, "debug-лог документа ожидается"
    # номер документа не логируется НИ В КАКОМ виде (CodeQL: clear-text
    # logging flagged even the mask_pii variant) — только факт наличия
    rec_extra = doc_records[-1].__dict__
    assert rec_extra["has_doc_number"] is True
    assert "doc_number" not in rec_extra
    assert doc_number not in caplog.text

    # --- 4) updatePatient: дубликат doc_number другого пациента -> 400;
    # неизменённое значение того же пациента разрешено.
    data = _execute(
        """
        mutation($id: Int!, $input: PatientUpdateInput!) {
          updatePatient(id: $id, input: $input) { success errors message }
        }
        """,
        {
            "id": d["patient"].id,
            "input": {"docType": "passport", "docNumber": doc_number},
        },
    )
    upd = data["updatePatient"]
    assert upd["success"] is False, upd
    assert upd["errors"] == ["DOC_NUMBER_EXISTS"], upd

    data = _execute(
        """
        mutation($id: Int!, $input: PatientUpdateInput!) {
          updatePatient(id: $id, input: $input) { success errors patient { id } }
        }
        """,
        {
            "id": r15_patient_id,
            "input": {"docType": "passport", "docNumber": doc_number},
        },
    )
    assert data["updatePatient"]["success"] is True, data["updatePatient"]

    # --- 5) createVisit без visitDate -> день конфигурированной таймзоны
    data = _execute(
        """
        mutation($input: VisitInput!) {
          createVisit(input: $input) { success visit { id visitDate } }
        }
        """,
        {
            "input": {
                "patientId": d["patient"].id,
                "doctorId": d["doctor"].id,
                "serviceIds": [d["service"].id],
            }
        },
    )
    visit = data["createVisit"]
    assert visit["success"] is True, visit
    tz_day = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    assert visit["visit"] is not None
    with S() as s:
        v15 = s.query(Visit).filter(Visit.id == visit["visit"]["id"]).first()
        assert v15 is not None
        assert v15.visit_date == tz_day, (
            f"visitDate={v15.visit_date}, TZ-day={tz_day} — дефолт должен "
            "браться из конфигурированной таймзоны, а не host date.today()"
        )

    # --- 6) updateServicePrice: ServiceAuditLog.user_id == актор
    data = _execute(
        "mutation($id: Int!) { updateServicePrice(id: $id, price: 275000) "
        "{ success service { id price } } }",
        {"id": d["service"].id},
    )
    price = data["updateServicePrice"]
    assert price["success"] is True, price
    admin = gql_data_ctx["admin_user"]
    with S() as s:
        audit_row = (
            s.query(ServiceAuditLog)
            .filter(ServiceAuditLog.service_id == d["service"].id)
            .order_by(ServiceAuditLog.id.desc())
            .first()
        )
        assert audit_row is not None, "service audit row expected"
        assert (
            audit_row.user_id == admin.id
        ), f"audit user_id={audit_row.user_id}, expected {admin.id}"


def test_graphql_round16(gql_data, gql_session_factory, test_db, monkeypatch, caplog):
    """Codex round-16: (1) имена пациента в debug-логе нормализации заменены
    длинами (PII, AGENTS.md L391-408); (2) отказ пост-коммит аудита
    deletePatient НЕ возвращает INTERNAL_ERROR после durably-коммита
    soft delete; (3) createService атрибутирует ServiceAuditLog актору;
    (4) дневные счётчики статистики считаются по дне конфигурированной
    таймзоны; (5) appointments eager-грузит patient/doctor/doctor.user
    (нет N+1 на странице)."""
    import logging
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from sqlalchemy import event

    from app.db import session as db_session_module
    from app.graphql import mutations as gql_mutations
    from app.models.service_audit import ServiceAuditLog

    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    d = gql_data
    suffix = d["suffix"]
    S = db_session_module.SessionLocal

    # --- 1) createPatient: нормализация имени логирует ТОЛЬКО длины
    raw_last = f"SYNTHETIC-R16-{suffix}"
    with caplog.at_level(logging.DEBUG, logger="app.services.patient_service"):
        data = _execute(
            """
            mutation($input: PatientInput!) {
              createPatient(input: $input) { success patient { id } }
            }
            """,
            {
                "input": {
                    "lastName": raw_last,
                    "firstName": "SYNTHETIC16",
                    "phone": f"+99871{str(int(suffix, 16) % 10**7).zfill(7)}",
                }
            },
        )
    created = data["createPatient"]
    assert created["success"] is True, created
    r16_patient_id = created["patient"]["id"]
    norm_records = [r for r in caplog.records if "Нормализация имени" in r.getMessage()]
    assert norm_records, "debug-лог нормализации ожидается"
    assert "SYNTHETIC16" not in norm_records[0].getMessage()
    assert raw_last not in caplog.text, "сырая фамилия попала в лог"

    # --- 2) deletePatient: отказ аудита сохраняет success (soft delete
    # уже durably закоммичен внутри crud)
    def _raiser(**kwargs):
        raise RuntimeError("audit boom")

    with monkeypatch.context() as m:
        m.setattr(gql_mutations, "log_critical_change", _raiser)
        data = _execute(
            "mutation($id: Int!) { deletePatient(id: $id) { success errors message } }",
            {"id": r16_patient_id},
        )
    deleted = data["deletePatient"]
    assert deleted["success"] is True, deleted
    with S() as s:
        row = s.query(Patient).filter(Patient.id == r16_patient_id).first()
        assert row is not None and row.is_deleted is True

    # --- 3) createService: ServiceAuditLog.user_id == актор
    data = _execute(
        """
        mutation($input: ServiceInput!) {
          createService(input: $input) { success service { id code } }
        }
        """,
        {
            "input": {
                "name": f"R16 Service {suffix}",
                "code": f"R16S-{suffix}",
                "price": 50000,
            }
        },
    )
    svc = data["createService"]
    assert svc["success"] is True, svc
    admin = gql_data_ctx["admin_user"]
    with S() as s:
        audit_row = (
            s.query(ServiceAuditLog)
            .filter(ServiceAuditLog.service_id == svc["service"]["id"])
            .order_by(ServiceAuditLog.id.desc())
            .first()
        )
        assert audit_row is not None and audit_row.action == "create"
        assert (
            audit_row.user_id == admin.id
        ), f"audit user_id={audit_row.user_id}, expected {admin.id}"

    # --- 4) дневные счётчики статистики — по TZ-дню (та же формула, что
    # и у мутаций; регрессия на date.today() ловится в ночном окне
    # 19:00-24:00 UTC)
    tz_day = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    with S() as s:
        v16 = Visit(
            patient_id=d["patient"].id,
            doctor_id=d["doctor"].id,
            status="scheduled",
            visit_date=tz_day,
        )
        s.add(v16)
        s.commit()
    data = _execute(
        "query($docId: Int!) { visitStats { total today } "
        "doctorStats(doctorId: $docId) { totalVisits todayVisits } }",
        {"docId": d["doctor"].id},
    )
    assert data["visitStats"]["today"] >= 1, data["visitStats"]
    assert data["doctorStats"]["todayVisits"] >= 1, data["doctorStats"]

    # --- 5) appointments: eager-load (нет N+1 по patient на страницу)
    with S() as s:
        for i in range(15):
            p = Patient(
                last_name=f"SYNTHETIC-R16P-{suffix}-{i}",
                first_name="SYNTHETIC",
                middle_name="SYNTHETIC",
                phone=f"DEV-R16-{suffix}-{i}",
            )
            s.add(p)
            s.flush()
            s.add(
                Appointment(
                    patient_id=p.id,
                    doctor_id=d["doctor"].id,
                    appointment_date=tz_day,
                    status="scheduled",
                )
            )
        s.commit()

    counter = {"selects": 0}

    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["selects"] += 1

    bind = (
        gql_session_factory.kw["bind"]
        if hasattr(gql_session_factory, "kw")
        else test_db
    )
    event.listen(bind, "before_cursor_execute", _count)
    try:
        data = _execute(
            """query { appointments(pagination: { page: 1, perPage: 1000 }) {
                 items { id patient { id } doctor { id } } pagination { total } } }"""
        )
    finally:
        event.remove(bind, "before_cursor_execute", _count)
    items = data["appointments"]["items"]
    assert data["appointments"]["pagination"]["total"] >= 15
    assert len(items) >= 15
    # без eager-load: 1 + ~3*N ленивых SELECT-ов; с selectinload — константа
    assert (
        counter["selects"] <= 10
    ), f"N+1: {counter['selects']} SELECTs на страницу из {len(items)} строк"
