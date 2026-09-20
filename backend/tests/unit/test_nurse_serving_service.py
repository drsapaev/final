"""NURSE-V2 N2-3 — unit suite for the assignment-scoped serving service.

The world mirrors the §6 scenario shape: a procedures QueueResource
station, one or two Nurse users with active assignments, waiting queue
entries, and a visit carrying station-routed VisitServices plus
doctor-routed ones (the D3 boundary).

The N2-3 brief decisions pinned here:
- deny-by-default data authorization (no/inactive/wrong assignment 403);
- call-next atomic claim + same-nurse idempotency (§6);
- start = station state (called -> in_progress, idempotent, visit
  resolve/link, open -> in_progress, NO visit closing);
- execution lifecycle (D1): attempt ordinals, one-active claim
  (same-nurse no-op / other-nurse 409), retry-after-incomplete history,
  performed_by handover, mandatory reason on incomplete;
- the last-completer entry flip (only when ALL station-routed services
  of the visit are done; doctor/other-station services never block);
- graceful drain on mid-flight assignment deactivation (starter may
  finish what she started; every NEW operation 403);
- no-show leaves sibling pending services untouched (restore path);
- entry-level incomplete requires every linked attempt resolved (409);
- actor-attributed UserAuditLog rows for every mutation.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.service_execution import ServiceExecution
from app.models.user import User
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit, VisitService
from app.services.nurse_serving_api_service import (
    NurseServingApiDomainError,
    NurseServingApiService,
)

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------------------
# world builders
# ----------------------------------------------------------------------------


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


def _nurse(db: Session, username: str) -> User:
    return _user(db, username, "Nurse")


def _resource(
    db: Session, code: str = "procedures", tag: str | None = None
) -> QueueResource:
    tag = tag or f"tag_{code}"
    resource = QueueResource(
        code=code,
        queue_tag=tag,
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
    db: Session,
    nurse: User,
    resource: QueueResource,
    cabinet: str | None = None,
    active: bool = True,
) -> NurseWorkplaceAssignment:
    row = NurseWorkplaceAssignment(
        user_id=nurse.id,
        queue_resource_id=resource.id,
        cabinet_override=cabinet,
        is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _station_queue(db: Session, resource: QueueResource, day=None) -> DailyQueue:
    queue = DailyQueue(
        day=day or clinic_today(db),
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
        cabinet_number=resource.default_cabinet,
        start_number=1,
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue


def _patient(db: Session, name: str) -> Patient:
    patient = Patient(first_name=name, last_name="Test")
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _entry(
    db: Session,
    queue: DailyQueue,
    number: int,
    *,
    patient: Patient | None = None,
    status: str = "waiting",
    priority: int = 0,
    visit: Visit | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id if patient else None,
        patient_name=patient.first_name if patient else f"walk-in {number}",
        status=status,
        priority=priority,
        source="desk",
        visit_id=visit.id if visit else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _visit(
    db: Session,
    patient: Patient,
    *,
    department: str,
    status: str = "open",
    day=None,
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=None,
        visit_date=day or clinic_today(db),
        department=department,
        status=status,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def _service(
    db: Session,
    code: str,
    *,
    queue_tag: str | None,
    requires_doctor: bool = False,
) -> Service:
    service = Service(
        code=code,
        name=f"Service {code}",
        queue_tag=queue_tag,
        requires_doctor=requires_doctor,
        active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _visit_service(
    db: Session, visit: Visit, service: Service, qty: int = 1
) -> VisitService:
    row = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=qty,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _audit_rows(db: Session, table: str) -> list[UserAuditLog]:
    return (
        db.query(UserAuditLog)
        .filter(UserAuditLog.resource_type == table)
        .order_by(UserAuditLog.id.asc())
        .all()
    )


def _expect(exc_info, status_code: int) -> None:
    assert exc_info.value.status_code == status_code, exc_info.value.detail


# ----------------------------------------------------------------------------
# A. authorization boundary (deny by default)
# ----------------------------------------------------------------------------


class TestAuthorizationBoundary:
    def test_call_next_without_assignment_is_403(self, db_session: Session):
        nurse = _nurse(db_session, "n23_no_assign")
        resource = _resource(db_session)
        _station_queue(db_session, resource)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        _expect(exc, 403)

    def test_call_next_with_inactive_assignment_is_403(self, db_session: Session):
        nurse = _nurse(db_session, "n23_inactive_assign")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource, active=False)
        _station_queue(db_session, resource)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        _expect(exc, 403)

    def test_assignment_on_other_resource_does_not_authorize(self, db_session: Session):
        nurse = _nurse(db_session, "n23_other_station")
        resource_a = _resource(db_session, "procedures_a")
        resource_b = _resource(db_session, "procedures_b")
        _assignment(db_session, nurse, resource_a)
        _station_queue(db_session, resource_b)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).call_next(nurse.id, resource_b.id)
        _expect(exc, 403)

    def test_missing_resource_is_404(self, db_session: Session):
        nurse = _nurse(db_session, "n23_missing_res")
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).call_next(nurse.id, 10**9)
        _expect(exc, 404)

    def test_no_active_station_queue_today_is_404(self, db_session: Session):
        nurse = _nurse(db_session, "n23_no_queue")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        _expect(exc, 404)


# ----------------------------------------------------------------------------
# B. call-next: atomic claim + same-nurse idempotency (§6)
# ----------------------------------------------------------------------------


class TestCallNext:
    def _world(self, db: Session, count: int = 2):
        nurse = _nurse(db, "n23_caller")
        resource = _resource(db)
        _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        entries = [_entry(db, queue, i + 1) for i in range(count)]
        return nurse, resource, queue, entries

    def test_claim_sets_called_and_attributes_the_nurse(self, db_session: Session):
        nurse, resource, queue, entries = self._world(db_session)
        result = NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        assert result["idempotent"] is False
        assert result["entry"]["id"] == entries[0].id
        db_session.refresh(entries[0])
        assert entries[0].status == "called"
        assert entries[0].called_by_user_id == nurse.id
        assert entries[0].called_at is not None

    def test_repeat_by_same_nurse_returns_the_held_entry(self, db_session: Session):
        nurse, resource, _queue, entries = self._world(db_session)
        service = NurseServingApiService(db_session)
        first = service.call_next(nurse.id, resource.id)
        second = service.call_next(nurse.id, resource.id)
        assert second["idempotent"] is True
        assert second["entry"]["id"] == first["entry"]["id"] == entries[0].id
        # The second waiting patient was NOT claimed by the repeat.
        db_session.refresh(entries[1])
        assert entries[1].status == "waiting"

    def test_priority_patient_is_claimed_first(self, db_session: Session):
        nurse, resource, queue, _entries = self._world(db_session, count=2)
        vip = _entry(db_session, queue, 3, priority=2)
        result = NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        assert result["entry"]["id"] == vip.id

    def test_empty_queue_is_404(self, db_session: Session):
        nurse, resource, _queue, entries = self._world(db_session, count=2)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        # Release the held claim, then drain the queue.
        service.mark_entry_no_show(nurse.id, resource.id, entries[0].id)
        service.call_next(nurse.id, resource.id)  # claims entries[1] -> hold again
        service.mark_entry_no_show(nurse.id, resource.id, entries[1].id)
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.call_next(nurse.id, resource.id)
        _expect(exc, 404)

    def test_two_nurses_claim_different_patients(self, db_session: Session):
        nurse_a, resource, queue, entries = self._world(db_session, count=2)
        nurse_b = _nurse(db_session, "n23_caller_b")
        _assignment(db_session, nurse_b, resource, cabinet="c3")
        service = NurseServingApiService(db_session)
        first = service.call_next(nurse_a.id, resource.id)
        second = service.call_next(nurse_b.id, resource.id)
        assert first["entry"]["id"] != second["entry"]["id"]
        assert {first["entry"]["id"], second["entry"]["id"]} == {
            entries[0].id,
            entries[1].id,
        }

    def test_reconnect_refetches_the_held_claim(self, db_session: Session):
        nurse, resource, queue, entries = self._world(db_session, count=2)
        # Serving requires a registered patient (the visit context).
        entries[0].patient_id = _patient(db_session, "Reconnect").id
        db_session.commit()
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entries[0].id)
        # The §6 "reconnect/reload does not lose the active serving": the
        # station state still surfaces MY in-flight entry.
        state = service.get_station_state(nurse.id, resource.id)
        assert state["my_entry"] is not None
        assert state["my_entry"]["id"] == entries[0].id
        assert state["my_entry"]["status"] == "in_progress"

    def test_claim_writes_actor_audit_row(self, db_session: Session):
        nurse, resource, _queue, entries = self._world(db_session)
        NurseServingApiService(db_session).call_next(nurse.id, resource.id)
        rows = _audit_rows(db_session, "online_queue_entries")
        assert any(
            r.action == "CALL_NEXT" and r.resource_id == entries[0].id for r in rows
        )
        assert all(r.user_id == nurse.id for r in rows)


# ----------------------------------------------------------------------------
# C. start serving (entry level)
# ----------------------------------------------------------------------------


class TestStartServing:
    def _claimed(self, db: Session):
        nurse = _nurse(db, "n23_starter")
        resource = _resource(db)
        _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        patient = _patient(db, "Start")
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        return nurse, resource, queue, patient, entry

    def test_start_moves_called_to_in_progress_and_links_visit(
        self, db_session: Session
    ):
        nurse, resource, _queue, patient, entry = self._claimed(db_session)
        result = NurseServingApiService(db_session).start_entry(
            nurse.id, resource.id, entry.id
        )
        assert result["status"] == "in_progress"
        assert result["idempotent"] is False
        db_session.refresh(entry)
        assert entry.status == "in_progress"
        assert entry.visit_id is not None
        visit = db_session.get(Visit, entry.visit_id)
        assert visit is not None
        assert visit.patient_id == patient.id
        assert visit.department == resource.queue_tag
        # The doctor-surface BUG-3 lesson: 'open' -> 'in_progress'.
        assert visit.status == "in_progress"

    def test_start_is_idempotent_station_state(self, db_session: Session):
        nurse, resource, _queue, _patient, entry = self._claimed(db_session)
        service = NurseServingApiService(db_session)
        service.start_entry(nurse.id, resource.id, entry.id)
        again = service.start_entry(nurse.id, resource.id, entry.id)
        assert again["idempotent"] is True
        assert again["status"] == "in_progress"

    def test_another_assigned_nurse_can_start_the_same_entry(self, db_session: Session):
        # The D1 handover surface + the admin-called display-board flow:
        # the start is the STATION's state, not a personal claim.
        nurse, resource, _queue, _patient, entry = self._claimed(db_session)
        nurse_b = _nurse(db_session, "n23_starter_b")
        _assignment(db_session, nurse_b, resource, cabinet="c3")
        result = NurseServingApiService(db_session).start_entry(
            nurse_b.id, resource.id, entry.id
        )
        assert result["status"] == "in_progress"

    def test_start_from_waiting_is_400(self, db_session: Session):
        nurse = _nurse(db_session, "n23_start_waiting")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        entry = _entry(db_session, queue, 1)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).start_entry(
                nurse.id, resource.id, entry.id
            )
        _expect(exc, 400)

    def test_start_of_unregistered_walkin_is_400(self, db_session: Session):
        # VisitService belongs to a Visit of a REGISTERED patient — an
        # unregistered walk-in has no servable service context.
        nurse = _nurse(db_session, "n23_start_walkin")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        entry = _entry(db_session, queue, 1)  # no patient_id
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.start_entry(nurse.id, resource.id, entry.id)
        _expect(exc, 400)

    def test_prelinked_visit_is_reused_not_duplicated(self, db_session: Session):
        nurse, resource, _queue, patient, entry = self._claimed(db_session)
        visit = _visit(
            db_session, patient, department=resource.queue_tag, status="in_progress"
        )
        entry.visit_id = visit.id
        db_session.commit()
        result = NurseServingApiService(db_session).start_entry(
            nurse.id, resource.id, entry.id
        )
        assert result["visit_id"] == visit.id
        assert (
            db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 1
        )

    def test_in_progress_visit_is_found_not_duplicated(self, db_session: Session):
        # The canonical procedures flow: the doctor already moved the
        # visit to in_progress; the station branch must find it (an
        # open-only search would create a duplicate visit).
        nurse, resource, _queue, patient, entry = self._claimed(db_session)
        _visit(db_session, patient, department=resource.queue_tag, status="in_progress")
        result = NurseServingApiService(db_session).start_entry(
            nurse.id, resource.id, entry.id
        )
        assert result["visit_id"] is not None
        assert (
            db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 1
        )

    def test_start_writes_actor_audit_row(self, db_session: Session):
        nurse, resource, _queue, _patient, entry = self._claimed(db_session)
        NurseServingApiService(db_session).start_entry(nurse.id, resource.id, entry.id)
        rows = _audit_rows(db_session, "online_queue_entries")
        assert any(
            r.action == "START_SERVING" and r.resource_id == entry.id for r in rows
        )


# ----------------------------------------------------------------------------
# D. executions (D1 FINAL)
# ----------------------------------------------------------------------------


class TestExecutions:
    def _served(self, db: Session, *, with_services: bool = True):
        """call -> start world; returns full tuple."""
        nurse = _nurse(db, "n23_exec_nurse")
        resource = _resource(db)
        _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        patient = _patient(db, "Exec")
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        db_session_like = db
        visit = db.get(Visit, entry.visit_id)
        station_service = None
        doctor_service = None
        visit_service = None
        if with_services:
            station_service = _service(
                db, "PROC1", queue_tag=resource.queue_tag, requires_doctor=False
            )
            doctor_service = _service(
                db, "CONS1", queue_tag="therapy", requires_doctor=True
            )
            visit_service = _visit_service(db, visit, station_service)
            _visit_service(db, visit, doctor_service)
        return {
            "nurse": nurse,
            "resource": resource,
            "queue": queue,
            "patient": patient,
            "entry": entry,
            "visit": visit,
            "station_service": station_service,
            "doctor_service": doctor_service,
            "visit_service": visit_service,
            "service": service,
        }

    def test_create_in_progress_attempt_with_required_entry(self, db_session: Session):
        world = self._served(db_session)
        result = world["service"].create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        assert result["created"] is True
        assert result["attempt_no"] == 1
        assert result["status"] == "in_progress"
        assert result["queue_entry_id"] == world["entry"].id
        assert result["started_by_user_id"] == world["nurse"].id

    def test_same_nurse_repeat_post_is_a_noop(self, db_session: Session):
        world = self._served(db_session)
        service = world["service"]
        first = service.create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        second = service.create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        assert second["created"] is False
        assert second["id"] == first["id"]
        assert (
            db_session.query(ServiceExecution)
            .filter(ServiceExecution.visit_service_id == world["visit_service"].id)
            .count()
            == 1
        )

    def test_other_nurse_conflict_is_409(self, db_session: Session):
        world = self._served(db_session)
        nurse_b = _nurse(db_session, "n23_exec_b")
        _assignment(db_session, nurse_b, world["resource"])
        world["service"].create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].create_execution(
                nurse_b.id,
                world["resource"].id,
                queue_entry_id=world["entry"].id,
                visit_service_id=world["visit_service"].id,
            )
        _expect(exc, 409)

    def test_retry_after_incomplete_creates_new_attempt(self, db_session: Session):
        world = self._served(db_session)
        service = world["service"]
        first = service.create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        aborted = service.incomplete_execution(
            world["nurse"].id, first["id"], "patient felt dizzy"
        )
        assert aborted["status"] == "incomplete"
        assert aborted["incomplete_reason"] == "patient felt dizzy"
        second = service.create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        assert second["attempt_no"] == 2
        # History is never overwritten (D1).
        rows = (
            db_session.query(ServiceExecution)
            .filter(ServiceExecution.visit_service_id == world["visit_service"].id)
            .order_by(ServiceExecution.attempt_no.asc())
            .all()
        )
        assert [r.attempt_no for r in rows] == [1, 2]
        assert rows[0].status == "incomplete"

    def test_service_not_routed_to_station_is_400(self, db_session: Session):
        world = self._served(db_session)
        other = _service(
            db_session, "OTHER1", queue_tag="other_tag", requires_doctor=False
        )
        other_vs = _visit_service(db_session, world["visit"], other)
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].create_execution(
                world["nurse"].id,
                world["resource"].id,
                queue_entry_id=world["entry"].id,
                visit_service_id=other_vs.id,
            )
        _expect(exc, 400)

    def test_doctor_routed_service_is_400(self, db_session: Session):
        world = self._served(db_session)
        # Same queue_tag but requires_doctor=True — the D3 gate.
        consult = _service(
            db_session,
            "CONS2",
            queue_tag=world["resource"].queue_tag,
            requires_doctor=True,
        )
        consult_vs = _visit_service(db_session, world["visit"], consult)
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].create_execution(
                world["nurse"].id,
                world["resource"].id,
                queue_entry_id=world["entry"].id,
                visit_service_id=consult_vs.id,
            )
        _expect(exc, 400)

    def test_foreign_visit_service_is_400(self, db_session: Session):
        world = self._served(db_session)
        other_patient = _patient(db_session, "Other")
        other_visit = _visit(
            db_session, other_patient, department=world["resource"].queue_tag
        )
        foreign_vs = _visit_service(db_session, other_visit, world["station_service"])
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].create_execution(
                world["nurse"].id,
                world["resource"].id,
                queue_entry_id=world["entry"].id,
                visit_service_id=foreign_vs.id,
            )
        _expect(exc, 400)

    def test_create_requires_in_progress_entry(self, db_session: Session):
        world = self._served(db_session)
        # A fresh waiting entry: executions require the serving context.
        fresh = _entry(db_session, world["queue"], 2)
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].create_execution(
                world["nurse"].id,
                world["resource"].id,
                queue_entry_id=fresh.id,
                visit_service_id=world["visit_service"].id,
            )
        _expect(exc, 400)

    def test_create_writes_actor_audit_row(self, db_session: Session):
        world = self._served(db_session)
        world["service"].create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=world["visit_service"].id,
        )
        rows = _audit_rows(db_session, "service_executions")
        assert any(r.action == "CREATE" for r in rows)
        assert all(r.user_id == world["nurse"].id for r in rows)


# ----------------------------------------------------------------------------
# E. complete / incomplete + the last-completer flip
# ----------------------------------------------------------------------------


class TestCompletion:
    def _multi_service_world(self, db: Session, station_count: int = 2):
        nurse = _nurse(db, "n23_completer")
        resource = _resource(db)
        _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        patient = _patient(db, "Complete")
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        station_vss = []
        for i in range(station_count):
            svc = _service(db, f"PROC{i + 1}", queue_tag=resource.queue_tag)
            station_vss.append(_visit_service(db, visit, svc))
        # A doctor-routed service of the SAME visit must never block the
        # station's entry flip (the D3 boundary).
        doctor_svc = _service(db, "THERAPY", queue_tag="therapy", requires_doctor=True)
        _visit_service(db, visit, doctor_svc)
        return {
            "nurse": nurse,
            "resource": resource,
            "entry": entry,
            "visit": visit,
            "station_vss": station_vss,
            "service": service,
        }

    def _start(self, world, visit_service) -> dict:
        return world["service"].create_execution(
            world["nurse"].id,
            world["resource"].id,
            queue_entry_id=world["entry"].id,
            visit_service_id=visit_service.id,
        )

    def test_first_completion_does_not_flip_the_entry(self, db_session: Session):
        world = self._multi_service_world(db_session)
        first = self._start(world, world["station_vss"][0])
        result = world["service"].complete_execution(world["nurse"].id, first["id"])
        assert result["entry_served"] is False
        db_session.refresh(world["entry"])
        assert world["entry"].status == "in_progress"

    def test_last_completer_flips_the_entry_with_attribution(self, db_session: Session):
        world = self._multi_service_world(db_session)
        first = self._start(world, world["station_vss"][0])
        world["service"].complete_execution(world["nurse"].id, first["id"])
        second = self._start(world, world["station_vss"][1])
        result = world["service"].complete_execution(world["nurse"].id, second["id"])
        assert result["entry_served"] is True
        assert result["entry_served_by_user_id"] == world["nurse"].id
        db_session.refresh(world["entry"])
        assert world["entry"].status == "served"
        assert world["entry"].served_by_user_id == world["nurse"].id
        assert world["entry"].served_at is not None

    def test_handover_completion_attributes_the_actual_nurse(self, db_session: Session):
        # D1: one nurse starts, another finishes.
        world = self._multi_service_world(db_session, station_count=1)
        nurse_b = _nurse(db_session, "n23_completer_b")
        _assignment(db_session, nurse_b, world["resource"], cabinet="c3")
        started = self._start(world, world["station_vss"][0])
        result = world["service"].complete_execution(nurse_b.id, started["id"])
        assert result["entry_served"] is True
        assert result["entry_served_by_user_id"] == nurse_b.id
        db_session.refresh(world["entry"])
        assert world["entry"].served_by_user_id == nurse_b.id

    def test_same_nurse_complete_repeat_is_a_noop(self, db_session: Session):
        world = self._multi_service_world(db_session, station_count=1)
        execution = self._start(world, world["station_vss"][0])
        world["service"].complete_execution(world["nurse"].id, execution["id"])
        again = world["service"].complete_execution(world["nurse"].id, execution["id"])
        assert again["status"] == "completed"
        assert again["performed_by_user_id"] == world["nurse"].id

    def test_other_nurse_complete_repeat_on_terminal_is_409(self, db_session: Session):
        world = self._multi_service_world(db_session, station_count=1)
        nurse_b = _nurse(db_session, "n23_completer_c")
        _assignment(db_session, nurse_b, world["resource"])
        execution = self._start(world, world["station_vss"][0])
        world["service"].complete_execution(world["nurse"].id, execution["id"])
        with pytest.raises(NurseServingApiDomainError) as exc:
            world["service"].complete_execution(nurse_b.id, execution["id"])
        _expect(exc, 409)

    def test_incomplete_execution_never_flips_the_entry(self, db_session: Session):
        world = self._multi_service_world(db_session, station_count=1)
        execution = self._start(world, world["station_vss"][0])
        result = world["service"].incomplete_execution(
            world["nurse"].id, execution["id"], "equipment failure"
        )
        assert result["entry_served"] is False
        db_session.refresh(world["entry"])
        assert world["entry"].status == "in_progress"

    def test_doctor_routed_services_never_block_the_flip(self, db_session: Session):
        # Single station service; the therapy line stays pending forever —
        # the station event still completes (D3 boundary).
        world = self._multi_service_world(db_session, station_count=1)
        execution = self._start(world, world["station_vss"][0])
        result = world["service"].complete_execution(world["nurse"].id, execution["id"])
        assert result["entry_served"] is True

    def test_cancelled_latest_attempt_counts_as_done(self, db_session: Session):
        world = self._multi_service_world(db_session, station_count=2)
        execution = self._start(world, world["station_vss"][0])
        world["service"].incomplete_execution(
            world["nurse"].id, execution["id"], "abort"
        )
        retry = self._start(world, world["station_vss"][0])
        # Simulate an explicit cancellation of the retry (the cancelled
        # vocabulary exists in D1; the nurse API creates retries only —
        # cancellation is a hand/ops path).
        db_session.query(ServiceExecution).filter(
            ServiceExecution.id == retry["id"]
        ).update({"status": "cancelled"})
        db_session.commit()
        second = self._start(world, world["station_vss"][1])
        result = world["service"].complete_execution(world["nurse"].id, second["id"])
        assert result["entry_served"] is True

    def test_only_incomplete_attempts_leave_the_service_pending(
        self, db_session: Session
    ):
        world = self._multi_service_world(db_session, station_count=1)
        execution = self._start(world, world["station_vss"][0])
        world["service"].incomplete_execution(
            world["nurse"].id, execution["id"], "patient left"
        )
        # Entry-level incomplete is now the explicit terminal decision.
        result = world["service"].mark_entry_incomplete(
            world["nurse"].id, world["resource"].id, world["entry"].id, "patient left"
        )
        assert result["new_status"] == "incomplete"
        db_session.refresh(world["entry"])
        assert world["entry"].incomplete_reason == "patient left"


# ----------------------------------------------------------------------------
# F. mid-flight assignment deactivation — graceful drain
# ----------------------------------------------------------------------------


class TestMidFlightDeactivation:
    def _inflight(self, db: Session):
        nurse = _nurse(db, "n23_drain_nurse")
        resource = _resource(db)
        assignment = _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        entry = _entry(db, queue, 1, patient=_patient(db, "Drain"))
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        station_service = _service(db, "DRN1", queue_tag=resource.queue_tag)
        visit_service = _visit_service(db, visit, station_service)
        execution = service.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit_service.id,
        )
        # Mid-flight: the admin deactivates the assignment.
        assignment.is_active = False
        db.commit()
        return nurse, resource, entry, execution, service

    def test_new_operations_are_403_after_deactivation(self, db_session: Session):
        nurse, resource, _entry_row, _execution, service = self._inflight(db_session)
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.call_next(nurse.id, resource.id)
        _expect(exc, 403)

    def test_starter_can_drain_the_inflight_attempt(self, db_session: Session):
        nurse, resource, entry, execution, service = self._inflight(db_session)
        result = service.complete_execution(nurse.id, execution["id"])
        assert result["status"] == "completed"
        assert result["entry_served"] is True  # single station service
        db_session.refresh(entry)
        assert entry.status == "served"

    def test_other_nurse_without_assignment_cannot_touch_the_attempt(
        self, db_session: Session
    ):
        nurse, _resource, _entry_row, execution, service = self._inflight(db_session)
        outsider = _nurse(db_session, "n23_outsider")
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.complete_execution(outsider.id, execution["id"])
        _expect(exc, 403)

    def test_incomplete_drain_also_works_for_the_starter(self, db_session: Session):
        nurse, _resource, _entry_row, execution, service = self._inflight(db_session)
        result = service.incomplete_execution(nurse.id, execution["id"], "shift ended")
        assert result["status"] == "incomplete"


# ----------------------------------------------------------------------------
# G. no-show / entry-level incomplete
# ----------------------------------------------------------------------------


class TestEntryTerminals:
    def _world(self, db: Session):
        nurse = _nurse(db, "n23_noshow")
        resource = _resource(db)
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        service = NurseServingApiService(db)
        return nurse, resource, queue, service

    def test_no_show_from_waiting_leaves_sibling_services_untouched(
        self, db_session: Session
    ):
        nurse, resource, queue, service = self._world(db_session)
        patient = _patient(db_session, "NoShow")
        visit = _visit(db_session, patient, department=resource.queue_tag)
        station_svc = _service(db_session, "NS1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, station_svc)
        entry = _entry(db_session, queue, 1, patient=patient, visit=visit)
        result = service.mark_entry_no_show(nurse.id, resource.id, entry.id)
        assert result["new_status"] == "no_show"
        db_session.refresh(vs)
        assert db_session.query(ServiceExecution).count() == 0
        # The brief's sibling decision: the pending VisitService stays
        # exactly as it was — the restore path can resume serving.
        assert vs.qty == 1

    def test_no_show_from_called(self, db_session: Session):
        nurse, resource, queue, service = self._world(db_session)
        entry = _entry(db_session, queue, 1)
        service.call_next(nurse.id, resource.id)
        result = service.mark_entry_no_show(nurse.id, resource.id, entry.id)
        assert result["new_status"] == "no_show"

    def test_no_show_from_in_progress_is_400(self, db_session: Session):
        nurse, resource, queue, service = self._world(db_session)
        entry = _entry(
            db_session, queue, 1, patient=_patient(db_session, "NoShowInProg")
        )
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.mark_entry_no_show(nurse.id, resource.id, entry.id)
        _expect(exc, 400)

    def test_entry_incomplete_blocked_by_inprogress_execution(
        self, db_session: Session
    ):
        nurse, resource, queue, service = self._world(db_session)
        patient = _patient(db_session, "Blocked")
        entry = _entry(db_session, queue, 1, patient=patient)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        station_svc = _service(db_session, "BLK1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, station_svc)
        service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.mark_entry_incomplete(
                nurse.id, resource.id, entry.id, "patient left"
            )
        _expect(exc, 409)

    def test_entry_incomplete_after_resolving_attempts(self, db_session: Session):
        nurse, resource, queue, service = self._world(db_session)
        patient = _patient(db_session, "Resolved")
        entry = _entry(db_session, queue, 1, patient=patient)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        station_svc = _service(db_session, "RES1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, station_svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        service.incomplete_execution(nurse.id, execution["id"], "partial only")
        result = service.mark_entry_incomplete(
            nurse.id, resource.id, entry.id, "patient left mid-service"
        )
        assert result["new_status"] == "incomplete"
        assert result["reason"] == "patient left mid-service"

    def test_terminals_write_actor_audit_rows(self, db_session: Session):
        nurse, resource, queue, service = self._world(db_session)
        entry = _entry(db_session, queue, 1)
        service.mark_entry_no_show(nurse.id, resource.id, entry.id)
        rows = _audit_rows(db_session, "online_queue_entries")
        assert any(
            r.action == "MARK_NO_SHOW" and r.resource_id == entry.id for r in rows
        )


# ----------------------------------------------------------------------------
# H. read plane
# ----------------------------------------------------------------------------


class TestReadPlane:
    def test_workplaces_lists_only_own_active_assignments(self, db_session: Session):
        nurse = _nurse(db_session, "n23_reader")
        other = _nurse(db_session, "n23_reader_other")
        resource_a = _resource(db_session, "read_a")
        resource_b = _resource(db_session, "read_b")
        _assignment(db_session, nurse, resource_a, cabinet="r9")
        _assignment(db_session, nurse, resource_b, active=False)
        _assignment(db_session, other, resource_b)
        items, total = NurseServingApiService(db_session).list_workplaces(nurse.id)
        assert total == 1
        assert items[0]["queue_resource_id"] == resource_a.id
        assert items[0]["effective_cabinet"] == "r9"  # D2 override ?? default
        assert items[0]["resource_default_cabinet"] == "c1"

    def test_station_state_orders_waiting_canonically(self, db_session: Session):
        nurse = _nurse(db_session, "n23_board")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        early = _entry(db_session, queue, 1)
        vip = _entry(db_session, queue, 3, priority=2)
        late = _entry(db_session, queue, 2)
        state = NurseServingApiService(db_session).get_station_state(
            nurse.id, resource.id
        )
        assert [e["id"] for e in state["waiting"]] == [vip.id, early.id, late.id]
        assert state["counts"]["waiting"] == 3
        assert state["my_entry"] is None

    def test_station_state_marks_my_claim_and_lists_services(self, db_session: Session):
        nurse = _nurse(db_session, "n23_claim_view")
        nurse_b = _nurse(db_session, "n23_claim_view_b")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource, cabinet="c2")
        _assignment(db_session, nurse_b, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "View")
        entry_a = _entry(db_session, queue, 1, patient=patient)
        entry_b = _entry(db_session, queue, 2, patient=_patient(db_session, "View2"))
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.call_next(nurse_b.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry_a.id)
        visit = db_session.get(Visit, entry_a.visit_id)
        svc = _service(db_session, "VIEW1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc, qty=2)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry_a.id, visit_service_id=vs.id
        )
        state = service.get_station_state(nurse.id, resource.id)
        assert state["my_entry"] is not None
        assert state["my_entry"]["id"] == entry_a.id
        assert state["my_entry"]["is_my_claim"] is True
        assert state["my_entry"]["visit_id"] == visit.id
        services = state["my_entry"]["services"]
        assert len(services) == 1
        assert services[0]["visit_service_id"] == vs.id
        assert services[0]["qty"] == 2
        assert services[0]["in_progress_execution_id"] == execution["id"]
        assert services[0]["pending"] is True
        # The other nurse's active claim is visible with my-claim False.
        other = next(e for e in state["active"] if e["id"] == entry_b.id)
        assert other["is_my_claim"] is False

    def test_get_station_state_requires_assignment(self, db_session: Session):
        nurse = _nurse(db_session, "n23_board_outsider")
        resource = _resource(db_session)
        _station_queue(db_session, resource)
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).get_station_state(nurse.id, resource.id)
        _expect(exc, 403)


# ----------------------------------------------------------------------------
# I. codex round-1 regressions (station chain / visit-day transfer / replay)
# ----------------------------------------------------------------------------


class TestCodexRound1StationChain:
    """P1 (L1025): the drain bypass requires a validated station chain."""

    def _world(self, db: Session):
        nurse = _nurse(db, "n23_chain_nurse")
        resource = _resource(db)
        _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        service = NurseServingApiService(db)
        return nurse, resource, queue, service

    def _inflight_execution(self, db: Session):
        nurse, resource, queue, service = self._world(db)
        patient = _patient(db, "Chain")
        entry = _entry(db, queue, 1, patient=patient)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        svc = _service(db, "CHN1", queue_tag=resource.queue_tag)
        vs = _visit_service(db, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        return nurse, resource, queue, service, entry, visit, vs, execution

    def test_orphaned_execution_is_refused_even_for_the_starter(
        self, db_session: Session
    ):
        # queue_entry_id is nullable (ON DELETE SET NULL): an orphaned
        # execution has NO reconstructable station — neither assignment
        # nor drain may authorize its mutation from the serving plane.
        (
            nurse,
            _resource,
            _queue,
            service,
            _entry,
            _visit,
            _vs,
            execution,
        ) = self._inflight_execution(db_session)
        db_session.query(ServiceExecution).filter(
            ServiceExecution.id == execution["id"]
        ).update({"queue_entry_id": None})
        db_session.commit()
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.complete_execution(nurse.id, execution["id"])
        _expect(exc, 403)

    def test_cross_station_hand_applied_row_is_refused(self, db_session: Session):
        # Station-A entry + station-B-routed VisitService: the A-assigned
        # STARTER must not complete B-routed work through the drain, and
        # the empty-station last-completer predicate must never flip.
        (
            nurse,
            resource,
            _queue,
            service,
            entry,
            visit,
            _vs,
            execution,
        ) = self._inflight_execution(db_session)
        resource_b = _resource(db_session, "station_b")
        b_service = _service(db_session, "CHNB", queue_tag=resource_b.queue_tag)
        # Hand-apply: repoint the execution's VisitService to a B-routed
        # service of the SAME visit (violates the D3 chain for station A).
        b_vs = _visit_service(db_session, visit, b_service)
        db_session.query(ServiceExecution).filter(
            ServiceExecution.id == execution["id"]
        ).update({"visit_service_id": b_vs.id})
        db_session.commit()
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.complete_execution(nurse.id, execution["id"])
        _expect(exc, 403)
        db_session.refresh(entry)
        assert entry.status == "in_progress"  # no empty-station flip

    def test_foreign_visit_execution_is_refused(self, db_session: Session):
        (
            nurse,
            _resource,
            _queue,
            service,
            entry,
            entry_visit,
            vs,
            execution,
        ) = self._inflight_execution(db_session)
        other_patient = _patient(db_session, "ChainOther")
        other_visit = _visit(
            db_session, other_patient, department="other", status="open"
        )
        # Hand-applied drift: the VisitService row is repointed at
        # another visit — the execution's chain is inconsistent.
        db_session.query(VisitService).filter(VisitService.id == vs.id).update(
            {"visit_id": other_visit.id}
        )
        db_session.commit()
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.complete_execution(nurse.id, execution["id"])
        _expect(exc, 403)
        db_session.refresh(entry)
        assert entry.status == "in_progress"
        assert entry_visit is not None


class TestCodexRound1VisitDayTransfer:
    """P1 (L780): the linked visit is revalidated against the queue day."""

    def _world(self, db: Session, *, visit_day):

        nurse = _nurse(db, "n23_transfer_nurse")
        resource = _resource(db)
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        patient = _patient(db, "Transfer")
        visit = _visit(db, patient, department=resource.queue_tag, day=visit_day)
        entry = _entry(db, queue, 1, patient=patient, visit=visit)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        return nurse, resource, queue, patient, visit, entry, service

    def test_solo_yesterday_visit_is_restamped_with_its_appointment(
        self, db_session: Session
    ):
        from datetime import timedelta

        from app.models.appointment import Appointment

        today = clinic_today(db_session)
        nurse, resource, _queue, patient, visit, entry, service = self._world(
            db_session, visit_day=today - timedelta(days=1)
        )
        appointment = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        db_session.refresh(visit)
        assert visit.visit_date == today  # the solo visit followed the ticket
        db_session.refresh(appointment)
        assert appointment.appointment_date == today  # round-43 mirror
        assert (
            db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 1
        )

    def test_shared_yesterday_visit_yields_a_fresh_same_day_visit(
        self, db_session: Session
    ):
        from datetime import timedelta

        today = clinic_today(db_session)
        nurse, resource, queue, patient, visit, entry, service = self._world(
            db_session, visit_day=today - timedelta(days=1)
        )
        # A live yesterday peer ticket of ANOTHER station still anchors
        # the old visit: the nurse resolution must NOT re-stamp it.
        other_resource = _resource(db_session, "transfer_anchor")
        peer_queue = _station_queue(
            db_session, other_resource, day=today - timedelta(days=1)
        )
        peer = OnlineQueueEntry(
            queue_id=peer_queue.id,
            number=9,
            patient_id=patient.id,
            patient_name=patient.first_name,
            status="waiting",
            source="desk",
            visit_id=visit.id,
        )
        db_session.add(peer)
        db_session.commit()

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] is not None
        assert result["visit_id"] != visit.id  # a FRESH visit was resolved
        db_session.refresh(visit)
        assert visit.visit_date == today - timedelta(days=1)  # untouched
        fresh = db_session.get(Visit, result["visit_id"])
        assert fresh.visit_date == today
        assert fresh.department == resource.queue_tag
        db_session.refresh(entry)
        assert entry.visit_id == fresh.id  # relinked

    def test_same_day_visit_is_served_as_is(self, db_session: Session):
        nurse, resource, _queue, patient, visit, entry, service = self._world(
            db_session, visit_day=clinic_today(db_session)
        )
        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        assert (
            db_session.query(Visit).filter(Visit.patient_id == patient.id).count() == 1
        )


class TestCodexRound1TerminalReplayBeforeAuth:
    """P2 (L1051): the same-performer replay precedes authorization."""

    def _completed_then_deactivated(self, db: Session):
        nurse = _nurse(db, "n23_replay_nurse")
        resource = _resource(db)
        assignment = _assignment(db, nurse, resource, cabinet="c2")
        queue = _station_queue(db, resource)
        patient = _patient(db, "Replay")
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        svc = _service(db, "RPL1", queue_tag=resource.queue_tag)
        vs = _visit_service(db, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        service.complete_execution(nurse.id, execution["id"])
        # Mid-flight: the assignment is deactivated AFTER the completion.
        assignment.is_active = False
        db.commit()
        return nurse, resource, entry, execution, service

    def test_completed_replay_survives_assignment_deactivation(
        self, db_session: Session
    ):
        nurse, _resource, entry, execution, service = self._completed_then_deactivated(
            db_session
        )
        result = service.complete_execution(nurse.id, execution["id"])
        assert result["status"] == "completed"
        assert result["performed_by_user_id"] == nurse.id
        db_session.refresh(entry)
        assert entry.status == "served"  # the flip is not re-triggered

    def test_incomplete_replay_survives_assignment_deactivation(
        self, db_session: Session
    ):
        nurse = _nurse(db_session, "n23_replay_incomplete")
        resource = _resource(db_session)
        assignment = _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "ReplayInc")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        svc = _service(db_session, "RPL2", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        service.incomplete_execution(nurse.id, execution["id"], "delayed")
        assignment.is_active = False
        db_session.commit()
        result = service.incomplete_execution(nurse.id, execution["id"], "delayed")
        assert result["status"] == "incomplete"
        assert result["performed_by_user_id"] == nurse.id

    def test_other_user_terminal_conflict_still_requires_authorization(
        self, db_session: Session
    ):
        # The PRE-auth replay covers only the SAME performer; another
        # user on a terminal attempt still passes through authorization
        # and gets the 403 (no assignment) — not a state disclosure.
        nurse, _resource, _entry, execution, service = self._completed_then_deactivated(
            db_session
        )
        outsider = _nurse(db_session, "n23_replay_outsider")
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.complete_execution(outsider.id, execution["id"])
        _expect(exc, 403)
