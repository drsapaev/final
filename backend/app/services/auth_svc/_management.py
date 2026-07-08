"""Management mixin for AuthenticationService.

Split from authentication_service.py.
"""
from __future__ import annotations

from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase


class ManagementMixin(AuthenticationServiceMixinBase):
    """Management methods."""

    def _is_user_locked(self, db: Session, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь"""
        try:
            # Подсчитываем неудачные попытки за последние 15 минут
            lockout_time = datetime.now(UTC) - timedelta(
                minutes=self.lockout_duration_minutes
            )
            failed_attempts = (
                db.query(LoginAttempt)
                .filter(
                    and_(
                        LoginAttempt.user_id == user_id,
                        LoginAttempt.success == False,
                        LoginAttempt.attempted_at > lockout_time,
                    )
                )
                .count()
            )

            return failed_attempts >= self.max_login_attempts
        except Exception as e:
            logger.error(f"Error checking user lock: {e}")
            return False

    # ===================== УПРАВЛЕНИЕ СЕССИЯМИ =====================


    def get_current_session(
        self, db: Session, user_id: int, ip_address: str = None, user_agent: str = None
    ) -> UserSession | None:
        """
        Получить текущую активную сессию пользователя
        """
        try:
            query = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.revoked == False,
                    UserSession.expires_at > datetime.now(UTC),
                )
            )

            # Если указаны IP и User-Agent, ищем точное совпадение
            if ip_address and user_agent:
                session = query.filter(
                    and_(
                        UserSession.ip == ip_address,
                        UserSession.user_agent == user_agent,
                    )
                ).first()

                if session:
                    return session

            # Если точного совпадения нет, ищем любую активную сессию
            session = query.order_by(desc(UserSession.created_at)).first()
            return session

        except Exception as e:
            logger.error(
                f"Ошибка получения текущей сессии для пользователя {user_id}: {e}"
            )
            return None


    def get_user_sessions(
        self, db: Session, user_id: int, active_only: bool = True
    ) -> list[UserSession]:
        """
        Получить все сессии пользователя
        """
        try:
            query = db.query(UserSession).filter(UserSession.user_id == user_id)

            if active_only:
                query = query.filter(
                    and_(
                        UserSession.revoked == False,
                        UserSession.expires_at > datetime.now(UTC),
                    )
                )

            sessions = query.order_by(desc(UserSession.created_at)).all()
            return sessions

        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя {user_id}: {e}")
            return []


    def create_user_session(
        self,
        db: Session,
        user_id: int,
        refresh_token: str,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None,
    ) -> UserSession:
        """
        Создать новую пользовательскую сессию
        """
        try:
            # Проверяем, есть ли уже активная сессия с такими же параметрами
            existing_session = None
            if ip_address and user_agent:
                existing_session = (
                    db.query(UserSession)
                    .filter(
                        and_(
                            UserSession.user_id == user_id,
                            UserSession.ip == ip_address,
                            UserSession.user_agent == user_agent,
                            UserSession.revoked == False,
                            UserSession.expires_at > datetime.now(UTC),
                        )
                    )
                    .first()
                )

            if existing_session:
                # Обновляем существующую сессию
                existing_session.refresh_token = refresh_token
                existing_session.expires_at = datetime.now(UTC) + timedelta(
                    hours=self.session_expire_hours
                )
                existing_session.last_activity = datetime.now(UTC)
                if device_fingerprint:
                    existing_session.device_fingerprint = device_fingerprint

                db.commit()
                db.refresh(existing_session)

                logger.info(f"Обновлена существующая сессия для пользователя {user_id}")
                return existing_session

            # Создаем новую сессию
            session = UserSession(
                user_id=user_id,
                refresh_token=refresh_token,
                expires_at=datetime.now(UTC)
                + timedelta(hours=self.session_expire_hours),
                ip=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                last_activity=datetime.now(UTC),
            )

            db.add(session)
            db.commit()
            db.refresh(session)

            logger.info(f"Создана новая сессия для пользователя {user_id}")
            return session

        except Exception as e:
            logger.error(f"Ошибка создания сессии для пользователя {user_id}: {e}")
            db.rollback()
            raise


    def update_session_activity(self, db: Session, session_id: int) -> bool:
        """
        Обновить время последней активности сессии
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if session and not session.revoked:
                session.last_activity = datetime.now(UTC)
                db.commit()
                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка обновления активности сессии {session_id}: {e}")
            db.rollback()
            return False


    def revoke_session(
        self, db: Session, session_id: int, reason: str = "manual"
    ) -> bool:
        """
        Отозвать сессию
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if session and not session.revoked:
                session.revoked = True
                session.revoked_at = datetime.now(UTC)
                # session.revoke_reason = reason  # Поле может не существовать в модели

                db.commit()

                # Логируем событие безопасности
                self._log_security_event(
                    db,
                    session.user_id,
                    event_type="session_revoked",
                    severity="low",
                    description=f"Сессия отозвана: {reason}",
                    ip_address=session.ip,
                    user_agent=session.user_agent,
                )

                logger.info(f"Сессия {session_id} отозвана: {reason}")
                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка отзыва сессии {session_id}: {e}")
            db.rollback()
            return False


    def revoke_all_user_sessions(
        self,
        db: Session,
        user_id: int,
        except_session_id: int = None,
        reason: str = "logout_all",
    ) -> int:
        """
        Отозвать все сессии пользователя (кроме указанной)
        """
        try:
            query = db.query(UserSession).filter(
                and_(UserSession.user_id == user_id, UserSession.revoked == False)
            )

            if except_session_id:
                query = query.filter(UserSession.id != except_session_id)

            sessions = query.all()
            revoked_count = 0

            for session in sessions:
                session.revoked = True
                session.revoked_at = datetime.now(UTC)
                # session.revoke_reason = reason  # Поле может не существовать в модели
                revoked_count += 1

            db.commit()

            if revoked_count > 0:
                # Логируем событие безопасности
                self._log_security_event(
                    db,
                    user_id,
                    event_type="sessions_revoked",
                    severity="medium",
                    description=f"Отозвано {revoked_count} сессий: {reason}",
                )

                logger.info(
                    f"Отозвано {revoked_count} сессий для пользователя {user_id}: {reason}"
                )

            return revoked_count

        except Exception as e:
            logger.error(f"Ошибка отзыва сессий пользователя {user_id}: {e}")
            db.rollback()
            return 0


    def cleanup_expired_sessions(self, db: Session) -> int:
        """
        Очистить истекшие сессии
        """
        try:
            expired_sessions = (
                db.query(UserSession)
                .filter(UserSession.expires_at <= datetime.now(UTC))
                .all()
            )

            count = len(expired_sessions)

            for session in expired_sessions:
                if not session.revoked:
                    session.revoked = True
                    session.revoked_at = datetime.now(UTC)
                    # session.revoke_reason = "expired"  # Поле может не существовать в модели

            db.commit()

            if count > 0:
                logger.info(f"Очищено {count} истекших сессий")

            return count

        except Exception as e:
            logger.error(f"Ошибка очистки истекших сессий: {e}")
            db.rollback()
            return 0


    def get_session_info(
        self, db: Session, session_id: int
    ) -> dict[str, Any] | None:
        """
        Получить информацию о сессии
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if not session:
                return None

            return {
                "id": session.id,
                "user_id": session.user_id,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "last_activity": getattr(session, 'last_activity', None),
                "ip": session.ip,
                "user_agent": session.user_agent,
                "device_fingerprint": getattr(session, 'device_fingerprint', None),
                "revoked": session.revoked,
                "revoked_at": session.revoked_at,
                "is_active": not session.revoked
                and session.expires_at > datetime.now(UTC),
            }

        except Exception as e:
            logger.error(f"Ошибка получения информации о сессии {session_id}: {e}")
            return None


    def validate_session_token(
        self, db: Session, user_id: int, refresh_token: str
    ) -> UserSession | None:
        """
        Проверить валидность токена сессии
        """
        try:
            session = (
                db.query(UserSession)
                .filter(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.refresh_token == refresh_token,
                        UserSession.revoked == False,
                        UserSession.expires_at > datetime.now(UTC),
                    )
                )
                .first()
            )

            if session:
                # Обновляем время последней активности если поле существует
                if hasattr(session, 'last_activity'):
                    session.last_activity = datetime.now(UTC)
                    db.commit()

            return session

        except Exception as e:
            logger.error(
                f"Ошибка валидации токена сессии для пользователя {user_id}: {e}"
            )
            return None


def get_authentication_service() -> "AuthenticationService":
    """Получить экземпляр сервиса аутентификации"""
    from app.services.auth_svc import AuthenticationService
    return AuthenticationService()


