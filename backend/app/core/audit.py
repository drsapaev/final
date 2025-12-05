"""
Система аудит-логирования для критичных операций.
Автоматически логирует все изменения в критичных таблицах.
"""
import json
import hashlib
from typing import Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.orm import Session as SQLAlchemySession

from app.models.user_profile import UserAuditLog
from app.models.user import User


# Критичные таблицы, которые требуют аудит-логирования
CRITICAL_TABLES = {
    "patients",
    "visits",
    "payments",
    "emr",
    "files",
    "appointments",
    "prescriptions",
    "lab_results",
    "unknown",  # Для логирования 403 на неизвестных ресурсах
}


def get_request_id(request: Request) -> str:
    """Получить или создать request_id для запроса"""
    if not hasattr(request.state, "request_id"):
        request.state.request_id = str(uuid4())
    return request.state.request_id


def get_client_ip(request: Request) -> Optional[str]:
    """Получить IP адрес клиента из запроса"""
    # Проверяем заголовки прокси
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Используем прямой IP
    if request.client:
        return request.client.host
    
    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Получить User-Agent из запроса"""
    return request.headers.get("User-Agent")


def calculate_diff_hash(old_data: Optional[Dict], new_data: Optional[Dict]) -> str:
    """Вычислить хеш различий между старыми и новыми данными"""
    diff = {
        "old": old_data or {},
        "new": new_data or {},
    }
    diff_json = json.dumps(diff, sort_keys=True, default=str)
    return hashlib.sha256(diff_json.encode()).hexdigest()[:16]


def log_audit_event(
    db: Session,
    user_id: int,
    action: str,
    table_name: str,
    row_id: Optional[int] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    description: Optional[str] = None,
) -> UserAuditLog:
    """
    Создать запись аудит-лога
    
    Args:
        db: Database session
        user_id: ID пользователя, выполнившего действие
        action: Действие (CREATE, UPDATE, DELETE)
        table_name: Имя таблицы
        row_id: ID измененной строки
        old_values: Старые значения (для UPDATE/DELETE)
        new_values: Новые значения (для CREATE/UPDATE)
        request_id: ID запроса для трассировки
        ip_address: IP адрес клиента
        user_agent: User-Agent клиента
        description: Дополнительное описание
    
    Returns:
        UserAuditLog: Созданная запись аудит-лога
    """
    # Вычисляем хеш различий
    diff_hash = calculate_diff_hash(old_values, new_values)
    
    # Создаем запись
    # Вычисляем хеш различий
    diff_hash = calculate_diff_hash(old_values, new_values)
    
    audit_log = UserAuditLog(
        user_id=user_id,
        action=action.upper(),
        resource_type=table_name,
        resource_id=row_id,
        old_values=old_values,
        new_values=new_values,
        diff_hash=diff_hash,
        description=description or f"{action} {table_name}",
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=request_id,  # Используем session_id для request_id
        request_id=request_id,  # Также сохраняем в request_id
    )
    
    db.add(audit_log)
    return audit_log


def audit_log_dependency(request: Request):
    """
    Dependency для получения контекста аудит-логирования из запроса.
    Устанавливает request_id в request.state.
    """
    get_request_id(request)
    return {
        "request_id": request.state.request_id,
        "ip_address": get_client_ip(request),
        "user_agent": get_user_agent(request),
    }


def log_critical_change(
    db: Session,
    user_id: int,
    action: str,
    table_name: str,
    row_id: Optional[int] = None,
    old_data: Optional[Dict] = None,
    new_data: Optional[Dict] = None,
    request: Optional[Request] = None,
    description: Optional[str] = None,
) -> Optional[UserAuditLog]:
    """
    Логировать изменение в критичной таблице.
    
    Args:
        db: Database session
        user_id: ID пользователя
        action: CREATE, UPDATE, DELETE
        table_name: Имя таблицы
        row_id: ID строки
        old_data: Старые данные (для UPDATE/DELETE)
        new_data: Новые данные (для CREATE/UPDATE)
        request: FastAPI Request объект (опционально)
        description: Дополнительное описание
    
    Returns:
        UserAuditLog или None если таблица не критичная
    """
    # Проверяем, является ли таблица критичной
    if table_name.lower() not in CRITICAL_TABLES:
        return None
    
    # Получаем контекст из request если доступен
    request_id = None
    ip_address = None
    user_agent = None
    
    if request:
        request_id = get_request_id(request)
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
    
    # Логируем
    audit_log = log_audit_event(
        db=db,
        user_id=user_id,
        action=action,
        table_name=table_name,
        row_id=row_id,
        old_values=old_data,
        new_values=new_data,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        description=description,
    )
    
    return audit_log


def extract_model_changes(old_instance: Any, new_instance: Any) -> tuple[Optional[Dict], Optional[Dict]]:
    """
    Извлечь изменения между старым и новым экземпляром модели.
    
    Args:
        old_instance: Старый экземпляр модели (может быть None для CREATE)
        new_instance: Новый экземпляр модели (может быть None для DELETE)
    
    Returns:
        Tuple (old_dict, new_dict) с измененными полями
    """
    from sqlalchemy.inspection import inspect
    
    old_dict = None
    new_dict = None
    
    if old_instance:
        old_dict = {}
        # ✅ FIX: Use inspect() instead of __table__.columns to handle __mapper_args__
        mapper = inspect(old_instance.__class__)
        for column in mapper.columns:
            col_name = column.key
            try:
                value = getattr(old_instance, col_name, None)
                # Сериализуем только изменяемые типы
                if value is not None:
                    if hasattr(value, "isoformat"):  # datetime, date
                        old_dict[col_name] = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        old_dict[col_name] = json.dumps(value, default=str)
                    else:
                        old_dict[col_name] = str(value)
            except Exception:
                # Skip columns that can't be accessed (e.g., relationships)
                pass
    
    if new_instance:
        new_dict = {}
        # ✅ FIX: Use inspect() instead of __table__.columns to handle __mapper_args__
        mapper = inspect(new_instance.__class__)
        for column in mapper.columns:
            col_name = column.key
            try:
                value = getattr(new_instance, col_name, None)
                if value is not None:
                    if hasattr(value, "isoformat"):  # datetime, date
                        new_dict[col_name] = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        new_dict[col_name] = json.dumps(value, default=str)
                    else:
                        new_dict[col_name] = str(value)
            except Exception:
                # Skip columns that can't be accessed (e.g., relationships)
                pass
    
    return old_dict, new_dict

