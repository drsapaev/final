"""
Сервис для управления фича-флагами
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.feature_flags import FeatureFlag, FeatureFlagHistory
from app.core.config import settings


class FeatureFlagService:
    """Сервис для управления фича-флагами"""
    
    def __init__(self, db: Session):
        self.db = db
        self._cache = {}  # Простой кэш для флагов
        self._cache_timestamp = None
        self.cache_ttl = 300  # 5 минут
    
    def is_enabled(self, flag_key: str, default: bool = False) -> bool:
        """
        Проверяет включен ли фича-флаг
        
        Args:
            flag_key: Ключ флага
            default: Значение по умолчанию если флаг не найден
            
        Returns:
            True если флаг включен, иначе False
        """
        try:
            flag = self._get_flag_from_cache_or_db(flag_key)
            if flag is None:
                return default
            
            # Проверяем окружение
            if flag.environment != "all" and flag.environment != settings.ENVIRONMENT:
                return default
                
            return flag.enabled
        except Exception:
            # В случае ошибки возвращаем значение по умолчанию
            return default
    
    def get_flag_config(self, flag_key: str) -> Dict[str, Any]:
        """
        Получает конфигурацию фича-флага
        
        Args:
            flag_key: Ключ флага
            
        Returns:
            Словарь с конфигурацией флага
        """
        flag = self._get_flag_from_cache_or_db(flag_key)
        if flag is None:
            return {}
        
        return flag.config or {}
    
    def set_flag(
        self, 
        flag_key: str, 
        enabled: bool, 
        user_id: str = None,
        reason: str = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> bool:
        """
        Устанавливает состояние фича-флага
        
        Args:
            flag_key: Ключ флага
            enabled: Новое состояние
            user_id: ID пользователя, изменившего флаг
            reason: Причина изменения
            ip_address: IP адрес пользователя
            user_agent: User-Agent пользователя
            
        Returns:
            True если флаг был изменен
        """
        flag = self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
        
        if flag is None:
            return False
        
        old_enabled = flag.enabled
        flag.enabled = enabled
        flag.updated_by = user_id
        flag.updated_at = datetime.utcnow()
        
        # Записываем в историю
        self._record_history(
            flag_key=flag_key,
            action="enabled" if enabled else "disabled",
            old_value={"enabled": old_enabled},
            new_value={"enabled": enabled},
            changed_by=user_id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.commit()
        self._invalidate_cache()
        
        return True
    
    def create_flag(
        self,
        key: str,
        name: str,
        description: str = None,
        enabled: bool = False,
        config: Dict[str, Any] = None,
        category: str = "general",
        environment: str = "all",
        user_id: str = None
    ) -> FeatureFlag:
        """
        Создает новый фича-флаг
        
        Args:
            key: Уникальный ключ флага
            name: Человекочитаемое название
            description: Описание флага
            enabled: Начальное состояние
            config: Дополнительная конфигурация
            category: Категория флага
            environment: Окружение (production, staging, development, all)
            user_id: ID пользователя, создавшего флаг
            
        Returns:
            Созданный фича-флаг
        """
        flag = FeatureFlag(
            key=key,
            name=name,
            description=description,
            enabled=enabled,
            config=config or {},
            category=category,
            environment=environment,
            created_by=user_id
        )
        
        self.db.add(flag)
        
        # Записываем в историю
        self._record_history(
            flag_key=key,
            action="created",
            old_value=None,
            new_value={
                "enabled": enabled,
                "config": config,
                "category": category,
                "environment": environment
            },
            changed_by=user_id
        )
        
        self.db.commit()
        self._invalidate_cache()
        
        return flag
    
    def update_flag_config(
        self,
        flag_key: str,
        config: Dict[str, Any],
        user_id: str = None,
        reason: str = None
    ) -> bool:
        """
        Обновляет конфигурацию фича-флага
        
        Args:
            flag_key: Ключ флага
            config: Новая конфигурация
            user_id: ID пользователя
            reason: Причина изменения
            
        Returns:
            True если конфигурация была обновлена
        """
        flag = self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
        
        if flag is None:
            return False
        
        old_config = flag.config
        flag.config = config
        flag.updated_by = user_id
        flag.updated_at = datetime.utcnow()
        
        # Записываем в историю
        self._record_history(
            flag_key=flag_key,
            action="updated",
            old_value={"config": old_config},
            new_value={"config": config},
            changed_by=user_id,
            reason=reason
        )
        
        self.db.commit()
        self._invalidate_cache()
        
        return True
    
    def get_all_flags(self, category: str = None) -> List[FeatureFlag]:
        """
        Получает все фича-флаги
        
        Args:
            category: Фильтр по категории (опционально)
            
        Returns:
            Список всех флагов
        """
        query = self.db.query(FeatureFlag)
        
        if category:
            query = query.filter(FeatureFlag.category == category)
        
        return query.order_by(FeatureFlag.category, FeatureFlag.key).all()
    
    def get_flag_history(self, flag_key: str, limit: int = 50) -> List[FeatureFlagHistory]:
        """
        Получает историю изменений флага
        
        Args:
            flag_key: Ключ флага
            limit: Максимальное количество записей
            
        Returns:
            Список записей истории
        """
        return (
            self.db.query(FeatureFlagHistory)
            .filter(FeatureFlagHistory.flag_key == flag_key)
            .order_by(FeatureFlagHistory.changed_at.desc())
            .limit(limit)
            .all()
        )
    
    def delete_flag(self, flag_key: str, user_id: str = None, reason: str = None) -> bool:
        """
        Удаляет фича-флаг
        
        Args:
            flag_key: Ключ флага
            user_id: ID пользователя
            reason: Причина удаления
            
        Returns:
            True если флаг был удален
        """
        flag = self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
        
        if flag is None:
            return False
        
        # Записываем в историю перед удалением
        self._record_history(
            flag_key=flag_key,
            action="deleted",
            old_value={
                "enabled": flag.enabled,
                "config": flag.config,
                "name": flag.name,
                "description": flag.description
            },
            new_value=None,
            changed_by=user_id,
            reason=reason
        )
        
        self.db.delete(flag)
        self.db.commit()
        self._invalidate_cache()
        
        return True
    
    def _get_flag_from_cache_or_db(self, flag_key: str) -> Optional[FeatureFlag]:
        """Получает флаг из кэша или базы данных"""
        now = datetime.utcnow()
        
        # Проверяем кэш
        if (self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self.cache_ttl and
            flag_key in self._cache):
            return self._cache[flag_key]
        
        # Загружаем из БД
        flag = self.db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
        
        # Обновляем кэш
        if not self._cache_timestamp or (now - self._cache_timestamp).total_seconds() >= self.cache_ttl:
            self._refresh_cache()
        else:
            self._cache[flag_key] = flag
        
        return flag
    
    def _refresh_cache(self):
        """Обновляет весь кэш флагов"""
        flags = self.db.query(FeatureFlag).all()
        self._cache = {flag.key: flag for flag in flags}
        self._cache_timestamp = datetime.utcnow()
    
    def _invalidate_cache(self):
        """Сбрасывает кэш"""
        self._cache = {}
        self._cache_timestamp = None
    
    def _record_history(
        self,
        flag_key: str,
        action: str,
        old_value: Optional[Dict[str, Any]],
        new_value: Optional[Dict[str, Any]],
        changed_by: str = None,
        reason: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Записывает изменение в историю"""
        history = FeatureFlagHistory(
            flag_key=flag_key,
            action=action,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(history)


# Предопределенные фича-флаги для системы подтверждения визитов
PREDEFINED_FLAGS = [
    {
        "key": "confirmation_before_queue",
        "name": "Подтверждение перед номером в очереди",
        "description": "Требовать подтверждение визита пациентом перед присвоением номера в очереди",
        "enabled": True,
        "category": "queue_management",
        "config": {
            "token_ttl_hours": 48,
            "morning_assignment_enabled": True,
            "auto_assign_today": True,
            "fallback_to_old_system": False
        }
    },
    {
        "key": "telegram_notifications",
        "name": "Telegram уведомления",
        "description": "Отправка уведомлений через Telegram бот",
        "enabled": True,
        "category": "notifications",
        "config": {
            "retry_attempts": 3,
            "retry_delay_minutes": 5,
            "fallback_to_sms": True
        }
    },
    {
        "key": "pwa_confirmation",
        "name": "PWA подтверждение",
        "description": "Возможность подтверждения визитов через PWA",
        "enabled": True,
        "category": "confirmation",
        "config": {
            "require_phone_verification": True,
            "session_timeout_minutes": 30
        }
    },
    {
        "key": "rate_limiting",
        "name": "Ограничение частоты запросов",
        "description": "Защита от спама и злоупотреблений",
        "enabled": True,
        "category": "security",
        "config": {
            "confirmation_limit": 5,
            "confirmation_window_minutes": 1,
            "block_duration_minutes": 15
        }
    },
    {
        "key": "audit_logging",
        "name": "Аудит логирование",
        "description": "Детальное логирование всех операций подтверждения",
        "enabled": True,
        "category": "security",
        "config": {
            "log_successful_attempts": True,
            "log_failed_attempts": True,
            "retention_days": 90
        }
    }
]


def initialize_feature_flags(db: Session):
    """
    Инициализирует предопределенные фича-флаги при первом запуске
    """
    service = FeatureFlagService(db)
    
    for flag_data in PREDEFINED_FLAGS:
        existing = db.query(FeatureFlag).filter(FeatureFlag.key == flag_data["key"]).first()
        
        if not existing:
            service.create_flag(
                key=flag_data["key"],
                name=flag_data["name"],
                description=flag_data["description"],
                enabled=flag_data["enabled"],
                category=flag_data["category"],
                config=flag_data["config"],
                user_id="system"
            )


# Глобальный экземпляр сервиса (будет инициализирован при запуске)
_feature_flag_service: Optional[FeatureFlagService] = None


def get_feature_flag_service(db: Session) -> FeatureFlagService:
    """Получает экземпляр сервиса фича-флагов"""
    return FeatureFlagService(db)


def is_feature_enabled(db: Session, flag_key: str, default: bool = False) -> bool:
    """
    Удобная функция для проверки состояния флага
    
    Args:
        db: Сессия базы данных
        flag_key: Ключ флага
        default: Значение по умолчанию
        
    Returns:
        True если флаг включен
    """
    service = get_feature_flag_service(db)
    return service.is_enabled(flag_key, default)
