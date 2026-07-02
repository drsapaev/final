"""Repository for one-time Telegram staff action confirmation tokens."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.telegram_config import TelegramStaffConfirmationToken


class TelegramStaffConfirmationTokenRepository:
    """Encapsulates storage access for hash-only staff confirmation tokens."""

    def __init__(self, db: Session):
        self.db = db

    def create(
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
    ) -> TelegramStaffConfirmationToken:
        record = TelegramStaffConfirmationToken(
            token_hash=token_hash,
            staff_user_id=staff_user_id,
            telegram_chat_id=telegram_chat_id,
            operation_key=operation_key,
            command_key=command_key,
            action_payload_hash=action_payload_hash,
            target_type=target_type,
            target_reference_hash=target_reference_hash,
            idempotency_key_hash=idempotency_key_hash,
            expires_at=expires_at,
            request_id=request_id,
        )
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_by_token_hash(
        self, token_hash: str
    ) -> TelegramStaffConfirmationToken | None:
        return (
            self.db.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.token_hash == token_hash)
            .first()
        )

    def consume_active(
        self,
        *,
        token_hash: str,
        staff_user_id: int,
        telegram_chat_id: int,
        operation_key: str,
        action_payload_hash: str,
        idempotency_key_hash: str | None,
        consumed_at: datetime,
    ) -> int:
        query = self.db.query(TelegramStaffConfirmationToken).filter(
            TelegramStaffConfirmationToken.token_hash == token_hash,
            TelegramStaffConfirmationToken.staff_user_id == staff_user_id,
            TelegramStaffConfirmationToken.telegram_chat_id == telegram_chat_id,
            TelegramStaffConfirmationToken.operation_key == operation_key,
            TelegramStaffConfirmationToken.action_payload_hash
            == action_payload_hash,
            TelegramStaffConfirmationToken.consumed_at.is_(None),
            TelegramStaffConfirmationToken.expires_at > consumed_at,
        )
        if idempotency_key_hash is None:
            query = query.filter(
                TelegramStaffConfirmationToken.idempotency_key_hash.is_(None)
            )
        else:
            query = query.filter(
                TelegramStaffConfirmationToken.idempotency_key_hash
                == idempotency_key_hash
            )

        return query.update(
            {TelegramStaffConfirmationToken.consumed_at: consumed_at},
            synchronize_session=False,
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
