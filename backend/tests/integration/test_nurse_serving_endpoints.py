"""NURSE-V2 N2-3 — endpoint-level contract for the nurse serving plane.

The auth matrix mirrors the N2-2 endpoint suite: anonymous 401, wrong
role 403, deactivated Nurse with an unexpired JWT 403 (the
``require_active_roles`` fail-closed factory), and the data-level
authorization (403 without an ACTIVE assignment) — plus a full happy
path through the REAL router: station board -> atomic call-next ->
start (visit resolve/link) -> execution create -> complete with the
last-completer flip, and the ledger join proof (the PR #3333 audit
identity contract: the serving mutations and denials surface in ONE
``get_by_resource()`` history).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.service_execution import ServiceExecution
from app.models.user import User
from app.models.visit import Visit, VisitService

_BASE = "/api/v1/nurse/serving"

pytestmark = pytest.mark.integration


def _user(db: Session, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password="x",
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _resource(db: Session, code: str = "procedures") -> QueueResource:
    resource = QueueResource(
        code=code,
        queue_tag=f"tag_{code}",
        display_name=f"Resource {code}",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
        default_cabinet="c1",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def _assignment(
    db: Session, nurse: User, resource: QueueResource, *, active: bool = True
) -> NurseWorkplaceAssignment:
    row = NurseWorkplaceAssignment(
        user_id=nurse.id,
        queue_resource_id=resource.id,
        is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _queue(db: Session, resource: QueueResource) -> DailyQueue:
    queue = DailyQueue(
        day=clinic_today(db),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
        start_number=1,
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue


def _entry(
    db: Session, queue: DailyQueue, number: int, patient: Patient
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        patient_name=patient.first_name,
        status="waiting",
        source="desk",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _patient(db: Session, name: str) -> Patient:
    patient = Patient(first_name=name, last_name="Endpoint")
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _headers(db: Session, user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


# ----------------------------------------------------------------------------
# auth matrix (the fail-closed contract)
# ----------------------------------------------------------------------------


def test_anonymous_is_401(client: TestClient, db_session: Session) -> None:
    response = client.get(f"{_BASE}/workplaces")
    assert response.status_code == 401, response.text


def test_wrong_role_is_403(client: TestClient, db_session: Session) -> None:
    doctor = _user(db_session, "n23_ep_doctor", "Doctor")
    resource = _resource(db_session)
    response = client.get(
        f"{_BASE}/queue-resources/{resource.id}/entries",
        headers=_headers(db_session, doctor),
    )
    assert response.status_code == 403, response.text


def test_deactivated_nurse_token_gets_403_and_writes_nothing(
    client: TestClient, db_session: Session
) -> None:
    """The N2-2 fail-closed factory regression, serving-plane edition."""
    nurse = _user(db_session, "n23_ep_deactivated", "Nurse")
    resource = _resource(db_session)
    _assignment(db_session, nurse, resource)
    _queue(db_session, resource)
    headers = _headers(db_session, nurse)
    nurse.is_active = False
    db_session.commit()
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers
    )
    assert response.status_code == 403, response.text
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.status == "called")
        .count()
        == 0
    )


def test_no_assignment_is_403_even_for_superuser(
    client: TestClient, db_session: Session
) -> None:
    """Deny-by-default DATA authorization: the role bypass does not carry.

    A superuser passes the role gate (the standard require_roles
    contract) but the serving plane requires the assignment ROW —
    Admin keeps its own resource-queue surfaces.
    """
    su = _user(db_session, "n23_ep_superuser", "Admin")
    su.is_superuser = True
    db_session.commit()
    resource = _resource(db_session)
    _queue(db_session, resource)
    response = client.get(
        f"{_BASE}/queue-resources/{resource.id}/entries",
        headers=_headers(db_session, su),
    )
    assert response.status_code == 403, response.text
    assert "назначени" in response.json()["detail"]


# ----------------------------------------------------------------------------
# happy path e2e through the real router
# ----------------------------------------------------------------------------


def test_full_serving_flow_with_last_completer_flip(
    client: TestClient, db_session: Session
) -> None:
    nurse = _user(db_session, "n23_ep_flow_nurse", "Nurse")
    resource = _resource(db_session)
    _assignment(db_session, nurse, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "Flow")
    entry = _entry(db_session, queue, 1, patient)
    headers = _headers(db_session, nurse)

    # 1. The workplaces list (self-scope).
    response = client.get(f"{_BASE}/workplaces", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["queue_resource_id"] == resource.id
    assert body["items"][0]["effective_cabinet"] == "c1"

    # 2. The station board sees the waiting patient.
    response = client.get(
        f"{_BASE}/queue-resources/{resource.id}/entries", headers=headers
    )
    assert response.status_code == 200, response.text
    board = response.json()
    assert board["counts"]["waiting"] == 1
    assert board["waiting"][0]["id"] == entry.id
    assert board["my_entry"] is None

    # 3. Atomic call-next.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers
    )
    assert response.status_code == 200, response.text
    claim = response.json()
    assert claim["idempotent"] is False
    assert claim["entry"]["id"] == entry.id
    assert claim["entry"]["is_my_claim"] is True

    # 4. Repeat POST = the SAME entry (the §6 idempotency).
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["idempotent"] is True
    assert response.json()["entry"]["id"] == entry.id

    # 5. Start serving: visit resolves and links.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/start",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    started = response.json()
    assert started["status"] == "in_progress"
    visit_id = started["visit_id"]
    assert visit_id is not None
    visit = db_session.get(Visit, visit_id)
    assert visit is not None
    assert visit.patient_id == patient.id
    assert visit.department == resource.queue_tag
    assert visit.status == "in_progress"

    # 6. Station-routed services of the visit.
    station_service = Service(
        code="EPROC1",
        name="Endpoint procedure",
        queue_tag=resource.queue_tag,
        requires_doctor=False,
        active=True,
    )
    doctor_service = Service(
        code="ECONS1",
        name="Endpoint consult",
        queue_tag="therapy",
        requires_doctor=True,
        active=True,
    )
    db_session.add_all([station_service, doctor_service])
    db_session.commit()
    db_session.refresh(station_service)
    db_session.refresh(doctor_service)
    vs_station = VisitService(
        visit_id=visit_id,
        service_id=station_service.id,
        code=station_service.code,
        name=station_service.name,
        qty=1,
    )
    vs_doctor = VisitService(
        visit_id=visit_id,
        service_id=doctor_service.id,
        code=doctor_service.code,
        name=doctor_service.name,
        qty=1,
    )
    db_session.add_all([vs_station, vs_doctor])
    db_session.commit()
    db_session.refresh(vs_station)
    db_session.refresh(vs_doctor)

    # The board's my_entry lists ONLY the station-routed service.
    response = client.get(
        f"{_BASE}/queue-resources/{resource.id}/entries", headers=headers
    )
    services = response.json()["my_entry"]["services"]
    assert [s["visit_service_id"] for s in services] == [vs_station.id]
    assert services[0]["pending"] is True

    # 7. Foreign/doctor-routed service is rejected by the boundary.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs_doctor.id},
        headers=headers,
    )
    assert response.status_code == 400, response.text

    # 8. Start the station execution (201), repeat = 200 no-op.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs_station.id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    execution = response.json()
    assert execution["attempt_no"] == 1
    assert execution["queue_entry_id"] == entry.id

    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs_station.id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == execution["id"]

    # 9. Complete: the last (only) station service flips the entry.
    response = client.post(
        f"{_BASE}/executions/{execution['id']}/complete", headers=headers
    )
    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["status"] == "completed"
    assert completed["performed_by_user_id"] == nurse.id
    assert completed["entry_served"] is True
    assert completed["entry_served_by_user_id"] == nurse.id

    db_session.refresh(entry)
    assert entry.status == "served"
    assert entry.served_by_user_id == nurse.id
    assert entry.served_at is not None

    # The visit itself stays open for the doctor lifecycle (the §5
    # forbidden list: one performed procedure never closes the visit).
    db_session.refresh(visit)
    assert visit.status == "in_progress"


def test_execution_conflict_matrix_through_router(
    client: TestClient, db_session: Session
) -> None:
    nurse_a = _user(db_session, "n23_ep_exec_a", "Nurse")
    nurse_b = _user(db_session, "n23_ep_exec_b", "Nurse")
    resource = _resource(db_session, "conflict")
    _assignment(db_session, nurse_a, resource)
    _assignment(db_session, nurse_b, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "Conflict")
    entry = _entry(db_session, queue, 1, patient)
    headers_a = _headers(db_session, nurse_a)
    headers_b = _headers(db_session, nurse_b)

    for headers in (headers_a, headers_b):
        client.post(f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers)
        client.post(
            f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/start",
            headers=headers,
        )
        break  # nurse A claims + starts

    service = Service(
        code="CFL1",
        name="Conflict procedure",
        queue_tag=resource.queue_tag,
        requires_doctor=False,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    visit_id = db_session.refresh(entry) or entry.visit_id
    vs = VisitService(
        visit_id=visit_id,
        service_id=service.id,
        code=service.code,
        name=service.name,
    )
    db_session.add(vs)
    db_session.commit()
    db_session.refresh(vs)

    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs.id},
        headers=headers_a,
    )
    assert response.status_code == 201, response.text
    execution_id = response.json()["id"]

    # Another nurse POSTing the SAME service: 409 (the one-active claim).
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs.id},
        headers=headers_b,
    )
    assert response.status_code == 409, response.text

    # The D1 handover: nurse B COMPLETES what nurse A started.
    response = client.post(
        f"{_BASE}/executions/{execution_id}/complete", headers=headers_b
    )
    assert response.status_code == 200, response.text
    assert response.json()["performed_by_user_id"] == nurse_b.id

    # Nurse A repeat-complete on the terminal attempt: 409.
    response = client.post(
        f"{_BASE}/executions/{execution_id}/complete", headers=headers_a
    )
    assert response.status_code == 409, response.text

    db_session.refresh(entry)
    assert entry.status == "served"
    assert entry.served_by_user_id == nurse_b.id


def test_no_show_and_entry_incomplete_through_router(
    client: TestClient, db_session: Session
) -> None:
    nurse = _user(db_session, "n23_ep_terminals", "Nurse")
    resource = _resource(db_session, "terminals")
    _assignment(db_session, nurse, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "Terminal")
    entry = _entry(db_session, queue, 1, patient)
    headers = _headers(db_session, nurse)

    # no-show straight from waiting; siblings untouched.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/no-show",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["new_status"] == "no_show"
    db_session.refresh(entry)
    assert entry.status == "no_show"
    assert db_session.query(ServiceExecution).count() == 0

    # entry-incomplete requires the in_progress state: 400 from no_show.
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/incomplete",
        json={"reason": "left"},
        headers=headers,
    )
    assert response.status_code == 400, response.text


# ----------------------------------------------------------------------------
# the ledger join proof (the PR #3333 audit identity contract)
# ----------------------------------------------------------------------------


def test_serving_mutations_join_one_resource_history(
    client: TestClient, db_session: Session
) -> None:
    """CALL_NEXT + START_SERVING retrieve together via get_by_resource."""
    from app.crud.user_management import user_audit_log

    nurse = _user(db_session, "n23_ep_ledger", "Nurse")
    resource = _resource(db_session, "ledger")
    _assignment(db_session, nurse, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "Ledger")
    entry = _entry(db_session, queue, 1, patient)
    headers = _headers(db_session, nurse)

    client.post(f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers)
    client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/start",
        headers=headers,
    )

    history = user_audit_log.get_by_resource(
        db_session, "online_queue_entries", entry.id
    )
    actions = {row.action for row in history}
    assert {"CALL_NEXT", "START_SERVING"} <= actions
    assert all(row.user_id == nurse.id for row in history if row.user_id is not None)


# ----------------------------------------------------------------------------
# codex round-3 P2: a mandatory reason must carry content
# ----------------------------------------------------------------------------


def test_incomplete_reason_validation_through_router(
    client: TestClient, db_session: Session
) -> None:
    """Blank and whitespace-only reasons fail 422 on BOTH incomplete
    surfaces; a padded valid reason is stored (and echoed) trimmed."""
    nurse = _user(db_session, "n23_ep_reason_val", "Nurse")
    resource = _resource(db_session, "reasonval")
    _assignment(db_session, nurse, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "ReasonVal")
    headers = _headers(db_session, nurse)

    # --- the entry-level terminal ---
    entry = _entry(db_session, queue, 1, patient)
    client.post(f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers)
    client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/start",
        headers=headers,
    )
    for blank in ("", "   "):
        response = client.post(
            f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/incomplete",
            json={"reason": blank},
            headers=headers,
        )
        assert response.status_code == 422, response.text
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/incomplete",
        json={"reason": "  отказ пациента  "},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "отказ пациента"
    db_session.refresh(entry)
    assert entry.incomplete_reason == "отказ пациента"

    # --- the execution-level abort ---
    entry2 = _entry(db_session, queue, 2, patient)
    client.post(f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers)
    client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry2.id}/start",
        headers=headers,
    )
    visit = db_session.get(Visit, entry2.visit_id)
    station_service = Service(
        code="REVAL1",
        name="Reason validation procedure",
        queue_tag=resource.queue_tag,
        requires_doctor=False,
        active=True,
    )
    db_session.add(station_service)
    db_session.commit()
    db_session.refresh(station_service)
    vs = VisitService(
        visit_id=visit.id,
        service_id=station_service.id,
        code=station_service.code,
        name=station_service.name,
        qty=1,
    )
    db_session.add(vs)
    db_session.commit()
    db_session.refresh(vs)
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry2.id, "visit_service_id": vs.id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    execution_id = response.json()["id"]

    for blank in ("", "   "):
        response = client.post(
            f"{_BASE}/executions/{execution_id}/incomplete",
            json={"reason": blank},
            headers=headers,
        )
        assert response.status_code == 422, response.text
    response = client.post(
        f"{_BASE}/executions/{execution_id}/incomplete",
        json={"reason": "  тошнота  "},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["incomplete_reason"] == "тошнота"
    execution = db_session.get(ServiceExecution, execution_id)
    assert execution.incomplete_reason == "тошнота"


# ----------------------------------------------------------------------------
# N2-3 follow-up (N2-5 §8): the drain-recovery discovery endpoint
# ----------------------------------------------------------------------------
def test_draining_executions_auth_matrix(
    client: TestClient, db_session: Session
) -> None:
    """Anonymous 401 / wrong role 403 on the discovery read (fail-closed)."""
    response = client.get(f"{_BASE}/draining-executions")
    assert response.status_code == 401, response.text

    doctor = _user(db_session, "n2dr_ep_doctor", "Doctor")
    response = client.get(
        f"{_BASE}/draining-executions", headers=_headers(db_session, doctor)
    )
    assert response.status_code == 403, response.text


def test_draining_discovery_flow_through_router(
    client: TestClient, db_session: Session
) -> None:
    """The §8 reload scenario end-to-end: deactivation mid-flight ->
    read plane collapses -> discovery surfaces the execution -> the
    drain finishes it -> discovery is empty again."""
    nurse = _user(db_session, "n2dr_ep_nurse", "Nurse")
    resource = _resource(db_session, "procedures_dr_ep")
    _assignment(db_session, nurse, resource)
    queue = _queue(db_session, resource)
    patient = _patient(db_session, "Reload")
    entry = _entry(db_session, queue, 1, patient)
    headers = _headers(db_session, nurse)

    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/call-next", headers=headers
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/entries/{entry.id}/start",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    visit_id = response.json()["visit_id"]
    assert visit_id is not None

    station_service = Service(
        code="DR-EP-PROC",
        name="Procedure DR-EP",
        queue_tag=resource.queue_tag,
        requires_doctor=False,
        active=True,
    )
    db_session.add(station_service)
    db_session.commit()
    db_session.refresh(station_service)
    vs = VisitService(
        visit_id=visit_id,
        service_id=station_service.id,
        code=station_service.code,
        name=station_service.name,
        qty=1,
    )
    db_session.add(vs)
    db_session.commit()
    db_session.refresh(vs)

    response = client.post(
        f"{_BASE}/queue-resources/{resource.id}/executions",
        json={"queue_entry_id": entry.id, "visit_service_id": vs.id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    execution_id = response.json()["id"]

    # mid-flight deactivation: the read plane the reload would see
    row = (
        db_session.query(NurseWorkplaceAssignment)
        .filter(
            NurseWorkplaceAssignment.user_id == nurse.id,
            NurseWorkplaceAssignment.queue_resource_id == resource.id,
        )
        .first()
    )
    row.is_active = False
    db_session.commit()

    response = client.get(f"{_BASE}/workplaces", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0

    response = client.get(
        f"{_BASE}/queue-resources/{resource.id}/entries", headers=headers
    )
    assert response.status_code == 403, response.text

    # the discovery: exactly the caller's own unfinished execution
    response = client.get(f"{_BASE}/draining-executions", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["execution"]["id"] == execution_id
    assert item["execution"]["status"] == "in_progress"
    assert item["station"]["queue_resource_id"] == resource.id
    assert item["entry"]["entry_id"] == entry.id
    assert item["entry"]["patient_name"] == "Reload"
    assert item["service"]["visit_service_id"] == vs.id

    # the drain through the discovered id
    response = client.post(
        f"{_BASE}/executions/{execution_id}/complete", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"

    response = client.get(f"{_BASE}/draining-executions", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


def test_draining_discovery_empty_for_fresh_nurse(
    client: TestClient, db_session: Session
) -> None:
    nurse = _user(db_session, "n2dr_ep_fresh", "Nurse")
    response = client.get(
        f"{_BASE}/draining-executions", headers=_headers(db_session, nurse)
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0}
