"""
CRUD операции для AI конфигурации
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.ai_config import AIPromptTemplate, AIProvider, AIUsageLog
from app.schemas.ai_config import (
    AIPromptTemplateCreate,
    AIPromptTemplateUpdate,
    AIProviderCreate,
    AIProviderUpdate,
)

# ===================== AI ПРОВАЙДЕРЫ =====================


def get_ai_providers(
    db: Session, skip: int = 0, limit: int = 100, active_only: bool = False
) -> List[AIProvider]:
    """Получить список AI провайдеров"""
    query = db.query(AIProvider)

    if active_only:
        query = query.filter(AIProvider.active == True)

    return query.offset(skip).limit(limit).all()


def get_ai_provider_by_id(db: Session, provider_id: int) -> Optional[AIProvider]:
    """Получить AI провайдера по ID"""
    return db.query(AIProvider).filter(AIProvider.id == provider_id).first()


def get_ai_provider_by_name(db: Session, name: str) -> Optional[AIProvider]:
    """Получить AI провайдера по имени"""
    return db.query(AIProvider).filter(AIProvider.name == name).first()


def get_default_ai_provider(db: Session) -> Optional[AIProvider]:
    """Получить провайдера по умолчанию"""
    return (
        db.query(AIProvider)
        .filter(and_(AIProvider.is_default == True, AIProvider.active == True))
        .first()
    )


def create_ai_provider(db: Session, provider: AIProviderCreate) -> AIProvider:
    """Создать AI провайдера"""
    # Если это первый активный провайдер, делаем его по умолчанию
    if (
        provider.active
        and not db.query(AIProvider).filter(AIProvider.is_default == True).first()
    ):
        provider.is_default = True

    # Если делаем провайдера по умолчанию, убираем флаг у других
    if provider.is_default:
        db.query(AIProvider).filter(AIProvider.is_default == True).update(
            {"is_default": False}
        )

    db_provider = AIProvider(**provider.model_dump())
    db.add(db_provider)
    db.commit()
    db.refresh(db_provider)
    return db_provider


def update_ai_provider(
    db: Session, provider_id: int, provider: AIProviderUpdate
) -> Optional[AIProvider]:
    """Обновить AI провайдера"""
    db_provider = get_ai_provider_by_id(db, provider_id)
    if not db_provider:
        return None

    update_data = provider.model_dump(exclude_unset=True)

    # Если делаем провайдера по умолчанию, убираем флаг у других
    if update_data.get("is_default"):
        db.query(AIProvider).filter(AIProvider.id != provider_id).update(
            {"is_default": False}
        )

    for field, value in update_data.items():
        setattr(db_provider, field, value)

    db.commit()
    db.refresh(db_provider)
    return db_provider


def delete_ai_provider(db: Session, provider_id: int) -> bool:
    """Удалить AI провайдера"""
    db_provider = get_ai_provider_by_id(db, provider_id)
    if not db_provider:
        return False

    # Если это провайдер по умолчанию, назначаем другой
    if db_provider.is_default:
        other_provider = (
            db.query(AIProvider)
            .filter(and_(AIProvider.id != provider_id, AIProvider.active == True))
            .first()
        )
        if other_provider:
            other_provider.is_default = True

    db_provider.active = False
    db.commit()
    return True


# ===================== ШАБЛОНЫ ПРОМПТОВ =====================


def get_prompt_templates(
    db: Session,
    provider_id: Optional[int] = None,
    task_type: Optional[str] = None,
    specialty: Optional[str] = None,
    language: str = "ru",
    active_only: bool = True,
) -> List[AIPromptTemplate]:
    """Получить шаблоны промптов"""
    query = db.query(AIPromptTemplate)

    if provider_id:
        query = query.filter(AIPromptTemplate.provider_id == provider_id)
    if task_type:
        query = query.filter(AIPromptTemplate.task_type == task_type)
    if specialty:
        query = query.filter(AIPromptTemplate.specialty == specialty)
    if language:
        query = query.filter(AIPromptTemplate.language == language)
    if active_only:
        query = query.filter(AIPromptTemplate.active == True)

    return query.all()


def get_prompt_template_by_id(
    db: Session, template_id: int
) -> Optional[AIPromptTemplate]:
    """Получить шаблон промпта по ID"""
    return db.query(AIPromptTemplate).filter(AIPromptTemplate.id == template_id).first()


def create_prompt_template(
    db: Session, template: AIPromptTemplateCreate
) -> AIPromptTemplate:
    """Создать шаблон промпта"""
    db_template = AIPromptTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def update_prompt_template(
    db: Session, template_id: int, template: AIPromptTemplateUpdate
) -> Optional[AIPromptTemplate]:
    """Обновить шаблон промпта"""
    db_template = get_prompt_template_by_id(db, template_id)
    if not db_template:
        return None

    for field, value in template.model_dump(exclude_unset=True).items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)
    return db_template


def delete_prompt_template(db: Session, template_id: int) -> bool:
    """Удалить шаблон промпта"""
    db_template = get_prompt_template_by_id(db, template_id)
    if not db_template:
        return False

    db_template.active = False
    db.commit()
    return True


# ===================== ЛОГИ И СТАТИСТИКА =====================


def create_ai_usage_log(
    db: Session,
    user_id: Optional[int],
    provider_id: int,
    task_type: str,
    specialty: Optional[str] = None,
    tokens_used: Optional[int] = None,
    response_time_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request_hash: Optional[str] = None,
    cached_response: bool = False,
) -> AIUsageLog:
    """Создать лог использования AI"""
    # Получаем провайдера для копирования его имени в audit log
    provider = get_ai_provider_by_id(db, provider_id)
    if not provider:
        raise ValueError(f"AI Provider с ID {provider_id} не найден")

    log = AIUsageLog(
        user_id=user_id,
        provider_id=provider_id,
        provider_name=provider.display_name,  # Копируем имя для audit trail
        task_type=task_type,
        specialty=specialty,
        tokens_used=tokens_used,
        response_time_ms=response_time_ms,
        success=success,
        error_message=error_message,
        request_hash=request_hash,
        cached_response=cached_response,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_ai_usage_stats(
    db: Session,
    days_back: int = 30,
    provider_id: Optional[int] = None,
    specialty: Optional[str] = None,
) -> Dict[str, Any]:
    """Получить статистику использования AI"""
    start_date = datetime.utcnow() - timedelta(days=days_back)

    query = db.query(AIUsageLog).filter(AIUsageLog.created_at >= start_date)

    if provider_id:
        query = query.filter(AIUsageLog.provider_id == provider_id)
    if specialty:
        query = query.filter(AIUsageLog.specialty == specialty)

    logs = query.all()

    total_requests = len(logs)
    successful_requests = len([l for l in logs if l.success])
    failed_requests = total_requests - successful_requests

    total_tokens = sum(l.tokens_used for l in logs if l.tokens_used)
    avg_response_time = (
        sum(l.response_time_ms for l in logs if l.response_time_ms) / len(logs)
        if logs
        else 0
    )
    cache_hits = len([l for l in logs if l.cached_response])
    cache_hit_rate = (cache_hits / total_requests) * 100 if total_requests > 0 else 0

    # Статистика по провайдерам
    by_provider = {}
    for log in logs:
        provider_name = log.provider.name if log.provider else "unknown"
        if provider_name not in by_provider:
            by_provider[provider_name] = {"requests": 0, "tokens": 0, "success_rate": 0}

        by_provider[provider_name]["requests"] += 1
        by_provider[provider_name]["tokens"] += log.tokens_used or 0

    # Вычисляем success rate для каждого провайдера
    for provider_name in by_provider:
        provider_logs = [
            l for l in logs if l.provider and l.provider.name == provider_name
        ]
        successful = len([l for l in provider_logs if l.success])
        by_provider[provider_name]["success_rate"] = (
            (successful / len(provider_logs)) * 100 if provider_logs else 0
        )

    # Статистика по типам задач
    by_task_type = {}
    for log in logs:
        task = log.task_type
        if task not in by_task_type:
            by_task_type[task] = {"requests": 0, "avg_tokens": 0}
        by_task_type[task]["requests"] += 1

    # Статистика по специальностям
    by_specialty = {}
    for log in logs:
        if log.specialty:
            if log.specialty not in by_specialty:
                by_specialty[log.specialty] = {"requests": 0}
            by_specialty[log.specialty]["requests"] += 1

    return {
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "total_tokens_used": total_tokens,
        "average_response_time_ms": avg_response_time,
        "cache_hit_rate": cache_hit_rate,
        "by_provider": by_provider,
        "by_task_type": by_task_type,
        "by_specialty": by_specialty,
        "period_start": start_date,
        "period_end": datetime.utcnow(),
    }


# ===================== НАСТРОЙКИ СИСТЕМЫ =====================


def get_ai_system_settings(db: Session) -> Dict[str, Any]:
    """Получить настройки AI системы"""
    from app.crud.clinic import get_settings_by_category

    ai_settings = get_settings_by_category(db, "ai")

    result = {
        "enabled": True,
        "default_provider": "openai",
        "fallback_chain": ["openai", "gemini", "deepseek"],
        "cache_enabled": True,
        "cache_ttl_hours": 24,
        "global_limits": {
            "requests_per_minute": 60,
            "tokens_per_day": 50000,
            "max_file_size_mb": 10,
        },
        "require_consent_for_files": True,
        "anonymize_data": True,
        "audit_all_requests": True,
    }

    # Применяем сохраненные настройки
    for setting in ai_settings:
        if setting.key in result:
            result[setting.key] = setting.value

    return result


def update_ai_system_settings(
    db: Session, settings: Dict[str, Any], user_id: int
) -> Dict[str, Any]:
    """Обновить настройки AI системы"""
    from app.crud.clinic import update_settings_batch

    # Сохраняем настройки в категории "ai"
    update_settings_batch(db, "ai", settings, user_id)

    return get_ai_system_settings(db)
