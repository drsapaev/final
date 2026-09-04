"""Repository helpers for two_factor_auth endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.authentication import RefreshToken, UserSession
from app.models.user import User


class TwoFactorAuthApiRepository:
    """Encapsulates ORM operations used by 2FA verification endpoint."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_session_by_token(self, pending_token: str) -> UserSession | None:
        """Active pending-2FA session by token (challenge flow).

        NULL session_kind (legacy rows) counts as 'pending_2fa';
        '2fa_enrollment' sessions are deliberately excluded.
        """
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.refresh_token == pending_token,
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
                UserSession.session_kind.is_(None)
                | (UserSession.session_kind == "pending_2fa"),
            )
            .first()
        )

    def get_active_enrollment_session_by_token(
        self, enrollment_token: str
    ) -> UserSession | None:
        """Active '2fa_enrollment' session by token — setup endpoints only."""
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.refresh_token == enrollment_token,
                UserSession.session_kind == "2fa_enrollment",
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
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
                UserSession.expires_at > datetime.now(UTC),
                UserSession.session_kind.is_(None)
                | (UserSession.session_kind == "pending_2fa"),
            )
            .first()
        )

    def get_active_enrollment_session_for_user(
        self,
        *,
        user_id: int,
        enrollment_token: str,
    ) -> UserSession | None:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == enrollment_token,
                UserSession.session_kind == "2fa_enrollment",
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
            )
            .first()
        )

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def add_refresh_token(self, refresh_token_obj: RefreshToken) -> None:
        self.db.add(refresh_token_obj)

    def commit(self) -> None:
        self.db.commit()
