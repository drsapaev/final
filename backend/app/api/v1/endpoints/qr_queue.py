"""
API эндпоинты для QR очередей

ACTIVE: Этот модуль содержит активные, рекомендуемые endpoints для работы с очередями.

Основные возможности:
- Генерация QR токенов (специалист/клиника)
- Session-based присоединение к очереди (двухэтапный процесс)
- Управление записями в очереди
- Аналитика и статистика
- Административные функции

Префикс: /api/v1/queue/*

Для legacy endpoints см.: queue.py (DEPRECATED)
Для переупорядочения очереди см.: queue_reorder.py

Документация:
- docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md - Migration guide
- docs/QUEUE_SYSTEM_ARCHITECTURE.md - Архитектура системы
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User

logger = logging.getLogger(__name__)

# NOTE: Doctor импортируется внутри функций для избежания circular dependency
from app.services.qr_queue_service import QRQueueService
from app.services.queue_service import (
    queue_service,
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
)
from app.services.service_mapping import get_service_code
from app.services.queue_session import get_or_create_session_id

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class QRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию QR токена"""

    specialist_id: int = Field(..., description="ID специалиста")
    department: str = Field(..., description="Отделение")
    expires_hours: int = Field(
        default=24, ge=1, le=168, description="Время жизни токена в часах"
    )
    target_date: Optional[str] = Field(
        None, description="Целевая дата для очереди (YYYY-MM-DD)"
    )
    visit_type: str = Field(
        default="paid", description="Тип визита: paid, repeat, benefit"
    )


class ClinicQRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию общего QR токена клиники"""

    target_date: Optional[str] = Field(
        None, description="Целевая дата для очереди (YYYY-MM-DD)"
    )
    expires_hours: int = Field(
        default=24, ge=1, le=168, description="Время жизни токена в часах"
    )


class QRTokenResponse(BaseModel):
    """Ответ с QR токеном"""

    token: str
    qr_url: str
    qr_code_base64: str
    specialist_id: int
    department: str
    expires_at: str
    active: bool


class QRTokenInfoResponse(BaseModel):
    """Информация о QR токене"""

    token: str
    specialist_id: Optional[int] = None  # None для общего QR клиники
    specialist_name: str
    department: str
    department_name: str
    queue_length: int
    queue_active: bool
    expires_at: Optional[str] = None
    is_clinic_wide: Optional[bool] = False  # Флаг общего QR
    target_date: Optional[str] = None  # Дата очереди


class JoinSessionStartRequest(BaseModel):
    """Запрос на начало сессии присоединения"""

    token: str = Field(..., description="QR токен")


class JoinSessionStartResponse(BaseModel):
    """Ответ с данными сессии"""

    session_token: str
    expires_at: str
    queue_info: Dict[str, Any]


class JoinSessionCompleteRequest(BaseModel):
    """Запрос на завершение сессии присоединения"""

    session_token: str = Field(..., description="Токен сессии")
    patient_name: str = Field(
        ..., min_length=2, max_length=200, description="ФИО пациента"
    )
    phone: str = Field(..., min_length=5, max_length=20, description="Номер телефона")
    telegram_id: Optional[int] = Field(None, description="Telegram ID")
    specialist_ids: Optional[List[int]] = Field(
        None, description="Список ID специалистов (для общего QR)"
    )


class JoinSessionCompleteMultipleResponse(BaseModel):
    """Ответ с результатом присоединения к нескольким очередям"""

    success: bool
    queue_time: str
    entries: List[Dict[str, Any]]
    errors: Optional[List[Dict[str, Any]]] = None
    message: str


class JoinSessionCompleteResponse(BaseModel):
    """Ответ с результатом присоединения"""

    success: bool
    queue_number: int
    queue_length: int
    estimated_wait_time: int
    specialist_name: str
    department: str


class QueueStatusResponse(BaseModel):
    """Статус очереди"""

    active: bool
    queue_length: int
    current_number: Optional[int]
    entries: List[Dict[str, Any]]


class CallNextPatientResponse(BaseModel):
    """Ответ на вызов следующего пациента"""

    success: bool
    message: Optional[str] = None
    patient: Optional[Dict[str, Any]] = None
    queue_length: Optional[int] = None


class ActiveQRTokenResponse(BaseModel):
    """Активный QR токен"""

    token: str
    specialist_id: int
    department: str
    created_at: str
    expires_at: str
    sessions_count: int
    successful_joins: int
    qr_url: str


class CancelServiceRequest(BaseModel):
    """Запрос на отмену услуги"""

    service_id: int = Field(..., description="ID услуги для отмены")
    cancel_reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Причина отмены (минимум 5 символов)",
    )
    was_paid: bool = Field(
        default=False, description="Была ли услуга оплачена до отмены"
    )


class CancelServiceResponse(BaseModel):
    """Ответ на отмену услуги"""

    success: bool
    message: str
    cancelled_service: Dict[str, Any]
    new_total_amount: int


# ===================== ЭНДПОИНТЫ =====================


@router.post("/admin/qr-tokens/generate", response_model=QRTokenResponse)
def generate_qr_token(
    request: QRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Генерирует QR токен для присоединения к очереди
    Доступно администраторам, врачам и регистраторам
    """
    qr_service = QRQueueService(db)

    try:
        target_date = None
        if request.target_date:
            target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()

        try:
            token_value, token_meta = queue_service.assign_queue_token(
                db,
            specialist_id=request.specialist_id,
            department=request.department,
            generated_by_user_id=current_user.id,
                target_date=target_date,
            expires_hours=request.expires_hours,
                is_clinic_wide=False,
            )
        except QueueValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except QueueNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

        base_url = qr_service._get_frontend_url()
        qr_url = f"{base_url}/queue/join?token={token_value}"
        qr_code_base64 = qr_service._generate_qr_code(qr_url)

        return QRTokenResponse(
            token=token_value,
            qr_url=qr_url,
            qr_code_base64=qr_code_base64,
            specialist_id=request.specialist_id,
            department=request.department,
            expires_at=(
                token_meta.get("expires_at").isoformat()
                if token_meta.get("expires_at")
                else None
            ),
            active=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR токена: {str(e)}",
        )


@router.post("/admin/qr-tokens/generate-clinic")
def generate_clinic_qr_token(
    request: ClinicQRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Генерирует общий QR токен для всей клиники
    Пациент сможет выбрать несколько специалистов после сканирования
    Доступно только администраторам и регистраторам
    """
    try:
        target_date = date.today()
        if request.target_date:
            target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()
        
        token, token_data = queue_service.assign_queue_token(
            db,
            specialist_id=None,
            department="clinic",
            generated_by_user_id=current_user.id,
            target_date=target_date,
            expires_hours=request.expires_hours,
            is_clinic_wide=True,
        )
        
        # Генерируем QR код
        from app.services.qr_queue_service import QRQueueService

        service = QRQueueService(db)
        
        # Формируем URL для QR (используем метод из сервиса)
        base_url = service._get_frontend_url()
        qr_url = f"{base_url}/queue/join?token={token}"
        
        # Генерируем QR код
        qr_code_base64 = service._generate_qr_code(qr_url)
        
        return {
            "token": token,
            "qr_url": qr_url,
            "qr_code_base64": qr_code_base64,
            "is_clinic_wide": True,
            "day": target_date.isoformat(),
            "expires_at": (
                token_data.get("expires_at").isoformat()
                if token_data.get("expires_at")
                else None
            ),
            "active": True,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации общего QR токена: {str(e)}",
        )


@router.get("/available-specialists")
def get_available_specialists(db: Session = Depends(get_db)):
    """
    Получает список доступных специалистов для QR-регистрации (публичный эндпоинт)
    Используется для динамического отображения списка специалистов в интерфейсе QR-регистрации
    """
    try:
        # Импортируем локально для избежания circular dependency
        from sqlalchemy.orm import joinedload

        from app.models.clinic import Doctor
        
        # Получаем всех активных врачей с eager loading user relationship
        doctors = (
            db.query(Doctor)
            .filter(Doctor.active == True)
            .options(joinedload(Doctor.user))
            .all()
        )
        
        # Маппинг специальностей на русские названия и иконки
        specialty_mapping = {
            'cardiology': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'cardio': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'dermatology': {
                'name': 'Дерматолог-косметолог',
                'icon': '✨',
                'color': '#FF9500',
            },
            'derma': {
                'name': 'Дерматолог-косметолог',
                'icon': '✨',
                'color': '#FF9500',
            },
            'dentistry': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'dentist': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'laboratory': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'},
            'lab': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'},
        }
        
        # Группируем по специальностям и выбираем первого врача из каждой группы
        specialists_by_specialty = {}
        for doctor in doctors:
            specialty_key = doctor.specialty.lower() if doctor.specialty else None
            if not specialty_key:
                continue
                
            # Нормализуем ключ специальности
            normalized_specialty = None
            for key in specialty_mapping.keys():
                if key in specialty_key or specialty_key in key:
                    normalized_specialty = key
                    break
            
            if not normalized_specialty:
                # Если специальность не найдена в маппинге, используем оригинальную
                normalized_specialty = specialty_key
                specialty_mapping[normalized_specialty] = {
                    'name': doctor.specialty or 'Специалист',
                    'icon': '👨‍⚕️',
                    'color': '#8E8E93',
                }
            
            # Берем первого врача из каждой специальности
            if normalized_specialty not in specialists_by_specialty:
                specialists_by_specialty[normalized_specialty] = {
                    'id': doctor.id,
                    'specialty': normalized_specialty,
                    'specialty_display': specialty_mapping[normalized_specialty][
                        'name'
                    ],
                    'icon': specialty_mapping[normalized_specialty]['icon'],
                    'color': specialty_mapping[normalized_specialty]['color'],
                    'doctor_name': (
                        doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                    ),
                    'cabinet': doctor.cabinet,
                }
        
        # Преобразуем в список
        specialists_list = list(specialists_by_specialty.values())
        
        # Сортируем по порядку: кардиолог, дерматолог, стоматолог, лаборатория
        sort_order = [
            'cardiology',
            'cardio',
            'dermatology',
            'derma',
            'dentistry',
            'dentist',
            'laboratory',
            'lab',
        ]
        specialists_list.sort(
            key=lambda x: (
                sort_order.index(x['specialty'])
                if x['specialty'] in sort_order
                else 999
            )
        )
        
        return {
            'success': True,
            'specialists': specialists_list,
            'total': len(specialists_list),
        }
        
    except Exception as e:
        import traceback

        logger.error(
            "[get_available_specialists] ОШИБКА: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка специалистов: {str(e)}",
        )


@router.get("/qr-tokens/{token}/info", response_model=QRTokenInfoResponse)
def get_qr_token_info(token: str, db: Session = Depends(get_db)):
    """
    Получает информацию о QR токене (публичный эндпоинт)
    """
    try:
        service = QRQueueService(db)

        token_info = service.get_qr_token_info(token)

        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR токен не найден или истек",
            )

        return QRTokenInfoResponse(**token_info)
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(
            "[get_qr_token_info] ОШИБКА: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о токене: {str(e)}",
        )


@router.post("/join/start", response_model=JoinSessionStartResponse)
def start_join_session(
    request: JoinSessionStartRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Начинает сессию присоединения к очереди (публичный эндпоинт)
    """
    import traceback
    
    service = QRQueueService(db)
    
    try:
        try:
            queue_service.validate_queue_token(db, request.token)
        except (QueueValidationError, QueueNotFoundError) as exc:
            raise ValueError(str(exc)) from exc

        logger.info(
            "[start_join_session] Запрос на начало сессии с токеном: %s...",
            request.token[:20],
        )
        result = service.start_join_session(
            token=request.token,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
        )
        
        logger.info(
            "[start_join_session] Сессия успешно создана: %s...",
            result.get('session_token', '')[:20],
        )
        return JoinSessionStartResponse(**result)
        
    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            "[start_join_session] ValueError: %s, Токен: %s...",
            error_msg,
            request.token[:20],
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        error_msg = f"Ошибка начала сессии: {str(e)}"
        logger.error(
            "[start_join_session] Неожиданная ошибка: %s",
            error_msg,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
        )


@router.post("/join/complete")
def complete_join_session(
    request: JoinSessionCompleteRequest, db: Session = Depends(get_db)
):
    """
    Завершает сессию присоединения к очереди (публичный эндпоинт)
    Поддерживает как одиночное, так и множественное присоединение
    """
    service = QRQueueService(db)

    try:
        logger.info(
            "[complete_join_session] Начало обработки запроса: session_token=%s, patient_name=%s, phone=%s, specialist_ids=%s",
            request.session_token,
            request.patient_name,
            request.phone,
            request.specialist_ids,
        )

        # Если передан список specialist_ids - множественное присоединение
        if request.specialist_ids and len(request.specialist_ids) > 0:
            result = service.complete_join_session_multiple(
                session_token=request.session_token,
                specialist_ids=request.specialist_ids,
                patient_name=request.patient_name,
                phone=request.phone,
                telegram_id=request.telegram_id,
            )
            logger.info(
                "[complete_join_session] Результат множественного присоединения: %s",
                result,
            )
            return JoinSessionCompleteMultipleResponse(**result)
        else:
            # Одиночное присоединение (старый способ)
            result = service.complete_join_session(
                session_token=request.session_token,
                patient_name=request.patient_name,
                phone=request.phone,
                telegram_id=request.telegram_id,
            )

            logger.info(
                "[complete_join_session] Результат получен: %s",
                result,
            )
            return JoinSessionCompleteResponse(**result)

    except ValueError as e:
        logger.warning(
            "[complete_join_session] ValueError: %s",
            str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.get("/status/{specialist_id}", response_model=QueueStatusResponse)
def get_queue_status(
    specialist_id: int,
    target_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Получает статус очереди специалиста
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    # Парсим дату если указана
    parsed_date = None
    if target_date:
        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )
    
    result = service.get_queue_status(specialist_id, parsed_date)
    
    return QueueStatusResponse(**result)


@router.post("/{specialist_id}/call-next", response_model=CallNextPatientResponse)
async def call_next_patient(
    specialist_id: int,
    target_date: Optional[str] = Query(
        None, description="Дата очереди (YYYY-MM-DD), по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Вызывает следующего пациента в очереди
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    try:
        # Парсим дату, если передана
        queue_date = None
        if target_date:
            from datetime import datetime

            queue_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # Вызываем пациента (синхронно, так как QRQueueService работает с синхронной сессией)
        from fastapi.concurrency import run_in_threadpool
        result = await run_in_threadpool(
            service.call_next_patient, specialist_id, current_user.id, queue_date
        )
        
        # --- Notification Logic ---
        if result.get("success") and result.get("patient") and result["patient"].get("id"):
            entry_id = result["patient"]["id"]
            
            # 1. User Notification (Mobile/PWA)
            try:
                from app.services.queue_position_notifications import get_queue_position_service
                from app.models.online_queue import OnlineQueueEntry
                
                # Re-fetch entry to ensure attached to session if needed, or use ID
                # Actually notify_patient_called needs entry object
                notify_service = get_queue_position_service(db)
                entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
                
                if entry:
                    # Determine cabinet (optional)
                    cabinet = None
                    if entry.queue and entry.queue.cabinet_number:
                        cabinet = entry.queue.cabinet_number
                    elif entry.queue and entry.queue.specialist: # Fallback to doctor's cabinet
                        cabinet = entry.queue.specialist.cabinet
                        
                    await notify_service.notify_patient_called(entry, cabinet_number=cabinet)
            except Exception as e:
                logger.warning(f"Failed to send user notification for entry {entry_id}: {e}")

            # 2. Display Board Notification (TV)
            try:
                from app.services.display_websocket import get_display_manager
                
                manager = get_display_manager()
                
                # Fetch fresh entry or use existing
                if not entry: # Should have been fetched above
                     entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
                
                if entry:
                    specialist_name = (
                        entry.queue.specialist.user.full_name
                        if entry.queue.specialist and entry.queue.specialist.user
                        else f"Врач"
                    )
                    
                    await manager.broadcast_patient_call(
                        queue_entry=entry,
                        doctor_name=specialist_name,
                        cabinet=entry.queue.cabinet_number  # Pass cabinet if available
                    )
            except Exception as e:
                logger.warning(f"Failed to update display for entry {entry_id}: {e}")
        # --------------------------

        return CallNextPatientResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error calling next patient: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента: {str(e)}",
        )


@router.get("/admin/qr-tokens/active", response_model=List[ActiveQRTokenResponse])
def get_active_qr_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Получает активные QR токены пользователя
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    tokens = service.get_active_qr_tokens(current_user.id)
    
    return [ActiveQRTokenResponse(**token) for token in tokens]


@router.delete("/admin/qr-tokens/{token}")
def deactivate_qr_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Деактивирует QR токен
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    success = service.deactivate_qr_token(token, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR токен не найден или вы не являетесь его создателем",
        )
    
    return {"message": "QR токен успешно деактивирован"}


# ===================== УПРАВЛЕНИЕ СТАТУСАМИ ОЧЕРЕДИ =====================


class RestoreToNextRequest(BaseModel):
    """Запрос на восстановление пациента следующим в очереди"""
    reason: Optional[str] = Field(None, description="Причина восстановления")


class SetIncompleteRequest(BaseModel):
    """Запрос на установку статуса incomplete"""
    reason: str = Field(..., min_length=3, max_length=200, description="Причина незавершённости")


@router.post("/entry/{entry_id}/restore-next")
async def restore_entry_to_next(
    entry_id: int,
    request: RestoreToNextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Восстанавливает пациента no_show как следующего в очереди
    Устанавливает priority=1 для приоритетной обработки
    """
    from app.models.online_queue import OnlineQueueEntry
    
    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )
    
    if entry.status not in ["no_show", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Можно восстановить только записи со статусом no_show или cancelled, текущий: {entry.status}"
        )
    
    # Восстанавливаем с приоритетом "следующий"
    entry.status = "waiting"
    entry.priority = 1  # Следующий в очереди
    db.commit()
    
    logger.info(
        "[restore_entry_to_next] Запись %d восстановлена следующей по запросу пользователя %d",
        entry_id,
        current_user.id
    )

    # --- Display Notification ---
    try:
        from app.services.display_websocket import get_display_manager
        manager = get_display_manager()
        await manager.broadcast_queue_update(queue_entry=entry, event_type="queue.restored")
    except Exception as e:
        logger.warning(f"Failed to update display for entry {entry_id}: {e}")
    # ----------------------------
    
    return {
        "success": True,
        "message": "Пациент восстановлен как следующий в очереди",
        "entry_id": entry_id,
        "new_status": "waiting",
        "priority": 1
    }


@router.post("/entry/{entry_id}/no-show")
async def mark_entry_no_show(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Отмечает пациента как неявившегося (no_show)
    """
    from app.models.online_queue import OnlineQueueEntry
    
    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )
    
    if entry.status not in ["waiting", "called"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неявку можно отметить только для waiting или called, текущий: {entry.status}"
        )
    
    entry.status = "no_show"
    db.commit()
    
    logger.info(
        "[mark_entry_no_show] Запись %d отмечена как no_show пользователем %d",
        entry_id,
        current_user.id
    )

    # --- Display Notification ---
    try:
        from app.services.display_websocket import get_display_manager
        manager = get_display_manager()
        await manager.broadcast_queue_update(queue_entry=entry, event_type="queue.updated")
        # Also clean up from "Called" section if it was there
    except Exception as e:
        logger.warning(f"Failed to update display for entry {entry_id}: {e}")
    # ----------------------------
    
    return {
        "success": True,
        "message": "Пациент отмечен как неявившийся",
        "entry_id": entry_id,
        "new_status": "no_show"
    }


@router.post("/entry/{entry_id}/diagnostics")
def send_entry_to_diagnostics(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Отправляет пациента на обследование (diagnostics)
    Запускает таймер ожидания
    """
    from app.models.online_queue import OnlineQueueEntry
    
    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )
    
    if entry.status not in ["called", "in_service"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"На обследование можно отправить только called или in_service, текущий: {entry.status}"
        )
    
    entry.status = "diagnostics"
    entry.diagnostics_started_at = datetime.utcnow()
    db.commit()
    
    logger.info(
        "[send_entry_to_diagnostics] Запись %d отправлена на диагностику пользователем %d",
        entry_id,
        current_user.id
    )
    
    return {
        "success": True,
        "message": "Пациент отправлен на обследование",
        "entry_id": entry_id,
        "new_status": "diagnostics",
        "started_at": entry.diagnostics_started_at.isoformat() + "Z"
    }


@router.post("/entry/{entry_id}/incomplete")
def mark_entry_incomplete(
    entry_id: int,
    request: SetIncompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Завершает приём с указанием причины незавершённости (incomplete)
    """
    from app.models.online_queue import OnlineQueueEntry
    
    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )
    
    if entry.status not in ["called", "in_service", "diagnostics"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete можно установить только для called/in_service/diagnostics, текущий: {entry.status}"
        )
    
    entry.status = "incomplete"
    entry.incomplete_reason = request.reason
    db.commit()
    
    logger.info(
        "[mark_entry_incomplete] Запись %d отмечена как incomplete (причина: %s) пользователем %d",
        entry_id,
        request.reason,
        current_user.id
    )
    
    return {
        "success": True,
        "message": "Приём отмечен как незавершённый",
        "entry_id": entry_id,
        "new_status": "incomplete",
        "reason": request.reason
    }


# ===================== СТАТИСТИКА И АНАЛИТИКА =====================


@router.get("/admin/queue-analytics/{specialist_id}")
def get_queue_analytics(
    specialist_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает аналитику по очередям специалиста
    Доступно только администраторам
    """
    # Парсим даты
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат start_date. Используйте YYYY-MM-DD",
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат end_date. Используйте YYYY-MM-DD",
            )
    
    # Если даты не указаны, берем последние 30 дней
    if not start_dt:
        start_dt = date.today() - timedelta(days=30)
    if not end_dt:
        end_dt = date.today()
    
    from app.models.online_queue import DailyQueue, QueueStatistics
    
    # Получаем статистику
    stats = (
        db.query(QueueStatistics)
        .join(DailyQueue)
        .filter(
        DailyQueue.specialist_id == specialist_id,
        QueueStatistics.date >= start_dt,
            QueueStatistics.date <= end_dt,
        )
        .all()
    )
    
    # Агрегируем данные
    total_online_joins = sum(s.online_joins for s in stats)
    total_desk_registrations = sum(s.desk_registrations for s in stats)
    total_telegram_joins = sum(s.telegram_joins for s in stats)
    total_confirmation_joins = sum(s.confirmation_joins for s in stats)
    total_served = sum(s.total_served for s in stats)
    total_no_show = sum(s.total_no_show for s in stats)
    
    avg_wait_time = None
    if stats:
        wait_times = [s.average_wait_time for s in stats if s.average_wait_time]
        if wait_times:
            avg_wait_time = sum(wait_times) / len(wait_times)
    
    return {
        "specialist_id": specialist_id,
        "period": {"start_date": start_dt.isoformat(), "end_date": end_dt.isoformat()},
        "totals": {
            "online_joins": total_online_joins,
            "desk_registrations": total_desk_registrations,
            "telegram_joins": total_telegram_joins,
            "confirmation_joins": total_confirmation_joins,
            "total_served": total_served,
            "total_no_show": total_no_show,
        },
        "metrics": {
            "average_wait_time": avg_wait_time,
            "no_show_rate": (
                (total_no_show / (total_served + total_no_show)) * 100
                if (total_served + total_no_show) > 0
                else 0
            ),
        },
        "daily_stats": [
            {
                "date": stat.date.isoformat(),
                "online_joins": stat.online_joins,
                "desk_registrations": stat.desk_registrations,
                "telegram_joins": stat.telegram_joins,
                "confirmation_joins": stat.confirmation_joins,
                "total_served": stat.total_served,
                "total_no_show": stat.total_no_show,
                "average_wait_time": stat.average_wait_time,
                "peak_hour": stat.peak_hour,
                "max_queue_length": stat.max_queue_length,
            }
            for stat in stats
        ],
    }


# ===================== ОБНОВЛЕНИЕ ОНЛАЙН ЗАПИСИ =====================


class UpdateOnlineEntryRequest(BaseModel):
    """Запрос на обновление данных онлайн записи"""

    patient_name: Optional[str] = None
    phone: Optional[str] = None
    birth_year: Optional[int] = None
    address: Optional[str] = None


@router.put("/online-entry/{entry_id}/update")
def update_online_entry(
    entry_id: int,
    request: UpdateOnlineEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Обновляет данные пациента в онлайн записи
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.patient import Patient

        # Находим запись
        entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        # Обновляем данные в OnlineQueueEntry
        if request.patient_name is not None:
            entry.patient_name = request.patient_name

        if request.phone is not None:
            entry.phone = request.phone

        if request.birth_year is not None:
            entry.birth_year = request.birth_year

        if request.address is not None:
            entry.address = request.address

        # Если есть patient_id, обновляем также данные в Patient
        if entry.patient_id:
            patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
            if patient:
                if request.patient_name:
                    # Разбираем ФИО
                    name_parts = request.patient_name.split()
                    if len(name_parts) >= 1:
                        patient.last_name = name_parts[0]
                    if len(name_parts) >= 2:
                        patient.first_name = name_parts[1]
                    if len(name_parts) >= 3:
                        patient.middle_name = name_parts[2]

                if request.phone:
                    patient.phone = request.phone

                if request.birth_year:
                    from datetime import date

                    patient.birth_date = date(request.birth_year, 1, 1)

                if request.address:
                    patient.address = request.address

        db.commit()
        db.refresh(entry)

        return {
            "success": True,
            "message": "Данные пациента обновлены",
            "entry": {
                "id": entry.id,
                "patient_name": entry.patient_name,
                "phone": entry.phone,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(
            "[update_online_entry] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления данных: {str(e)}",
        )


# ===================== ПОЛНОЕ ОБНОВЛЕНИЕ ОНЛАЙН ЗАПИСИ (ДЛЯ МАСТЕРА) =====================


class FullUpdateOnlineEntryRequest(BaseModel):
    """Запрос на полное обновление онлайн записи через мастер регистрации"""

    patient_data: dict  # {patient_name, phone, birth_year, address}
    visit_type: str  # paid/repeat/benefit
    discount_mode: str  # none/repeat/benefit
    services: List[dict]  # [{service_id, quantity}]
    all_free: bool = False
    aggregated_ids: Optional[List[int]] = None  # ⭐ FIX: IDs of all merged entries for dedup check


@router.put("/online-entry/{entry_id}/full-update")
def full_update_online_entry(
    entry_id: int,
    request: FullUpdateOnlineEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist")
    ),
):
    """
    Полное обновление онлайн записи через мастер регистрации:
    - Данные пациента (ФИО, телефон, год рождения, адрес)
    - Тип визита и режим скидки
    - Список услуг
    - Расчет итоговой суммы с учетом скидок
    """
    try:
        import json
        from datetime import date

        from app.models.online_queue import OnlineQueueEntry
        from app.models.patient import Patient
        from app.models.service import Service

        logger.info(
            "[full_update_online_entry] Обновление записи ID=%d, Данные пациента: %s, Тип визита: %s, Услуги: %s",
            entry_id,
            request.patient_data,
            request.visit_type,
            request.services,
        )

        # 1. Находим запись
        entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        logger.info(
            "[full_update_online_entry] Запись найдена: %s, phone=%s",
            entry.patient_name,
            entry.phone,
        )

        # 2. Обновляем данные пациента в OnlineQueueEntry
        patient_data = request.patient_data
        if patient_data.get('patient_name'):
            entry.patient_name = patient_data['patient_name']
            logger.info(
                "[full_update_online_entry] Обновлено ФИО: %s",
                entry.patient_name,
            )

        if patient_data.get('phone'):
            entry.phone = patient_data['phone']
            logger.info(
                "[full_update_online_entry] Обновлен телефон: %s",
                entry.phone,
            )

        if patient_data.get('birth_year') is not None:
            entry.birth_year = patient_data['birth_year']
            logger.info(
                "[full_update_online_entry] Обновлен год рождения: %s",
                entry.birth_year,
            )

        if patient_data.get('address'):
            entry.address = patient_data['address']
            logger.info(
                "[full_update_online_entry] Обновлен адрес: %s",
                entry.address,
            )

        # 3. Обновляем тип визита и режим скидки
        entry.visit_type = request.visit_type
        # ✅ ИСПРАВЛЕНО: Если all_free = True, устанавливаем discount_mode = "all_free"
        entry.discount_mode = "all_free" if request.all_free else request.discount_mode
        logger.info(
            "[full_update_online_entry] Тип визита: %s, режим скидки: %s, all_free: %s",
            entry.visit_type,
            entry.discount_mode,
            request.all_free,
        )

        # 4. Обновляем услуги и рассчитываем сумму
        # ✅ НОВЫЙ ФОРМАТ: Полные объекты услуг с метаданными
        services_list = []
        service_codes_list = []  # Сохраняем для обратной совместимости
        total_amount = 0

        # ⭐ FIX: Определяем существующие услуги из ВСЕХ записей пациента за день (не только текущей entry)
        from datetime import datetime, timezone
        from app.models.online_queue import DailyQueue

        existing_service_ids = set()
        # ⭐ FIX PHASE 2: Сохраняем оригинальные queue_times для существующих услуг
        existing_service_queue_times = {}
        
        # ⭐ FIX 3: Backend САМ вычисляет aggregated_ids по patient_id + дате или phone + дате
        # Frontend aggregated_ids используем только как fallback
        computed_aggregated_ids = []
        today = date.today()
        
        queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
        queue_day = queue.day if queue else today
        
        if entry.visit_id:
            # ⭐ FIX 4: Если есть visit_id, ищем строго по нему (это одна сессия обслуживания)
            visit_entries = (
                db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.visit_id == entry.visit_id,
                    OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
                )
                .all()
            )
            computed_aggregated_ids = [e.id for e in visit_entries]
            logger.info(
                "[full_update_online_entry] ⭐ FIX 4: Вычислены aggregated_ids по visit_id=%d: %s",
                entry.visit_id, computed_aggregated_ids
            )
        else:
            # Если нет visit_id, используем поиск по patient_id/phone за текущий день
            # (это случай первой регистрации или когда visit еще не создан)
            if entry.patient_id:
                patient_entries = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        OnlineQueueEntry.patient_id == entry.patient_id,
                        DailyQueue.day == queue_day,
                        OnlineQueueEntry.visit_id == None, # ⭐ Только записи без визита (потенциально текущая сессия)
                        OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
                    )
                    .all()
                )
                computed_aggregated_ids = list(set([e.id for e in patient_entries] + [entry.id]))
                logger.info(
                    "[full_update_online_entry] ⭐ FIX 3: Вычислены aggregated_ids по patient_id=%d (no visit): %s",
                    entry.patient_id, computed_aggregated_ids
                )
            elif entry.phone:
                phone_entries = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        OnlineQueueEntry.phone == entry.phone,
                        DailyQueue.day == queue_day,
                        OnlineQueueEntry.visit_id == None,
                        OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
                    )
                    .all()
                )
                computed_aggregated_ids = list(set([e.id for e in phone_entries] + [entry.id]))
                logger.info(
                    "[full_update_online_entry] ⭐ FIX 3: Вычислены aggregated_ids по phone=%s (no visit): %s",
                    entry.phone, computed_aggregated_ids
                )
        
        # Используем computed_aggregated_ids, frontend's aggregated_ids только как fallback
        final_aggregated_ids = computed_aggregated_ids if computed_aggregated_ids else (request.aggregated_ids or [])
        if not computed_aggregated_ids and request.aggregated_ids:
            logger.warning(
                "[full_update_online_entry] ⚠️ Используем aggregated_ids из frontend (fallback): %s",
                request.aggregated_ids
            )
        
        # ⭐ DEBUG: Логируем начальное состояние
        logger.info(
            "[full_update_online_entry] ⭐ DEBUG: entry.patient_id=%s, final_aggregated_ids=%s, entry.services=%s",
            entry.patient_id,
            final_aggregated_ids,
            entry.services[:200] if entry.services else None,
        )
        
        # ⭐ FIX: Используем final_aggregated_ids для получения всех записей пациента
        if final_aggregated_ids and len(final_aggregated_ids) > 0:
            logger.info(
                "[full_update_online_entry] ⭐ FIX: Используем aggregated_ids для поиска существующих услуг: %s",
                final_aggregated_ids,
            )
            all_entries = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id.in_(final_aggregated_ids))
                .all()
            )
            
            for agg_entry in all_entries:
                if agg_entry.services:
                    try:
                        agg_services = json.loads(agg_entry.services)
                        # ⭐ FIX: Обрабатываем двойное кодирование JSON
                        if isinstance(agg_services, str):
                            agg_services = json.loads(agg_services)
                        
                        if isinstance(agg_services, list):
                            for svc in agg_services:
                                svc_id = svc.get('service_id')
                                if svc_id:
                                    existing_service_ids.add(svc_id)
                                    # ⭐ FIX: Сохраняем оригинальное queue_time
                                    if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                        existing_service_queue_times[svc_id] = svc.get('queue_time')
                    except Exception as e:
                        logger.warning(
                            "[full_update_online_entry] Ошибка парсинга services для entry %d: %s",
                            agg_entry.id, e,
                        )
            
            logger.info(
                "[full_update_online_entry] ⭐ FIX: Найдено %d существующих услуг из aggregated_ids: %s",
                len(existing_service_ids),
                list(existing_service_ids),
            )
        
        # Используем queue из FIX 3 блока выше (queue_day уже вычислен)
        
        # ⭐ FIX: Если aggregated_ids не предоставлен или пустой, используем старую логику
        # Но ТОЛЬКО если мы ещё не нашли услуги через aggregated_ids
        if len(existing_service_ids) == 0:
            if entry.patient_id and queue:
                # ⭐ Запрашиваем ВСЕ записи этого пациента за этот день
                all_patient_entries = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        OnlineQueueEntry.patient_id == entry.patient_id,
                        DailyQueue.day == queue.day
                    )
                    .all()
                )
                
                logger.info(
                    "[full_update_online_entry] ⭐ FIX: Найдено %d записей пациента за %s",
                    len(all_patient_entries),
                    queue.day,
                )
                
                for patient_entry in all_patient_entries:
                    if patient_entry.services:
                        try:
                            entry_services = json.loads(patient_entry.services)
                            for svc in entry_services:
                                svc_id = svc.get('service_id')
                                if svc_id:
                                    existing_service_ids.add(svc_id)
                                    # ⭐ FIX: Сохраняем оригинальное queue_time
                                    if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                        existing_service_queue_times[svc_id] = svc.get('queue_time')
                        except:
                            pass
            else:
                # Fallback: только текущая entry (как было раньше)
                logger.info(
                    "[full_update_online_entry] ⭐ DEBUG: Fallback - patient_id is None or no queue, using entry.services only"
                )
                if entry.services:
                    try:
                        # ⭐ FIX: Обрабатываем двойное кодирование JSON
                        existing_services = json.loads(entry.services)
                        # Если результат — строка, значит данные двойно закодированы
                        if isinstance(existing_services, str):
                            existing_services = json.loads(existing_services)
                            logger.warning(
                                "[full_update_online_entry] ⚠️ Обнаружено двойное кодирование JSON в entry.services"
                            )
                        
                        if isinstance(existing_services, list):
                            logger.info(
                                "[full_update_online_entry] ⭐ DEBUG: Найдено %d услуг в entry.services: %s",
                                len(existing_services),
                                [s.get('service_id') for s in existing_services],
                            )
                            for svc in existing_services:
                                svc_id = svc.get('service_id')
                                if svc_id:
                                    existing_service_ids.add(svc_id)
                                    # ⭐ FIX: Сохраняем оригинальное queue_time
                                    if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                        existing_service_queue_times[svc_id] = svc.get('queue_time')
                        else:
                            logger.warning(
                                "[full_update_online_entry] ⚠️ entry.services не является списком: %s",
                                type(existing_services).__name__
                            )
                    except Exception as parse_err:
                        logger.error(
                            "[full_update_online_entry] ⭐ DEBUG: Ошибка парсинга entry.services: %s",
                            parse_err,
                        )
        
        logger.info(
            "[full_update_online_entry] Существующие услуги: %s, сохранённые queue_times: %s",
            existing_service_ids,
            list(existing_service_queue_times.keys()),
        )

        # Определяем новые услуги (которые не были в entry.services)
        new_service_ids = []
        for service_item in request.services:
            if service_item['service_id'] not in existing_service_ids:
                new_service_ids.append(service_item['service_id'])

        logger.info(
            "[full_update_online_entry] ⭐ DEBUG: Новые услуги для добавления: %s",
            new_service_ids,
        )
        logger.info(
            "[full_update_online_entry] ⭐ DEBUG: request.services содержит: %s",
            [s['service_id'] for s in request.services],
        )
        logger.info(
            "[full_update_online_entry] ⭐ DEBUG: existing_service_ids: %s",
            list(existing_service_ids),
        )

        # Определяем: это первичная регистрация или редактирование?
        # ⭐ DEBUG: Добавляем логирование для отладки
        logger.info(
            "[full_update_online_entry] DEBUG: entry.queue_time=%s, entry.services=%s (type=%s, len=%s)",
            entry.queue_time,
            entry.services[:100] if entry.services else None,
            type(entry.services).__name__,
            len(entry.services) if entry.services else 0,
        )
        
        # ⭐ FIX: Улучшенная логика определения первичной регистрации
        # Считаем "первичной регистрацией" ТОЛЬКО если queue_time = None
        # Если есть entry.services (даже пустой JSON []), но queue_time есть - это редактирование
        has_services = False
        if entry.services:
            try:
                parsed = json.loads(entry.services) if isinstance(entry.services, str) else entry.services
                has_services = len(parsed) > 0
            except (json.JSONDecodeError, TypeError):
                has_services = False
        
        # ⭐ FIX CRITICAL: Улучшенная логика определения первичной регистрации
        # Для QR-записей: если entry.services пустой И мы не нашли услуг в БД для этого пациента — это "первое заполнение"
        # Если услуги в БД найдены (даже если в этой конкретной entry пусто), значит это редактирование (добавление новых)
        is_first_fill_qr = (
            not has_services 
            and entry.queue_time is not None 
            and entry.source == "online" 
            and len(existing_service_ids) == 0  # ⭐ FIX: Только если вообще нет услуг у пациента
        )
        is_initial_registration = entry.queue_time is None
        
        logger.info(
            "[full_update_online_entry] DEBUG: has_services=%s, is_initial_registration=%s, is_first_fill_qr=%s, source=%s",
            has_services,
            is_initial_registration,
            is_first_fill_qr,
            entry.source,
        )

        if is_initial_registration:
            # Первичная регистрация - обновляем текущую entry со всеми услугами
            queue_time = entry.queue_time or datetime.now(timezone.utc)
            logger.info(
                "[full_update_online_entry] Первичная регистрация, queue_time: %s",
                queue_time,
            )

        elif is_first_fill_qr:
            # ⭐ FIX 13: Первое заполнение QR-записи
            # ТОЛЬКО ОДНА услуга-консультация (is_consultation=True) получает QR время
            # ВСЕ остальные услуги получают ТЕКУЩЕЕ время и создаются как Independent Queue Entries
            queue_time = entry.queue_time
            logger.info(
                "[full_update_online_entry] ⭐ Первое заполнение QR-записи, queue_time: %s",
                queue_time,
            )
            
            # ⭐ FIX 13: Ищем РОВНО ОДНУ консультационную услугу
            consultation_service_id = None
            additional_service_ids = []
            
            for service_item in request.services:
                svc_id = service_item['service_id']
                service = db.query(Service).filter(Service.id == svc_id).first()
                
                # ⭐ Консультация определяется ТОЛЬКО явным флагом is_consultation
                if service and service.is_consultation and consultation_service_id is None:
                    # Первая найденная консультация получает QR время
                    consultation_service_id = svc_id
                    existing_service_queue_times[svc_id] = (
                        queue_time.isoformat() if hasattr(queue_time, 'isoformat') else str(queue_time)
                    )
                    logger.info(
                        "[full_update_online_entry] ⭐ FIX 13: Консультация %s (ID=%d) получает QR время: %s",
                        service.name if service else "?",
                        svc_id,
                        queue_time,
                    )
                else:
                    # Все остальные услуги — дополнительные, получают текущее время
                    additional_service_ids.append(svc_id)
                    logger.info(
                        "[full_update_online_entry] ⭐ FIX 13: Услуга %s (ID=%d) — дополнительная, получит текущее время",
                        service.name if service else "?",
                        svc_id,
                    )
            
            # ⭐ new_service_ids содержит ТОЛЬКО дополнительные услуги (НЕ консультации)
            # Они будут созданы как Independent Queue Entries с текущим временем
            new_service_ids = additional_service_ids
            
            logger.info(
                "[full_update_online_entry] ⭐ FIX 13: Консультация ID=%s, Дополнительные услуги (new_service_ids): %s",
                consultation_service_id,
                new_service_ids,
            )
            
            # ⭐ FIX 13: Создаём Independent Queue Entries для дополнительных услуг
            # Эти услуги получают ТЕКУЩЕЕ время, а не QR время
            if new_service_ids:
                from datetime import timezone as tz
                from sqlalchemy import text
                from zoneinfo import ZoneInfo
                
                # ⭐ FIX: Use local Tashkent time, not UTC
                local_tz = ZoneInfo("Asia/Tashkent")
                current_queue_time = datetime.now(local_tz)
                default_queue_id = entry.queue_id
                
                logger.info(
                    "[full_update_online_entry] ⭐ FIX 13: Creating %d Independent Queue Entries with current time: %s",
                    len(new_service_ids),
                    current_queue_time,
                )
                
                for new_service_id in new_service_ids:
                    new_service = db.query(Service).filter(Service.id == new_service_id).first()
                    if not new_service:
                        continue
                    
                    # Определение целевой очереди по queue_tag услуги
                    target_queue_id = default_queue_id
                    if new_service.queue_tag:
                        candidate_queue = (
                            db.query(DailyQueue)
                            .filter(
                                DailyQueue.day == entry.queue.day,
                                DailyQueue.queue_tag == new_service.queue_tag,
                                DailyQueue.active == True
                            )
                            .first()
                        )
                        if candidate_queue:
                            target_queue_id = candidate_queue.id
                            logger.info(
                                "[full_update_online_entry] ⭐ FIX 13: Услуга %s → очередь %s (ID=%d)",
                                new_service.name, new_service.queue_tag, target_queue_id
                            )
                        else:
                            # ⭐ FIX: Auto-create DailyQueue if missing (NOT silent fallback)
                            logger.warning(
                                "[full_update_online_entry] ⚠️ DailyQueue for queue_tag=%s not found, creating...",
                                new_service.queue_tag
                            )
                            new_queue = queue_service.get_or_create_daily_queue(
                                db,
                                day=entry.queue.day,
                                specialist_id=entry.queue.specialist_id,
                                queue_tag=new_service.queue_tag,
                            )
                            target_queue_id = new_queue.id
                            logger.info(
                                "[full_update_online_entry] ✅ Created DailyQueue for %s (ID=%d)",
                                new_service.queue_tag, target_queue_id
                            )
                    # else: queue_tag is None → fallback to original queue is OK
                    
                    # Вычисляем номер в целевой очереди
                    next_number = db.execute(
                        text("SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid"),
                        {"qid": target_queue_id}
                    ).scalar()
                    
                    # Рассчитываем цену
                    service_item_data = next((s for s in request.services if s['service_id'] == new_service_id), None)
                    quantity = service_item_data.get('quantity', 1) if service_item_data else 1
                    item_price = new_service.price * quantity
                    
                    if new_service.is_consultation and request.discount_mode in ['repeat', 'benefit']:
                        item_price = 0
                    if request.all_free:
                        item_price = 0
                    
                    # Создаём Independent Queue Entry с ТЕКУЩИМ временем
                    # ⭐ session_id для группировки услуг пациента в одной очереди
                    session_id = get_or_create_session_id(
                        db, entry.patient_id, target_queue_id, entry.queue.day
                    )
                    
                    new_entry = OnlineQueueEntry(
                        queue_id=target_queue_id,
                        number=next_number,
                        queue_time=current_queue_time,  # ⭐ ТЕКУЩЕЕ время, НЕ QR время
                        patient_id=entry.patient_id,
                        patient_name=entry.patient_name,
                        phone=entry.phone,
                        birth_year=entry.birth_year,
                        address=entry.address,
                        status="waiting",
                        source=entry.source or "online",
                        discount_mode=request.discount_mode or entry.discount_mode,
                        visit_id=None,
                        session_id=session_id,  # ⭐ NEW: Session grouping
                        services=json.dumps([{
                            "service_id": new_service.id,
                            "name": new_service.name,
                            "code": new_service.code or "UNKNOWN",
                            "quantity": quantity,
                            "price": int(item_price),
                            "queue_time": current_queue_time.isoformat(),
                            "cancelled": False,
                        }], ensure_ascii=False),
                        service_codes=json.dumps([new_service.code or "UNKNOWN"], ensure_ascii=False),
                        total_amount=int(item_price),
                    )
                    db.add(new_entry)
                    db.flush()
                    
                    logger.info(
                        "[full_update_online_entry] ⭐ FIX 13: Created Independent Entry for %s (ID=%d), queue_id=%d, number=%d, time=%s",
                        new_service.name,
                        new_service_id,
                        target_queue_id,
                        next_number,
                        current_queue_time,
                    )
            
            # ⭐ FIX 2: Создаём Visit для QR-записи при первом заполнении
            if entry.patient_id and entry.visit_id is None and request.services:
                try:
                    from app.services.qr_queue_service import QRQueueService
                    
                    qr_service = QRQueueService(db)
                    
                    # Подготавливаем услуги для Visit
                    services_for_visit = []
                    for svc_item in request.services:
                        svc = db.query(Service).filter(Service.id == svc_item['service_id']).first()
                        if svc:
                            services_for_visit.append({
                                'service_id': svc.id,
                                'name': svc.name,
                                'code': svc.code,
                                'price': float(svc.price) if svc.price else 0,
                                'quantity': svc_item.get('quantity', 1),
                            })
                    
                    if services_for_visit:
                        visit = qr_service._create_visit_for_qr(
                            patient_id=entry.patient_id,
                            visit_date=date.today(),
                            services=services_for_visit,
                            visit_type=entry.visit_type or "paid",
                            discount_mode=request.discount_mode or "none",
                            notes=f"QR-регистрация: {entry.patient_name}",
                        )
                        entry.visit_id = visit.id
                        logger.info(
                            "[full_update_online_entry] ⭐ FIX 2: Создан Visit ID=%d для QR-записи ID=%d",
                            visit.id, entry.id,
                        )
                except Exception as visit_err:
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Не удалось создать Visit для QR-записи: %s",
                        str(visit_err),
                    )

        else:
            # Редактирование - обновляем текущую entry ТОЛЬКО со старыми услугами
            # Новые услуги будут добавлены как отдельные entries
            queue_time = entry.queue_time
            logger.info(
                "[full_update_online_entry] Редактирование существующей записи, сохраняем оригинальное queue_time: %s",
                queue_time,
            )
            
            # ⭐ PHASE 2.2 + FIX 13: Создаём ОТДЕЛЬНЫЕ entries для НОВЫХ/дополнительных услуг
            # Каждая новая услуга получает текущее queue_time и новый номер
            # ⭐ FIX 13: Это теперь работает и для First Fill (дополнительные услуги кроме консультации)
            if new_service_ids:
                from app.models.online_queue import DailyQueue, OnlineQueueEntry
                from datetime import timezone
                from zoneinfo import ZoneInfo
                
                logger.info(
                    "[full_update_online_entry] ⭐ Creating %d Independent Queue Entries for additional services",
                    len(new_service_ids),
                )
                
                # ⭐ FIX: Use local Tashkent time, not UTC
                local_tz = ZoneInfo("Asia/Tashkent")
                current_queue_time = datetime.now(local_tz)
                
                today = datetime.now(local_tz).date()
                
                # Мы будем вычислять next_number внутри цикла для каждой целевой очереди
                # Поэтому предварительный расчет убираем, но оставляем queue_id по умолчанию
                default_queue_id = entry.queue_id
                
                for new_service_id in new_service_ids:
                    new_service = db.query(Service).filter(Service.id == new_service_id).first()
                    if not new_service:
                        continue
                    
                    # ⭐ FIX: Определение целевой очереди (распределение по колонкам)
                    target_queue_id = default_queue_id
                    
                    # Если у услуги есть тег (например, 'echokg', 'lab'), ищем соответствующую очередь на сегодня
                    if new_service.queue_tag:
                         candidate_queue = (
                             db.query(DailyQueue)
                             .filter(
                                 DailyQueue.day == entry.queue.day, # Та же дата, что у оригинальной записи
                                 DailyQueue.queue_tag == new_service.queue_tag,
                                 DailyQueue.active == True
                             )
                             .first()
                         )
                         if candidate_queue:
                             target_queue_id = candidate_queue.id
                             logger.info(
                                 "[full_update_online_entry] 🔀 Услуга %s перемещена в очередь %s (ID=%d)",
                                 new_service.name, new_service.queue_tag, target_queue_id
                             )
                         else:
                             # ⭐ FIX: Auto-create DailyQueue if missing (NOT silent fallback)
                             logger.warning(
                                 "[full_update_online_entry] ⚠️ DailyQueue for queue_tag=%s not found, creating...",
                                 new_service.queue_tag
                             )
                             new_queue = queue_service.get_or_create_daily_queue(
                                 db,
                                 day=entry.queue.day,
                                 specialist_id=entry.queue.specialist_id,
                                 queue_tag=new_service.queue_tag,
                             )
                             target_queue_id = new_queue.id
                             logger.info(
                                 "[full_update_online_entry] ✅ Created DailyQueue for %s (ID=%d)",
                                 new_service.queue_tag, target_queue_id
                             )
                    # else: queue_tag is None → fallback to original queue is OK
                    
                    # ⭐ FIX: Вычисляем номер для КОНКРЕТНОЙ целевой очереди
                    # (теперь внутри цикла, так как очередь может меняться)
                    next_number = db.execute(
                        text("SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid"),
                        {"qid": target_queue_id}
                    ).scalar()
                    
                    # Рассчитываем цену
                    service_item_data = next((s for s in request.services if s['service_id'] == new_service_id), None)
                    quantity = service_item_data.get('quantity', 1) if service_item_data else 1
                    item_price = new_service.price * quantity
                    
                    if new_service.is_consultation and request.discount_mode in ['repeat', 'benefit']:
                        item_price = 0
                    if request.all_free:
                        item_price = 0
                    
                    # Создаём новую entry
                    # ⭐ session_id для группировки услуг пациента в одной очереди
                    session_id = get_or_create_session_id(
                        db, entry.patient_id, target_queue_id, entry.queue.day
                    )
                    
                    new_entry = OnlineQueueEntry(
                        queue_id=target_queue_id,
                        number=next_number,
                        queue_time=current_queue_time,
                        patient_id=entry.patient_id,
                        patient_name=entry.patient_name,
                        phone=entry.phone,
                        birth_year=entry.birth_year,
                        address=entry.address,
                        status="waiting",
                        source=entry.source or "online",
                        discount_mode=request.discount_mode or entry.discount_mode,
                        visit_id=None,  # ⭐ CRITICAL FIX: Новая услуга = новая independent entry
                        session_id=session_id,  # ⭐ NEW: Session grouping
                        services=json.dumps([{
                            "service_id": new_service.id,
                            "name": new_service.name,
                            "code": new_service.code or "UNKNOWN",
                            "quantity": quantity,
                            "price": int(item_price),
                            "queue_time": current_queue_time.isoformat(),
                            "cancelled": False,
                        }], ensure_ascii=False),
                        service_codes=json.dumps([new_service.code or "UNKNOWN"], ensure_ascii=False),
                        total_amount=int(item_price),
                    )
                    db.add(new_entry)
                    db.flush() # Важно сохранить, чтобы следующий next_number (в этой же очереди) был корректным
                    
                    logger.info(
                        "[full_update_online_entry] ⭐ PHASE 2.2: Создана новая entry для услуги %s (ID=%d), queue_id=%d, number=%d",
                        new_service.name,
                        new_service_id,
                        target_queue_id,
                        next_number,
                    )
                
                db.flush()  # Сохраняем новые entries

        # ⭐ Обрабатываем услуги для текущей entry
        # При первичной регистрации - добавляем все услуги
        # При редактировании - добавляем только СУЩЕСТВУЮЩИЕ услуги (новые уже созданы как отдельные entries)
        for service_item in request.services:
            service_id = service_item['service_id']

            # ⭐ FIX 13: Пропускаем услуги, которые уже созданы как Independent Queue Entries
            # Это включает:
            # 1. Редактирование: новые услуги (new_service_ids)
            # 2. First Fill: дополнительные услуги (не консультации, тоже в new_service_ids)
            if service_id in new_service_ids:
                logger.info(
                    "[full_update_online_entry] ⭐ Пропуск услуги %d — уже создана как Independent Queue Entry",
                    service_id,
                )
                continue

            service = db.query(Service).filter(Service.id == service_id).first()
            if service:
                # Рассчитываем стоимость с учетом скидок
                item_price = service.price * service_item.get('quantity', 1)

                logger.info(
                    "[full_update_online_entry] Услуга: %s, базовая цена: %s",
                    service.name,
                    item_price,
                )

                # Применяем скидки
                if service.is_consultation and request.discount_mode in [
                    'repeat',
                    'benefit',
                ]:
                    logger.info(
                        "[full_update_online_entry] Применена скидка на консультацию (%s)",
                        request.discount_mode,
                    )
                    item_price = 0  # Консультация бесплатна для повторных и льготных

                if request.all_free:
                    logger.info("[full_update_online_entry] Применена скидка all_free")
                    item_price = 0  # Всё бесплатно

                total_amount += item_price

                # ⭐ FIX PHASE 2: Для существующих услуг используем оригинальное queue_time
                if service_id in existing_service_queue_times:
                    service_queue_time = existing_service_queue_times[service_id]
                    logger.info(
                        "[full_update_online_entry] ⭐ Сохраняем оригинальное queue_time для %s: %s",
                        service.name,
                        service_queue_time,
                    )
                    
                    # ✅ НОВОЕ: Создаем полный объект услуги
                    service_obj = {
                        "service_id": service.id,
                        "name": service.name,
                        "code": service.code or "UNKNOWN",
                        "quantity": service_item.get('quantity', 1),
                        "price": int(item_price),
                        "queue_time": service_queue_time,  # ⭐ FIX: Используем правильное время
                        "cancelled": False,
                        "cancel_reason": None,
                        "cancelled_by": None,
                        "was_paid_before_cancel": False,
                    }
                    services_list.append(service_obj)
                    service_codes_list.append(service.code or "UNKNOWN")
                else:
                    # Новая услуга
                    if is_initial_registration or is_first_fill_qr:
                        # Первичная регистрация или первое заполнение QR — время регистрации
                        service_queue_time = (
                            queue_time.isoformat()
                            if hasattr(queue_time, 'isoformat')
                            else str(queue_time)
                        )
                        # Добавляем в services_list ТОЛЬКО для First Fill
                        service_obj = {
                            "service_id": service.id,
                            "name": service.name,
                            "code": service.code or "UNKNOWN",
                            "quantity": service_item.get('quantity', 1),
                            "price": int(item_price),
                            "queue_time": service_queue_time,  # ⭐ FIX: Используем правильное время
                            "cancelled": False,
                            "cancel_reason": None,
                            "cancelled_by": None,
                            "was_paid_before_cancel": False,
                        }
                        services_list.append(service_obj)
                        service_codes_list.append(service.code or "UNKNOWN")
                    else:
                        # ⭐ PHASE 2.2 FIX: Повторное редактирование — Пропускаем добавление в entry.services!
                        # Новые услуги будут созданы как отдельные entries.
                        logger.info(
                            "[full_update_online_entry] ⭐ Пропуск новой услуги %d (уже создана отдельная queue_entry)",
                            service_id
                        )
                        # НЕ добавляем в services_list

        entry.services = json.dumps(services_list, ensure_ascii=False)
        entry.service_codes = json.dumps(
            service_codes_list, ensure_ascii=False
        )  # Обратная совместимость
        entry.total_amount = int(
            total_amount
        )  # ✅ СОХРАНЯЕМ СУММУ (конвертируем в int)

        # ⭐ FIX: При первичной регистрации устанавливаем queue_time на entry
        # Это критически важно! Без этого entry.queue_time остается None,
        # и при следующем редактировании система думает, что это первичная регистрация,
        # перезаписывая queue_time существующих услуг.
        if is_initial_registration and entry.queue_time is None:
            entry.queue_time = queue_time
            logger.info(
                "[full_update_online_entry] ⭐ Установлен queue_time на entry: %s",
                queue_time,
            )

        logger.info(
            "[full_update_online_entry] Услуги обновлены (новый формат): %d услуг(и), Итоговая сумма: %s",
            len(services_list),
            total_amount,
        )

        # ✅ НОВОЕ: Если all_free = True, создаем или обновляем Visit для одобрения
        visit = None  # ✅ Инициализируем переменную visit для использования в проверках после коммита
        if request.all_free:
            from decimal import Decimal

            from app.models.online_queue import DailyQueue
            from app.models.visit import Visit, VisitService
            
            logger.info(
                "[full_update_online_entry] all_free=True, создаем/обновляем Visit для одобрения",
            )
            
            # Получаем данные из связанной очереди
            queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
            visit_date = queue.day if queue else date.today()
            doctor_id = queue.specialist_id if queue else None
            
            # ✅ ИСПРАВЛЕНО: Определяем department из queue_tag или по услугам
            department = None
            if queue and queue.queue_tag:
                # Маппинг queue_tag -> department
                queue_tag_to_dept = {
                    'cardiology': 'cardiology',
                    'cardio': 'cardiology',
                    'dermatology': 'dermatology',
                    'derma': 'dermatology',
                    'stomatology': 'stomatology',
                    'dentist': 'stomatology',
                    'lab': 'laboratory',
                    'laboratory': 'laboratory',
                    'ecg': 'cardiology',
                    'echokg': 'cardiology',
                }
                department = queue_tag_to_dept.get(queue.queue_tag.lower())
            
            # Если не определили по queue_tag, определяем по услугам
            if not department and request.services:
                for service_item in request.services:
                    service = (
                        db.query(Service)
                        .filter(Service.id == service_item['service_id'])
                        .first()
                    )
                    if service:
                        # Определяем department по category_code услуги
                        # ✅ SSOT: Используем service_mapping.get_service_category() вместо дублирующей логики
                        from app.services.service_mapping import get_service_category

                        service_code = (
                            get_service_code(service.id, db) or service.code or ''
                        )
                        category, _ = get_service_category(service_code)
                        if category and category.value == 'K':
                            department = 'cardiology'
                            break
                        elif category and category.value == 'D':
                            department = 'dermatology'
                            break
                        elif category and category.value == 'S':
                            department = 'stomatology'
                            break
                        elif category and category.value == 'L':
                            department = 'laboratory'
                            break
            
            # Если department все еще не определен, используем значение по умолчанию
            if not department:
                department = 'general'
            
            # Вычисляем оригинальную сумму (без скидки all_free)
            original_total_amount = Decimal('0')
            for service_item in request.services:
                service = (
                    db.query(Service)
                    .filter(Service.id == service_item['service_id'])
                    .first()
                )
                if service:
                    original_total_amount += (
                        service.price or Decimal('0')
                    ) * service_item.get('quantity', 1)
            
            # ✅ ИСПРАВЛЕНО: Для QR-пациентов без patient_id нужно создать Patient или пропустить создание Visit
            # Но Visit требует patient_id (nullable=False), поэтому создаем временного пациента если нужно
            patient_id_for_visit = entry.patient_id
            if not patient_id_for_visit:
                # ✅ ИСПРАВЛЕНО: Создаем временного пациента используя единую функцию нормализации
                logger.info(
                    "[full_update_online_entry] Создание временного пациента для QR-записи",
                )
                from app.crud.patient import normalize_patient_name

                patient_name = patient_data.get('patient_name', 'Неизвестный пациент')
                name_parts = normalize_patient_name(full_name=patient_name)
                
                # Гарантируем, что поля не пустые
                last_name = name_parts["last_name"] or 'Неизвестный'
                first_name = name_parts["first_name"] or 'Пациент'
                
                temp_patient = Patient(
                    last_name=last_name,
                    first_name=first_name,
                    middle_name=name_parts.get("middle_name"),
                    phone=patient_data.get('phone', ''),
                    birth_date=(
                        date(patient_data.get('birth_year', 1990), 1, 1)
                        if patient_data.get('birth_year')
                        else None
                    ),
                    address=patient_data.get('address', ''),
                )
                db.add(temp_patient)
                db.flush()
                patient_id_for_visit = temp_patient.id
                # ✅ Связываем OnlineQueueEntry с созданным пациентом
                entry.patient_id = patient_id_for_visit
                logger.info(
                    "[full_update_online_entry] Создан временный пациент ID=%d и связан с OnlineQueueEntry",
                    patient_id_for_visit,
                )
            
            # ✅ ИСПРАВЛЕНО: Улучшенный поиск существующего Visit для предотвращения дублирования
            visit = None
            
            # Приоритет 1: Ищем по entry.visit_id (если уже связан)
            if entry.visit_id:
                visit = db.query(Visit).filter(Visit.id == entry.visit_id).first()
                if visit:
                    logger.info(
                        "[full_update_online_entry] Найден Visit по entry.visit_id: %d",
                        visit.id,
                    )
            
            # Приоритет 2: Если не найден, ищем по patient_id + visit_date (без фильтра по discount_mode)
            # Это важно, так как при первом редактировании может быть создан Visit с другим discount_mode
            if not visit and patient_id_for_visit:
                visit = (
                    db.query(Visit)
                    .filter(
                    Visit.patient_id == patient_id_for_visit,
                        Visit.visit_date == visit_date,
                    )
                    .order_by(Visit.created_at.desc())
                    .first()
                )  # Берем самый последний
                if visit:
                    logger.info(
                        "[full_update_online_entry] Найден Visit по patient_id + visit_date: %d, discount_mode=%s",
                        visit.id,
                        visit.discount_mode,
                    )
            
            # Приоритет 3: Если все еще не найден, ищем по patient_id + visit_date + discount_mode="all_free"
            if not visit and patient_id_for_visit:
                visit = (
                    db.query(Visit)
                    .filter(
                    Visit.patient_id == patient_id_for_visit,
                    Visit.visit_date == visit_date,
                        Visit.discount_mode == "all_free",
                    )
                    .first()
                )
                if visit:
                    logger.info(
                        "[full_update_online_entry] Найден Visit по patient_id + visit_date + all_free: %d",
                        visit.id,
                    )
            
            if visit:
                # ✅ ИСПРАВЛЕНО: Обновляем существующий Visit (не создаем новый)
                logger.info(
                    "[full_update_online_entry] Обновление существующего Visit ID=%d",
                    visit.id,
                )
                visit.approval_status = (
                    "pending"  # Сбрасываем статус на pending при обновлении
                )
                visit.discount_mode = "all_free"  # Убеждаемся, что режим правильный
                visit.department = department  # Обновляем department
                visit.doctor_id = doctor_id  # Обновляем doctor_id

                # ⭐ ИСПРАВЛЕНИЕ #2: Проверяем есть ли оплаченный инвойс перед удалением услуг
                from app.models.payment_invoice import (
                    PaymentInvoice,
                    PaymentInvoiceVisit,
                )

                has_paid_invoice = (
                    db.query(PaymentInvoiceVisit)
                    .join(PaymentInvoice)
                    .filter(
                    PaymentInvoiceVisit.visit_id == visit.id,
                        PaymentInvoice.status == 'paid',
                    )
                    .first()
                )

                if has_paid_invoice:
                    # ⚠️ Визит УЖЕ оплачен - НЕ удаляем существующие услуги!
                    # Только добавляем новые услуги к уже существующим
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Visit %d имеет оплаченный инвойс - НЕ удаляем услуги, только добавляем новые",
                        visit.id,
                    )
                    deleted_count = 0
                else:
                    # ✅ Визит не оплачен - безопасно удалять и пересоздавать услуги
                    deleted_count = (
                        db.query(VisitService)
                        .filter(VisitService.visit_id == visit.id)
                        .delete()
                    )
                    db.flush()  # Коммитим удаление перед добавлением новых
                    logger.info(
                        "[full_update_online_entry] Удалено старых услуг: %d",
                        deleted_count,
                    )
                
                # ✅ Связываем OnlineQueueEntry с Visit (если еще не связан)
                if not entry.visit_id or entry.visit_id != visit.id:
                    entry.visit_id = visit.id
                    logger.info(
                        "[full_update_online_entry] Связан OnlineQueueEntry %d с Visit %d",
                        entry.id,
                        visit.id,
                    )
                
                # ✅ ИСПРАВЛЕНО: Синхронизируем discount_mode в OnlineQueueEntry с Visit
                if entry.discount_mode != "all_free":
                    entry.discount_mode = "all_free"
                    logger.info(
                        "[full_update_online_entry] Синхронизирован discount_mode в OnlineQueueEntry %d с Visit %d",
                        entry.id,
                        visit.id,
                    )
            else:
                # ✅ Создаем новый Visit только если действительно не найден существующий
                logger.info(
                    "[full_update_online_entry] Создание нового Visit для all_free (существующий не найден)",
                )
                visit = Visit(
                    patient_id=patient_id_for_visit,
                    doctor_id=doctor_id,
                    visit_date=visit_date,
                    visit_time=None,  # Время не сохраняется в OnlineQueueEntry
                    department=department,
                    discount_mode="all_free",
                    approval_status="pending",
                    notes=f"All Free заявка из онлайн записи #{entry.id}",
                    source="online",  # ✅ SSOT: QR-запись
                )
                db.add(visit)
                db.flush()  # Получаем ID визита
                
                # Связываем OnlineQueueEntry с Visit
                entry.visit_id = visit.id
                
                # ✅ ИСПРАВЛЕНО: Синхронизируем discount_mode в OnlineQueueEntry с Visit
                entry.discount_mode = "all_free"
                
                logger.info(
                    "[full_update_online_entry] Visit создан с ID=%d, department=%s, discount_mode синхронизирован",
                    visit.id,
                    department,
                )
            
            # ✅ ИСПРАВЛЕНО: Добавляем услуги к Visit (после удаления старых ИЛИ к существующим)
            added_services = []
            for service_item in request.services:
                service = (
                    db.query(Service)
                    .filter(Service.id == service_item['service_id'])
                    .first()
                )
                if service:
                    # ✅ Проверяем, нет ли уже такой услуги
                    existing_service = (
                        db.query(VisitService)
                        .filter(
                        VisitService.visit_id == visit.id,
                            VisitService.service_id == service.id,
                        )
                        .first()
                    )

                    if not existing_service:
                        # ⭐ ИСПРАВЛЕНИЕ #2: Добавляем новую услугу (работает и для оплаченных, и для неоплаченных)
                        # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                        service_code = get_service_code(service.id, db) or service.code
                        visit_service = VisitService(
                            visit_id=visit.id,
                            service_id=service.id,
                            code=service_code,
                            name=service.name,
                            qty=service_item.get('quantity', 1),
                            price=Decimal('0'),  # All Free - всё бесплатно
                            currency="UZS",
                        )
                        db.add(visit_service)
                        added_services.append(service.name)
                        if has_paid_invoice:
                            logger.info(
                                "[full_update_online_entry] ✅ Добавлена НОВАЯ услуга к оплаченному визиту: %s",
                                service.name,
                            )
                    else:
                        # Обновляем количество если услуга уже есть
                        existing_service.qty = service_item.get('quantity', 1)
                        added_services.append(f"{service.name} (обновлено)")
            
            db.flush()  # Коммитим добавление услуг
            logger.info(
                "[full_update_online_entry] Visit ID=%d обновлен с услугами для all_free: %s",
                visit.id,
                added_services,
            )

        # 5. Если есть patient_id, обновляем также запись Patient
        if entry.patient_id:
            patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
            if patient:
                logger.info(
                    "[full_update_online_entry] Обновление связанного пациента ID=%d",
                    patient.id,
                )

                if patient_data.get('patient_name'):
                    # Разбираем ФИО на компоненты
                    name_parts = patient_data['patient_name'].split()
                    if len(name_parts) >= 1:
                        patient.last_name = name_parts[0]
                    if len(name_parts) >= 2:
                        patient.first_name = name_parts[1]
                    if len(name_parts) >= 3:
                        patient.middle_name = name_parts[2]

                if patient_data.get('phone'):
                    patient.phone = patient_data['phone']

                if patient_data.get('birth_year'):
                    patient.birth_date = date(patient_data['birth_year'], 1, 1)

                if patient_data.get('address'):
                    patient.address = patient_data['address']

                logger.info(
                    "[full_update_online_entry] Пациент обновлен: %s %s",
                    patient.last_name,
                    patient.first_name,
                )

                # ✅ НОВОЕ: Синхронизируем все остальные queue_entries для этого пациента
                # Это предотвращает дубликаты в UI (одна запись с данными, другие без)
                other_entries = (
                    db.query(OnlineQueueEntry)
                    .filter(
                    OnlineQueueEntry.patient_id == entry.patient_id,
                        OnlineQueueEntry.id
                        != entry.id,  # Исключаем текущую запись (уже обновлена)
                    )
                    .all()
                )

                if other_entries:
                    logger.info(
                        "[full_update_online_entry] Синхронизация данных в %d других queue_entries для пациента %d",
                        len(other_entries),
                        entry.patient_id,
                    )
                    for other_entry in other_entries:
                        # ⭐ Queue Integrity Patch: Защита от перезаписи старого времени и номера
                        # Сохраняем оригинальные значения перед обновлением
                        original_queue_time = other_entry.queue_time
                        original_number = other_entry.number
                        
                        # Обновляем только те поля, которые были переданы
                        if patient_data.get('patient_name'):
                            other_entry.patient_name = patient_data['patient_name']
                        if patient_data.get('phone'):
                            other_entry.phone = patient_data['phone']
                        if patient_data.get('birth_year') is not None:
                            other_entry.birth_year = patient_data['birth_year']
                        if patient_data.get('address'):
                            other_entry.address = patient_data['address']
                        
                        # ⭐ ВАЖНО: Восстанавливаем queue_time и number (не перезаписываем!)
                        if original_queue_time:
                            other_entry.queue_time = original_queue_time
                        if original_number:
                            other_entry.number = original_number
                        logger.info(
                            "[full_update_online_entry] ✅ Защита: сохранены queue_time=%s, number=%s для entry_id=%d",
                            original_queue_time,
                            original_number,
                            other_entry.id,
                        )

                        # ⭐ ИСПРАВЛЕНО: НЕ копируем услуги между queue_entries
                        # Каждая queue_entry должна получать услуги только из своего Visit
                        # Синхронизация услуг между записями удалена во избежание дублирования

                        # Если у other_entry есть visit_id, синхронизируем услуги из Visit
                        if other_entry.visit_id:
                            from app.models.visit import VisitService

                            visit_services = (
                                db.query(VisitService)
                                .filter(VisitService.visit_id == other_entry.visit_id)
                                .all()
                            )

                            if visit_services:
                                # Формируем JSON со услугами из Visit
                                visit_services_list = []
                                visit_total = 0

                                for vs in visit_services:
                                    vs_price = float(vs.price) if vs.price else 0
                                    vs_qty = vs.qty or 1
                                    visit_total += vs_price * vs_qty

                                    service_obj = {
                                        'service_id': vs.service_id,
                                        'name': vs.name,
                                        'code': vs.code,
                                        'quantity': vs_qty,
                                        'price': int(vs_price),
                                        'queue_time': (
                                            other_entry.queue_time.isoformat()
                                            if other_entry.queue_time
                                            else None
                                        ),
                                        'cancelled': False,
                                        'cancel_reason': None,
                                        'cancelled_by': None,
                                        'was_paid_before_cancel': False,
                                    }
                                    visit_services_list.append(service_obj)

                                # Обновляем услуги из Visit (не копируем из других queue_entries!)
                                other_entry.services = json.dumps(
                                    visit_services_list, ensure_ascii=False
                                )
                                other_entry.total_amount = int(visit_total)
                                logger.info(
                                    "[full_update_online_entry] ✅ Синхронизировано %d услуг из Visit %d для entry %d",
                                    len(visit_services_list),
                                    other_entry.visit_id,
                                    other_entry.id,
                                )

                    logger.info(
                        "[full_update_online_entry] ✅ Синхронизировано %d записей",
                        len(other_entries),
                    )

        # ⭐ DISABLED: СОЗДАНИЕ НОВЫХ QUEUE_ENTRIES ДЛЯ НОВЫХ УСЛУГ
        # Этот код отключён, т.к. новые OnlineQueueEntry уже создаются в PHASE 2.2 (строки 1560-1635)
        # Оставлять два места создания приводит к дублированию записей!
        # Выполняется даже для QR-записей без visit_id
        # Условие: есть новые услуги И это редактирование (не первичная регистрация)
        if False and len(new_service_ids) > 0 and not is_initial_registration:  # ⭐ DISABLED
            logger.info(
                "[full_update_online_entry] ⭐ Создание %d новых queue_entries для новых услуг (visit_id=%s)",
                len(new_service_ids),
                entry.visit_id,
            )

            from datetime import datetime, timezone

            current_time = datetime.now(timezone.utc)

            # ⭐ FIX: Получаем услуги из request.services (работает и без visit_id)
            services_by_category = {}
            
            for service_item in request.services:
                service_id = service_item['service_id']
                
                # Только новые услуги
                if service_id not in new_service_ids:
                    continue
                    
                service = db.query(Service).filter(Service.id == service_id).first()
                if not service:
                    continue
                
                # Получаем код услуги (⭐ FIX: используем service_code, не code)
                service_code = service.service_code or service.code or ""

                # ⭐ SSOT FIX: Использовать РЕАЛЬНЫЙ queue_tag из Service модели
                # Вместо hardcoded маппинга категорий!
                queue_tag = service.queue_tag
                
                # Fallback на 'general' если queue_tag не определён
                if not queue_tag:
                    queue_tag = 'general'
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Service %s (id=%d) has no queue_tag, using 'general'",
                        service.name, service_id
                    )

                if queue_tag not in services_by_category:
                    services_by_category[queue_tag] = []
                services_by_category[queue_tag].append({
                    'service_id': service_id,
                    'service': service,
                    'quantity': service_item.get('quantity', 1),
                })
                
                # ⭐ DEBUG: Логируем присвоение queue_tag для каждой услуги
                logger.info(
                    "[full_update_online_entry] ⭐ Услуга %s (code=%s, id=%d) -> queue_tag=%s (from Service.queue_tag)",
                    service.name,
                    service_code,
                    service_id,
                    queue_tag,
                )

            logger.info(
                "[full_update_online_entry] Новые услуги распределены по категориям: %s",
                list(services_by_category.keys()),
            )

            # ⭐ FIX: Определяем queue_tag оригинальной entry
            original_queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
            original_queue_tag = original_queue.queue_tag if original_queue else None
            logger.info(
                "[full_update_online_entry] ⭐ Оригинальный queue_tag записи: %s",
                original_queue_tag,
            )

            # Создаем queue_entry для каждой категории с новыми услугами
            for queue_tag, services in services_by_category.items():
                # ⭐ FIX: Если новые услуги относятся к ТОЙ ЖЕ очереди, добавляем к существующей entry
                if queue_tag == original_queue_tag:
                    logger.info(
                        "[full_update_online_entry] ⭐ Услуги %s относятся к той же очереди (%s), добавляем к существующей entry %d",
                        [s['service']['name'] for s in services],
                        queue_tag,
                        entry.id,
                    )
                    
                    # Добавляем новые услуги к существующей entry (entry.services уже обновлён выше)
                    # Не создаём новую entry, не меняем queue_time
                    continue
                # Находим или создаем DailyQueue
                from datetime import date as date_module

                today = date_module.today()

                # Получаем specialist_id из текущей очереди
                current_queue = (
                    db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                )
                specialist_id_for_queue = (
                    current_queue.specialist_id if current_queue else None
                )

                daily_queue = (
                    db.query(DailyQueue)
                    .filter(DailyQueue.day == today, DailyQueue.queue_tag == queue_tag)
                    .first()
                )

                if not daily_queue:
                    # Создаем новую очередь
                    if not specialist_id_for_queue:
                        from app.models.user import User

                        fallback_user = (
                            db.query(User).filter(User.is_active == True).first()
                        )
                        specialist_id_for_queue = (
                            fallback_user.id if fallback_user else 1
                        )

                    daily_queue = DailyQueue(
                        day=today,
                        specialist_id=specialist_id_for_queue,
                        queue_tag=queue_tag,
                        active=True,
                    )
                    db.add(daily_queue)
                    db.flush()
                    logger.info(
                        "[full_update_online_entry] Создана новая DailyQueue для %s",
                        queue_tag,
                    )

                next_number = queue_service.get_next_queue_number(
                    db,
                    daily_queue=daily_queue,
                    queue_tag=queue_tag,
                )

                # Формируем JSON услуг для новой entry
                services_list_new = []
                total_amount_new = 0

                for svc_data in services:
                    # ⭐ FIX: Используем новую структуру данных
                    service = svc_data['service']
                    svc_quantity = svc_data.get('quantity', 1)
                    svc_price = float(service.price) if service.price else 0
                    total_amount_new += svc_price * svc_quantity

                    service_obj = {
                        'service_id': svc_data['service_id'],
                        'name': service.name,
                        'code': service.service_code or service.code,
                        'quantity': svc_quantity,
                        'price': int(svc_price),
                        'queue_time': current_time.isoformat(),  # ⭐ ТЕКУЩЕЕ ВРЕМЯ
                        'cancelled': False,
                        'cancel_reason': None,
                        'cancelled_by': None,
                        'was_paid_before_cancel': False,
                    }
                    services_list_new.append(service_obj)

                # ⭐ FIX 4: Не создаём entry если список услуг пустой
                if not services_list_new:
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Пропуск создания entry для %s — нет услуг (services_list_new пустой)",
                        queue_tag
                    )
                    continue

                # Создаем новую OnlineQueueEntry
                # ⭐ session_id для группировки услуг пациента в одной очереди
                session_id = get_or_create_session_id(
                    db, entry.patient_id, daily_queue.id, daily_queue.day
                ) if entry.patient_id else f"entry_{entry.id}"
                
                new_queue_entry = OnlineQueueEntry(
                    queue_id=daily_queue.id,
                    number=next_number,
                    patient_id=entry.patient_id,
                    patient_name=entry.patient_name,
                    phone=entry.phone,
                    birth_year=entry.birth_year,
                    address=entry.address,
                    visit_id=entry.visit_id,  # ⭐ Сохраняем visit_id (может быть None для QR)
                    session_id=session_id,  # ⭐ NEW: Session grouping
                    source=entry.source or "desk",
                    queue_time=current_time,  # ⭐ ТЕКУЩЕЕ ВРЕМЯ
                    services=json.dumps(services_list_new, ensure_ascii=False),
                    service_codes=json.dumps(
                        [s['code'] for s in services_list_new], ensure_ascii=False
                    ),
                    total_amount=int(total_amount_new),
                    visit_type=entry.visit_type,
                    discount_mode=entry.discount_mode,
                )

                db.add(new_queue_entry)
                db.flush()

                service_names = [svc_data['service'].name for svc_data in services]
                logger.info(
                    "[full_update_online_entry] ⭐ Создана queue_entry #%d для %s: %s, queue_time=%s",
                    next_number,
                    queue_tag,
                    service_names,
                    current_time,
                )


            db.flush()  # Сохраняем новые entries
            logger.info(
                "[full_update_online_entry] ✅ Создано %d новых queue_entries",
                len(services_by_category),
            )

        # ✅ ИСПРАВЛЕНО: Коммитим все изменения одной транзакцией
        try:
            db.commit()
            db.refresh(entry)
            
            # ✅ Проверяем, что Visit правильно связан с OnlineQueueEntry (если all_free)
            if request.all_free and visit:
                db.refresh(visit)
                if entry.visit_id != visit.id:
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Предупреждение: entry.visit_id (%s) != visit.id (%d), исправляем...",
                        entry.visit_id,
                        visit.id,
                    )
                    entry.visit_id = visit.id
                    db.commit()
                    db.refresh(entry)
            
            # ✅ Проверяем количество VisitService для отладки (если all_free)
            if request.all_free and visit:
                visit_services_count = (
                    db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .count()
                )
                logger.info(
                    "[full_update_online_entry] ✅ Финальная проверка: Visit %d имеет %d услуг (ожидалось %d)",
                    visit.id,
                    visit_services_count,
                    len(request.services),
                )
                if visit_services_count != len(request.services):
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Предупреждение: Количество услуг не совпадает! Возможно дубликаты.",
                    )
            
            logger.info("[full_update_online_entry] Запись успешно обновлена")

            return {
                "success": True,
                "message": "Запись успешно обновлена",
                "entry": {
                    "id": entry.id,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "birth_year": entry.birth_year,
                    "address": entry.address,
                    "services": services_list,
                    "service_codes": service_codes_list,
                    "total_amount": total_amount,
                    "discount_mode": entry.discount_mode,
                    "visit_type": entry.visit_type,
                    "all_free": request.all_free,
                    "visit_id": entry.visit_id if request.all_free else None,
                },
            }
        except Exception as commit_error:
            db.rollback()
            import traceback

            logger.error(
                "[full_update_online_entry] ❌ Ошибка при коммите: %s: %s",
                type(commit_error).__name__,
                str(commit_error),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка сохранения изменений: {str(commit_error)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(
            "[full_update_online_entry] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении записи: {str(e)}",
        )


@router.post(
    "/online-entry/{entry_id}/cancel-service", response_model=CancelServiceResponse
)
def cancel_service_in_entry(
    entry_id: int,
    request: CancelServiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Отменяет услугу в записи очереди с сохранением аудита

    ВАЖНО:
    - Услуга помечается как отмененная (cancelled=True), но НЕ удаляется
    - Сохраняется причина отмены и информация о том, кто отменил
    - Пересчитывается итоговая сумма
    - Если услуга была оплачена, сохраняется флаг was_paid_before_cancel
    - Синхронизируется со всеми другими queue_entries этого пациента

    Доступно: администраторам, регистраторам и врачам
    """
    import json

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    logger.info(
        "[cancel_service] Отмена услуги service_id=%d в entry_id=%d, Причина: %s, Была оплачена: %s, Отменяет: %s (ID: %d)",
        request.service_id,
        entry_id,
        request.cancel_reason,
        request.was_paid,
        current_user.username,
        current_user.id,
    )

    try:
        # Получаем запись
        entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        # Парсим текущие услуги
        services_list = json.loads(entry.services) if entry.services else []

        # Проверяем, что услуги в новом формате (с service_id)
        if not services_list or not isinstance(services_list[0], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Услуги в старом формате. Необходимо выполнить миграцию данных.",
            )

        # Ищем услугу для отмены
        service_found = False
        cancelled_service_obj = None
        new_total = 0

        for service_obj in services_list:
            if service_obj.get(
                'service_id'
            ) == request.service_id and not service_obj.get('cancelled', False):
                # Отменяем услугу
                service_obj['cancelled'] = True
                service_obj['cancel_reason'] = request.cancel_reason
                service_obj['cancelled_by'] = current_user.id
                service_obj['was_paid_before_cancel'] = request.was_paid
                service_found = True
                cancelled_service_obj = service_obj.copy()
                logger.info(
                    "[cancel_service] Услуга '%s' отменена",
                    service_obj.get('name'),
                )

            # Пересчитываем сумму (только не отмененные услуги)
            if not service_obj.get('cancelled', False):
                new_total += service_obj.get('price', 0) * service_obj.get(
                    'quantity', 1
                )

        if not service_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Услуга с ID {request.service_id} не найдена или уже отменена",
            )

        # Обновляем services и total_amount
        entry.services = json.dumps(services_list, ensure_ascii=False)
        entry.total_amount = new_total

        logger.info(
            "[cancel_service] Новая сумма: %s",
            new_total,
        )

        # Синхронизируем с другими queue_entries этого пациента
        if entry.patient_id:
            other_entries = (
                db.query(OnlineQueueEntry)
                .filter(
                OnlineQueueEntry.patient_id == entry.patient_id,
                    OnlineQueueEntry.id != entry.id,
                )
                .all()
            )

            if other_entries:
                logger.info(
                    "[cancel_service] Синхронизация отмены с %d другими записями",
                    len(other_entries),
                )

                for other_entry in other_entries:
                    other_services = (
                        json.loads(other_entry.services) if other_entry.services else []
                    )

                    # Проверяем формат
                    if other_services and isinstance(other_services[0], dict):
                        other_total = 0
                        updated = False

                        for other_service_obj in other_services:
                            # Отменяем ту же услугу
                            if other_service_obj.get(
                                'service_id'
                            ) == request.service_id and not other_service_obj.get(
                                'cancelled', False
                            ):
                                other_service_obj['cancelled'] = True
                                other_service_obj['cancel_reason'] = (
                                    request.cancel_reason
                                )
                                other_service_obj['cancelled_by'] = current_user.id
                                other_service_obj['was_paid_before_cancel'] = (
                                    request.was_paid
                                )
                                updated = True

                            # Пересчитываем сумму
                            if not other_service_obj.get('cancelled', False):
                                other_total += other_service_obj.get(
                                    'price', 0
                                ) * other_service_obj.get('quantity', 1)

                        if updated:
                            other_entry.services = json.dumps(
                                other_services, ensure_ascii=False
                            )
                            other_entry.total_amount = other_total
                            logger.info(
                                "[cancel_service] Синхронизирована запись %d, новая сумма: %s",
                                other_entry.id,
                                other_total,
                            )

        # Коммитим изменения
        db.commit()
        db.refresh(entry)

        logger.info("[cancel_service] ✅ Услуга успешно отменена")

        return {
            "success": True,
            "message": f"Услуга '{cancelled_service_obj.get('name')}' успешно отменена",
            "cancelled_service": cancelled_service_obj,
            "new_total_amount": new_total,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback

        logger.error(
            "[cancel_service] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при отмене услуги: {str(e)}",
        )
