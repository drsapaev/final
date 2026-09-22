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

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today
from app.models.appointment import Appointment
from app.models.department import Department
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


# ----------------------------------------------------------------------------
# J. codex round-2 regressions (late services / replay flip outcome)
# ----------------------------------------------------------------------------


class TestCodexRound2LatePending:
    """P1 (L1226): late station services are never SILENTLY stranded."""

    def test_served_entry_with_late_service_is_surfaced_on_the_board(
        self, db_session: Session
    ):
        # The full flow: claim -> start -> execute -> complete (flip),
        # THEN the doctor prescribes another station-routed procedure
        # (the add-service paths append VisitServices without touching
        # queue entries).
        nurse = _nurse(db_session, "n23_late_nurse")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Late")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        svc = _service(db_session, "LATE1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        result = service.complete_execution(nurse.id, execution["id"])
        assert result["entry_served"] is True

        late_svc = _service(db_session, "LATE2", queue_tag=resource.queue_tag)
        late_vs = _visit_service(db_session, visit, late_svc)

        state = service.get_station_state(nurse.id, resource.id)
        # The served entry with the pending late service is VISIBLE.
        assert state["counts"]["late_pending"] == 1
        assert [item["id"] for item in state["late_pending"]] == [entry.id]
        late_services = state["late_pending"][0]["services"]
        assert {s["visit_service_id"] for s in late_services} == {vs.id, late_vs.id}
        pending = {s["visit_service_id"] for s in late_services if s["pending"]}
        assert pending == {late_vs.id}  # the completed one is done

        # The serving plane still refuses to execute on a terminal entry
        # (the patient is not at the station — rejoin first).
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.create_execution(
                nurse.id,
                resource.id,
                queue_entry_id=entry.id,
                visit_service_id=vs.id,
            )
        _expect(exc, 400)

    def test_rejoin_flow_serves_the_late_service(self, db_session: Session):
        # The EXISTING rejoin path: a new ticket for the same visit —
        # the next entry's serving sees ALL pending station services of
        # the visit, including the late one.
        nurse = _nurse(db_session, "n23_rejoin_nurse")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Rejoin")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        svc = _service(db_session, "RJN1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        service.complete_execution(nurse.id, execution["id"])

        late_svc = _service(db_session, "RJN2", queue_tag=resource.queue_tag)
        late_vs = _visit_service(db_session, visit, late_svc)

        # The desk re-tickets the patient for the same visit.
        entry2 = _entry(db_session, queue, 2, patient=patient, visit=visit)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry2.id)
        late_execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry2.id, visit_service_id=late_vs.id
        )
        result = service.complete_execution(nurse.id, late_execution["id"])
        assert result["entry_served"] is True  # entry2 flips
        db_session.refresh(entry2)
        assert entry2.status == "served"
        # The board no longer reports late-pending anything.
        state = service.get_station_state(nurse.id, resource.id)
        assert state["counts"]["late_pending"] == 0


class TestCodexRound2ReplayFlipOutcome:
    """P2 (L1188): the terminal replay preserves the flip outcome."""

    def test_completed_replay_reports_the_served_entry(self, db_session: Session):
        nurse = _nurse(db_session, "n23_flip_replay")
        resource = _resource(db_session)
        assignment = _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "FlipReplay")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        svc = _service(db_session, "FLP1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        first = service.complete_execution(nurse.id, execution["id"])
        assert first["entry_served"] is True

        # Assignment deactivated AFTER the flip: the lost-response retry
        # must still report the DURABLE served state, not a default false.
        assignment.is_active = False
        db_session.commit()
        replay = service.complete_execution(nurse.id, execution["id"])
        assert replay["status"] == "completed"
        assert replay["entry_served"] is True
        assert replay["entry_served_by_user_id"] == nurse.id


class TestCodexRound3ReasonPhiContainment:
    """P1: the free-text clinical reason never enters the general
    UserAuditLog (a different access/search/export surface) — presence
    + length only; the full text stays in the clinical row."""

    PHI = "Пациент с ВИЧ-инфекцией отказался от процедуры из-за тошноты"

    def test_execution_incomplete_reason_stays_out_of_general_audit(
        self, db_session: Session
    ):
        nurse = _nurse(db_session, "n23_phi_exec")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "PhiExec")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db_session.get(Visit, entry.visit_id)
        svc = _service(db_session, "PHI1", queue_tag=resource.queue_tag)
        vs = _visit_service(db_session, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )

        result = service.incomplete_execution(nurse.id, execution["id"], self.PHI)

        # The clinical row keeps the full text (the profiled place).
        assert result["incomplete_reason"] == self.PHI
        row = db_session.get(ServiceExecution, execution["id"])
        assert row.incomplete_reason == self.PHI

        # The general audit ledger: presence + length, never the text —
        # not in the description, not in ANY serialized values payload.
        rows = [
            r
            for r in _audit_rows(db_session, "service_executions")
            if r.action == "UPDATE" and r.resource_id == execution["id"]
        ]
        assert len(rows) == 1
        audit = rows[0]
        assert self.PHI not in (audit.description or "")
        assert "ВИЧ" not in (audit.description or "")
        assert self.PHI not in json.dumps(audit.old_values or {}, ensure_ascii=False)
        assert self.PHI not in json.dumps(audit.new_values or {}, ensure_ascii=False)
        assert "incomplete_reason" not in (audit.new_values or {})
        assert audit.new_values["reason_present"] is True
        assert audit.new_values["reason_length"] == len(self.PHI)

    def test_entry_incomplete_reason_stays_out_of_general_audit(
        self, db_session: Session
    ):
        nurse = _nurse(db_session, "n23_phi_entry")
        resource = _resource(db_session)
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "PhiEntry")
        entry = _entry(db_session, queue, 1, patient=patient)
        service = NurseServingApiService(db_session)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)

        result = service.mark_entry_incomplete(
            nurse.id, resource.id, entry.id, self.PHI
        )

        # The clinical row keeps the full text (the profiled place).
        assert result["reason"] == self.PHI
        db_session.refresh(entry)
        assert entry.incomplete_reason == self.PHI

        # The general audit ledger: presence + length, never the text.
        rows = [
            r
            for r in _audit_rows(db_session, "online_queue_entries")
            if r.action == "MARK_INCOMPLETE" and r.resource_id == entry.id
        ]
        assert len(rows) == 1
        audit = rows[0]
        assert self.PHI not in (audit.description or "")
        assert "ВИЧ" not in (audit.description or "")
        assert self.PHI not in json.dumps(audit.old_values or {}, ensure_ascii=False)
        assert self.PHI not in json.dumps(audit.new_values or {}, ensure_ascii=False)
        assert audit.new_values == {
            "status": "incomplete",
            "reason_present": True,
            "reason_length": len(self.PHI),
        }


class TestCodexRound3BoardQueryBudget:
    """P2 (N+1): the station board's SQL budget is CONSTANT in the number
    of board rows — batched enrichment, no late_pending re-enrichment.
    Several tablets poll this board all day while the terminal list
    grows, so a per-row query count would multiply across the fleet."""

    def _board_world(
        self,
        db: Session,
        *,
        suffix: str,
        n_active: int,
        n_late: int,
        n_done: int,
    ) -> tuple[User, QueueResource]:
        nurse = _nurse(db, f"n23_budget_{suffix}")
        resource = _resource(db, f"budget_{suffix}")
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        svc = _service(db, f"BUD{suffix}", queue_tag=resource.queue_tag)
        number = 0
        for i in range(n_active):
            number += 1
            patient = _patient(db, f"Act{suffix}{i}")
            visit = _visit(db, patient, department=resource.queue_tag)
            _entry(
                db,
                queue,
                number,
                patient=patient,
                status="in_progress",
                visit=visit,
            )
            _visit_service(db, visit, svc)
        for i in range(n_late):
            number += 1
            patient = _patient(db, f"Late{suffix}{i}")
            visit = _visit(db, patient, department=resource.queue_tag)
            _entry(db, queue, number, patient=patient, status="served", visit=visit)
            _visit_service(db, visit, svc)  # pending -> late_pending
        for i in range(n_done):
            number += 1
            patient = _patient(db, f"Done{suffix}{i}")
            visit = _visit(db, patient, department=resource.queue_tag)
            _entry(
                db, queue, number, patient=patient, status="served", visit=visit
            )  # no station services -> folded empty, NOT late_pending
        return nurse, resource

    @staticmethod
    def _counted_station_state(
        bind: object,
        service: NurseServingApiService,
        nurse_id: int,
        resource_id: int,
    ) -> tuple[dict[str, Any], int]:
        """get_station_state under a before_cursor_execute counter."""
        state: dict[str, int] = {"queries": 0}

        def _count(*_args: object, **_kwargs: object) -> None:
            state["queries"] += 1

        event.listen(bind, "before_cursor_execute", _count)
        try:
            board = service.get_station_state(nurse_id, resource_id)
        finally:
            event.remove(bind, "before_cursor_execute", _count)
        return board, state["queries"]

    def test_board_query_count_is_constant_in_board_rows(self, db_session: Session):
        nurse_small, resource_small = self._board_world(
            db_session, suffix="s", n_active=2, n_late=2, n_done=2
        )
        nurse_large, resource_large = self._board_world(
            db_session, suffix="l", n_active=6, n_late=8, n_done=8
        )

        service = NurseServingApiService(db_session)
        bind = db_session.get_bind()
        boards = []
        counts = []
        for nurse, resource in (
            (nurse_small, resource_small),
            (nurse_large, resource_large),
        ):
            board, counted = self._counted_station_state(
                bind, service, nurse.id, resource.id
            )
            boards.append(board)
            counts.append(counted)

        # The worlds really do differ in board size (the pin has teeth).
        assert len(boards[0]["active"]) == 2
        assert boards[0]["counts"]["late_pending"] == 2
        assert len(boards[1]["active"]) == 6
        assert boards[1]["counts"]["late_pending"] == 8

        # CONSTANT budget: the 22-row board costs the SAME SQL as the
        # 6-row one (3 lookups + 3 entry lists + 2 enrichment batches).
        assert counts[0] == counts[1]
        assert counts[0] <= 12


# ----------------------------------------------------------------------------
# N2-3 follow-up (N2-5 §8): drain-recovery discovery
# ----------------------------------------------------------------------------
class TestDrainRecoveryDiscovery:
    """The reload-discovery loop the graceful drain was missing.

    Before this endpoint a mid-flight deactivation collapsed the read
    plane to "no workplace" (empty workplaces list) + 403 board, so a
    RELOADED tablet could not rediscover the in_progress execution the
    drain still lets the starter finish — empirically proven on main
    (the N2-5 §8 gate scenario).
    """

    def test_discovery_surfaces_own_execution_after_deactivation(self, db_session):
        nurse = _nurse(db_session, "n2dr_a")
        resource = _resource(db_session, "procedures_dr")
        _assignment(db_session, nurse, resource, cabinet="7")
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Drain")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "dr_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        execution = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        exec_id = execution["id"]

        # mid-flight deactivation
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

        # the read plane the reload has:
        items, total = svc.list_workplaces(nurse.id)
        assert total == 0
        with pytest.raises(NurseServingApiDomainError) as exc:
            svc.get_station_state(nurse.id, resource.id)
        _expect(exc, 403)

        # the discovery closes the loop:
        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["execution"]["id"] == exec_id
        assert item["execution"]["status"] == "in_progress"
        assert item["execution"]["attempt_no"] == 1
        assert item["station"]["queue_resource_id"] == resource.id
        assert item["station"]["effective_cabinet"] == "7"
        assert item["entry"]["entry_id"] == entry.id
        assert item["entry"]["number"] == 1
        assert item["entry"]["patient_name"] == "Drain"
        assert item["service"]["visit_service_id"] == visit.services[0].id
        assert item["service"]["name"] == f"Service {service.code}"

        # and the drain is reachable end-to-end through the discovery id
        result = svc.complete_execution(nurse.id, exec_id)
        assert result["status"] == "completed"

        # terminal work disappears from the discovery
        assert svc.list_draining_executions(nurse.id)["total"] == 0

    def test_discovery_is_empty_while_assignment_is_active(self, db_session):
        nurse = _nurse(db_session, "n2dr_b")
        resource = _resource(db_session, "procedures_dr2")
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Active")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "dr_proc2", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        # ACTIVE assignment: the board is the surface, no drain duplicate
        payload = svc.list_draining_executions(nurse.id)
        assert payload == {"items": [], "total": 0}

    def test_discovery_never_surfaces_another_nurses_work(self, db_session):
        nurse_a = _nurse(db_session, "n2dr_starter")
        nurse_b = _nurse(db_session, "n2dr_other")
        resource = _resource(db_session, "procedures_dr3")
        _assignment(db_session, nurse_a, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Cross")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "dr_proc3", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse_a.id, resource.id, entry.id)
        svc.create_execution(
            nurse_a.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        # A's assignment deactivated mid-flight
        row = (
            db_session.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == nurse_a.id,
                NurseWorkplaceAssignment.queue_resource_id == resource.id,
            )
            .first()
        )
        row.is_active = False
        db_session.commit()

        # B (never assigned here at all) must NOT discover A's execution
        assert svc.list_draining_executions(nurse_b.id) == {"items": [], "total": 0}
        # ...while A still can
        assert svc.list_draining_executions(nurse_a.id)["total"] == 1

    def test_discovery_tracks_only_the_latest_in_progress_attempt(
        self,
        db_session,
    ):
        nurse = _nurse(db_session, "n2dr_retry")
        resource = _resource(db_session, "procedures_dr4")
        _assignment(db_session, nurse, resource)
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Retry")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "dr_proc4", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        first = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        # abort the first attempt, then re-claim (attempt 2)
        svc.incomplete_execution(
            nurse.id, first["id"], reason="пациент временно отложил"
        )
        second = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        assert second["attempt_no"] == 2

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

        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["execution"]["id"] == second["id"]
        assert item["execution"]["attempt_no"] == 2
        assert item["execution"]["status"] == "in_progress"

    # ------------------------------------------------------------------
    # owner-review round (PR #3358): an ACTIVE assignment alone is NOT
    # proof the board covers the execution — P1
    # ------------------------------------------------------------------
    def test_reassignment_next_day_still_discovers_the_execution(
        self, db_session, monkeypatch
    ):
        """P1 pin: day rollover + re-assignment -> the discovery returns.

        The old predicate (\"an active assignment exists -> the board
        covers it\") hid the day-D execution once the nurse was
        re-assigned: the board resolves TODAY's queue and never shows
        the day-D entry, so a RELOADED tablet had no way to obtain the
        execution id again — the terminal drain stayed authorized but
        unreachable, and the in_progress row kept blocking retries
        through the partial unique index.
        """
        import app.services.nurse_serving_api_service as svc_module

        nurse = _nurse(db_session, "n2dr_reatt")
        resource = _resource(db_session, "procedures_reatt")
        _assignment(db_session, nurse, resource, cabinet="7")
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Reatt")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "reatt_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        execution = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        exec_id = execution["id"]

        # mid-flight deactivation ...
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
        # ... then the administrator re-assigns the SAME pair (the
        # partial unique permits a new active row per pair).
        _assignment(db_session, nurse, resource, cabinet="12")

        # the day rolls over: the board now resolves tomorrow's queue
        tomorrow = clinic_today(db_session) + timedelta(days=1)
        monkeypatch.setattr(svc_module, "clinic_today", lambda _db: tomorrow)

        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        assert payload["items"][0]["execution"]["id"] == exec_id
        # the terminal drain is STILL reachable through the discovered id
        result = svc.complete_execution(nurse.id, exec_id)
        assert result["status"] == "completed"

    def test_reassignment_same_day_board_provably_covers_no_duplicate(self, db_session):
        """Guard: same-day re-assignment + the entry still active on
        TODAY's queue -> the board REALLY covers it (my_entry carries
        in_progress_execution_id), so the discovery adds no duplicate."""
        nurse = _nurse(db_session, "n2dr_reatt_same")
        resource = _resource(db_session, "procedures_reatt_same")
        _assignment(db_session, nurse, resource, cabinet="7")
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "ReattSame")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "reatt_same_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        # the canonical claim flow: waiting -> called (called_by = nurse)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="waiting", visit=visit
        )

        svc = NurseServingApiService(db_session)
        claimed = svc.call_next(nurse.id, resource.id)
        assert claimed["entry"]["id"] == entry.id
        svc.start_entry(nurse.id, resource.id, entry.id)
        execution = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        exec_id = execution["id"]

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
        _assignment(db_session, nurse, resource, cabinet="12")

        payload = svc.list_draining_executions(nurse.id)
        assert payload == {"items": [], "total": 0}

        # ... and the exclusion is JUSTIFIED: the board (which the active
        # assignment now opens) surfaces the execution id itself.
        board = svc.get_station_state(nurse.id, resource.id)
        assert board["my_entry"] is not None
        assert board["my_entry"]["id"] == entry.id
        service_execution_ids = [
            item["in_progress_execution_id"] for item in board["my_entry"]["services"]
        ]
        assert exec_id in service_execution_ids

    def test_day_rollover_without_reassignment_still_discovers(
        self, db_session, monkeypatch
    ):
        """Guard: the plain day rollover (no re-assignment at all) keeps
        the execution discoverable — the board of the NEW day cannot
        show the day-D entry either."""
        import app.services.nurse_serving_api_service as svc_module

        nurse = _nurse(db_session, "n2dr_roll")
        resource = _resource(db_session, "procedures_roll")
        _assignment(db_session, nurse, resource, cabinet="3")
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Roll")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "roll_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        execution = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
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

        tomorrow = clinic_today(db_session) + timedelta(days=1)
        monkeypatch.setattr(svc_module, "clinic_today", lambda _db: tomorrow)
        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        assert payload["items"][0]["execution"]["id"] == execution["id"]

    # ------------------------------------------------------------------
    # owner-review round (PR #3358): effective_cabinet = the assignment
    # PROVABLY in effect at execution start — P2
    # ------------------------------------------------------------------
    def test_draining_cabinet_is_the_assignment_in_effect_at_start(self, db_session):
        """P2 pin: the temporal resolution — the cabinet override of the
        assignment that authorized the start, NOT the latest
        re-assignment's value (assignment #1 cabinet 7 -> execution
        started -> #1 deactivated -> #2 cabinet 12 -> #2 deactivated ->
        recovery must answer cabinet 7)."""
        nurse = _nurse(db_session, "n2dr_cab")
        resource = _resource(db_session, "procedures_cab")
        anchor = datetime.now(UTC)
        first = NurseWorkplaceAssignment(
            user_id=nurse.id,
            queue_resource_id=resource.id,
            cabinet_override="7",
            is_active=True,
            created_at=anchor - timedelta(hours=2),
        )
        db_session.add(first)
        db_session.commit()

        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "Cabinet")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "cab_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        execution = svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
        exec_id = execution["id"]

        # a LATER re-assignment in another cabinet (created AFTER the
        # execution started), then BOTH rows deactivated.
        second = NurseWorkplaceAssignment(
            user_id=nurse.id,
            queue_resource_id=resource.id,
            cabinet_override="12",
            is_active=True,
            created_at=anchor + timedelta(hours=1),
        )
        db_session.add(second)
        db_session.commit()
        first.is_active = False
        second.is_active = False
        db_session.commit()

        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["execution"]["id"] == exec_id
        assert item["station"]["effective_cabinet"] == "7"

    def test_draining_cabinet_is_null_without_a_provable_snapshot(self, db_session):
        """P2 pin: the assignment that authorized the start carried NO
        override -> effective_cabinet is None. The resource's CURRENT
        default_cabinet is not a provable historical snapshot (it is
        mutable after the fact) — a possibly-wrong cabinet must not be
        presented as the recovery context."""
        nurse = _nurse(db_session, "n2dr_cab_null")
        resource = _resource(db_session, "procedures_cab_null")
        _assignment(db_session, nurse, resource)  # cabinet_override=None
        queue = _station_queue(db_session, resource)
        patient = _patient(db_session, "CabNull")
        visit = _visit(db_session, patient, department="procedures")
        service = _service(db_session, "cab_null_proc", queue_tag=resource.queue_tag)
        _visit_service(db_session, visit, service)
        entry = _entry(
            db_session, queue, 1, patient=patient, status="called", visit=visit
        )

        svc = NurseServingApiService(db_session)
        svc.start_entry(nurse.id, resource.id, entry.id)
        svc.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry.id,
            visit_service_id=visit.services[0].id,
        )
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

        payload = svc.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        assert payload["items"][0]["station"]["effective_cabinet"] is None

    # ------------------------------------------------------------------
    # owner-review round (PR #3358): the polling discovery keeps a
    # CONSTANT query budget — P2 (the tablet polls every 30 seconds)
    # ------------------------------------------------------------------
    def test_draining_query_count_is_constant_in_executions(self, db_session):
        """P2 pin: 1 draining execution costs the SAME SQL as 4 draining
        executions on 4 different stations — entries/queues/resources/
        visit services/services/assignments/today queues load in ONE
        IN-batch each; the old code ran a per-execution N+1 (the row
        list grows with every unfinished attempt)."""

        def _world(suffix: str, stations: int) -> User:
            nurse = _nurse(db_session, f"n2dr_qc_{suffix}")
            for index in range(stations):
                resource = _resource(db_session, f"procedures_qc_{suffix}_{index}")
                _assignment(db_session, nurse, resource)
                queue = _station_queue(db_session, resource)
                patient = _patient(db_session, f"QC{suffix}{index}")
                visit = _visit(db_session, patient, department="procedures")
                service = _service(
                    db_session, f"qc_{suffix}_{index}", queue_tag=resource.queue_tag
                )
                _visit_service(db_session, visit, service)
                entry = _entry(
                    db_session,
                    queue,
                    1,
                    patient=patient,
                    status="called",
                    visit=visit,
                )
                svc = NurseServingApiService(db_session)
                svc.start_entry(nurse.id, resource.id, entry.id)
                svc.create_execution(
                    nurse.id,
                    resource.id,
                    queue_entry_id=entry.id,
                    visit_service_id=visit.services[0].id,
                )
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
            return nurse

        nurse_one = _world("one", stations=1)
        nurse_many = _world("many", stations=4)

        svc = NurseServingApiService(db_session)
        bind = db_session.get_bind()

        def _counted(user_id: int) -> tuple[dict[str, Any], int]:
            state: dict[str, int] = {"queries": 0}

            def _count(*_args: object, **_kwargs: object) -> None:
                state["queries"] += 1

            event.listen(bind, "before_cursor_execute", _count)
            try:
                payload = svc.list_draining_executions(user_id)
            finally:
                event.remove(bind, "before_cursor_execute", _count)
            return payload, state["queries"]

        payload_one, count_one = _counted(nurse_one.id)
        payload_many, count_many = _counted(nurse_many.id)

        # the worlds really do differ in draining rows (the pin has teeth)
        assert payload_one["total"] == 1
        assert payload_many["total"] == 4

        # CONSTANT budget: 4 unfinished attempts on 4 stations cost the
        # SAME SQL as 1 (the batches just carry more ids).
        assert count_one == count_many
        assert count_one <= 16


# ----------------------------------------------------------------------------
# Corrective follow-up (owner verdict on the merged #3355 + #3358 runtime):
# P1 — precise Visit<->Appointment pairing on the day transfer
# ----------------------------------------------------------------------------
class TestOwnerFollowupAppointmentPairing:
    """The owner's repro: ONE patient, TWO doctorless same-day appointments
    (laboratory + procedures, different departments, no time). The old
    bulk UPDATE matched BOTH rows and moved the lab appointment together
    with the procedures transfer. The pairing is now narrowed by the
    visit's department axis, locked, moves EXACTLY ONE row and fails
    closed on ambiguity."""

    @staticmethod
    def _departments(db: Session) -> tuple[Department, Department]:
        lab = Department(key="lab", name_ru="Лаборатория")
        procedures = Department(key="procedures", name_ru="Процедуры")
        db.add_all([lab, procedures])
        db.commit()
        db.refresh(lab)
        db.refresh(procedures)
        return lab, procedures

    def _world(
        self,
        db: Session,
        *,
        visit_department_id: int | None,
        day,
    ):

        nurse = _nurse(db, "cfu_pair_nurse")
        resource = _resource(db, "procedures", tag="procedures")
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        patient = _patient(db, "Pairing")
        visit = _visit(db, patient, department="procedures", day=day)
        if visit_department_id is not None:
            visit.department_id = visit_department_id
            db.commit()
        entry = _entry(db, queue, 1, patient=patient, visit=visit)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        return nurse, resource, patient, visit, entry, service

    def test_transfer_moves_only_the_same_department_appointment_fk_axis(
        self, db_session: Session
    ):
        from datetime import timedelta

        lab, procedures = self._departments(db_session)
        today = clinic_today(db_session)
        nurse, resource, patient, visit, entry, service = self._world(
            db_session,
            visit_department_id=procedures.id,
            day=today - timedelta(days=1),
        )
        a_lab = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=lab.id,
        )
        a_proc = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=procedures.id,
        )
        db_session.add_all([a_lab, a_proc])
        db_session.commit()

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        db_session.refresh(visit)
        assert visit.visit_date == today
        # The procedures appointment followed its visit; the laboratory
        # appointment of the same patient/day stayed on its own day.
        db_session.refresh(a_proc)
        db_session.refresh(a_lab)
        assert a_proc.appointment_date == today
        assert a_lab.appointment_date == today - timedelta(days=1)

    def test_transfer_moves_only_the_same_department_appointment_key_axis(
        self, db_session: Session
    ):
        from datetime import timedelta

        lab, procedures = self._departments(db_session)
        today = clinic_today(db_session)
        # visit.department_id stays NULL: the canonical FK is resolved
        # from the department STRING (queue tag -> Department.key).
        nurse, resource, patient, visit, entry, service = self._world(
            db_session, visit_department_id=None, day=today - timedelta(days=1)
        )
        a_lab = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=lab.id,
        )
        a_proc = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=procedures.id,
        )
        db_session.add_all([a_lab, a_proc])
        db_session.commit()

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        db_session.refresh(a_proc)
        db_session.refresh(a_lab)
        assert a_proc.appointment_date == today
        assert a_lab.appointment_date == today - timedelta(days=1)

    def test_ambiguous_pairing_fails_closed_nothing_moves(self, db_session: Session):
        from datetime import timedelta

        _lab, procedures = self._departments(db_session)
        today = clinic_today(db_session)
        yesterday = today - timedelta(days=1)
        nurse, resource, patient, visit, entry, service = self._world(
            db_session, visit_department_id=procedures.id, day=yesterday
        )
        # TWO live appointments match even the narrowed pairing (same
        # department, doctorless, no time): the transfer must fail
        # closed instead of bulk-moving both rows.
        a_one = Appointment(
            patient_id=patient.id,
            appointment_date=yesterday,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=procedures.id,
        )
        a_two = Appointment(
            patient_id=patient.id,
            appointment_date=yesterday,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=procedures.id,
        )
        db_session.add_all([a_one, a_two])
        db_session.commit()

        with pytest.raises(NurseServingApiDomainError) as exc:
            service.start_entry(nurse.id, resource.id, entry.id)
        _expect(exc, 409)
        db_session.rollback()
        db_session.refresh(visit)
        assert visit.visit_date == yesterday  # the visit did not move
        db_session.refresh(a_one)
        db_session.refresh(a_two)
        assert a_one.appointment_date == yesterday  # nothing moved
        assert a_two.appointment_date == yesterday

    # ------------------------------------------------------------------
    # codex round-1 (PR #3367): the staged eligibility contract
    # ------------------------------------------------------------------
    def test_null_department_appointment_still_follows_its_visit(
        self, db_session: Session
    ):
        """codex round-1 P2: a uniquely-matching appointment that predates
        the department axis (department_id NULL) must still follow its
        visit — a strict FK-only predicate would strand it on the old
        day and recreate the round-43 duplicate-visit risk."""
        from datetime import timedelta

        _lab, procedures = self._departments(db_session)
        today = clinic_today(db_session)
        nurse, resource, patient, visit, entry, service = self._world(
            db_session, visit_department_id=procedures.id, day=today - timedelta(days=1)
        )
        legacy_appointment = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=None,  # the pre-department-axis pairing row
        )
        db_session.add(legacy_appointment)
        db_session.commit()

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        db_session.refresh(legacy_appointment)
        assert legacy_appointment.appointment_date == today  # it followed

    def test_unresolvable_visit_never_moves_a_scoped_foreign_appointment(
        self, db_session: Session
    ):
        """codex round-1 P1: a legacy visit whose department resolves to
        NOTHING must never fall back to the broad set — a lone SCOPED
        appointment of a known department is provably not this visit's
        pair, and moving it is exactly the cross-department corruption
        the verdict forbids."""
        from datetime import timedelta

        lab, _procedures = self._departments(db_session)
        today = clinic_today(db_session)
        # department string that maps to no Department row: unresolvable.
        nurse, resource, patient, visit, entry, service = self._world(
            db_session, visit_department_id=None, day=today - timedelta(days=1)
        )
        visit.department = "tag_unknown_queue"
        db_session.commit()
        foreign_scoped = Appointment(
            patient_id=patient.id,
            appointment_date=visit.visit_date,
            appointment_time=None,
            doctor_id=None,
            status="confirmed",
            department_id=lab.id,  # provably the lab department's pair
        )
        db_session.add(foreign_scoped)
        db_session.commit()

        result = service.start_entry(nurse.id, resource.id, entry.id)
        assert result["visit_id"] == visit.id
        db_session.refresh(visit)
        assert visit.visit_date == today  # the visit itself still moves
        db_session.refresh(foreign_scoped)
        # ...but the lab appointment NEVER follows an unresolvable visit.
        assert foreign_scoped.appointment_date == today - timedelta(days=1)


# ----------------------------------------------------------------------------
# Corrective follow-up (owner verdict on the merged runtime):
# P1 — immutable execution-to-station routing (Service retag mid-flight)
# ----------------------------------------------------------------------------
class TestOwnerFollowupRoutingSnapshot:
    """The owner's repro: nurse starts execution X on station A; an admin
    validly re-tags the Service A->B mid-flight; the terminal endpoint
    consulted the CURRENT catalog, answered 403 and the draining surface
    skipped the row — X stayed in_progress forever with the one-active
    index blocking every retry. The attempt now persists the routing
    snapshot and the terminal/drain paths prove routing from IT."""

    def _started_execution(self, db: Session, *, suffix: str = "cfu_rt"):
        nurse = _nurse(db, f"{suffix}_nurse")
        resource = _resource(db, f"{suffix}_station_a", tag=f"tag_{suffix}_a")
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        patient = _patient(db, f"{suffix.title()}")
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        svc = _service(db, f"{suffix.upper()}", queue_tag=resource.queue_tag)
        vs = _visit_service(db, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        return nurse, resource, svc, entry, visit, vs, execution

    @staticmethod
    def _retag(db: Session, svc: Service, new_tag: str) -> None:
        svc.queue_tag = new_tag
        db.commit()
        db.refresh(svc)

    def test_execution_persists_the_routing_snapshot(self, db_session: Session):
        nurse, resource, svc, entry, visit, vs, execution = self._started_execution(
            db_session
        )
        assert nurse is not None and visit is not None and vs is not None
        row = db_session.get(ServiceExecution, execution["id"])
        assert row.queue_resource_id == resource.id
        assert row.routing_queue_tag_snapshot == resource.queue_tag
        assert row.routing_service_id == svc.id
        assert row.routing_service_id == vs.service_id

    def test_starter_completes_after_service_retag(self, db_session: Session):
        nurse, resource, svc, entry, visit, vs, execution = self._started_execution(
            db_session, suffix="cfu_rt_c"
        )
        assert resource is not None and visit is not None and vs is not None
        # Valid admin action mid-flight: the canonical re-tag commits a
        # new queue_tag (no in-progress check exists on that surface).
        self._retag(db_session, svc, "tag_elsewhere")
        result = NurseServingApiService(db_session).complete_execution(
            nurse.id, execution["id"]
        )
        assert result["status"] == "completed"
        db_session.refresh(entry)
        assert entry.status == "served"  # the last-completer flip still works

    def test_starter_incompletes_after_service_retag(self, db_session: Session):
        nurse, resource, svc, entry, visit, vs, execution = self._started_execution(
            db_session, suffix="cfu_rt_i"
        )
        assert resource is not None and visit is not None
        self._retag(db_session, svc, "tag_elsewhere")
        service = NurseServingApiService(db_session)
        result = service.incomplete_execution(
            nurse.id, execution["id"], reason="прибор занят"
        )
        assert result["status"] == "incomplete"
        db_session.refresh(entry)
        assert entry.status == "in_progress"  # incomplete never flips
        # And the retry (a NEW attempt) is gated by the CURRENT catalog:
        # the re-tagged service no longer routes here, so a fresh start
        # on this station is a 400 — the old attempt stays finishable,
        # new work follows the new routing.
        with pytest.raises(NurseServingApiDomainError) as exc:
            service.create_execution(
                nurse.id,
                resource.id,
                queue_entry_id=entry.id,
                visit_service_id=vs.id,
            )
        _expect(exc, 400)

    def test_retagged_execution_stays_in_drain_discovery(self, db_session: Session):
        nurse, resource, svc, entry, visit, vs, execution = self._started_execution(
            db_session, suffix="cfu_rt_d"
        )
        # Mid-flight deactivation + re-tag: the exact stranding pair.
        self._retag(db_session, svc, "tag_elsewhere")
        assignment = (
            db_session.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == nurse.id,
                NurseWorkplaceAssignment.queue_resource_id == resource.id,
            )
            .first()
        )
        assignment.is_active = False
        db_session.commit()

        service = NurseServingApiService(db_session)
        payload = service.list_draining_executions(nurse.id)
        assert payload["total"] == 1
        assert payload["items"][0]["execution"]["id"] == execution["id"]
        assert payload["items"][0]["station"]["queue_resource_id"] == resource.id
        # ...and the starter can still finish it through the drain.
        result = service.complete_execution(nurse.id, execution["id"])
        assert result["status"] == "completed"
        db_session.refresh(entry)
        assert entry.status == "served"

    def test_same_nurse_reclaim_after_retag_is_a_noop(self, db_session: Session):
        nurse, resource, svc, entry, visit, vs, execution = self._started_execution(
            db_session, suffix="cfu_rt_r"
        )
        assert visit is not None and vs is not None
        self._retag(db_session, svc, "tag_elsewhere")
        # The tablet's repeat POST must re-claim HER in-progress attempt
        # (200/created=False), not answer the catalog 400 — the attempt
        # is still legally hers to finish.
        result = NurseServingApiService(db_session).create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        assert result["created"] is False
        assert result["id"] == execution["id"]

    def test_other_station_nurse_cannot_complete_retagged_execution(
        self, db_session: Session
    ):
        nurse_a, resource_a, svc, entry, visit, vs_a, execution = (
            self._started_execution(db_session, suffix="cfu_rt_x")
        )
        assert nurse_a is not None and entry is not None and visit is not None
        assert vs_a is not None and resource_a is not None
        # The re-tag moved the service to station B; a nurse ASSIGNED to
        # B is not the starter and holds no assignment on A (the
        # snapshot station) — no completion through either axis.
        resource_b = _resource(db_session, "cfu_rt_station_b", tag="tag_elsewhere")
        nurse_b = _nurse(db_session, "cfu_rt_nurse_b")
        _assignment(db_session, nurse_b, resource_b)
        self._retag(db_session, svc, "tag_elsewhere")
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).complete_execution(
                nurse_b.id, execution["id"]
            )
        _expect(exc, 403)

    def test_hand_repointed_visit_service_is_refused_under_snapshot(
        self, db_session: Session
    ):
        # The codex round-1 cross-station guard must SURVIVE the catalog
        # immunity: repointing the attempt's visit_service_id at a
        # B-routed line of the same visit breaks the routing_service_id
        # binding and fails closed.
        (
            nurse_a,
            resource_a,
            svc_a,
            entry,
            visit,
            vs_a,
            execution,
        ) = self._started_execution(db_session, suffix="cfu_rt_s")
        assert nurse_a is not None and resource_a is not None
        assert svc_a is not None and vs_a is not None
        resource_b = _resource(db_session, "cfu_rt_st_b", tag="tag_cfu_rt_s_b")
        svc_b = _service(db_session, "CFURT_S_B", queue_tag=resource_b.queue_tag)
        b_vs = _visit_service(db_session, visit, svc_b)
        db_session.query(ServiceExecution).filter(
            ServiceExecution.id == execution["id"]
        ).update({"visit_service_id": b_vs.id})
        db_session.commit()
        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).complete_execution(
                nurse_a.id, execution["id"]
            )
        _expect(exc, 403)
        db_session.refresh(entry)
        assert entry.status == "in_progress"  # no empty-station flip

    # ------------------------------------------------------------------
    # codex round-1 (PR #3367): the idempotent re-claim is station-bound
    # ------------------------------------------------------------------
    def test_cross_station_reclaim_is_not_a_noop(self, db_session: Session):
        """codex round-1 P1: a nurse assigned to BOTH stations must not be
        handed station A's in-progress execution by a station B POST —
        the no-op is bound to the attempt's snapshot station, so the
        cross-station request falls to the catalog D3 gate (400 while
        the service still routes only to A)."""
        nurse, resource_a, svc, entry_a, visit, vs_a, execution = (
            self._started_execution(db_session, suffix="cfu_rt_cs")
        )
        assert visit is not None and vs_a is not None
        resource_b = _resource(db_session, "cfu_rt_cs_station_b", tag="tag_cfu_rt_cs_b")
        _assignment(db_session, nurse, resource_b)
        queue_b = _station_queue(db_session, resource_b)
        entry_b = _entry(
            db_session,
            queue_b,
            1,
            patient=db_session.get(Patient, entry_a.patient_id),
            visit=visit,
        )
        entry_b.status = "in_progress"
        db_session.commit()

        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).create_execution(
                nurse.id,
                resource_b.id,
                queue_entry_id=entry_b.id,
                visit_service_id=vs_a.id,
            )
        _expect(exc, 400)  # D3: the service still routes only to station A
        row = db_session.get(ServiceExecution, execution["id"])
        assert row.status == "in_progress"  # A's attempt untouched
        assert row.queue_resource_id == resource_a.id

    def test_cross_station_reclaim_after_retag_is_409_with_station_context(
        self, db_session: Session
    ):
        """The re-tagged variant: the service NOW routes to B, so the
        station-B request passes the catalog gate — but the live attempt
        is bound to A by its snapshot. The answer is a 409 carrying the
        station context, never a silent adoption of A's work."""
        nurse, resource_a, svc, entry_a, visit, vs_a, execution = (
            self._started_execution(db_session, suffix="cfu_rt_cr")
        )
        assert visit is not None and vs_a is not None
        resource_b = _resource(
            db_session, "cfu_rt_cr_station_b", tag="tag_elsewhere_cr"
        )
        _assignment(db_session, nurse, resource_b)
        queue_b = _station_queue(db_session, resource_b)
        entry_b = _entry(
            db_session,
            queue_b,
            1,
            patient=db_session.get(Patient, entry_a.patient_id),
            visit=visit,
        )
        entry_b.status = "in_progress"
        # re-tag the service onto station B's tag mid-flight
        self._retag(db_session, svc, resource_b.queue_tag)

        with pytest.raises(NurseServingApiDomainError) as exc:
            NurseServingApiService(db_session).create_execution(
                nurse.id,
                resource_b.id,
                queue_entry_id=entry_b.id,
                visit_service_id=vs_a.id,
            )
        _expect(exc, 409)
        assert "другом рабочем месте" in exc.value.detail
        row = db_session.get(ServiceExecution, execution["id"])
        assert row.status == "in_progress"
        assert row.queue_resource_id == resource_a.id  # still bound to A


# ----------------------------------------------------------------------------
# Corrective follow-up (owner verdict on the merged runtime):
# P2 — late_pending must not outlive the re-ticket it asks for
# ----------------------------------------------------------------------------
class TestOwnerFollowupLatePendingRejoin:
    """The owner's repro: E1 served + late service -> E1 in late_pending;
    the registrar re-tickets the visit (E2 waiting/called/in_progress);
    E1 KEPT sitting in late_pending next to the live E2 — a false
    "still needs re-ticketing" signal. The suppression must be
    IMMEDIATE (the moment E2 exists), not eventual (after completion)."""

    def _served_with_late_service(self, db: Session, *, suffix: str):
        nurse = _nurse(db, f"{suffix}_nurse")
        resource = _resource(db, f"{suffix}_station")
        _assignment(db, nurse, resource)
        queue = _station_queue(db, resource)
        patient = _patient(db, suffix.title())
        entry = _entry(db, queue, 1, patient=patient)
        service = NurseServingApiService(db)
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry.id)
        visit = db.get(Visit, entry.visit_id)
        svc = _service(db, f"{suffix.upper()}1", queue_tag=resource.queue_tag)
        vs = _visit_service(db, visit, svc)
        execution = service.create_execution(
            nurse.id, resource.id, queue_entry_id=entry.id, visit_service_id=vs.id
        )
        service.complete_execution(nurse.id, execution["id"])
        late_svc = _service(db, f"{suffix.upper()}2", queue_tag=resource.queue_tag)
        late_vs = _visit_service(db, visit, late_svc)
        return nurse, resource, queue, visit, entry, late_vs, service

    def test_reticketed_visit_leaves_late_pending_immediately(
        self, db_session: Session
    ):
        nurse, resource, queue, visit, entry, late_vs, service = (
            self._served_with_late_service(db_session, suffix="cfu_lpr")
        )
        # Before the re-ticket: the late work IS signalled.
        state = service.get_station_state(nurse.id, resource.id)
        assert state["counts"]["late_pending"] == 1
        assert [item["id"] for item in state["late_pending"]] == [entry.id]

        # The registrar re-tickets the same visit: E2 waiting.
        entry2 = _entry(
            db_session,
            queue,
            2,
            patient=db_session.get(Patient, entry.patient_id),
            visit=visit,
        )

        state = service.get_station_state(nurse.id, resource.id)
        # E1 disappears IMMEDIATELY — the rejoin has happened.
        assert state["counts"]["late_pending"] == 0
        assert [item["id"] for item in state["waiting"]] == [entry2.id]

        # E2 walks the queue: called -> active entry carries the pending
        # late service (the desk sees the real work, not a stale signal).
        service.call_next(nurse.id, resource.id)
        state = service.get_station_state(nurse.id, resource.id)
        assert state["counts"]["late_pending"] == 0
        active_ids = [item["id"] for item in state["active"]]
        assert active_ids == [entry2.id]
        e2_services = state["active"][0]["services"]
        pending_ids = {s["visit_service_id"] for s in e2_services if s["pending"]}
        assert pending_ids == {late_vs.id}  # the late work rides on E2 now

    def test_terminal_entry_without_pending_station_services_stays_out(
        self, db_session: Session
    ):
        # Volume guard (P2-B): served entries whose visits have NO
        # station-routed pending services never materialize at all —
        # the SQL-level candidate query is the only late-work surface.
        nurse, resource, queue, visit, entry, late_vs, service = (
            self._served_with_late_service(db_session, suffix="cfu_lp2")
        )
        # Finish the late service through the rejoin flow.
        entry2 = _entry(
            db_session,
            queue,
            2,
            patient=db_session.get(Patient, entry.patient_id),
            visit=visit,
        )
        service.call_next(nurse.id, resource.id)
        service.start_entry(nurse.id, resource.id, entry2.id)
        late_execution = service.create_execution(
            nurse.id,
            resource.id,
            queue_entry_id=entry2.id,
            visit_service_id=late_vs.id,
        )
        result = service.complete_execution(nurse.id, late_execution["id"])
        assert result["entry_served"] is True
        state = service.get_station_state(nurse.id, resource.id)
        assert state["counts"]["late_pending"] == 0
        assert state["active"] == []
