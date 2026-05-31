from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)


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

        class Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return SimpleNamespace(id=9, patient_id=99)

        class Db:
            def query(self, model):
                return Query()

        class Repository:
            db = Db()

            def get_patient_deposit(self, *, patient_id):
                return deposit

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
