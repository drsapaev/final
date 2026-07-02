"""Repository helpers for two_factor_auth endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.authentication import RefreshToken, UserSession
from app.models.user import User


class TwoFactorAuthApiRepository:
    """Encapsulates ORM operations used by 2FA verification endpoint."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_session_by_token(self, pending_token: str) -> UserSession | None:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.refresh_token == pending_token,
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.utcnow(),
            )
            .first()
        )

    def get_active_session_for_user(
        self,
        *,
        user_id: int,
        pending_token: str,
    ) -> UserSession | None:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == pending_token,
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.utcnow(),
            )
            .first()
        )

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def add_refresh_token(self, refresh_token_obj: RefreshToken) -> None:
        self.db.add(refresh_token_obj)

    def commit(self) -> None:
        self.db.commit()
