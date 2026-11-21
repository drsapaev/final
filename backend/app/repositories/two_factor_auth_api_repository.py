"""Repository helpers for two_factor_auth endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.authentication import RefreshToken, UserSession
from app.models.patient import Patient
from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.services.two_factor_patient_pending import pending_session_kind_filter


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
                pending_session_kind_filter(UserSession.session_kind),
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
        lock: bool = False,
    ) -> UserSession | None:
        query = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == pending_token,
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
                pending_session_kind_filter(UserSession.session_kind),
            )
        )
        if lock:
            query = query.with_for_update().populate_existing()
        return query.first()

    def get_active_enrollment_session_for_user(
        self,
        *,
        user_id: int,
        enrollment_token: str,
        lock: bool = False,
    ) -> UserSession | None:
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.refresh_token == enrollment_token,
            UserSession.session_kind == "2fa_enrollment",
            UserSession.revoked.is_(False),
            UserSession.expires_at > datetime.now(UTC),
        )
        if lock:
            query = query.with_for_update().populate_existing()
        return query.first()

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_for_update(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .with_for_update(key_share=True)
            .populate_existing()
            .first()
        )

    def get_patient_id_for_update(self, patient_id: int, user_id: int) -> int | None:
        """Lock and verify the live card bound to a pending patient login."""
        row = (
            self.db.query(Patient.id)
            .filter(
                Patient.id == patient_id,
                Patient.user_id == user_id,
                Patient.is_deleted.is_not(True),
            )
            .with_for_update()
            .first()
        )
        return row[0] if row else None

    def get_verified_two_factor_for_update(self, user_id: int) -> TwoFactorAuth | None:
        return (
            self.db.query(TwoFactorAuth)
            .filter(
                TwoFactorAuth.user_id == user_id,
                TwoFactorAuth.totp_enabled.is_(True),
                TwoFactorAuth.totp_verified.is_(True),
            )
            .with_for_update()
            .populate_existing()
            .first()
        )

    def add_refresh_token(self, refresh_token_obj: RefreshToken) -> None:
        self.db.add(refresh_token_obj)

    def commit(self) -> None:
        self.db.commit()

    def flush(self) -> None:
        self.db.flush()

    def rollback(self) -> None:
        self.db.rollback()
