"""Protected domain adapters for confirmed Telegram staff actions."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, UTC
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud import audit as crud_audit
from app.models.clinic import Schedule
from app.models.payment import Payment
from app.models.visit import Visit
from app.services.billing_service import BillingService
from app.services.queue_service import QueueBusinessService


class TelegramStaffActionAdapterError(ValueError):
    """Raised when a protected staff action cannot be executed safely."""


def _reference_hash(kind: str, value: Any) -> str:
    digest = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()
    alphabetic_digest = digest[:24].translate(
        str.maketrans("0123456789abcdef", "abcdefghijklmnop")
    )
    return f"{kind}:{alphabetic_digest}"


class TelegramStaffActionAdapterService:
    """Executes confirmed staff actions through the clinic domain layer.

    Telegram remains a request/notification surface. These adapters are intended
    for the protected app confirmation step and do not trust Telegram text as a
    source of raw target identifiers.
    """

    def __init__(self, db: Session):
        self.db = db
        self.queue_service = QueueBusinessService()

    def _record_audit(
        self,
        *,
        action: str,
        actor_user_id: int,
        operation_key: str,
        target_type: str,
        target_id: int | str | None,
        result: str,
        command_key: str | None = None,
        telegram_chat_id: int | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "actor_user_id": actor_user_id,
            "operation_key": operation_key,
            "command_key": command_key,
            "actor_role": "protected_app_staff",
            "telegram_user_id_hash": (
                _reference_hash("telegram_chat", telegram_chat_id)
                if telegram_chat_id is not None
                else None
            ),
            "action_key": action,
            "target_type": target_type,
            "target_reference_hash": (
                _reference_hash(target_type, target_id)
                if target_id is not None
                else _reference_hash(target_type, operation_key)
            ),
            "result": result,
            "timestamp": datetime.now(UTC).isoformat(),
            "confirmation_required": True,
            "telegram_execution_enabled": False,
            "domain_mutation": result == "completed",
            "state_changing_action": True,
            "redacted": True,
        }
        if reason:
            payload["reason"] = reason
        if extra:
            payload.update(extra)

        crud_audit.log(
            self.db,
            action=action,
            entity_type=target_type,
            entity_id=int(target_id) if isinstance(target_id, int) else None,
            actor_user_id=actor_user_id,
            payload=payload,
        )

    def _confirmed(
        self,
        *,
        actor_user_id: int,
        operation_key: str,
        target_type: str,
        target_id: int | str | None,
        command_key: str | None,
        telegram_chat_id: int | None,
    ) -> None:
        self._record_audit(
            action="staff_action_confirmed",
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type=target_type,
            target_id=target_id,
            result="confirmed",
            telegram_chat_id=telegram_chat_id,
        )

    def _completed(
        self,
        *,
        actor_user_id: int,
        operation_key: str,
        target_type: str,
        target_id: int | str | None,
        command_key: str | None,
        telegram_chat_id: int | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._record_audit(
            action="staff_action_completed",
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type=target_type,
            target_id=target_id,
            result="completed",
            telegram_chat_id=telegram_chat_id,
            extra=extra,
        )

    def _failed(
        self,
        *,
        actor_user_id: int,
        operation_key: str,
        target_type: str,
        target_id: int | str | None,
        command_key: str | None,
        telegram_chat_id: int | None,
        reason: str,
    ) -> None:
        self._record_audit(
            action="staff_action_failed",
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type=target_type,
            target_id=target_id,
            result="failed",
            telegram_chat_id=telegram_chat_id,
            reason=reason,
        )

    def _commit_or_flush(self, commit: bool) -> None:
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def staff_call_next_patient(
        self,
        *,
        actor_user_id: int,
        queue_id: int | None = None,
        specialist_id: int | None = None,
        queue_tag: str | None = None,
        target_date: date | None = None,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "queue_call_or_skip_patient"
        command_key = "/call"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="queue",
            target_id=queue_id or queue_tag or "next_patient",
            telegram_chat_id=telegram_chat_id,
        )
        try:
            result = self.queue_service.staff_call_next_patient(
                self.db,
                queue_id=queue_id,
                specialist_id=specialist_id,
                queue_tag=queue_tag,
                target_date=target_date,
                actor_user_id=actor_user_id,
                commit=False,
            )
            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="queue_entry",
                target_id=result.get("entry_id"),
                telegram_chat_id=telegram_chat_id,
                extra={"queue_time_preserved": result.get("queue_time_preserved")},
            )
            self._commit_or_flush(commit)
            return result
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="queue",
                target_id=queue_id or queue_tag or "next_patient",
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_skip_queue_entry(
        self,
        *,
        entry_id: int,
        actor_user_id: int,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "queue_call_or_skip_patient"
        command_key = "/skip"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="queue_entry",
            target_id=entry_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            result = self.queue_service.staff_skip_queue_entry(
                self.db,
                entry_id=entry_id,
                actor_user_id=actor_user_id,
                commit=False,
            )
            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="queue_entry",
                target_id=entry_id,
                telegram_chat_id=telegram_chat_id,
                extra={"queue_time_preserved": result.get("queue_time_preserved")},
            )
            self._commit_or_flush(commit)
            return result
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="queue_entry",
                target_id=entry_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_cancel_visit(
        self,
        *,
        visit_id: int,
        actor_user_id: int,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "visit_cancel_or_move"
        command_key = "/cancel_visit"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="visit",
            target_id=visit_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise TelegramStaffActionAdapterError("visit_not_found")
            if str(visit.status or "").lower() in {"closed", "canceled", "cancelled"}:
                raise TelegramStaffActionAdapterError("visit_already_closed")

            previous_visit_status = visit.status
            visit.status = "cancelled"
            queue_result = self.queue_service.staff_cancel_visit_queue_link(
                self.db,
                visit_id=visit_id,
                actor_user_id=actor_user_id,
                commit=False,
            )
            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="visit",
                target_id=visit_id,
                telegram_chat_id=telegram_chat_id,
                extra={
                    "previous_visit_status": previous_visit_status,
                    "visit_status": visit.status,
                    "queue_entry_status": queue_result.get("status"),
                    "queue_time_preserved": queue_result.get("queue_time_preserved"),
                },
            )
            self._commit_or_flush(commit)
            return {
                "success": True,
                "action": "staff_cancel_visit",
                "visit_id": visit.id,
                "previous_visit_status": previous_visit_status,
                "visit_status": visit.status,
                "queue": queue_result,
            }
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="visit",
                target_id=visit_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_move_visit(
        self,
        *,
        visit_id: int,
        new_visit_date: date,
        actor_user_id: int,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "visit_cancel_or_move"
        command_key = "/move_visit"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="visit",
            target_id=visit_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise TelegramStaffActionAdapterError("visit_not_found")
            if str(visit.status or "").lower() in {"closed", "canceled", "cancelled"}:
                raise TelegramStaffActionAdapterError("visit_already_closed")
            if new_visit_date < date.today():
                raise TelegramStaffActionAdapterError("new_visit_date_in_past")

            previous_visit_date = visit.visit_date
            visit.visit_date = new_visit_date
            queue_result = self.queue_service.staff_move_visit_queue_link(
                self.db,
                visit_id=visit_id,
                actor_user_id=actor_user_id,
                commit=False,
            )
            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="visit",
                target_id=visit_id,
                telegram_chat_id=telegram_chat_id,
                extra={
                    "previous_visit_date": (
                        previous_visit_date.isoformat()
                        if previous_visit_date
                        else None
                    ),
                    "visit_date": visit.visit_date.isoformat(),
                    "queue_entry_status": queue_result.get("status"),
                    "queue_time_preserved": queue_result.get("queue_time_preserved"),
                },
            )
            self._commit_or_flush(commit)
            return {
                "success": True,
                "action": "staff_move_visit",
                "visit_id": visit.id,
                "previous_visit_date": previous_visit_date,
                "visit_date": visit.visit_date,
                "queue": queue_result,
            }
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="visit",
                target_id=visit_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_change_payment_status(
        self,
        *,
        payment_id: int,
        new_status: str,
        actor_user_id: int,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "payment_status_change"
        command_key = "/payment_status"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="payment",
            target_id=payment_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            payment = BillingService(self.db).update_payment_status(
                payment_id,
                new_status,
                meta={
                    "staff_action": "telegram_confirmed_payment_status_change",
                    "actor_user_id": actor_user_id,
                },
                commit=False,
            )
            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="payment",
                target_id=payment_id,
                telegram_chat_id=telegram_chat_id,
                extra={"payment_status": payment.status},
            )
            self._commit_or_flush(commit)
            return {
                "success": True,
                "action": "staff_change_payment_status",
                "payment_id": payment.id,
                "status": payment.status,
            }
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="payment",
                target_id=payment_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_refund_payment(
        self,
        *,
        payment_id: int,
        actor_user_id: int,
        amount: Decimal | int | str | None = None,
        reason: str | None = None,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "refund_issue"
        command_key = "/refund"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="payment",
            target_id=payment_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise TelegramStaffActionAdapterError("payment_not_found")
            if payment.status not in {"paid", "completed"}:
                raise TelegramStaffActionAdapterError("payment_status_not_refundable")

            already_refunded = payment.refunded_amount or Decimal("0")
            available = payment.amount - already_refunded
            refund_amount = available if amount is None else Decimal(str(amount))
            if refund_amount <= 0:
                raise TelegramStaffActionAdapterError("refund_amount_not_positive")
            if refund_amount > available:
                raise TelegramStaffActionAdapterError("refund_amount_exceeds_available")

            payment.refunded_amount = already_refunded + refund_amount
            payment.refund_reason = (reason or "Protected staff Telegram action")[:512]
            payment.refunded_at = datetime.now(UTC)
            payment.refunded_by = actor_user_id
            if payment.refunded_amount >= payment.amount:
                payment.status = "refunded"

            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="payment",
                target_id=payment_id,
                telegram_chat_id=telegram_chat_id,
                extra={
                    "payment_status": payment.status,
                    "refund_amount": str(refund_amount),
                    "refunded_amount": str(payment.refunded_amount),
                },
            )
            self._commit_or_flush(commit)
            return {
                "success": True,
                "action": "staff_refund_payment",
                "payment_id": payment.id,
                "status": payment.status,
                "refund_amount": refund_amount,
                "refunded_amount": payment.refunded_amount,
                "remaining_amount": payment.amount - payment.refunded_amount,
            }
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="payment",
                target_id=payment_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise

    def staff_change_doctor_schedule(
        self,
        *,
        schedule_id: int,
        actor_user_id: int,
        start_time: time | None = None,
        end_time: time | None = None,
        breaks: list[dict[str, str]] | None = None,
        active: bool | None = None,
        telegram_chat_id: int | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        operation_key = "doctor_schedule_change"
        command_key = "/change_schedule"
        self._confirmed(
            actor_user_id=actor_user_id,
            operation_key=operation_key,
            command_key=command_key,
            target_type="schedule",
            target_id=schedule_id,
            telegram_chat_id=telegram_chat_id,
        )
        try:
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                raise TelegramStaffActionAdapterError("schedule_not_found")
            if start_time is None and end_time is None and breaks is None and active is None:
                raise TelegramStaffActionAdapterError("schedule_change_empty")
            if start_time is not None and end_time is not None and start_time >= end_time:
                raise TelegramStaffActionAdapterError("schedule_time_range_invalid")

            previous = {
                "start_time": schedule.start_time.isoformat()
                if schedule.start_time
                else None,
                "end_time": schedule.end_time.isoformat() if schedule.end_time else None,
                "active": schedule.active,
            }
            if start_time is not None:
                schedule.start_time = start_time
            if end_time is not None:
                schedule.end_time = end_time
            if breaks is not None:
                schedule.breaks = breaks
            if active is not None:
                schedule.active = active

            self._completed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="schedule",
                target_id=schedule_id,
                telegram_chat_id=telegram_chat_id,
                extra={
                    "previous": previous,
                    "start_time": schedule.start_time.isoformat()
                    if schedule.start_time
                    else None,
                    "end_time": schedule.end_time.isoformat()
                    if schedule.end_time
                    else None,
                    "active": schedule.active,
                },
            )
            self._commit_or_flush(commit)
            return {
                "success": True,
                "action": "staff_change_doctor_schedule",
                "schedule_id": schedule.id,
                "start_time": schedule.start_time,
                "end_time": schedule.end_time,
                "active": schedule.active,
            }
        except HTTPException:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="schedule",
                target_id=schedule_id,
                telegram_chat_id=telegram_chat_id,
                reason="HTTPException",
            )
            self._commit_or_flush(commit)
            raise
        except Exception as exc:
            self.db.rollback()
            self._failed(
                actor_user_id=actor_user_id,
                operation_key=operation_key,
                command_key=command_key,
                target_type="schedule",
                target_id=schedule_id,
                telegram_chat_id=telegram_chat_id,
                reason=type(exc).__name__,
            )
            self._commit_or_flush(commit)
            raise
