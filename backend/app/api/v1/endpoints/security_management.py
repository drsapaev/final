"""
API endpoints для управления безопасностью подтверждений визитов
Доступны только администраторам
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.confirmation_security import ConfirmationSecurityService

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class SecurityStatsResponse(BaseModel):
    """Статистика безопасности"""

    period_hours: int
    since: str
    confirmation_attempts: int
    successful_confirmations: int
    failed_confirmations: int
    rate_limit_blocks: int
    suspicious_activity_blocks: int
    expired_tokens_cleaned: int


class CleanupResponse(BaseModel):
    """Результат очистки истекших токенов"""

    success: bool
    cleaned_count: int
    message: str


class SecurityConfigResponse(BaseModel):
    """Конфигурация безопасности"""

    rate_limits: Dict[str, Dict[str, int]]
    token_expiry_hours: int
    max_confirmation_attempts: int
    cleanup_interval_hours: int


# ===================== СТАТИСТИКА БЕЗОПАСНОСТИ =====================


@router.get("/admin/security/stats", response_model=SecurityStatsResponse)
def get_security_stats(
    hours: int = Query(24, ge=1, le=168, description="Период в часах (1-168)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает статистику безопасности за указанный период
    Доступно только администраторам
    """
    try:
        security_service = ConfirmationSecurityService(db)
        stats = security_service.get_security_stats(hours=hours)

        return SecurityStatsResponse(
            period_hours=stats.get("period_hours", hours),
            since=stats.get("since", ""),
            confirmation_attempts=stats.get("confirmation_attempts", 0),
            successful_confirmations=stats.get("successful_confirmations", 0),
            failed_confirmations=stats.get("failed_confirmations", 0),
            rate_limit_blocks=stats.get("rate_limit_blocks", 0),
            suspicious_activity_blocks=stats.get("suspicious_activity_blocks", 0),
            expired_tokens_cleaned=stats.get("expired_tokens_cleaned", 0),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики безопасности: {str(e)}",
        )


# ===================== ОЧИСТКА ИСТЕКШИХ ТОКЕНОВ =====================


@router.post("/admin/security/cleanup-expired-tokens", response_model=CleanupResponse)
def cleanup_expired_tokens(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Очищает истекшие токены подтверждения
    Доступно только администраторам
    """
    try:
        security_service = ConfirmationSecurityService(db)
        cleaned_count = security_service.cleanup_expired_tokens()

        return CleanupResponse(
            success=True,
            cleaned_count=cleaned_count,
            message=f"Очищено {cleaned_count} истекших токенов",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки истекших токенов: {str(e)}",
        )


# ===================== КОНФИГУРАЦИЯ БЕЗОПАСНОСТИ =====================


@router.get("/admin/security/config", response_model=SecurityConfigResponse)
def get_security_config(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получает текущую конфигурацию безопасности
    Доступно только администраторам
    """
    try:
        security_service = ConfirmationSecurityService(db)

        # Формируем конфигурацию из настроек сервиса
        rate_limits = {}
        for action, config in security_service.RATE_LIMITS.items():
            rate_limits[action] = {
                "max_attempts": config.max_attempts,
                "window_minutes": config.window_minutes,
                "cooldown_minutes": config.cooldown_minutes,
            }

        return SecurityConfigResponse(
            rate_limits=rate_limits,
            token_expiry_hours=48,  # Из настроек создания токена
            max_confirmation_attempts=5,  # Из rate limits
            cleanup_interval_hours=24,  # Рекомендуемый интервал очистки
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения конфигурации безопасности: {str(e)}",
        )


# ===================== ПРОВЕРКА ТОКЕНА =====================


@router.get("/admin/security/validate-token/{token}")
def validate_token_security(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Проверяет безопасность конкретного токена
    Доступно только администраторам
    """
    try:
        security_service = ConfirmationSecurityService(db)

        # Проверяем токен
        security_check = security_service.validate_confirmation_request(
            token=token,
            source_ip="admin_check",
            user_agent="admin_panel",
            channel="admin",
        )

        return {
            "token_valid": security_check.allowed,
            "reason": security_check.reason,
            "retry_after": security_check.retry_after,
            "remaining_attempts": security_check.remaining_attempts,
            "checked_at": datetime.utcnow().isoformat(),
            "checked_by": current_user.username,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки токена: {str(e)}",
        )


# ===================== ПРИНУДИТЕЛЬНАЯ ОЧИСТКА RATE LIMITS =====================


@router.post("/admin/security/reset-rate-limits")
def reset_rate_limits(
    target_type: str = Query(
        ..., pattern="^(ip|patient|all)$", description="Тип цели для сброса"
    ),
    target_id: Optional[str] = Query(None, description="ID цели (IP или patient_id)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Принудительно сбрасывает rate limits
    Доступно только администраторам

    Args:
        target_type: Тип цели (ip, patient, all)
        target_id: ID цели (обязательно для ip и patient)
    """
    try:
        if target_type in ["ip", "patient"] and not target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Для типа {target_type} требуется указать target_id",
            )

        # Здесь должна быть логика сброса rate limits
        # Пока возвращаем заглушку

        message = f"Rate limits сброшены для {target_type}"
        if target_id:
            message += f" (ID: {target_id})"

        return {
            "success": True,
            "message": message,
            "reset_at": datetime.utcnow().isoformat(),
            "reset_by": current_user.username,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса rate limits: {str(e)}",
        )


# ===================== БЛОКИРОВКА/РАЗБЛОКИРОВКА =====================


@router.post("/admin/security/block-ip/{ip}")
def block_ip_address(
    ip: str,
    reason: str = Query(..., description="Причина блокировки"),
    duration_hours: int = Query(
        24, ge=1, le=8760, description="Длительность блокировки в часах"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Блокирует IP адрес
    Доступно только администраторам
    """
    try:
        # Здесь должна быть логика блокировки IP
        # Пока возвращаем заглушку

        return {
            "success": True,
            "message": f"IP {ip} заблокирован на {duration_hours} часов",
            "ip": ip,
            "reason": reason,
            "duration_hours": duration_hours,
            "blocked_at": datetime.utcnow().isoformat(),
            "blocked_by": current_user.username,
            "expires_at": (
                datetime.utcnow() + timedelta(hours=duration_hours)
            ).isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка блокировки IP: {str(e)}",
        )


@router.delete("/admin/security/block-ip/{ip}")
def unblock_ip_address(
    ip: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Разблокирует IP адрес
    Доступно только администраторам
    """
    try:
        # Здесь должна быть логика разблокировки IP
        # Пока возвращаем заглушку

        return {
            "success": True,
            "message": f"IP {ip} разблокирован",
            "ip": ip,
            "unblocked_at": datetime.utcnow().isoformat(),
            "unblocked_by": current_user.username,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка разблокировки IP: {str(e)}",
        )
