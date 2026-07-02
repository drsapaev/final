"""Service layer for two_factor_auth endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from app.models.authentication import RefreshToken
from app.repositories.two_factor_auth_api_repository import TwoFactorAuthApiRepository


class TwoFactorAuthApiService:
    """Builds pending-token user lookup and token exchange payloads."""

    def __init__(self, db, repository: TwoFactorAuthApiRepository | None = None):
        self.repository = repository or TwoFactorAuthApiRepository(db)

    def get_user_from_pending_token(self, pending_token: str):
        pending_session = self.repository.get_active_session_by_token(pending_token)
        if not pending_session:
            return None
        return self.repository.get_user(pending_session.user_id)

    def exchange_pending_token_for_tokens(
        self,
        *,
        user,
        pending_token: str,
        auth_service,
    ) -> dict | None:
        pending_session = self.repository.get_active_session_for_user(
            user_id=user.id,
            pending_token=pending_token,
        )
        if not pending_session:
            return None

        jti = str(uuid.uuid4())
        access_token = auth_service.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            }
        )
        refresh_token = auth_service.create_refresh_token(user.id, jti)
        self.repository.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                token=refresh_token,
                jti=jti,
                expires_at=datetime.utcnow()
                + timedelta(days=auth_service.refresh_token_expire_days),
            )
        )
        pending_session.user_agent = (pending_session.user_agent or "") + "|2fa-verified"
        self.repository.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": auth_service.access_token_expire_minutes * 60,
        }
