"""
CRUD операции для двухфакторной аутентификации (2FA)
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.two_factor_auth import (
    TwoFactorAuth, TwoFactorBackupCode, TwoFactorRecovery, 
    TwoFactorSession, TwoFactorDevice
)
from app.models.user import User
from app.schemas.two_factor_auth import (
    TwoFactorAuthCreate, TwoFactorAuthUpdate, TwoFactorBackupCodeCreate,
    TwoFactorRecoveryCreate, TwoFactorSessionCreate, TwoFactorDeviceCreate
)
from app.crud.base import CRUDBase


class CRUDTwoFactorAuth(CRUDBase[TwoFactorAuth, TwoFactorAuthCreate, TwoFactorAuthUpdate]):
    """CRUD операции для 2FA"""

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[TwoFactorAuth]:
        """Получить 2FA по ID пользователя"""
        return db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()

    def is_enabled(self, db: Session, user_id: int) -> bool:
        """Проверить, включена ли 2FA для пользователя"""
        two_factor_auth = self.get_by_user_id(db, user_id)
        return two_factor_auth and two_factor_auth.totp_enabled

    def enable(self, db: Session, user_id: int) -> TwoFactorAuth:
        """Включить 2FA для пользователя"""
        two_factor_auth = self.get_by_user_id(db, user_id)
        if two_factor_auth:
            two_factor_auth.totp_enabled = True
            two_factor_auth.totp_verified = True
        else:
            two_factor_auth = TwoFactorAuth(
                user_id=user_id,
                totp_enabled=True,
                totp_verified=True
            )
            db.add(two_factor_auth)
        
        db.commit()
        db.refresh(two_factor_auth)
        return two_factor_auth

    def disable(self, db: Session, user_id: int) -> bool:
        """Отключить 2FA для пользователя"""
        two_factor_auth = self.get_by_user_id(db, user_id)
        if two_factor_auth:
            two_factor_auth.totp_enabled = False
            two_factor_auth.totp_verified = False
            db.commit()
            return True
        return False

    def update_last_used(self, db: Session, user_id: int) -> bool:
        """Обновить время последнего использования"""
        two_factor_auth = self.get_by_user_id(db, user_id)
        if two_factor_auth:
            from datetime import datetime
            two_factor_auth.last_used = datetime.utcnow()
            db.commit()
            return True
        return False


class CRUDTwoFactorBackupCode(CRUDBase[TwoFactorBackupCode, TwoFactorBackupCodeCreate, None]):
    """CRUD операции для backup кодов"""

    def get_by_two_factor_auth_id(self, db: Session, two_factor_auth_id: int) -> List[TwoFactorBackupCode]:
        """Получить все backup коды для 2FA"""
        return db.query(TwoFactorBackupCode).filter(
            TwoFactorBackupCode.two_factor_auth_id == two_factor_auth_id
        ).all()

    def get_unused_codes(self, db: Session, two_factor_auth_id: int) -> List[TwoFactorBackupCode]:
        """Получить неиспользованные backup коды"""
        return db.query(TwoFactorBackupCode).filter(
            and_(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth_id,
                TwoFactorBackupCode.used == False
            )
        ).all()

    def get_unused_count(self, db: Session, two_factor_auth_id: int) -> int:
        """Получить количество неиспользованных backup кодов"""
        return db.query(TwoFactorBackupCode).filter(
            and_(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth_id,
                TwoFactorBackupCode.used == False
            )
        ).count()

    def use_code(self, db: Session, two_factor_auth_id: int, code: str) -> bool:
        """Использовать backup код"""
        backup_code = db.query(TwoFactorBackupCode).filter(
            and_(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth_id,
                TwoFactorBackupCode.code == code,
                TwoFactorBackupCode.used == False
            )
        ).first()
        
        if backup_code:
            from datetime import datetime
            backup_code.used = True
            backup_code.used_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def delete_all_for_user(self, db: Session, two_factor_auth_id: int) -> int:
        """Удалить все backup коды для пользователя"""
        count = db.query(TwoFactorBackupCode).filter(
            TwoFactorBackupCode.two_factor_auth_id == two_factor_auth_id
        ).delete()
        db.commit()
        return count


class CRUDTwoFactorRecovery(CRUDBase[TwoFactorRecovery, TwoFactorRecoveryCreate, None]):
    """CRUD операции для восстановления 2FA"""

    def get_by_token(self, db: Session, token: str) -> Optional[TwoFactorRecovery]:
        """Получить попытку восстановления по токену"""
        return db.query(TwoFactorRecovery).filter(
            TwoFactorRecovery.recovery_token == token
        ).first()

    def get_valid_token(self, db: Session, token: str) -> Optional[TwoFactorRecovery]:
        """Получить действительный токен восстановления"""
        from datetime import datetime
        return db.query(TwoFactorRecovery).filter(
            and_(
                TwoFactorRecovery.recovery_token == token,
                TwoFactorRecovery.verified == False,
                TwoFactorRecovery.expires_at > datetime.utcnow()
            )
        ).first()

    def verify_token(self, db: Session, token: str) -> bool:
        """Верифицировать токен восстановления"""
        recovery = self.get_valid_token(db, token)
        if recovery:
            from datetime import datetime
            recovery.verified = True
            recovery.verified_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def get_by_two_factor_auth_id(self, db: Session, two_factor_auth_id: int) -> List[TwoFactorRecovery]:
        """Получить все попытки восстановления для 2FA"""
        return db.query(TwoFactorRecovery).filter(
            TwoFactorRecovery.two_factor_auth_id == two_factor_auth_id
        ).order_by(desc(TwoFactorRecovery.created_at)).all()

    def cleanup_expired(self, db: Session) -> int:
        """Очистить истекшие токены восстановления"""
        from datetime import datetime
        count = db.query(TwoFactorRecovery).filter(
            TwoFactorRecovery.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDTwoFactorSession(CRUDBase[TwoFactorSession, TwoFactorSessionCreate, None]):
    """CRUD операции для сессий 2FA"""

    def get_by_token(self, db: Session, token: str) -> Optional[TwoFactorSession]:
        """Получить сессию по токену"""
        return db.query(TwoFactorSession).filter(
            TwoFactorSession.session_token == token
        ).first()

    def get_valid_session(self, db: Session, token: str) -> Optional[TwoFactorSession]:
        """Получить действительную сессию"""
        from datetime import datetime
        return db.query(TwoFactorSession).filter(
            and_(
                TwoFactorSession.session_token == token,
                TwoFactorSession.expires_at > datetime.utcnow()
            )
        ).first()

    def get_by_user_id(self, db: Session, user_id: int) -> List[TwoFactorSession]:
        """Получить все сессии пользователя"""
        return db.query(TwoFactorSession).filter(
            TwoFactorSession.user_id == user_id
        ).order_by(desc(TwoFactorSession.created_at)).all()

    def get_by_device_fingerprint(self, db: Session, device_fingerprint: str) -> Optional[TwoFactorSession]:
        """Получить сессию по отпечатку устройства"""
        from datetime import datetime
        return db.query(TwoFactorSession).filter(
            and_(
                TwoFactorSession.device_fingerprint == device_fingerprint,
                TwoFactorSession.expires_at > datetime.utcnow()
            )
        ).first()

    def update_activity(self, db: Session, token: str) -> bool:
        """Обновить активность сессии"""
        session = self.get_valid_session(db, token)
        if session:
            from datetime import datetime
            session.last_activity = datetime.utcnow()
            db.commit()
            return True
        return False

    def cleanup_expired(self, db: Session) -> int:
        """Очистить истекшие сессии"""
        from datetime import datetime
        count = db.query(TwoFactorSession).filter(
            TwoFactorSession.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDTwoFactorDevice(CRUDBase[TwoFactorDevice, TwoFactorDeviceCreate, None]):
    """CRUD операции для устройств 2FA"""

    def get_by_user_id(self, db: Session, user_id: int) -> List[TwoFactorDevice]:
        """Получить все устройства пользователя"""
        return db.query(TwoFactorDevice).filter(
            TwoFactorDevice.user_id == user_id
        ).order_by(desc(TwoFactorDevice.created_at)).all()

    def get_by_fingerprint(self, db: Session, fingerprint: str) -> Optional[TwoFactorDevice]:
        """Получить устройство по отпечатку"""
        return db.query(TwoFactorDevice).filter(
            TwoFactorDevice.device_fingerprint == fingerprint
        ).first()

    def get_trusted_devices(self, db: Session, user_id: int) -> List[TwoFactorDevice]:
        """Получить доверенные устройства пользователя"""
        return db.query(TwoFactorDevice).filter(
            and_(
                TwoFactorDevice.user_id == user_id,
                TwoFactorDevice.trusted == True,
                TwoFactorDevice.active == True
            )
        ).all()

    def trust_device(self, db: Session, device_id: int) -> bool:
        """Доверять устройству"""
        device = db.query(TwoFactorDevice).filter(TwoFactorDevice.id == device_id).first()
        if device:
            device.trusted = True
            device.active = True
            db.commit()
            return True
        return False

    def untrust_device(self, db: Session, device_id: int) -> bool:
        """Отозвать доверие к устройству"""
        device = db.query(TwoFactorDevice).filter(TwoFactorDevice.id == device_id).first()
        if device:
            device.trusted = False
            device.active = False
            db.commit()
            return True
        return False

    def update_last_used(self, db: Session, device_id: int) -> bool:
        """Обновить время последнего использования устройства"""
        device = db.query(TwoFactorDevice).filter(TwoFactorDevice.id == device_id).first()
        if device:
            from datetime import datetime
            device.last_used = datetime.utcnow()
            db.commit()
            return True
        return False

    def deactivate_device(self, db: Session, device_id: int) -> bool:
        """Деактивировать устройство"""
        device = db.query(TwoFactorDevice).filter(TwoFactorDevice.id == device_id).first()
        if device:
            device.active = False
            db.commit()
            return True
        return False


# Создаем экземпляры CRUD классов
two_factor_auth = CRUDTwoFactorAuth(TwoFactorAuth)
two_factor_backup_code = CRUDTwoFactorBackupCode(TwoFactorBackupCode)
two_factor_recovery = CRUDTwoFactorRecovery(TwoFactorRecovery)
two_factor_session = CRUDTwoFactorSession(TwoFactorSession)
two_factor_device = CRUDTwoFactorDevice(TwoFactorDevice)
