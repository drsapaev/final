"""Tokens mixin for AuthenticationService.

Split from authentication_service.py.
"""
from __future__ import annotations

from sqlalchemy.orm import joinedload

from app.core.pii_masker import mask_identifier  # PR-31: mask usernames in logs
from app.core.roles import is_login_blocked_role
from app.core.user_token_claims import (
    has_patient_binding,
    is_user_access_claims,
    is_user_allowed_for_claims,
    parse_user_auth_epoch,
    user_auth_epoch_matches,
)
from app.models.authentication import TokenBlacklist
from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase
from app.services.auth_svc._login_profiling import LoginPhaseTimer


class TokensMixin(AuthenticationServiceMixinBase):
    """Tokens methods."""

    def __init__(self):
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        self.password_reset_expire_hours = 1
        self.email_verification_expire_hours = 24
        self.session_expire_hours = 24
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 15

    @staticmethod
    def _login_user_payload(db: Session, user: User) -> dict[str, Any]:
        """Build the staff profile used for the post-login route decision.

        Doctor specialty is owned by the active ``Doctor`` profile, not by
        ``User.role``.  Returning only the generic role made the frontend fall
        back to ``/doctor`` immediately after login, so specialty panels (and
        their EMR workflow) never mounted until another profile request ran.
        """
        specialty = None
        doctor_id = None
        cabinet = None
        if getattr(user, "role", None) in ("Doctor", "cardio", "derma", "dentist"):
            from app.models.clinic import Doctor

            doctor = (
                db.query(Doctor)
                .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
                .first()
            )
            if doctor:
                specialty = doctor.specialty
                doctor_id = doctor.id
                cabinet = doctor.cabinet

        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "specialty": specialty,
            "doctor_id": doctor_id,
            "cabinet": cabinet,
        }

    def _secret_for(self, token_type: str) -> str:
        if token_type == "refresh":
            return settings.REFRESH_TOKEN_SECRET or settings.SECRET_KEY
        return settings.SECRET_KEY


    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Создает JWT access токен"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=self.algorithm
        )
        return encoded_jwt


    def create_refresh_token(self, user_id: int, jti: str, auth_epoch: int = 0) -> str:
        """Создает JWT refresh токен"""
        if type(auth_epoch) is not int or not 0 <= auth_epoch <= 2**63 - 1:
            raise ValueError("Invalid authentication epoch")
        data = {"user_id": user_id, "jti": jti, "type": "refresh", "auth_epoch": auth_epoch}
        expire = datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days)
        data.update({"exp": expire})

        encoded_jwt = jwt.encode(data, self._secret_for("refresh"), algorithm=self.algorithm)
        return encoded_jwt

    @staticmethod
    def _lock_auth_user(db: Session, user_id: int) -> User | None:
        """The common serialization point for session issuance and revocation."""
        return (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update(key_share=True)
            .populate_existing()
            .first()
        )

    def _revoke_account_sessions_locked(
        self, db: Session, user: User, *, exclude_session_id: int | None = None,
        revoke_password_resets: bool = False,
    ) -> None:
        """Revoke the account under its existing User lock without committing."""
        from app.services.token_blacklist_service import revoke_account_sessions_locked

        revoke_account_sessions_locked(
            db, user, exclude_session_id=exclude_session_id,
            revoke_password_resets=revoke_password_resets,
        )

    def revoke_all_for_new_login_locked(
        self, db: Session, user: User, *, exclude_session_id: int | None = None
    ) -> None:
        """Apply the configured new-login policy in the caller's transaction.

        The caller must hold the User NO KEY UPDATE lock and, when it also
        holds a 2FA lock, lock existing UserSession rows before that lock.
        """
        if getattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", True):
            self._revoke_account_sessions_locked(
                db, user, exclude_session_id=exclude_session_id
            )


    def verify_token(
        self, token: str, token_type: str = "access"
    ) -> dict[str, Any] | None:
        """Проверяет JWT токен (без проверки blacklist)"""
        try:
            # peek: читаем type ДО верификации подписи (чтобы выбрать ключ)
            try:
                unverified = jwt.decode(token, options={"verify_signature": False})
            except Exception:
                return None

            actual_type = unverified.get("type", "access")
            if actual_type != token_type:
                return None

            payload = jwt.decode(
                token, self._secret_for(actual_type), algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None


    def verify_token_with_blacklist(
        self, db: Session, token: str, token_type: str = "access"
    ) -> dict[str, Any] | None:
        """
        Проверяет JWT токен с проверкой черного списка.

        Используйте этот метод для критических операций.
        """
        payload = self.verify_token(token, token_type)
        if not payload or parse_user_auth_epoch(payload) is None:
            return None

        if token_type == "access" and not is_user_access_claims(payload):
            return None

        try:
            user_id = payload.get("user_id") if token_type == "refresh" else payload.get("sub")
            if type(user_id) is int and user_id > 0:
                query = db.query(User).filter(User.id == user_id)
            elif isinstance(user_id, str) and user_id.isascii() and user_id.isdigit() and int(user_id) > 0:
                query = db.query(User).filter(User.id == int(user_id))
            else:
                return None
            user = query.populate_existing().first()
            if not user or not user.is_active or is_login_blocked_role(user.role) or not user_auth_epoch_matches(payload, user.auth_epoch):
                return None
            if token_type == "access" and (
                not is_user_allowed_for_claims(payload, role=user.role, is_active=user.is_active, is_superuser=user.is_superuser)
                or not has_patient_binding(db, payload, user.id)
            ):
                return None
            jti = payload.get("jti")
            if jti is not None and not isinstance(jti, str):
                return None
            from app.services.token_blacklist_service import TokenBlacklistService
            if TokenBlacklistService.is_token_blacklisted(
                db, jti or "", user_id=user.id, auth_epoch=user.auth_epoch
            ):
                return None
            return payload
        except Exception as exc:
            logger.error("Token validation failed: %s", type(exc).__name__)
            return None


    def authenticate_user(
        self,
        db: Session,
        username: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
    ) -> tuple[User | None, str]:
        """Аутентифицирует пользователя"""
        timer = LoginPhaseTimer()
        try:
            logger.debug("authenticate_user called with username=%s", mask_identifier(username))

            # Ищем пользователя по username или email
            # Eager-load two_factor_auth: login_user checks it on every login,
            # and a lazy load here would cost an extra RTT to the remote DB.
            timer.mark("user_lookup")
            user = (
                db.query(User)
                .options(joinedload(User.two_factor_auth))
                .filter(or_(User.username == username, User.email == username))
                .first()
            )
            timer.mark("user_lookup_done")

            if not user:
                logger.debug("User not found for username=%s", mask_identifier(username))
                self._log_login_attempt(
                    db, None, username, ip_address, user_agent, False, "user_not_found"
                )
                return None, "Пользователь не найден"

            logger.debug(
                "User found: ID=%d, Username=%s, IsActive=%s",
                user.id,
                mask_identifier(user.username),
                user.is_active,
            )

            if not user.is_active:
                logger.debug("User is inactive")
                self._log_login_attempt(
                    db,
                    user.id,
                    username,
                    ip_address,
                    user_agent,
                    False,
                    "user_inactive",
                )
                return None, "Пользователь деактивирован"

            # QD-1.1 (queue resource role cleanup): internal-only sentinel
            # roles are structural non-logins. Synthetic queue-resource
            # accounts (0055) must never authenticate whatever their password
            # state — the '!disabled:' hash is not the defense, the role is.
            if is_login_blocked_role(user.role):
                logger.debug("Login blocked for internal-only role user_id=%s", user.id)
                self._log_login_attempt(
                    db,
                    user.id,
                    username,
                    ip_address,
                    user_agent,
                    False,
                    "internal_role_login_blocked",
                )
                return None, "Аккаунт технический, вход запрещён"

            timer.mark("pre_verify")
            logger.debug("Verifying password...")
            # Capture the account state that was actually authenticated,
            # before the audit helper commits and expires ORM attributes.
            authenticated_epoch = user.auth_epoch
            authenticated_hash = user.hashed_password
            password_valid = verify_password(password, authenticated_hash)
            timer.mark("password_verify")
            logger.debug("Password verification result: %s", password_valid)

            if not password_valid:
                logger.debug("Invalid password")
                self._log_login_attempt(
                    db,
                    user.id,
                    username,
                    ip_address,
                    user_agent,
                    False,
                    "invalid_password",
                )
                timer.report(mask_identifier(username))
                return None, "Неверный пароль"

            timer.mark("pre_lockout")
            # Проверяем блокировку
            if self._is_user_locked(db, user.id):
                logger.debug("User is locked")
                self._log_login_attempt(
                    db, user.id, username, ip_address, user_agent, False, "user_locked"
                )
                return (
                    None,
                    "Пользователь заблокирован из-за множественных неудачных попыток входа",
                )

            # Успешный вход
            logger.debug("Authentication successful")
            timer.mark("pre_audit")
            self._log_login_attempt(
                db, user.id, username, ip_address, user_agent, True, None
            )
            self._log_user_activity(
                db, user.id, "login", "Успешный вход в систему", ip_address, user_agent
            )
            timer.mark("audit_writes")
            timer.report(mask_identifier(username))

            # Non-persistent snapshot permits the issuing step to reject a
            # logout/password change that raced the password verification.
            user._password_auth_snapshot = (authenticated_epoch, authenticated_hash)
            return user, "Успешная аутентификация"

        except Exception as e:
            timer.report(mask_identifier(username))
            logger.error("Error authenticating user: %s", type(e).__name__)
            return None, "Ошибка аутентификации"


    def login_user(
        self,
        db: Session,
        username: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None,
        remember_me: bool = False,
    ) -> dict[str, Any]:
        """Выполняет вход пользователя"""
        logger.debug("login_user called with username=%s", mask_identifier(username))

        user, message = self.authenticate_user(
            db, username, password, ip_address, user_agent
        )

        logger.debug(
            "authenticate_user returned user=%s, message=%s",
            user is not None,
            message,
        )

        # Post-auth phase timer (continues the login latency story from
        # authenticate_user's own profile line).
        timer = LoginPhaseTimer()
        timer.mark("auth_complete")

        if not user:
            timer.report(mask_identifier(username))
            logger.debug("Authentication failed, returning error")
            return {"success": False, "message": message, "user": None, "tokens": None}

        # Authentication may race a password change, deactivation or global
        # logout. Re-read and re-check the principal under the same lock used
        # for all session minting/revocation; do not issue from stale state.
        authenticated_snapshot = getattr(user, "_password_auth_snapshot", None)
        user = self._lock_auth_user(db, user.id)
        if (
            not user
            or not user.is_active
            or is_login_blocked_role(user.role)
            or authenticated_snapshot != (user.auth_epoch, user.hashed_password)
            or not verify_password(password, user.hashed_password)
        ):
            db.rollback()
            return {"success": False, "message": "Ошибка аутентификации", "user": None, "tokens": None}
        db.expire(user, ["two_factor_auth"])

        # ✅ SECURITY: Проверяем, требуется ли 2FA до выдачи токенов
        requires_2fa = False
        two_factor_method = None

        # ✅ CERTIFICATION: Принудительное 2FA для критичных ролей (Admin, Cashier)
        from app.core.roles import Roles

        CRITICAL_2FA_ROLES = {Roles.ADMIN, Roles.CASHIER}
        user_role = getattr(user, "role", None)
        is_critical_role = user_role in CRITICAL_2FA_ROLES

        # Проверяем, настроена ли 2FA у пользователя
        has_2fa_enabled = (
            user.two_factor_auth
            and user.two_factor_auth.totp_enabled
            and user.two_factor_auth.totp_verified
        )

        # Если роль критичная (Admin/Cashier), но 2FA не настроена —
        # двухстадийная аутентификация: пароль уже верен, поэтому выдаём
        # строго ограниченный одноразовый enrollment-токен (сервер-сайд,
        # НЕ JWT), который принимают ТОЛЬКО /2fa/setup и /2fa/verify-setup.
        timer.mark("twofa_check")
        if is_critical_role and not has_2fa_enabled:
            enrollment_token = secrets.token_urlsafe(32)
            db.add(
                UserSession(
                    user_id=user.id,
                    refresh_token=enrollment_token,
                    session_kind="2fa_enrollment",
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                    ip=ip_address,
                    user_agent=user_agent,
                )
            )
            db.commit()
            return {
                "success": True,
                "message": "Требуется настройка 2FA",
                "user": self._login_user_payload(db, user),
                "tokens": None,
                "requires_2fa": False,
                "requires_2fa_setup": True,
                "two_factor_method": None,
                "enrollment_token": enrollment_token,
                "enrollment_expires_in": 600,
            }

        # Если 2FA настроена, требуем верификацию
        if has_2fa_enabled:
            requires_2fa = True
            two_factor_method = "totp"

        # Если 2FA требуется — НЕ выдаём основные токены. Создаём временный pending_2fa_token
        if requires_2fa:
            pending_2fa_token = secrets.token_urlsafe(32)
            # Храним маркер в таблице сессий как незавершённую аутентификацию
            session_expires = datetime.now(UTC) + timedelta(
                hours=self.session_expire_hours
            )
            user_session = UserSession(
                user_id=user.id,
                refresh_token=pending_2fa_token,
                session_kind="pending_2fa",
                expires_at=session_expires,
                ip=ip_address,
                user_agent=user_agent,
            )
            db.add(user_session)
            db.commit()
            return {
                "success": True,
                "message": "Требуется подтверждение 2FA",
                "user": self._login_user_payload(db, user),
                "tokens": None,
                "requires_2fa": True,
                "two_factor_method": two_factor_method,
                "pending_2fa_token": pending_2fa_token,
            }

        # Иначе — обычная выдача токенов
        # M4-P0-3: Session fixation protection — revoke all existing sessions
        # before creating a new one. Prevents stolen sessions from remaining
        # valid after a fresh login.
        timer.mark("pre_revoke")
        self.revoke_all_for_new_login_locked(db, user)
        timer.mark("sessions_revoked")

        jti = str(uuid.uuid4())
        access_token = self.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "auth_epoch": user.auth_epoch,
            }
        )
        refresh_token = self.create_refresh_token(user.id, jti, auth_epoch=user.auth_epoch)
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            jti=jti,
            expires_at=datetime.now(UTC)
            + timedelta(days=self.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
        )
        db.add(refresh_token_obj)
        db.commit()
        timer.mark("tokens_issued")
        timer.report(mask_identifier(username))

        return {
            "success": True,
            "message": "Успешный вход",
            "user": self._login_user_payload(db, user),
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60,
            },
            "requires_2fa": requires_2fa,
            "two_factor_method": two_factor_method,
            "must_change_password": getattr(user, 'must_change_password', False),
        }


    def refresh_access_token(self, db: Session, refresh_token: str) -> dict[str, Any]:
        """Обновляет access токен.

        SECURITY (RFC 6749 §10.4): refresh-token rotation — при каждом успешном
        обмене выдаём НОВЫЙ refresh-токен и отзываем старый. Повторное использование
        отозванного refresh-токена трактуется как кража — отзываем всю сессию-семью.
        """
        try:
            # Verify the signed claims before trusting their owner or JTI.
            payload = self.verify_token(refresh_token, "refresh")
            if not payload or type(payload.get("user_id")) is not int or payload["user_id"] <= 0 or not isinstance(payload.get("jti"), str) or not payload["jti"] or parse_user_auth_epoch(payload) is None:
                return {"success": False, "message": "Недействительный refresh токен"}

            # All account-wide revocation and minting takes this lock first.
            user = self._lock_auth_user(db, payload["user_id"])
            if not user or not user.is_active or is_login_blocked_role(user.role) or not user_auth_epoch_matches(payload, user.auth_epoch):
                db.rollback()
                return {"success": False, "message": "Недействительный refresh токен"}

            # This helper returns True on a storage failure; refresh fails
            # closed and checks both the JTI and any applicable legacy marker.
            from app.services.token_blacklist_service import TokenBlacklistService
            if TokenBlacklistService.is_token_blacklisted(
                db, payload["jti"], user_id=user.id, auth_epoch=user.auth_epoch
            ):
                db.rollback()
                return {"success": False, "message": "Недействительный refresh токен"}

            # Lock linked sessions before the refresh record, matching logout
            # and enrollment. Legacy/direct logins need not have such a row.
            sessions = (
                db.query(UserSession)
                .filter(UserSession.user_id == user.id)
                .order_by(UserSession.id)
                .with_for_update()
                .populate_existing()
                .all()
            )
            linked_sessions = [s for s in sessions if s.refresh_token == refresh_token]
            token_obj = (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.token == refresh_token,
                    RefreshToken.user_id == user.id,
                    RefreshToken.jti == payload["jti"],
                )
                .with_for_update()
                .populate_existing()
                .first()
            )

            if not token_obj:
                db.rollback()
                return {
                    "success": False,
                    "message": "Refresh токен не найден или истек",
                }

            # The signed token may have expired while waiting on row locks.
            if not self.verify_token(refresh_token, "refresh"):
                db.rollback()
                return {"success": False, "message": "Недействительный refresh токен"}

            # A replay invalidates the whole account's prior epoch in the
            # same transaction as session and refresh-token revocation.
            if token_obj.revoked:
                self._revoke_account_sessions_locked(db, user)
                db.commit()
                logger.warning("Refresh-token reuse detected; account sessions revoked")
                return {
                    "success": False,
                    "message": "Refresh токен недействителен",
                }

            now = datetime.now(UTC)
            expires_at = token_obj.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if now >= expires_at or any(
                s.revoked or now >= (s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=UTC))
                for s in linked_sessions
            ):
                db.rollback()
                return {
                    "success": False,
                    "message": "Refresh токен не найден или истек",
                }

            # Rotate only once while holding the account and token locks.
            new_jti = str(uuid.uuid4())
            access_token = self.create_access_token(
                {
                    "sub": str(user.id),
                    "username": user.username,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                    "auth_epoch": user.auth_epoch,
                }
            )
            new_refresh_token = self.create_refresh_token(user.id, new_jti, auth_epoch=user.auth_epoch)

            # 6) Отзываем старый refresh-токен и записываем новый в БД.
            token_obj.revoked = True
            token_obj.revoked_at = datetime.now(UTC)

            new_token_obj = RefreshToken(
                user_id=user.id,
                token=new_refresh_token,
                jti=new_jti,
                expires_at=datetime.now(UTC)
                + timedelta(days=self.refresh_token_expire_days),
                ip_address=token_obj.ip_address,
                user_agent=token_obj.user_agent,
                device_fingerprint=token_obj.device_fingerprint,
            )
            db.add(new_token_obj)

            for session in linked_sessions:
                session.refresh_token = new_refresh_token

            # Token generation can itself take time. Do not commit a rotation
            # whose signed credential has expired since the previous check.
            if not self.verify_token(refresh_token, "refresh"):
                db.rollback()
                return {"success": False, "message": "Недействительный refresh токен"}

            db.commit()

            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": new_refresh_token,  # NEW: rotated token
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60,
            }

        except Exception as e:
            logger.error("Error refreshing token: %s", type(e).__name__)
            db.rollback()
            return {"success": False, "message": "Ошибка обновления токена"}


    def logout_user(
        self,
        db: Session,
        refresh_token: str = None,
        user_id: int = None,
        logout_all: bool = False,
        access_token_jti: str | None = None,
        access_token_exp: datetime | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Выполняет выход пользователя.

        Args:
            access_token_jti: JTI текущего access-токена (для индивидуального отзыва).
            access_token_exp: expiry access-токена (нужен для blacklist_token).
        """
        try:
            if logout_all and user_id:
                user = self._lock_auth_user(db, user_id)
                if not user:
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                if access_token is not None and not self._logout_bearer_claims(db, user, access_token):
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                self._revoke_account_sessions_locked(db, user, revoke_password_resets=True)
                if access_token is not None and not self.verify_token(access_token, "access"):
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                db.commit()
                self._log_user_activity(
                    db, user_id, "logout_all", "Выход со всех устройств"
                )

            elif refresh_token or (user_id and (access_token_jti or access_token is not None)):
                # When no user is supplied (legacy internal callers), an
                # initial lookup only selects the lock owner; the actual row
                # is re-read under that user's lock before mutation.
                owner_id = user_id
                if owner_id is None and refresh_token:
                    owner_id = db.query(RefreshToken.user_id).filter(
                        RefreshToken.token == refresh_token
                    ).scalar()
                user = self._lock_auth_user(db, owner_id) if owner_id else None
                if not user:
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                if access_token is not None:
                    claims = self._logout_bearer_claims(db, user, access_token)
                    if not claims:
                        db.rollback()
                        return {"success": False, "message": "Ошибка выхода"}
                    access_token_jti = claims["jti"]
                    access_token_exp = datetime.fromtimestamp(claims["exp"], tz=UTC)

                linked_sessions = []
                token_obj = None
                if refresh_token:
                    linked_sessions = (
                        db.query(UserSession)
                        .filter(UserSession.user_id == user.id, UserSession.refresh_token == refresh_token)
                        .order_by(UserSession.id)
                        .with_for_update()
                        .populate_existing()
                        .all()
                    )
                    token_obj = (
                        db.query(RefreshToken)
                        .filter(RefreshToken.user_id == user.id, RefreshToken.token == refresh_token)
                        .with_for_update()
                        .populate_existing()
                        .first()
                    )
                if access_token is not None and not self.verify_token(access_token, "access"):
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                if token_obj:
                    token_obj.revoked = True
                    token_obj.revoked_at = datetime.now(UTC)
                for session in linked_sessions:
                    session.revoked = True

                # Individual access revocation commits atomically with the
                # refresh/session revocation, without advancing other sessions.
                if access_token_jti and access_token_exp:
                    expiry = access_token_exp
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=UTC)
                    if expiry > datetime.now(UTC) and not db.query(TokenBlacklist.id).filter(
                        TokenBlacklist.jti == access_token_jti
                    ).first():
                        db.add(TokenBlacklist(
                            jti=access_token_jti, user_id=user.id,
                            expires_at=expiry, reason="logout",
                        ))
                if access_token is not None and not self.verify_token(access_token, "access"):
                    db.rollback()
                    return {"success": False, "message": "Ошибка выхода"}
                db.commit()
                self._log_user_activity(db, user.id, "logout", "Выход из системы")

            else:
                db.commit()

            return {"success": True, "message": "Успешный выход"}

        except Exception as e:
            logger.error("Error logging out user: %s", type(e).__name__)
            db.rollback()
            return {"success": False, "message": "Ошибка выхода"}

    def _logout_bearer_claims(self, db: Session, user: User, token: str) -> dict[str, Any] | None:
        """Revalidate public logout credentials under the account row lock."""
        payload = self.verify_token_with_blacklist(db, token, "access")
        if (
            not payload
            or int(payload["sub"]) != user.id
            or not isinstance(payload.get("jti"), str)
            or not payload["jti"]
            or type(payload.get("exp")) is not int
        ):
            return None
        return payload

    def _revoke_all_user_sessions(
        self, db: Session, user_id: int, *, reason: str = "unspecified"
    ) -> int:
        """M4-P0-3: Revoke all active sessions + refresh tokens for a user.

        Used for session fixation protection on new login.
        Returns the number of sessions revoked.

        Args:
            db: SQLAlchemy session
            user_id: User whose sessions to revoke
            reason: Audit reason (e.g. 'new_login', 'security_alert')
        """
        try:
            user = self._lock_auth_user(db, user_id)
            if not user:
                db.rollback()
                return 0
            session_count = db.query(UserSession).filter(
                UserSession.user_id == user_id, UserSession.revoked.is_(False)
            ).count()
            self._revoke_account_sessions_locked(db, user)
            db.commit()

            if session_count > 0:
                logger.info(
                    "Revoked %d sessions (reason=%s)",
                    session_count,
                    reason,
                )

            return session_count

        except Exception as e:
            logger.error("Error revoking user sessions: %s", type(e).__name__)
            db.rollback()
            return 0


