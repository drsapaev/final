from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.refund_deposit import DepositTransaction, PatientDeposit, RefundType
from app.models.visit import Visit
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from app.services.force_majeure_service import ForceMajeureService, get_force_majeure_service


@pytest.mark.unit
class TestForceMajeureApiService:
    def test_transfer_entry_ids_are_scoped_to_requested_specialist_and_date(
        self, monkeypatch
    ):
        captured = {}
        selected_entries = [SimpleNamespace(id=11)]

        class Repository:
            db = object()

            def list_pending_entries_by_ids(
                self, entry_ids, *, specialist_id, target_date
            ):
                captured["entry_ids"] = entry_ids
                captured["specialist_id"] = specialist_id
                captured["target_date"] = target_date
                return selected_entries

        force_service = SimpleNamespace(
            transfer_entries_to_tomorrow=lambda **kwargs: {
                "success": True,
                "transferred_ids": [entry.id for entry in kwargs["entries"]],
            }
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: force_service,
        )

        target_date = date.today()
        service = ForceMajeureApiService(db=None, repository=Repository())
        result = service.transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                entry_ids=[11, 12],
                specialist_id=77,
                target_date=target_date,
                daily_queue_id=None,
                reason="doctor emergency",
                send_notifications=False,
            ),
            current_user_id=10,
        )

        assert result["success"] is True
        assert captured == {
            "entry_ids": [11, 12],
            "specialist_id": 77,
            "target_date": target_date,
        }

    def test_repository_filters_explicit_entry_ids_by_specialist_and_date(
        self, db_session, test_doctor, test_patient
    ):
        today = date.today()
        other_day = today + timedelta(days=1)
        requested_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        other_specialist_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id + 1000,
            queue_tag="dermatology_common",
            active=True,
        )
        other_day_queue = DailyQueue(
            day=other_day,
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add_all([requested_queue, other_specialist_queue, other_day_queue])
        db_session.flush()

        scoped_entry = OnlineQueueEntry(
            queue_id=requested_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Scoped Patient",
            status="waiting",
            source="desk",
        )
        other_specialist_entry = OnlineQueueEntry(
            queue_id=other_specialist_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Other Specialist",
            status="waiting",
            source="desk",
        )
        other_day_entry = OnlineQueueEntry(
            queue_id=other_day_queue.id,
            number=3,
            patient_id=test_patient.id,
            patient_name="Other Day",
            status="waiting",
            source="desk",
        )
        db_session.add_all([scoped_entry, other_specialist_entry, other_day_entry])
        db_session.flush()

        entries = ForceMajeureApiRepository(db_session).list_pending_entries_by_ids(
            [scoped_entry.id, other_specialist_entry.id, other_day_entry.id],
            specialist_id=test_doctor.id,
            target_date=today,
        )

        assert [entry.id for entry in entries] == [scoped_entry.id]

    # -- Review round 2 (#3809 P1): queue identity binding -----------------

    def test_pending_entries_bind_to_requested_daily_queue_not_registry_surface(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """The registrar row's canonical daily_queue_id is the ONLY target.

        The doctor's specialty tag has a registry-backed resource surface
        (the shadow-queue case): the legacy specialist resolution prefers it
        and would return ANOTHER queue's patients. Bound to daily_queue_id
        the preview returns exactly the row's own queue entries.
        """
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        resource = QueueResource(
            code="cardio_surface",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        surface_queue = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_own_queue",
            active=True,
        )
        db_session.add_all([surface_queue, doctor_queue])
        db_session.flush()

        doctor_entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Doctor Queue Patient",
            status="waiting",
            source="desk",
        )
        surface_entry = OnlineQueueEntry(
            queue_id=surface_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Surface Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([doctor_entry, surface_entry])
        db_session.flush()

        service = ForceMajeureApiService(db_session)

        bound = service.get_pending_entries(
            specialist_id=test_doctor.id,
            target_date=today,
            daily_queue_id=doctor_queue.id,
        )
        assert [entry["id"] for entry in bound] == [doctor_entry.id]

        # The legacy path (no daily_queue_id) still prefers the registry
        # surface — the exact hazard the binding removes for the UI.
        legacy = service.get_pending_entries(
            specialist_id=test_doctor.id,
            target_date=today,
        )
        assert [entry["id"] for entry in legacy] == [surface_entry.id]

    def test_pending_entries_daily_queue_id_rejects_unknown_queue(
        self, db_session, test_doctor
    ):
        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=999999,
            )
        assert exc_info.value.status_code == 404

    def test_pending_entries_daily_queue_id_rejects_foreign_specialist_queue(
        self, db_session, test_doctor
    ):
        other_specialist_queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id + 1000,
            queue_tag="foreign_queue",
            active=True,
        )
        db_session.add(other_specialist_queue)
        db_session.flush()

        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=other_specialist_queue.id,
            )
        assert exc_info.value.status_code == 422

    def test_pending_entries_daily_queue_id_rejects_day_mismatch(
        self, db_session, test_doctor
    ):
        other_day_queue = DailyQueue(
            day=date.today() + timedelta(days=3),
            specialist_id=test_doctor.id,
            queue_tag="future_day_queue",
            active=True,
        )
        db_session.add(other_day_queue)
        db_session.flush()

        service = ForceMajeureApiService(db_session)
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.get_pending_entries(
                specialist_id=test_doctor.id,
                target_date=date.today(),
                daily_queue_id=other_day_queue.id,
            )
        assert exc_info.value.status_code == 422

    def test_daily_queue_id_and_entry_ids_are_mutually_exclusive(self, monkeypatch):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        with pytest.raises(ForceMajeureApiDomainError) as transfer_error:
            service.transfer_queue_to_tomorrow(
                request=SimpleNamespace(
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=5,
                    entry_ids=[1, 2],
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert transfer_error.value.status_code == 422

        with pytest.raises(ForceMajeureApiDomainError) as cancel_error:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=5,
                    entry_ids=[1, 2],
                    reason="reason",
                    refund_type="deposit",
                    send_notifications=False,
                ),
                current_user_id=1,
            )
        assert cancel_error.value.status_code == 422

    def test_transfer_passes_resolved_source_day_to_domain_service(self, monkeypatch):
        captured = {}

        def fake_transfer(**kwargs):
            captured.update(kwargs)
            return {"success": True, "transferred": len(kwargs["entries"])}

        force_service = SimpleNamespace(
            get_pending_entries=lambda **kwargs: [SimpleNamespace(id=11)],
            transfer_entries_to_tomorrow=fake_transfer,
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: force_service,
        )

        source_day = date(2026, 11, 5)
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace(db=None))
        service.transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=7,
                target_date=source_day,
                daily_queue_id=None,
                entry_ids=None,
                reason="doctor absent on Nov 5",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        # round 2 P1: the destination day must derive from the SOURCE queue
        # day, never from the current clinic day
        assert captured["source_date"] == source_day

    def test_transfer_destination_is_source_day_plus_one_for_future_queue(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        """A future-dated queue transfers to source day + 1, not clinic
        tomorrow: on clinic day 2026-10-30 the Nov 5 queue moves to Nov 6
        (the old behavior recreated the entries on Oct 31 — backwards)."""
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        clinic_day = date(2026, 10, 30)
        monkeypatch.setattr(
            "app.services.force_majeure_service.clinic_today", lambda db: clinic_day
        )
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.clinic_today",
            lambda db: clinic_day,
        )

        source_day = date(2026, 11, 5)
        source_queue = DailyQueue(
            day=source_day,
            specialist_id=test_doctor.id,
            queue_tag="doctor_future_queue",
            active=True,
        )
        db_session.add(source_queue)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=source_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Future Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add(entry)
        db_session.flush()

        result = ForceMajeureApiService(db_session).transfer_queue_to_tomorrow(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=source_day,
                daily_queue_id=source_queue.id,
                entry_ids=None,
                reason="doctor absent on Nov 5",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["transferred"] == 1
        assert result["new_date"] == "2026-11-06"
        db_session.refresh(entry)
        assert entry.status == "cancelled"
        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        moved_queue = db_session.get(DailyQueue, moved.queue_id)
        assert moved_queue.day == date(2026, 11, 6)

    def test_cancel_with_refund_selects_only_the_bound_queue_entries(
        self, db_session, test_doctor, test_patient, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )
        today = date.today()
        resource = QueueResource(
            code="cardio_surface_c",
            queue_tag=test_doctor.specialty,
            display_name="Кардиология (реестр)",
            active=True,
        )
        db_session.add(resource)
        db_session.flush()
        surface_queue = DailyQueue(
            day=today,
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=test_doctor.specialty,
            active=True,
        )
        doctor_queue = DailyQueue(
            day=today,
            specialist_id=test_doctor.id,
            queue_tag="doctor_own_queue_c",
            active=True,
        )
        db_session.add_all([surface_queue, doctor_queue])
        db_session.flush()

        own_entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name="Own Queue Patient",
            status="waiting",
            source="desk",
        )
        surface_entry = OnlineQueueEntry(
            queue_id=surface_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name="Surface Queue Patient",
            status="waiting",
            source="desk",
        )
        db_session.add_all([own_entry, surface_entry])
        db_session.flush()

        captured = {}
        real_service = get_force_majeure_service(db_session)

        def fake_cancel(**kwargs):
            captured["entries"] = kwargs["entries"]
            return {"success": True, "cancelled": len(kwargs["entries"])}

        monkeypatch.setattr(real_service, "cancel_entries_with_refund", fake_cancel)
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: real_service,
        )

        result = ForceMajeureApiService(db_session).cancel_queue_with_refund(
            request=SimpleNamespace(
                specialist_id=test_doctor.id,
                target_date=today,
                daily_queue_id=doctor_queue.id,
                entry_ids=None,
                reason="doctor emergency",
                refund_type="deposit",
                send_notifications=False,
            ),
            current_user_id=1,
        )

        assert result["cancelled"] == 1
        assert [entry.id for entry in captured["entries"]] == [own_entry.id]

    def test_cancel_with_refund_rejects_entry_linked_to_other_patient_visit(
        self,
        db_session,
        test_doctor,
        test_patient,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.force_majeure_service.get_fcm_service",
            lambda: object(),
        )

        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998900000113",
        )
        db_session.add_all([queue, other_patient])
        db_session.flush()

        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="14:00",
            status="open",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.utcnow(),
        )
        db_session.add(other_visit)
        db_session.flush()

        payment = Payment(
            visit_id=other_visit.id,
            amount=Decimal("120.00"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            visit_id=other_visit.id,
            source="online",
            status="waiting",
        )
        db_session.add_all([payment, entry])
        db_session.commit()
        db_session.refresh(entry)
        db_session.refresh(other_visit)

        result = ForceMajeureService(db_session).cancel_entries_with_refund(
            entries=[entry],
            reason="Doctor emergency",
            refund_type=RefundType.DEPOSIT,
            performed_by_id=1,
            send_notifications=False,
        )

        assert result["cancelled"] == 0
        assert result["failed"] == 1
        assert "does not belong" in result["errors"][0]["error"]

        db_session.refresh(entry)
        db_session.refresh(other_visit)
        assert entry.status == "waiting"
        assert other_visit.status == "open"
        assert (
            db_session.query(PatientDeposit)
            .filter(PatientDeposit.patient_id == test_patient.id)
            .count()
            == 0
        )
        assert (
            db_session.query(DepositTransaction)
            .filter(DepositTransaction.payment_id == payment.id)
            .count()
            == 0
        )

    def test_cancel_queue_with_refund_rejects_invalid_type(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: SimpleNamespace(),
        )

        repository = SimpleNamespace(db=None)
        service = ForceMajeureApiService(db=None, repository=repository)

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    refund_type="bad",
                    entry_ids=None,
                    specialist_id=1,
                    target_date=None,
                    daily_queue_id=None,
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=10,
            )

        assert exc_info.value.status_code == 400

    def test_process_refund_request_reject_requires_reason(self):
        request_obj = SimpleNamespace(
            status="pending",
            processed_by=None,
            processed_at=None,
            patient=None,
            processor=None,
            id=1,
            patient_id=2,
            payment_id=3,
            original_amount=Decimal("10"),
            refund_amount=Decimal("10"),
            commission_amount=Decimal("0"),
            refund_type="deposit",
            reason="r",
            is_automatic=False,
            bank_card_number=None,
            created_at=None,
        )

        class Repository:
            def get_refund_request(self, request_id):
                return request_obj

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.process_refund_request(
                request_id=1,
                process_request=SimpleNamespace(
                    action="reject",
                    rejection_reason=None,
                    bank_card_number=None,
                    manager_notes=None,
                ),
                current_user=SimpleNamespace(id=1, full_name="Admin"),
            )
        assert exc_info.value.status_code == 400

    def test_refund_request_serialization_exposes_backend_owned_actions(self):
        service = ForceMajeureApiService(db=None, repository=SimpleNamespace())

        def make_request(status):
            return SimpleNamespace(
                status=status,
                processed_by=None,
                processed_at=None,
                patient=None,
                processor=None,
                id=1,
                patient_id=2,
                payment_id=3,
                original_amount=Decimal("10"),
                refund_amount=Decimal("10"),
                commission_amount=Decimal("0"),
                refund_type="deposit",
                reason="r",
                is_automatic=False,
                bank_card_number=None,
                created_at=None,
            )

        pending = service._serialize_refund_request(make_request("pending"))
        approved = service._serialize_refund_request(make_request("approved"))
        rejected = service._serialize_refund_request(make_request("rejected"))

        assert pending["available_actions"] == ["approve", "reject"]
        assert pending["can_approve"] is True
        assert pending["can_reject"] is True
        assert pending["can_complete"] is False

        assert approved["available_actions"] == ["reject", "complete"]
        assert approved["can_approve"] is False
        assert approved["can_reject"] is True
        assert approved["can_complete"] is True

        assert rejected["available_actions"] == []
        assert rejected["can_approve"] is False
        assert rejected["can_reject"] is False
        assert rejected["can_complete"] is False

    def test_use_deposit_for_payment_checks_balance(self):
        deposit = SimpleNamespace(
            balance=Decimal("50"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )

        class Repository:
            def get_patient_deposit(self, *, patient_id):
                return deposit

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.use_deposit_for_payment(
                request=SimpleNamespace(
                    patient_id=2,
                    amount=100,
                    visit_id=None,
                    description=None,
                ),
                current_user_id=1,
            )
        assert exc_info.value.status_code == 400

    def test_use_deposit_for_payment_rejects_cross_patient_visit(self):
        deposit = SimpleNamespace(
            balance=Decimal("100"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )
        state = {"flushed": False}

        class Repository:
            def get_patient_deposit(self, *, patient_id):
                return deposit

            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id, patient_id=99)

            def flush(self):
                state["flushed"] = True

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.use_deposit_for_payment(
                request=SimpleNamespace(
                    patient_id=2,
                    amount=40,
                    visit_id=9,
                    description=None,
                ),
                current_user_id=1,
            )

        assert exc_info.value.status_code == 400
        assert deposit.balance == Decimal("100")
        assert state["flushed"] is False
