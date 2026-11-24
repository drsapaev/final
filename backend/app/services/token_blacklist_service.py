"""
Сервис для управления черным списком токенов (Token Blacklist)

Обеспечивает немедленный отзыв access токенов при:
- Logout
- Смене пароля
- Подозрительной активности
- Блокировке пользователя
"""
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist

logger = logging.getLogger(__name__)


def _lock_clean_user(db: Session, user_id: int):
    """Lock a live User without overwriting local unflushed field changes."""
    from app.models.user import User

    loaded = db.identity_map.get(db.identity_key(User, user_id))
    if loaded is not None and db.is_modified(loaded, include_collections=False):
        raise ValueError("User must not have unflushed changes when advancing generation")
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update(key_share=True)
        .populate_existing()
        .first()
    )
    if user is None:
        raise ValueError("User not found")
    return user


def bump_user_auth_epoch(db: Session, user_id: int) -> int:
    """Advance a user's revocation generation without committing the caller's transaction.

    Call before changing User or locking session, 2FA or refresh-token rows.
    Reject a dirty identity-map instance rather than silently discarding its
    unflushed changes while refreshing. The caller must roll back on failure.
    """
    user = _lock_clean_user(db, user_id)
    epoch = user.auth_epoch
    if type(epoch) is not int or not 0 <= epoch < (1 << 63) - 1:
        raise ValueError("Invalid or exhausted authentication generation")
    user.auth_epoch = epoch + 1
    db.flush()
    return user.auth_epoch


def revoke_account_sessions_locked(
    db: Session, user, *, exclude_session_id: int | None = None,
    revoke_password_resets: bool = False,
    revoke_recovery: bool | None = None,
) -> int:
    """Revoke one account's credentials without committing the transaction.

    Caller MUST hold the freshly loaded User row FOR NO KEY UPDATE before
    acquiring any session, 2FA or refresh-token locks. If an already-locked
    enrollment/pending session is excluded, the caller MUST consume that
    one-use session in the same transaction before committing. The caller
    must roll back on every failure, including generation overflow.
    Account-security changes and logout-all also revoke outstanding reset and
    recovery tokens. Ordinary new login preserves recovery, including the
    factor being consumed by its pending challenge in this transaction.
    Unless explicitly specified, recovery revocation follows reset revocation.
    """
    from sqlalchemy.orm import object_session

    from app.models.authentication import PasswordResetToken, RefreshToken, UserSession
    from app.models.two_factor_auth import TwoFactorAuth, TwoFactorRecovery

    if user is None or object_session(user) is not db or user.id is None:
        raise ValueError("A persistent locked user in this session is required")
    if exclude_session_id is not None and (
        type(exclude_session_id) is not int or exclude_session_id <= 0
    ):
        raise ValueError("Invalid excluded session")
    epoch = user.auth_epoch
    if type(epoch) is not int or not 0 <= epoch < (1 << 63) - 1:
        raise ValueError("Invalid or exhausted authentication generation")
    user.auth_epoch = epoch + 1

    session_query = db.query(UserSession).filter(
        UserSession.user_id == user.id, UserSession.revoked.is_not(True)
    )
    if exclude_session_id is not None:
        session_query = session_query.filter(UserSession.id != exclude_session_id)
    sessions = session_query.order_by(UserSession.id).with_for_update().populate_existing().all()
    for session in sessions:
        session.revoked = True

    now = datetime.now(UTC)
    if revoke_recovery is None:
        revoke_recovery = revoke_password_resets
    if revoke_recovery:
        two_factor = (
            db.query(TwoFactorAuth)
            .filter(TwoFactorAuth.user_id == user.id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if two_factor is not None:
            db.query(TwoFactorRecovery).filter(
                TwoFactorRecovery.two_factor_auth_id == two_factor.id,
                TwoFactorRecovery.verified.is_(False),
            ).update(
                {"verified": True, "verified_at": now}, synchronize_session=False
            )

    refresh_tokens = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_not(True))
        .order_by(RefreshToken.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    for token in refresh_tokens:
        token.revoked = True
        token.revoked_at = now
    if revoke_password_resets:
        reset_tokens = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_not(True))
            .order_by(PasswordResetToken.id)
            .with_for_update()
            .all()
        )
        for token in reset_tokens:
            token.used = True
            token.used_at = now
    db.flush()
    return user.auth_epoch


class TokenBlacklistService:
    """Сервис для работы с черным списком токенов"""

    @staticmethod
    def blacklist_token(
        db: Session,
        jti: str,
        expires_at: datetime,
        user_id: int | None = None,
        reason: str = "logout"
    ) -> bool:
        """
        Добавить токен в черный список

        Args:
            db: Сессия базы данных
            jti: JWT ID токена
            expires_at: Время истечения токена
            user_id: ID пользователя (опционально)
            reason: Причина блокировки

        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Проверяем, не истёк ли уже токен
            if expires_at < datetime.now(UTC):
                logger.debug(f"Token {jti} already expired, skipping blacklist")
                return True

            # Serialize user-token revocation against in-flight authentication
            # exchanges. Device credentials have no associated User row.
            if user_id is not None:
                _lock_clean_user(db, user_id)

            # Проверяем, не заблокирован ли уже
            existing = db.query(TokenBlacklist).filter(
                TokenBlacklist.jti == jti
            ).first()

            if existing:
                if user_id is not None:
                    db.commit()  # release the User lock held by this standalone writer
                logger.debug(f"Token {jti} already blacklisted")
                return True

            blacklist_entry = TokenBlacklist(
                jti=jti,
                user_id=user_id,
                expires_at=expires_at,
                reason=reason
            )
            db.add(blacklist_entry)
            db.commit()

            logger.info(f"Token {jti} blacklisted (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Error blacklisting token {jti}: {e}")
            db.rollback()
            return False

    @staticmethod
    def is_token_blacklisted(
        db: Session, jti: str, user_id: int | None = None, *, auth_epoch: int = 0
    ) -> bool:
        """
        Проверить, находится ли токен в черном списке.

        Проверка двух типов записей:
        1. Точный jti — для индивидуально отозванных токенов (logout).
        2. Активный legacy sentinel для поколения 0. Миграция переводит
           пользователей с существующим sentinel в поколение 1; после этого
           глобальные отзывы должны атомарно увеличивать User.auth_epoch.

        Args:
            db: Сессия базы данных
            jti: JWT ID токена
            user_id: ID пользователя (опционально; передаётся deps.get_current_user)
            auth_epoch: поколение проверенного JWT, повторно сверяемое со
                свежей записью User; default 0 сохраняет legacy поведение.

        Returns:
            True если токен в черном списке
        """
        if type(auth_epoch) is not int or not 0 <= auth_epoch <= (1 << 63) - 1:
            return True
        try:
            if user_id is None:
                # Device credentials have no User epoch; only their own JTI
                # belongs to this namespace.
                return db.query(TokenBlacklist.id).filter(TokenBlacklist.jti == jti).first() is not None

            from app.core.user_token_claims import user_auth_epoch_matches
            from app.models.user import User

            jti_bl = select(TokenBlacklist.id).where(TokenBlacklist.jti == jti).exists()
            sentinel_bl = (
                select(TokenBlacklist.id)
                .where(
                    TokenBlacklist.user_id == User.id,
                    TokenBlacklist.reason.like("all_user_tokens:%"),
                    TokenBlacklist.expires_at > datetime.now(UTC),
                )
                .exists()
            )
            row = db.execute(
                select(User.auth_epoch, jti_bl, sentinel_bl).where(User.id == user_id)
            ).first()
            if row is None:
                return True
            live_epoch, jti_hit, sentinel_hit = row
            return bool(
                jti_hit
                or not user_auth_epoch_matches({"auth_epoch": auth_epoch}, live_epoch)
                or (sentinel_hit and auth_epoch == 0)
            )
        except Exception as e:
            logger.error("Error checking token blacklist: %s", type(e).__name__)
            return True

    @staticmethod
    def blacklist_all_user_tokens(
        db: Session,
        user_id: int,
        reason: str = "security"
    ) -> int:
        """
        Отозвать все токены пользователя

        Используется при:
        - Смене пароля
        - Блокировке пользователя
        - Подозрительной активности

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            reason: Причина отзыва

        Returns:
            Количество отозванных токенов
        """
        try:
            # Standalone compatibility wrapper. Transactional callers must use
            # bump_user_auth_epoch directly and commit their mutations together.
            user = _lock_clean_user(db, user_id)
            revoke_account_sessions_locked(db, user)
            db.commit()
            logger.info("User authentication generation advanced")
            return 1

        except Exception as e:
            logger.error("Error advancing authentication generation: %s", type(e).__name__)
            db.rollback()
            return 0

    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Удалить истёкшие записи из черного списка

        Рекомендуется вызывать периодически (например, раз в сутки)

        Returns:
            Количество удалённых записей
        """
        try:
            deleted = db.query(TokenBlacklist).filter(
                TokenBlacklist.expires_at < datetime.now(UTC)
            ).delete()
            db.commit()

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired blacklist entries")

            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up blacklist: {e}")
            db.rollback()
            return 0


# Singleton instance
token_blacklist_service = TokenBlacklistService()
