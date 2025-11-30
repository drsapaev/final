"""
API endpoints для управления доверенными устройствами 2FA
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service, TwoFactorService

router = APIRouter()


class DeviceInfo(BaseModel):
    id: str
    name: Optional[str] = None
    device_type: str
    browser: Optional[str] = None
    os: Optional[str] = None
    location: Optional[str] = None
    ip_address: str
    user_agent: str
    created_at: datetime
    last_used: datetime
    is_current: bool = False


class DeviceCreateRequest(BaseModel):
    name: Optional[str] = None
    device_fingerprint: str
    user_agent: str
    ip_address: str


@router.get("/devices", response_model=List[DeviceInfo])
async def get_trusted_devices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить список доверенных устройств"""
    try:
        service = get_two_factor_service()

        devices = service.get_trusted_devices(db=db, user_id=current_user.id)

        return devices

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения устройств: {str(e)}",
        )


@router.post("/devices", response_model=DeviceInfo)
async def add_trusted_device(
    device_data: DeviceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавить доверенное устройство"""
    try:
        service = get_two_factor_service()

        device = service.add_trusted_device(
            db=db,
            user_id=current_user.id,
            name=device_data.name,
            device_fingerprint=device_data.device_fingerprint,
            user_agent=device_data.user_agent,
            ip_address=device_data.ip_address,
        )

        return device

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка добавления устройства: {str(e)}",
        )


@router.delete("/devices/{device_id}")
async def revoke_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать доступ для устройства"""
    try:
        service = get_two_factor_service()

        success = service.revoke_device(
            db=db, user_id=current_user.id, device_id=device_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Устройство не найдено"
            )

        return {"success": True, "message": "Доступ устройства отозван"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отзыва устройства: {str(e)}",
        )


@router.put("/devices/{device_id}/name")
async def update_device_name(
    device_id: str,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить название устройства"""
    try:
        service = get_two_factor_service()

        success = service.update_device_name(
            db=db, user_id=current_user.id, device_id=device_id, name=name
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Устройство не найдено"
            )

        return {"success": True, "message": "Название устройства обновлено"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления устройства: {str(e)}",
        )


@router.get("/devices/{device_id}/sessions")
async def get_device_sessions(
    device_id: str,
    limit: int = Query(50, description="Количество записей"),
    offset: int = Query(0, description="Смещение"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить сессии устройства"""
    try:
        service = get_two_factor_service()

        sessions = service.get_device_sessions(
            db=db,
            user_id=current_user.id,
            device_id=device_id,
            limit=limit,
            offset=offset,
        )

        return {
            "sessions": sessions,
            "total": len(sessions),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сессий: {str(e)}",
        )


@router.post("/devices/revoke-all")
async def revoke_all_devices(
    password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать доступ для всех устройств"""
    try:
        service = get_two_factor_service()

        # Проверяем пароль
        if not service.verify_password(current_user, password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный пароль"
            )

        success = service.revoke_all_devices(db=db, user_id=current_user.id)

        return {"success": True, "message": "Доступ всех устройств отозван"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отзыва устройств: {str(e)}",
        )


@router.get("/devices/statistics")
async def get_device_statistics(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить статистику устройств"""
    try:
        service = get_two_factor_service()

        stats = service.get_device_statistics(db=db, user_id=current_user.id)

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )


@router.post("/devices/{device_id}/trust")
async def trust_device(
    device_id: str,
    trust_duration_days: int = Query(30, description="Длительность доверия в днях"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Доверить устройству доступ на определенный период"""
    try:
        service = get_two_factor_service()

        success = service.trust_device(
            db=db,
            user_id=current_user.id,
            device_id=device_id,
            trust_until=datetime.utcnow() + timedelta(days=trust_duration_days),
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Устройство не найдено"
            )

        return {
            "success": True,
            "message": f"Устройство доверено на {trust_duration_days} дней",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка доверия устройству: {str(e)}",
        )


@router.get("/devices/{device_id}/security-check")
async def check_device_security(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить безопасность устройства"""
    try:
        service = get_two_factor_service()

        security_info = service.check_device_security(
            db=db, user_id=current_user.id, device_id=device_id
        )

        return security_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки безопасности: {str(e)}",
        )
