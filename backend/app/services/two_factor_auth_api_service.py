"""Service layer for two_factor_auth endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

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

    def get_user_from_enrollment_token(self, enrollment_token: str):
        """Resolve user from a single-use '2fa_enrollment' session token.

        The token is a random server-side session value, not a JWT: it is
        accepted only by /2fa/setup and /2fa/verify-setup and can never
        authenticate on business endpoints (those require JWTs).
        """
        enrollment_session = self.repository.get_active_enrollment_session_by_token(
            enrollment_token
        )
        if not enrollment_session:
            return None
        return self.repository.get_user(enrollment_session.user_id)

    def exchange_enrollment_token_for_tokens(
        self,
        *,
        user,
        enrollment_token: str,
        auth_service,
    ) -> dict | None:
        """Complete enrollment: verify-setup success -> normal tokens.

        Single-use: the enrollment session is revoked immediately, so a
        replayed token resolves to nothing.
        """
        # Re-read the principal and session under the same lock order used by
        # setup/verify. A caller must still prove the factor in its transaction.
        user = self.repository.get_user_for_update(user.id)
        if not user or not user.is_active:
            self.repository.rollback()
            return None
        enrollment_session = self.repository.get_active_enrollment_session_for_user(
            user_id=user.id,
            enrollment_token=enrollment_token,
            lock=True,
        )
        if not enrollment_session:
            self.repository.rollback()
            return None

        def enrollment_expired() -> bool:
            expires = enrollment_session.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            return bool(enrollment_session.revoked or datetime.now(UTC) >= expires)

        # Query predicates can become stale while waiting on FOR UPDATE.
        if enrollment_expired():
            self.repository.rollback()
            return None
        if not self.repository.get_verified_two_factor_for_update(user.id):
            self.repository.rollback()
            return None

        # Apply new-login session policy only after the factor is verified;
        # this helper shares our transaction and excludes the challenge being
        # consumed below. The new JWTs use the updated locked-user epoch.
        auth_service.revoke_all_for_new_login_locked(
            self.repository.db, user, exclude_session_id=enrollment_session.id
        )
        jti = str(uuid.uuid4())
        access_token = auth_service.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "auth_epoch": user.auth_epoch,
            }
        )
        refresh_token = auth_service.create_refresh_token(user.id, jti, auth_epoch=user.auth_epoch)
        self.repository.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                token=refresh_token,
                jti=jti,
                expires_at=datetime.now(UTC)
                + timedelta(days=auth_service.refresh_token_expire_days),
            )
        )
        enrollment_session.revoked = True  # single-use
        # Flush 2FA, refresh-token and revocation writes, then check the
        # deadline again before their single shared commit.
        self.repository.flush()
        expires = enrollment_session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if datetime.now(UTC) >= expires:
            self.repository.rollback()
            return None
        self.repository.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": auth_service.access_token_expire_minutes * 60,
        }

    def exchange_pending_token_for_tokens(
        self,
        *,
        user,
        pending_token: str,
        auth_service,
    ) -> dict | None:
        # The caller must first verify the second factor in this transaction.
        user = self.repository.get_user_for_update(user.id)
        if not user or not user.is_active:
            self.repository.rollback()
            return None
        pending_session = self.repository.get_active_session_for_user(
            user_id=user.id,
            pending_token=pending_token,
            lock=True,
        )
        if not pending_session:
            self.repository.rollback()
            return None
        expires = pending_session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if pending_session.revoked or datetime.now(UTC) >= expires:
            self.repository.rollback()
            return None
        if not self.repository.get_verified_two_factor_for_update(user.id):
            self.repository.rollback()
            return None

        from app.services.two_factor_patient_pending import (
            is_patient_pending_kind,
            parse_patient_pending_kind,
        )

        patient_pending = is_patient_pending_kind(pending_session.session_kind)
        patient_id = None
        if patient_pending:
            try:
                patient_id = parse_patient_pending_kind(pending_session.session_kind)
            except ValueError:
                self.repository.rollback()
                return None
            if user.role != "Patient" or not user.is_active or user.is_superuser:
                self.repository.rollback()
                return None
            if patient_id is not None:
                patient = self.repository.get_patient_id_for_update(
                    patient_id=patient_id, user_id=user.id
                )
                if patient is None:
                    self.repository.rollback()
                    return None

        auth_service.revoke_all_for_new_login_locked(
            self.repository.db, user, exclude_session_id=pending_session.id
        )
        if patient_pending:
            from app.api.deps import create_access_token
            from app.core.config import settings

            claims = {"sub": str(user.id), "auth_epoch": user.auth_epoch}
            if patient_id is not None:
                claims.update({"scope": "patient_portal", "patient_id": patient_id})
            access_token = create_access_token(data=claims)
            pending_session.revoked = True
            self.repository.flush()
            if datetime.now(UTC) >= expires:
                self.repository.rollback()
                return None
            self.repository.commit()
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }
        jti = str(uuid.uuid4())
        access_token = auth_service.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "auth_epoch": user.auth_epoch,
            }
        )
        refresh_token = auth_service.create_refresh_token(user.id, jti, auth_epoch=user.auth_epoch)
        self.repository.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                token=refresh_token,
                jti=jti,
                expires_at=datetime.now(UTC)
                + timedelta(days=auth_service.refresh_token_expire_days),
            )
        )
        pending_session.revoked = True
        self.repository.flush()
        if datetime.now(UTC) >= expires:
            self.repository.rollback()
            return None
        self.repository.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": auth_service.access_token_expire_minutes * 60,
        }
