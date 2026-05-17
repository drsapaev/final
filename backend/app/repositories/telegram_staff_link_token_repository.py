"""Repository for one-time Telegram staff link tokens."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.telegram_config import TelegramStaffLinkToken


class TelegramStaffLinkTokenRepository:
    """Encapsulates storage access for hash-only staff link tokens."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        expires_at: datetime,
        issued_by_user_id: int | None = None,
        request_id: str | None = None,
    ) -> TelegramStaffLinkToken:
        record = TelegramStaffLinkToken(
            token_hash=token_hash,
            staff_user_id=staff_user_id,
            telegram_chat_id=telegram_chat_id,
            expires_at=expires_at,
            issued_by_user_id=issued_by_user_id,
            request_id=request_id,
        )
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_by_token_hash(self, token_hash: str) -> TelegramStaffLinkToken | None:
        return (
            self.db.query(TelegramStaffLinkToken)
            .filter(TelegramStaffLinkToken.token_hash == token_hash)
            .first()
        )

    def consume_active(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        consumed_at: datetime,
    ) -> int:
        return (
            self.db.query(TelegramStaffLinkToken)
            .filter(
                TelegramStaffLinkToken.token_hash == token_hash,
                TelegramStaffLinkToken.staff_user_id == staff_user_id,
                TelegramStaffLinkToken.telegram_chat_id == telegram_chat_id,
                TelegramStaffLinkToken.consumed_at.is_(None),
                TelegramStaffLinkToken.expires_at > consumed_at,
            )
            .update(
                {TelegramStaffLinkToken.consumed_at: consumed_at},
                synchronize_session=False,
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
