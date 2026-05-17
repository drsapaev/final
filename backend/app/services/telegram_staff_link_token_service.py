"""Service for one-time Telegram staff link token storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.telegram_config import TelegramStaffLinkToken
from app.repositories.telegram_staff_link_token_repository import (
    TelegramStaffLinkTokenRepository,
)

logger = logging.getLogger(__name__)


class TelegramStaffLinkTokenService:
    """Issues and consumes hash-only staff link tokens."""

    def __init__(
        self,
        db: Session,
        repository: TelegramStaffLinkTokenRepository | None = None,
    ):
        self.repository = repository or TelegramStaffLinkTokenRepository(db)

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def issue_token(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        expires_at: datetime,
        issued_by_user_id: int | None = None,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> TelegramStaffLinkToken:
        expires_at_utc = self.as_utc(expires_at)
        now_utc = self.as_utc(now or self.utc_now())
        if expires_at_utc <= now_utc:
            raise ValueError("staff link token expiry must be in the future")

        try:
            logger.info(
                "Issuing Telegram staff link token user_id=%s chat_id=%s",
                staff_user_id,
                telegram_chat_id,
            )
            record = self.repository.create(
                token_hash=token_hash,
                staff_user_id=staff_user_id,
                telegram_chat_id=telegram_chat_id,
                expires_at=expires_at_utc,
                issued_by_user_id=issued_by_user_id,
                request_id=request_id,
            )
            self.repository.commit()
            return record
        except Exception:
            self.repository.rollback()
            logger.exception(
                "Failed to issue Telegram staff link token user_id=%s chat_id=%s",
                staff_user_id,
                telegram_chat_id,
            )
            raise

    def consume_for_validation(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now_utc = self.as_utc(now or self.utc_now())
        record = self.repository.get_by_token_hash(token_hash)
        if record is None:
            return {"valid": False, "reason": "token_not_issued"}

        mismatch = (
            int(record.staff_user_id) != int(staff_user_id)
            or int(record.telegram_chat_id) != int(telegram_chat_id)
        )
        if mismatch:
            return {"valid": False, "reason": "token_binding_mismatch"}

        if record.consumed_at is not None:
            return {"valid": False, "reason": "already_used"}

        expires_at = self.as_utc(record.expires_at)
        if expires_at <= now_utc:
            return {"valid": False, "reason": "expired"}

        updated = self.repository.consume_active(
            token_hash=token_hash,
            staff_user_id=staff_user_id,
            telegram_chat_id=telegram_chat_id,
            consumed_at=now_utc,
        )
        if updated != 1:
            refreshed = self.repository.get_by_token_hash(token_hash)
            if refreshed and refreshed.consumed_at is not None:
                return {"valid": False, "reason": "already_used"}
            return {"valid": False, "reason": "token_consume_conflict"}

        self.repository.commit()
        logger.info(
            "Consumed Telegram staff link token user_id=%s chat_id=%s",
            staff_user_id,
            telegram_chat_id,
        )
        return {
            "valid": True,
            "reason": "ok",
            "single_use_enforced": True,
            "consumed_at": now_utc.isoformat(),
        }
