"""Service for one-time Telegram staff action confirmation token storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.telegram_config import TelegramStaffConfirmationToken
from app.repositories.telegram_staff_confirmation_token_repository import (
    TelegramStaffConfirmationTokenRepository,
)

logger = logging.getLogger(__name__)


class TelegramStaffConfirmationTokenService:
    """Issues and consumes hash-only staff action confirmation tokens."""

    def __init__(
        self,
        db: Session,
        repository: TelegramStaffConfirmationTokenRepository | None = None,
    ):
        self.repository = repository or TelegramStaffConfirmationTokenRepository(db)

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def require_non_empty(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    def issue_token(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        operation_key: str,
        action_payload_hash: str,
        expires_at: datetime,
        command_key: str | None = None,
        target_type: str | None = None,
        target_reference_hash: str | None = None,
        idempotency_key_hash: str | None = None,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> TelegramStaffConfirmationToken:
        token_hash = self.require_non_empty(token_hash, "token_hash")
        operation_key = self.require_non_empty(operation_key, "operation_key")
        action_payload_hash = self.require_non_empty(
            action_payload_hash,
            "action_payload_hash",
        )
        expires_at_utc = self.as_utc(expires_at)
        now_utc = self.as_utc(now or self.utc_now())
        if expires_at_utc <= now_utc:
            raise ValueError("staff confirmation token expiry must be in the future")

        try:
            logger.info(
                "Issuing Telegram staff confirmation token user_id=%s "
                "chat_id=%s operation_key=%s",
                staff_user_id,
                telegram_chat_id,
                operation_key,
            )
            record = self.repository.create(
                token_hash=token_hash,
                staff_user_id=staff_user_id,
                telegram_chat_id=telegram_chat_id,
                operation_key=operation_key,
                command_key=command_key,
                action_payload_hash=action_payload_hash,
                target_type=target_type,
                target_reference_hash=target_reference_hash,
                idempotency_key_hash=idempotency_key_hash,
                expires_at=expires_at_utc,
                request_id=request_id,
            )
            self.repository.commit()
            return record
        except Exception:
            self.repository.rollback()
            logger.exception(
                "Failed to issue Telegram staff confirmation token user_id=%s "
                "chat_id=%s operation_key=%s",
                staff_user_id,
                telegram_chat_id,
                operation_key,
            )
            raise

    def consume_for_confirmation(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        operation_key: str,
        action_payload_hash: str,
        idempotency_key_hash: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now_utc = self.as_utc(now or self.utc_now())
        record = self.repository.get_by_token_hash(token_hash)
        if record is None:
            return {"valid": False, "reason": "token_not_issued"}

        if (
            int(record.staff_user_id) != int(staff_user_id)
            or int(record.telegram_chat_id) != int(telegram_chat_id)
        ):
            return {"valid": False, "reason": "token_binding_mismatch"}

        if (
            record.operation_key != operation_key
            or record.action_payload_hash != action_payload_hash
            or record.idempotency_key_hash != idempotency_key_hash
        ):
            return {"valid": False, "reason": "action_binding_mismatch"}

        if record.consumed_at is not None:
            return {"valid": False, "reason": "already_used"}

        expires_at = self.as_utc(record.expires_at)
        if expires_at <= now_utc:
            return {"valid": False, "reason": "expired"}

        updated = self.repository.consume_active(
            token_hash=token_hash,
            staff_user_id=staff_user_id,
            telegram_chat_id=telegram_chat_id,
            operation_key=operation_key,
            action_payload_hash=action_payload_hash,
            idempotency_key_hash=idempotency_key_hash,
            consumed_at=now_utc,
        )
        if updated != 1:
            refreshed = self.repository.get_by_token_hash(token_hash)
            if refreshed and refreshed.consumed_at is not None:
                return {"valid": False, "reason": "already_used"}
            return {"valid": False, "reason": "token_consume_conflict"}

        self.repository.commit()
        logger.info(
            "Consumed Telegram staff confirmation token user_id=%s "
            "chat_id=%s operation_key=%s",
            staff_user_id,
            telegram_chat_id,
            operation_key,
        )
        return {
            "valid": True,
            "reason": "ok",
            "single_use_enforced": True,
            "consumed_at": now_utc.isoformat(),
            "operation_key": record.operation_key,
            "command_key": record.command_key,
            "target_type": record.target_type,
            "request_id": record.request_id,
        }
