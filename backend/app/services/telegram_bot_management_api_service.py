"""Service layer for telegram_bot_management endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.telegram_bot_management_repository import (
    TelegramBotManagementRepository,
)


class TelegramBotManagementApiService:
    """Builds payloads for Telegram bot management API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: TelegramBotManagementRepository | None = None,
    ):
        self.repository = repository or TelegramBotManagementRepository(db)

    def get_stats_payload(self) -> dict:
        return {
            "total_users": self.repository.count_users_with_telegram(),
            "active_users": self.repository.count_active_users_with_telegram(),
            "admin_users": self.repository.count_admin_users_with_telegram(),
            "messages_sent_today": 0,
            "commands_processed_today": 0,
        }

    def count_admin_recipients(self) -> int:
        return self.repository.count_admin_users_with_telegram()

    def list_active_user_recipients(self) -> list[int]:
        return self.repository.list_active_user_ids_with_telegram()

    def get_users_with_telegram_payload(self) -> dict:
        users = self.repository.list_users_with_telegram()
        payload = [
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "telegram_chat_id": user.telegram_chat_id,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
            for user in users
        ]
        return {"users": payload, "total_count": len(payload)}
