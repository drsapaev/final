from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from app.models.audit import AuditLog
from app.models.clinic import Schedule
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit
from app.services.telegram_staff_action_adapter_service import (
    TelegramStaffActionAdapterError,
    TelegramStaffActionAdapterService,
)


def _linked_queue_entry(db_session, *, visit_id: int, test_doctor, test_patient):
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        visit_id=visit_id,
        number=7,
        patient_id=test_patient.id,
        patient_name="Adapter Patient",
        phone="+998901234567",
        source="desk",
        status="waiting",
    )
    db_session.add(entry)
    db_session.flush()
    return entry


def _other_patient_queue_entry(db_session, *, visit_id: int, test_doctor):
    other_patient = Patient(
        first_name="Other",
        last_name="Queue",
        phone="+998901239998",
    )
    db_session.add(other_patient)
    db_session.flush()
    return _linked_queue_entry(
        db_session,
        visit_id=visit_id,
        test_doctor=test_doctor,
        test_patient=other_patient,
    )


def _audit_actions(db_session) -> list[str]:
    return [
        row.action
        for row in db_session.query(AuditLog).order_by(AuditLog.id.asc()).all()
    ]


def test_staff_cancel_visit_adapter_mutates_visit_and_queue_with_audit(
    db_session, admin_user, test_visit, test_doctor, test_patient
):
    test_visit.status = "open"
    entry = _linked_queue_entry(
        db_session,
        visit_id=test_visit.id,
        test_doctor=test_doctor,
        test_patient=test_patient,
    )
    wrong_owner_entry = _other_patient_queue_entry(
        db_session,
        visit_id=test_visit.id,
        test_doctor=test_doctor,
    )
    db_session.flush()

    result = TelegramStaffActionAdapterService(db_session).staff_cancel_visit(
        visit_id=test_visit.id,
        actor_user_id=admin_user.id,
        telegram_chat_id=7701,
        commit=False,
    )

    assert result["success"] is True
    assert result["action"] == "staff_cancel_visit"
    assert test_visit.status == "cancelled"
    assert entry.status == "cancelled"
    assert wrong_owner_entry.status == "waiting"
    assert result["queue"]["queue_time_preserved"] is True
    assert _audit_actions(db_session) == [
        "staff_action_confirmed",
        "staff_action_completed",
    ]
    completed = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "staff_action_completed")
        .one()
    )
    assert completed.actor_user_id == admin_user.id
    assert completed.payload["operation_key"] == "visit_cancel_or_move"
    assert completed.payload["target_type"] == "visit"
    assert completed.payload["domain_mutation"] is True
    assert "7701" not in str(completed.payload)


def test_staff_move_visit_adapter_updates_date_and_preserves_queue_time(
    db_session, admin_user, test_visit, test_doctor, test_patient
):
    test_visit.status = "open"
    original_date = date.today()
    test_visit.visit_date = original_date
    entry = _linked_queue_entry(
        db_session,
        visit_id=test_visit.id,
        test_doctor=test_doctor,
        test_patient=test_patient,
    )
    wrong_owner_entry = _other_patient_queue_entry(
        db_session,
        visit_id=test_visit.id,
        test_doctor=test_doctor,
    )
    original_queue_time = entry.queue_time
    db_session.flush()

    new_date = original_date + timedelta(days=1)
    result = TelegramStaffActionAdapterService(db_session).staff_move_visit(
        visit_id=test_visit.id,
        new_visit_date=new_date,
        actor_user_id=admin_user.id,
        telegram_chat_id=7702,
        commit=False,
    )

    assert result["success"] is True
    assert test_visit.visit_date == new_date
    assert entry.status == "rescheduled"
    assert wrong_owner_entry.status == "waiting"
    assert entry.queue_time == original_queue_time
    assert result["queue"]["queue_time_preserved"] is True
    assert _audit_actions(db_session) == [
        "staff_action_confirmed",
        "staff_action_completed",
    ]


def test_staff_payment_status_adapter_uses_billing_transition_and_audit(
    db_session, admin_user, test_visit
):
    payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("120000"),
        currency="UZS",
        method="cash",
        status="pending",
    )
    db_session.add(payment)
    db_session.flush()

    result = TelegramStaffActionAdapterService(db_session).staff_change_payment_status(
        payment_id=payment.id,
        new_status="paid",
        actor_user_id=admin_user.id,
        telegram_chat_id=7703,
        commit=False,
    )

    assert result["success"] is True
    assert result["status"] == "paid"
    assert payment.status == "paid"
    assert payment.provider_data["staff_action"] == (
        "telegram_confirmed_payment_status_change"
    )
    assert _audit_actions(db_session) == [
        "staff_action_confirmed",
        "staff_action_completed",
    ]


def test_staff_refund_payment_adapter_enforces_refundable_status(
    db_session, admin_user, test_visit
):
    payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("90000"),
        currency="UZS",
        method="cash",
        status="paid",
    )
    db_session.add(payment)
    db_session.flush()

    result = TelegramStaffActionAdapterService(db_session).staff_refund_payment(
        payment_id=payment.id,
        amount=Decimal("90000"),
        reason="Patient requested refund",
        actor_user_id=admin_user.id,
        telegram_chat_id=7704,
        commit=False,
    )

    assert result["success"] is True
    assert result["status"] == "refunded"
    assert payment.status == "refunded"
    assert payment.refunded_amount == Decimal("90000")
    assert payment.refunded_by == admin_user.id
    assert _audit_actions(db_session) == [
        "staff_action_confirmed",
        "staff_action_completed",
    ]


def test_staff_refund_payment_adapter_records_failed_audit_on_policy_block(
    db_session, admin_user, test_visit
):
    payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("90000"),
        currency="UZS",
        method="cash",
        status="pending",
    )
    db_session.add(payment)
    db_session.flush()

    with pytest.raises(TelegramStaffActionAdapterError):
        TelegramStaffActionAdapterService(db_session).staff_refund_payment(
            payment_id=payment.id,
            actor_user_id=admin_user.id,
            telegram_chat_id=7705,
            commit=False,
        )

    assert payment.status == "pending"
    assert _audit_actions(db_session) == ["staff_action_failed"]
    failed = (
        db_session.query(AuditLog).filter(AuditLog.action == "staff_action_failed").one()
    )
    assert failed.payload["operation_key"] == "refund_issue"
    assert failed.payload["result"] == "failed"
    assert failed.payload["domain_mutation"] is False


def test_staff_schedule_adapter_updates_schedule_and_audits(
    db_session, admin_user, test_doctor
):
    schedule = Schedule(
        doctor_id=test_doctor.id,
        weekday=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        active=True,
    )
    db_session.add(schedule)
    db_session.flush()

    result = TelegramStaffActionAdapterService(db_session).staff_change_doctor_schedule(
        schedule_id=schedule.id,
        start_time=time(10, 0),
        end_time=time(16, 0),
        actor_user_id=admin_user.id,
        telegram_chat_id=7706,
        commit=False,
    )

    assert result["success"] is True
    assert schedule.start_time == time(10, 0)
    assert schedule.end_time == time(16, 0)
    assert _audit_actions(db_session) == [
        "staff_action_confirmed",
        "staff_action_completed",
    ]
