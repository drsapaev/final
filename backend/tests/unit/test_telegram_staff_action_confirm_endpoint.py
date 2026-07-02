from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.admin_telegram import (
    StaffActionConfirmRequest,
    confirm_staff_action,
    _staff_runtime_reference_hash,
)
from app.models.clinic import Schedule
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.telegram_config import TelegramStaffConfirmationToken
from app.models.visit import Visit
from app.services.telegram_staff_confirmation_token_service import (
    TelegramStaffConfirmationTokenService,
)


def _issue_confirmation(
    db_session,
    *,
    user,
    operation_key: str,
    command_key: str,
    target_type: str | None = None,
    target_id: int | None = None,
):
    return TelegramStaffConfirmationTokenService(db_session).issue_token(
        token_hash=f"staff_confirmation_token:{uuid4().hex}",
        staff_user_id=user.id,
        telegram_chat_id=8800 + user.id,
        operation_key=operation_key,
        command_key=command_key,
        action_payload_hash=f"staff_action_payload:{uuid4().hex}",
        target_type=target_type or "telegram_staff_action",
        target_reference_hash=(
            _staff_runtime_reference_hash(target_type, target_id)
            if target_type and target_id is not None
            else f"staff_action:{uuid4().hex}"
        ),
        idempotency_key_hash=f"staff_action_idempotency:{uuid4().hex}",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )


def _queue_entry(db_session, *, test_doctor, test_patient, visit_id: int | None = None):
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag=f"staff_action_{uuid4().hex[:8]}",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        visit_id=visit_id,
        number=1,
        patient_id=test_patient.id,
        patient_name="Target Bound Patient",
        phone="+998901234575",
        source="desk",
        status="waiting",
        queue_time=datetime.utcnow().replace(microsecond=0),
    )
    db_session.add(entry)
    db_session.flush()
    return entry


def _assert_consumed(db_session, record: TelegramStaffConfirmationToken):
    db_session.refresh(record)
    assert record.consumed_at is not None


def test_confirm_skip_executes_only_with_bound_queue_entry(
    db_session, registrar_user, test_doctor, test_patient
):
    entry = _queue_entry(
        db_session,
        test_doctor=test_doctor,
        test_patient=test_patient,
    )
    record = _issue_confirmation(
        db_session,
        user=registrar_user,
        operation_key="queue_call_or_skip_patient",
        command_key="/skip",
        target_type="queue_entry",
        target_id=entry.id,
    )

    result = confirm_staff_action(
        record.id,
        db_session,
        registrar_user,
        StaffActionConfirmRequest(entry_id=entry.id),
    )

    db_session.refresh(entry)
    assert result["success"] is True
    assert result["command_key"] == "/skip"
    assert entry.status == "no_show"
    _assert_consumed(db_session, record)


def test_confirm_cancel_and_move_visit_use_bound_visit_payloads(
    db_session, admin_user, test_doctor, test_patient
):
    cancel_visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    move_visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add_all([cancel_visit, move_visit])
    db_session.flush()
    cancel_entry = _queue_entry(
        db_session,
        test_doctor=test_doctor,
        test_patient=test_patient,
        visit_id=cancel_visit.id,
    )
    move_entry = _queue_entry(
        db_session,
        test_doctor=test_doctor,
        test_patient=test_patient,
        visit_id=move_visit.id,
    )
    cancel_record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="visit_cancel_or_move",
        command_key="/cancel_visit",
        target_type="visit",
        target_id=cancel_visit.id,
    )
    move_record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="visit_cancel_or_move",
        command_key="/move_visit",
        target_type="visit",
        target_id=move_visit.id,
    )

    cancel_result = confirm_staff_action(
        cancel_record.id,
        db_session,
        admin_user,
        StaffActionConfirmRequest(visit_id=cancel_visit.id),
    )
    move_result = confirm_staff_action(
        move_record.id,
        db_session,
        admin_user,
        StaffActionConfirmRequest(
            visit_id=move_visit.id,
            new_visit_date=date.today() + timedelta(days=1),
        ),
    )

    db_session.refresh(cancel_visit)
    db_session.refresh(move_visit)
    db_session.refresh(cancel_entry)
    db_session.refresh(move_entry)
    assert cancel_result["visit_status"] == "cancelled"
    assert cancel_visit.status == "cancelled"
    assert cancel_entry.status == "cancelled"
    assert move_result["visit_date"] == (date.today() + timedelta(days=1)).isoformat()
    assert move_visit.visit_date == date.today() + timedelta(days=1)
    assert move_entry.status == "rescheduled"
    _assert_consumed(db_session, cancel_record)
    _assert_consumed(db_session, move_record)


def test_confirm_payment_status_and_refund_use_bound_payment_payloads(
    db_session, admin_user, test_visit
):
    status_payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("100000"),
        currency="UZS",
        method="cash",
        status="pending",
    )
    refund_payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("50000"),
        currency="UZS",
        method="cash",
        status="paid",
    )
    db_session.add_all([status_payment, refund_payment])
    db_session.flush()
    status_record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="payment_status_change",
        command_key="/payment_status",
        target_type="payment",
        target_id=status_payment.id,
    )
    refund_record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="refund_issue",
        command_key="/refund",
        target_type="payment",
        target_id=refund_payment.id,
    )

    status_result = confirm_staff_action(
        status_record.id,
        db_session,
        admin_user,
        StaffActionConfirmRequest(payment_id=status_payment.id, new_status="paid"),
    )
    refund_result = confirm_staff_action(
        refund_record.id,
        db_session,
        admin_user,
        StaffActionConfirmRequest(
            payment_id=refund_payment.id,
            refund_amount=Decimal("50000"),
            refund_reason="Confirmed in protected app",
        ),
    )

    db_session.refresh(status_payment)
    db_session.refresh(refund_payment)
    assert status_result["status"] == "paid"
    assert status_payment.status == "paid"
    assert refund_result["status"] == "refunded"
    assert refund_payment.status == "refunded"
    assert refund_payment.refunded_amount == Decimal("50000")
    _assert_consumed(db_session, status_record)
    _assert_consumed(db_session, refund_record)


def test_confirm_schedule_change_uses_bound_schedule_payload(
    db_session, admin_user, test_doctor
):
    schedule = Schedule(
        doctor_id=test_doctor.id,
        weekday=2,
        start_time=time(9, 0),
        end_time=time(17, 0),
        active=True,
    )
    db_session.add(schedule)
    db_session.flush()
    record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="doctor_schedule_change",
        command_key="/change_schedule",
        target_type="schedule",
        target_id=schedule.id,
    )

    result = confirm_staff_action(
        record.id,
        db_session,
        admin_user,
        StaffActionConfirmRequest(
            schedule_id=schedule.id,
            start_time=time(10, 0),
            end_time=time(16, 0),
        ),
    )

    db_session.refresh(schedule)
    assert result["success"] is True
    assert schedule.start_time == time(10, 0)
    assert schedule.end_time == time(16, 0)
    _assert_consumed(db_session, record)


def test_confirm_refund_rejects_mismatched_bound_payment_target(
    db_session, admin_user, test_visit
):
    bound_payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("50000"),
        currency="UZS",
        method="cash",
        status="paid",
    )
    other_payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("60000"),
        currency="UZS",
        method="cash",
        status="paid",
    )
    db_session.add_all([bound_payment, other_payment])
    db_session.flush()
    record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="refund_issue",
        command_key="/refund",
        target_type="payment",
        target_id=bound_payment.id,
    )

    with pytest.raises(HTTPException) as exc_info:
        confirm_staff_action(
            record.id,
            db_session,
            admin_user,
            StaffActionConfirmRequest(
                payment_id=other_payment.id,
                refund_amount=Decimal("60000"),
            ),
        )

    db_session.refresh(record)
    db_session.refresh(bound_payment)
    db_session.refresh(other_payment)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "target_binding_mismatch"
    assert record.consumed_at is None
    assert bound_payment.status == "paid"
    assert other_payment.status == "paid"
    assert bound_payment.refunded_amount is None
    assert other_payment.refunded_amount is None


def test_confirm_refund_rejects_unbound_command_level_token(
    db_session, admin_user, test_visit
):
    payment = Payment(
        visit_id=test_visit.id,
        amount=Decimal("50000"),
        currency="UZS",
        method="cash",
        status="paid",
    )
    db_session.add(payment)
    db_session.flush()
    record = _issue_confirmation(
        db_session,
        user=admin_user,
        operation_key="refund_issue",
        command_key="/refund",
    )

    with pytest.raises(HTTPException) as exc_info:
        confirm_staff_action(
            record.id,
            db_session,
            admin_user,
            StaffActionConfirmRequest(
                payment_id=payment.id,
                refund_amount=Decimal("50000"),
            ),
        )

    db_session.refresh(record)
    db_session.refresh(payment)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "target_binding_mismatch"
    assert record.consumed_at is None
    assert payment.status == "paid"
    assert payment.refunded_amount is None
