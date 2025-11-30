"""
API эндпоинты для QR очередей

✅ ACTIVE: Этот модуль содержит активные, рекомендуемые endpoints для работы с очередями.

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
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles

logger = logging.getLogger(__name__)
from app.models.user import User
# NOTE: Doctor импортируется внутри функций для избежания circular dependency
from app.services.qr_queue_service import QRQueueService
from app.services.queue_service import (
    queue_service,
    QueueValidationError,
    QueueNotFoundError,
    QueueConflictError,
)
from app.services.service_mapping import get_service_code

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class QRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию QR токена"""
    specialist_id: int = Field(..., description="ID специалиста")
    department: str = Field(..., description="Отделение")
    expires_hours: int = Field(default=24, ge=1, le=168, description="Время жизни токена в часах")
    target_date: Optional[str] = Field(None, description="Целевая дата для очереди (YYYY-MM-DD)")
    visit_type: str = Field(default="paid", description="Тип визита: paid, repeat, benefit")


class ClinicQRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию общего QR токена клиники"""
    target_date: Optional[str] = Field(None, description="Целевая дата для очереди (YYYY-MM-DD)")
    expires_hours: int = Field(default=24, ge=1, le=168, description="Время жизни токена в часах")


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
    patient_name: str = Field(..., min_length=2, max_length=200, description="ФИО пациента")
    phone: str = Field(..., min_length=5, max_length=20, description="Номер телефона")
    telegram_id: Optional[int] = Field(None, description="Telegram ID")
    specialist_ids: Optional[List[int]] = Field(None, description="Список ID специалистов (для общего QR)")


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
    cancel_reason: str = Field(..., min_length=5, max_length=500, description="Причина отмены (минимум 5 символов)")
    was_paid: bool = Field(default=False, description="Была ли услуга оплачена до отмены")


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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except QueueNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        base_url = qr_service._get_frontend_url()
        qr_url = f"{base_url}/queue/join?token={token_value}"
        qr_code_base64 = qr_service._generate_qr_code(qr_url)

        return QRTokenResponse(
            token=token_value,
            qr_url=qr_url,
            qr_code_base64=qr_code_base64,
            specialist_id=request.specialist_id,
            department=request.department,
            expires_at=token_meta.get("expires_at").isoformat() if token_meta.get("expires_at") else None,
            active=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR токена: {str(e)}"
        )


@router.post("/admin/qr-tokens/generate-clinic")
def generate_clinic_qr_token(
    request: ClinicQRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
            "expires_at": token_data.get("expires_at").isoformat() if token_data.get("expires_at") else None,
            "active": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации общего QR токена: {str(e)}"
        )


@router.get("/available-specialists")
def get_available_specialists(
    db: Session = Depends(get_db)
):
    """
    Получает список доступных специалистов для QR-регистрации (публичный эндпоинт)
    Используется для динамического отображения списка специалистов в интерфейсе QR-регистрации
    """
    try:
        # Импортируем локально для избежания circular dependency
        from app.models.clinic import Doctor
        from sqlalchemy.orm import joinedload
        
        # Получаем всех активных врачей с eager loading user relationship
        doctors = db.query(Doctor).filter(
            Doctor.active == True
        ).options(joinedload(Doctor.user)).all()
        
        # Маппинг специальностей на русские названия и иконки
        specialty_mapping = {
            'cardiology': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'cardio': {'name': 'Кардиолог', 'icon': '❤️', 'color': '#FF3B30'},
            'dermatology': {'name': 'Дерматолог-косметолог', 'icon': '✨', 'color': '#FF9500'},
            'derma': {'name': 'Дерматолог-косметолог', 'icon': '✨', 'color': '#FF9500'},
            'dentistry': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'dentist': {'name': 'Стоматолог', 'icon': '🦷', 'color': '#007AFF'},
            'laboratory': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'},
            'lab': {'name': 'Лаборатория', 'icon': '🔬', 'color': '#34C759'}
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
                    'color': '#8E8E93'
                }
            
            # Берем первого врача из каждой специальности
            if normalized_specialty not in specialists_by_specialty:
                specialists_by_specialty[normalized_specialty] = {
                    'id': doctor.id,
                    'specialty': normalized_specialty,
                    'specialty_display': specialty_mapping[normalized_specialty]['name'],
                    'icon': specialty_mapping[normalized_specialty]['icon'],
                    'color': specialty_mapping[normalized_specialty]['color'],
                    'doctor_name': doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                    'cabinet': doctor.cabinet
                }
        
        # Преобразуем в список
        specialists_list = list(specialists_by_specialty.values())
        
        # Сортируем по порядку: кардиолог, дерматолог, стоматолог, лаборатория
        sort_order = ['cardiology', 'cardio', 'dermatology', 'derma', 'dentistry', 'dentist', 'laboratory', 'lab']
        specialists_list.sort(key=lambda x: (
            sort_order.index(x['specialty']) if x['specialty'] in sort_order else 999
        ))
        
        return {
            'success': True,
            'specialists': specialists_list,
            'total': len(specialists_list)
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
            detail=f"Ошибка получения списка специалистов: {str(e)}"
        )


@router.get("/qr-tokens/{token}/info", response_model=QRTokenInfoResponse)
def get_qr_token_info(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Получает информацию о QR токене (публичный эндпоинт)
    """
    try:
        service = QRQueueService(db)

        token_info = service.get_qr_token_info(token)

        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR токен не найден или истек"
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
            detail=f"Ошибка получения информации о токене: {str(e)}"
        )


@router.post("/join/start", response_model=JoinSessionStartResponse)
def start_join_session(
    request: JoinSessionStartRequest,
    http_request: Request,
    db: Session = Depends(get_db)
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
            user_agent=http_request.headers.get("User-Agent")
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        error_msg = f"Ошибка начала сессии: {str(e)}"
        logger.error(
            "[start_join_session] Неожиданная ошибка: %s",
            error_msg,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/join/complete")
def complete_join_session(
    request: JoinSessionCompleteRequest,
    db: Session = Depends(get_db)
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
                telegram_id=request.telegram_id
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.get("/status/{specialist_id}", response_model=QueueStatusResponse)
def get_queue_status(
    specialist_id: int,
    target_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
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
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
    
    result = service.get_queue_status(specialist_id, parsed_date)
    
    return QueueStatusResponse(**result)


@router.post("/{specialist_id}/call-next", response_model=CallNextPatientResponse)
def call_next_patient(
    specialist_id: int,
    target_date: Optional[str] = Query(None, description="Дата очереди (YYYY-MM-DD), по умолчанию сегодня"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
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
        
        result = service.call_next_patient(specialist_id, current_user.id, queue_date)
        
        return CallNextPatientResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента: {str(e)}"
        )


@router.get("/admin/qr-tokens/active", response_model=List[ActiveQRTokenResponse])
def get_active_qr_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
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
            detail="QR токен не найден или вы не являетесь его создателем"
        )
    
    return {"message": "QR токен успешно деактивирован"}


# ===================== СТАТИСТИКА И АНАЛИТИКА =====================

@router.get("/admin/queue-analytics/{specialist_id}")
def get_queue_analytics(
    specialist_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
                detail="Неверный формат start_date. Используйте YYYY-MM-DD"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат end_date. Используйте YYYY-MM-DD"
            )
    
    # Если даты не указаны, берем последние 30 дней
    if not start_dt:
        start_dt = date.today() - timedelta(days=30)
    if not end_dt:
        end_dt = date.today()
    
    from app.models.online_queue import QueueStatistics, DailyQueue
    
    # Получаем статистику
    stats = db.query(QueueStatistics).join(DailyQueue).filter(
        DailyQueue.specialist_id == specialist_id,
        QueueStatistics.date >= start_dt,
        QueueStatistics.date <= end_dt
    ).all()
    
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
        "period": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat()
        },
        "totals": {
            "online_joins": total_online_joins,
            "desk_registrations": total_desk_registrations,
            "telegram_joins": total_telegram_joins,
            "confirmation_joins": total_confirmation_joins,
            "total_served": total_served,
            "total_no_show": total_no_show
        },
        "metrics": {
            "average_wait_time": avg_wait_time,
            "no_show_rate": (total_no_show / (total_served + total_no_show)) * 100 if (total_served + total_no_show) > 0 else 0
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
                "max_queue_length": stat.max_queue_length
            }
            for stat in stats
        ]
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"))
):
    """
    Обновляет данные пациента в онлайн записи
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.patient import Patient

        # Находим запись
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
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
                "phone": entry.phone
            }
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
            detail=f"Ошибка обновления данных: {str(e)}"
        )


# ===================== ПОЛНОЕ ОБНОВЛЕНИЕ ОНЛАЙН ЗАПИСИ (ДЛЯ МАСТЕРА) =====================

class FullUpdateOnlineEntryRequest(BaseModel):
    """Запрос на полное обновление онлайн записи через мастер регистрации"""
    patient_data: dict  # {patient_name, phone, birth_year, address}
    visit_type: str  # paid/repeat/benefit
    discount_mode: str  # none/repeat/benefit
    services: List[dict]  # [{service_id, quantity}]
    all_free: bool = False


@router.put("/online-entry/{entry_id}/full-update")
def full_update_online_entry(
    entry_id: int,
    request: FullUpdateOnlineEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Полное обновление онлайн записи через мастер регистрации:
    - Данные пациента (ФИО, телефон, год рождения, адрес)
    - Тип визита и режим скидки
    - Список услуг
    - Расчет итоговой суммы с учетом скидок
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.patient import Patient
        from app.models.service import Service
        from datetime import date
        import json

        logger.info(
            "[full_update_online_entry] Обновление записи ID=%d, Данные пациента: %s, Тип визита: %s, Услуги: %s",
            entry_id,
            request.patient_data,
            request.visit_type,
            request.services,
        )

        # 1. Находим запись
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
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

        # ⭐ Определяем существующие услуги для дальнейшего сравнения
        from datetime import datetime, timezone

        existing_service_ids = set()
        if entry.services:
            try:
                existing_services = json.loads(entry.services)
                existing_service_ids = {svc.get('service_id') for svc in existing_services if svc.get('service_id')}
                logger.info(
                    "[full_update_online_entry] Существующие услуги: %s",
                    existing_service_ids,
                )
            except:
                pass

        # Определяем новые услуги (которые не были в entry.services)
        new_service_ids = []
        for service_item in request.services:
            if service_item['service_id'] not in existing_service_ids:
                new_service_ids.append(service_item['service_id'])

        logger.info(
            "[full_update_online_entry] Новые услуги для добавления: %s",
            new_service_ids,
        )

        # Определяем: это первичная регистрация или редактирование?
        is_initial_registration = entry.queue_time is None or not entry.services

        if is_initial_registration:
            # Первичная регистрация - обновляем текущую entry со всеми услугами
            queue_time = entry.queue_time or datetime.now(timezone.utc)
            logger.info(
                "[full_update_online_entry] Первичная регистрация, queue_time: %s",
                queue_time,
            )
        else:
            # Редактирование - обновляем текущую entry ТОЛЬКО со старыми услугами
            # Новые услуги будут добавлены как отдельные entries ПОСЛЕ обновления Visit
            queue_time = entry.queue_time
            logger.info(
                "[full_update_online_entry] Редактирование существующей записи, сохраняем оригинальное queue_time: %s",
                queue_time,
            )

        # ⭐ Обрабатываем услуги для текущей entry
        # При первичной регистрации - добавляем все услуги
        # При редактировании - добавляем только СУЩЕСТВУЮЩИЕ услуги (новые уже созданы как отдельные entries)
        for service_item in request.services:
            service_id = service_item['service_id']

            # Если это редактирование и услуга новая - пропускаем (она уже добавлена как отдельная entry)
            if not is_initial_registration and service_id in new_service_ids:
                logger.info(
                    "[full_update_online_entry] Пропуск новой услуги %d (уже создана отдельная queue_entry)",
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
                if service.is_consultation and request.discount_mode in ['repeat', 'benefit']:
                    logger.info(
                        "[full_update_online_entry] Применена скидка на консультацию (%s)",
                        request.discount_mode,
                    )
                    item_price = 0  # Консультация бесплатна для повторных и льготных

                if request.all_free:
                    logger.info("[full_update_online_entry] Применена скидка all_free")
                    item_price = 0  # Всё бесплатно

                total_amount += item_price

                # ✅ НОВОЕ: Создаем полный объект услуги
                service_obj = {
                    "service_id": service.id,
                    "name": service.name,
                    "code": service.code or "UNKNOWN",
                    "quantity": service_item.get('quantity', 1),
                    "price": int(item_price),
                    "queue_time": queue_time.isoformat() if hasattr(queue_time, 'isoformat') else str(queue_time),
                    "cancelled": False,
                    "cancel_reason": None,
                    "cancelled_by": None,
                    "was_paid_before_cancel": False
                }
                services_list.append(service_obj)
                service_codes_list.append(service.code or "UNKNOWN")

        entry.services = json.dumps(services_list, ensure_ascii=False)
        entry.service_codes = json.dumps(service_codes_list, ensure_ascii=False)  # Обратная совместимость
        entry.total_amount = int(total_amount)  # ✅ СОХРАНЯЕМ СУММУ (конвертируем в int)

        logger.info(
            "[full_update_online_entry] Услуги обновлены (новый формат): %d услуг(и), Итоговая сумма: %s",
            len(services_list),
            total_amount,
        )

        # ✅ НОВОЕ: Если all_free = True, создаем или обновляем Visit для одобрения
        visit = None  # ✅ Инициализируем переменную visit для использования в проверках после коммита
        if request.all_free:
            from app.models.visit import Visit, VisitService
            from decimal import Decimal
            from app.models.online_queue import DailyQueue
            
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
                    'echokg': 'cardiology'
                }
                department = queue_tag_to_dept.get(queue.queue_tag.lower())
            
            # Если не определили по queue_tag, определяем по услугам
            if not department and request.services:
                for service_item in request.services:
                    service = db.query(Service).filter(Service.id == service_item['service_id']).first()
                    if service:
                        # Определяем department по category_code услуги
                        # ✅ SSOT: Используем service_mapping.get_service_category() вместо дублирующей логики
                        from app.services.service_mapping import get_service_category
                        service_code = get_service_code(service.id, db) or service.code or ''
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
                service = db.query(Service).filter(Service.id == service_item['service_id']).first()
                if service:
                    original_total_amount += (service.price or Decimal('0')) * service_item.get('quantity', 1)
            
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
                    birth_date=date(patient_data.get('birth_year', 1990), 1, 1) if patient_data.get('birth_year') else None,
                    address=patient_data.get('address', '')
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
                visit = db.query(Visit).filter(
                    Visit.patient_id == patient_id_for_visit,
                    Visit.visit_date == visit_date
                ).order_by(Visit.created_at.desc()).first()  # Берем самый последний
                if visit:
                    logger.info(
                        "[full_update_online_entry] Найден Visit по patient_id + visit_date: %d, discount_mode=%s",
                        visit.id,
                        visit.discount_mode,
                    )
            
            # Приоритет 3: Если все еще не найден, ищем по patient_id + visit_date + discount_mode="all_free"
            if not visit and patient_id_for_visit:
                visit = db.query(Visit).filter(
                    Visit.patient_id == patient_id_for_visit,
                    Visit.visit_date == visit_date,
                    Visit.discount_mode == "all_free"
                ).first()
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
                visit.approval_status = "pending"  # Сбрасываем статус на pending при обновлении
                visit.discount_mode = "all_free"  # Убеждаемся, что режим правильный
                visit.department = department  # Обновляем department
                visit.doctor_id = doctor_id  # Обновляем doctor_id

                # ⭐ ИСПРАВЛЕНИЕ #2: Проверяем есть ли оплаченный инвойс перед удалением услуг
                from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit

                has_paid_invoice = db.query(PaymentInvoiceVisit).join(
                    PaymentInvoice
                ).filter(
                    PaymentInvoiceVisit.visit_id == visit.id,
                    PaymentInvoice.status == 'paid'
                ).first()

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
                    deleted_count = db.query(VisitService).filter(VisitService.visit_id == visit.id).delete()
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
                    notes=f"All Free заявка из онлайн записи #{entry.id}"
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
                service = db.query(Service).filter(Service.id == service_item['service_id']).first()
                if service:
                    # ✅ Проверяем, нет ли уже такой услуги
                    existing_service = db.query(VisitService).filter(
                        VisitService.visit_id == visit.id,
                        VisitService.service_id == service.id
                    ).first()

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
                            currency="UZS"
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
                other_entries = db.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.patient_id == entry.patient_id,
                    OnlineQueueEntry.id != entry.id  # Исключаем текущую запись (уже обновлена)
                ).all()

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
                            visit_services = db.query(VisitService).filter(
                                VisitService.visit_id == other_entry.visit_id
                            ).all()

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
                                        'queue_time': other_entry.queue_time.isoformat() if other_entry.queue_time else None,
                                        'cancelled': False,
                                        'cancel_reason': None,
                                        'cancelled_by': None,
                                        'was_paid_before_cancel': False
                                    }
                                    visit_services_list.append(service_obj)

                                # Обновляем услуги из Visit (не копируем из других queue_entries!)
                                other_entry.services = json.dumps(visit_services_list, ensure_ascii=False)
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

        # ⭐ FIX #4 (ПЕРЕРАБОТАН): СОЗДАНИЕ НОВЫХ QUEUE_ENTRIES ДЛЯ НОВЫХ УСЛУГ
        # Выполняется ПОСЛЕ обновления Visit, чтобы получить актуальные услуги
        if entry.visit_id and len(new_service_ids) > 0:
            logger.info(
                "[full_update_online_entry] ⭐ Создание %d новых queue_entries для новых услуг",
                len(new_service_ids),
            )

            from datetime import datetime, timezone

            current_time = datetime.now(timezone.utc)

            # Получаем все услуги из обновленного Visit
            visit_services_all = db.query(VisitService).filter(
                VisitService.visit_id == entry.visit_id
            ).all()

            # Группируем услуги по категориям
            services_by_category = {}
            for vs in visit_services_all:
                service_code = vs.code or ""
                category = service_code[0] if service_code else "G"

                # Маппинг категории -> queue_tag
                category_to_queue_tag = {
                    'K': 'cardiology',
                    'D': 'dermatology',
                    'S': 'stomatology',
                    'L': 'laboratory',
                    'P': 'procedures',
                    'E': 'ecg',  # ⭐ ECG отдельная очередь
                    'G': 'general'
                }
                queue_tag = category_to_queue_tag.get(category, 'general')

                # Проверяем: это новая услуга?
                is_new_service = vs.service_id in new_service_ids

                if is_new_service:
                    if queue_tag not in services_by_category:
                        services_by_category[queue_tag] = []
                    services_by_category[queue_tag].append(vs)

            logger.info(
                "[full_update_online_entry] Новые услуги распределены по категориям: %s",
                list(services_by_category.keys()),
            )

            # Создаем queue_entry для каждой категории с новыми услугами
            for queue_tag, services in services_by_category.items():
                # Находим или создаем DailyQueue
                from datetime import date as date_module
                today = date_module.today()

                # Получаем specialist_id из текущей очереди
                current_queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                specialist_id_for_queue = current_queue.specialist_id if current_queue else None

                daily_queue = db.query(DailyQueue).filter(
                    DailyQueue.day == today,
                    DailyQueue.queue_tag == queue_tag
                ).first()

                if not daily_queue:
                    # Создаем новую очередь
                    if not specialist_id_for_queue:
                        from app.models.user import User
                        fallback_user = db.query(User).filter(User.is_active == True).first()
                        specialist_id_for_queue = fallback_user.id if fallback_user else 1

                    daily_queue = DailyQueue(
                        day=today,
                        specialist_id=specialist_id_for_queue,
                        queue_tag=queue_tag,
                        active=True
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

                for vs in services:
                    vs_price = float(vs.price) if vs.price else 0
                    vs_qty = vs.qty or 1
                    total_amount_new += vs_price * vs_qty

                    service_obj = {
                        'service_id': vs.service_id,
                        'name': vs.name,
                        'code': vs.code,
                        'quantity': vs_qty,
                        'price': int(vs_price),
                        'queue_time': current_time.isoformat(),  # ⭐ ТЕКУЩЕЕ ВРЕМЯ
                        'cancelled': False,
                        'cancel_reason': None,
                        'cancelled_by': None,
                        'was_paid_before_cancel': False
                    }
                    services_list_new.append(service_obj)

                # Создаем новую OnlineQueueEntry
                new_queue_entry = OnlineQueueEntry(
                    queue_id=daily_queue.id,
                    number=next_number,
                    patient_id=entry.patient_id,
                    patient_name=entry.patient_name,
                    phone=entry.phone,
                    birth_year=entry.birth_year,
                    address=entry.address,
                    visit_id=entry.visit_id,  # ⭐ Сохраняем visit_id
                    source=entry.source or "desk",
                    queue_time=current_time,  # ⭐ ТЕКУЩЕЕ ВРЕМЯ
                    services=json.dumps(services_list_new, ensure_ascii=False),
                    service_codes=json.dumps([s['code'] for s in services_list_new], ensure_ascii=False),
                    total_amount=int(total_amount_new),
                    visit_type=entry.visit_type,
                    discount_mode=entry.discount_mode
                )

                db.add(new_queue_entry)
                db.flush()

                service_names = [vs.name for vs in services]
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
                visit_services_count = db.query(VisitService).filter(VisitService.visit_id == visit.id).count()
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
                    "visit_id": entry.visit_id if request.all_free else None
                }
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
                detail=f"Ошибка сохранения изменений: {str(commit_error)}"
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
            detail=f"Ошибка при обновлении записи: {str(e)}"
        )


@router.post("/online-entry/{entry_id}/cancel-service", response_model=CancelServiceResponse)
def cancel_service_in_entry(
    entry_id: int,
    request: CancelServiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
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
    from app.models.online_queue import OnlineQueueEntry, DailyQueue

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
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )

        # Парсим текущие услуги
        services_list = json.loads(entry.services) if entry.services else []

        # Проверяем, что услуги в новом формате (с service_id)
        if not services_list or not isinstance(services_list[0], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Услуги в старом формате. Необходимо выполнить миграцию данных."
            )

        # Ищем услугу для отмены
        service_found = False
        cancelled_service_obj = None
        new_total = 0

        for service_obj in services_list:
            if service_obj.get('service_id') == request.service_id and not service_obj.get('cancelled', False):
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
                new_total += service_obj.get('price', 0) * service_obj.get('quantity', 1)

        if not service_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Услуга с ID {request.service_id} не найдена или уже отменена"
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
            other_entries = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.patient_id == entry.patient_id,
                OnlineQueueEntry.id != entry.id
            ).all()

            if other_entries:
                logger.info(
                    "[cancel_service] Синхронизация отмены с %d другими записями",
                    len(other_entries),
                )

                for other_entry in other_entries:
                    other_services = json.loads(other_entry.services) if other_entry.services else []

                    # Проверяем формат
                    if other_services and isinstance(other_services[0], dict):
                        other_total = 0
                        updated = False

                        for other_service_obj in other_services:
                            # Отменяем ту же услугу
                            if other_service_obj.get('service_id') == request.service_id and not other_service_obj.get('cancelled', False):
                                other_service_obj['cancelled'] = True
                                other_service_obj['cancel_reason'] = request.cancel_reason
                                other_service_obj['cancelled_by'] = current_user.id
                                other_service_obj['was_paid_before_cancel'] = request.was_paid
                                updated = True

                            # Пересчитываем сумму
                            if not other_service_obj.get('cancelled', False):
                                other_total += other_service_obj.get('price', 0) * other_service_obj.get('quantity', 1)

                        if updated:
                            other_entry.services = json.dumps(other_services, ensure_ascii=False)
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
            "new_total_amount": new_total
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
            detail=f"Ошибка при отмене услуги: {str(e)}"
        )
