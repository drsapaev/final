"""Repository helpers for telegram_bot_management endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User


class TelegramBotManagementRepository:
    """Encapsulates user lookups for Telegram bot admin endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def count_users_with_telegram(self) -> int:
        return self.db.query(User).filter(User.telegram_chat_id.isnot(None)).count()

    def count_active_users_with_telegram(self) -> int:
        return (
            self.db.query(User)
            .filter(User.telegram_chat_id.isnot(None), User.is_active.is_(True))
            .count()
        )

    def count_admin_users_with_telegram(self) -> int:
        return (
            self.db.query(User)
            .filter(
                User.role.in_(["Admin", "SuperAdmin"]),
                User.telegram_chat_id.isnot(None),
            )
            .count()
        )

    def list_active_user_ids_with_telegram(self) -> list[int]:
        rows = (
            self.db.query(User.id)
            .filter(User.telegram_chat_id.isnot(None), User.is_active.is_(True))
            .all()
        )
        return [row.id for row in rows]

    def list_users_with_telegram(self) -> list[User]:
        return self.db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
