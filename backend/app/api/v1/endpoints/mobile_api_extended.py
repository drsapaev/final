"""
Расширенные мобильные API endpoints для PWA
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import (
    appointment as crud_appointment,
)
from app.crud import (
    clinic as crud_doctor,
)
from app.crud import (
    patient as crud_patient,
)
from app.crud import (
    queue as crud_queue,
)
from app.crud import (
    service as crud_service,
)
from app.crud import (
    user as crud_user,
)
from app.db.session import get_db
from app.models.user import User
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot

router = APIRouter()


# ==================== PYDANTIC MODELS ====================


class DoctorSearchRequest(BaseModel):
    """Запрос поиска врачей"""

    specialty: str | None = None
    name: str | None = None
    available_date: str | None = None
    limit: int = 10


class ServiceSearchRequest(BaseModel):
    """Запрос поиска услуг"""

    category: str | None = None
    name: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    limit: int = 20


class QueueStatusResponse(BaseModel):
    """Статус очереди"""

    doctor_id: int
    doctor_name: str
    specialty: str
    current_number: int
    total_numbers: int
    estimated_wait_time: int  # в минутах
    queue_status: str  # active, paused, closed


class AppointmentCancelRequest(BaseModel):
    """Запрос отмены записи"""

    appointment_id: int
    reason: str | None = None


class AppointmentRescheduleRequest(BaseModel):
    """Запрос переноса записи"""

    appointment_id: int
    new_date: str
    new_time: str | None = None
    reason: str | None = None


class FeedbackRequest(BaseModel):
    """Запрос обратной связи"""

    type: str  # review, complaint, suggestion, question
    rating: int | None = None  # 1-5
    message: str
    appointment_id: int | None = None


class EmergencyContactRequest(BaseModel):
    """Запрос экстренной связи"""

    type: str  # ambulance, emergency_doctor, clinic
    message: str | None = None
    location: dict[str, float] | None = None  # {"lat": 41.0, "lng": 69.0}


class ProfileUpdateRequest(BaseModel):
    """Обновление профиля"""

    full_name: str | None = None
    birth_date: str | None = None
    address: str | None = None
    emergency_contact: str | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None


class NotificationSettingsRequest(BaseModel):
    """Настройки уведомлений"""

    push_enabled: bool = True
    sms_enabled: bool = True
    email_enabled: bool = True
    appointment_reminders: bool = True
    lab_results: bool = True
    promotions: bool = False


# ==================== ВРАЧИ И УСЛУГИ ====================


@router.post("/doctors/search")
async def search_doctors(
    request: DoctorSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Поиск врачей с фильтрами"""
    try:
        doctors = crud_doctor.search_doctors(
            db,
            specialty=request.specialty,
            name=request.name,
            available_date=request.available_date,
            limit=request.limit,
        )

        result = []
        for doctor in doctors:
            # Получаем статистику врача
            total_patients = crud_appointment.count_doctor_patients(
                db, doctor_id=doctor.id
            )
            avg_rating = crud_appointment.get_doctor_avg_rating(db, doctor_id=doctor.id)

            result.append(
                {
                    "id": doctor.id,
                    "name": doctor.full_name,
                    "specialty": doctor.specialty,
                    "experience_years": doctor.experience_years,
                    "education": doctor.education,
                    "photo_url": doctor.photo_url,
                    "rating": avg_rating or 0.0,
                    "total_patients": total_patients,
                    "available_today": crud_doctor.is_doctor_available_today(
                        db, doctor.id
                    ),
                    "next_available_slot": crud_doctor.get_next_available_slot(
                        db, doctor.id
                    ),
                    "consultation_fee": doctor.consultation_fee or 0,
                }
            )

        return {"doctors": result, "total_found": len(result)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка поиска врачей: {str(e)}")


@router.get("/doctors/{doctor_id}/schedule")
async def get_doctor_schedule(
    doctor_id: int,
    date_from: str = Query(..., description="Дата начала в формате YYYY-MM-DD"),
    date_to: str = Query(..., description="Дата окончания в формате YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Расписание врача на период"""
    try:
        schedule = crud_doctor.get_doctor_schedule(
            db,
            doctor_id=doctor_id,
            date_from=datetime.fromisoformat(date_from).date(),
            date_to=datetime.fromisoformat(date_to).date(),
        )

        return {"doctor_id": doctor_id, "schedule": schedule}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения расписания: {str(e)}"
        )


@router.post("/services/search")
async def search_services(
    request: ServiceSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Поиск услуг с фильтрами"""
    try:
        services = crud_service.search_services(
            db,
            category=request.category,
            name=request.name,
            price_min=request.price_min,
            price_max=request.price_max,
            limit=request.limit,
        )

        result = []
        for service in services:
            result.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "description": service.description,
                    "category": service.category,
                    "price": service.price,
                    "duration_minutes": service.duration_minutes,
                    "requires_preparation": service.requires_preparation,
                    "preparation_instructions": service.preparation_instructions,
                    "available_doctors": crud_service.get_service_doctors_count(
                        db, service.id
                    ),
                }
            )

        return {"services": result, "total_found": len(result)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка поиска услуг: {str(e)}")


@router.get("/services/categories")
async def get_service_categories(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Категории услуг"""
    try:
        categories = crud_service.get_service_categories(db)

        result = []
        for category in categories:
            services_count = crud_service.count_services_in_category(db, category.name)

            result.append(
                {
                    "name": category.name,
                    "display_name": category.display_name,
                    "description": category.description,
                    "icon": category.icon,
                    "services_count": services_count,
                    "average_price": crud_service.get_category_avg_price(
                        db, category.name
                    ),
                }
            )

        return {"categories": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения категорий: {str(e)}"
        )


# ==================== ОЧЕРЕДИ ====================


@router.get("/queues/status")
async def get_queues_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Статус всех очередей на сегодня"""
    try:
        today = date.today()
        queues = crud_queue.get_daily_queues(db, day=today, active_only=True)

        result = []
        for queue in queues:
            doctor = crud_doctor.get_doctor(db, doctor_id=queue.doctor_id)

            # Рассчитываем примерное время ожидания
            waiting_patients = queue.total_numbers - queue.current_number
            estimated_wait = waiting_patients * 15  # 15 минут на пациента

            result.append(
                QueueStatusResponse(
                    doctor_id=queue.doctor_id,
                    doctor_name=doctor.full_name if doctor else "Неизвестно",
                    specialty=doctor.specialty if doctor else "Неизвестно",
                    current_number=queue.current_number,
                    total_numbers=queue.total_numbers,
                    estimated_wait_time=estimated_wait,
                    queue_status="active" if queue.active else "paused",
                )
            )

        return {"queues": result, "last_updated": datetime.now()}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статуса очередей: {str(e)}"
        )


@router.get("/queues/my-position")
async def get_my_queue_position(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Моя позиция в очередях"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        positions = crud_queue.get_patient_queue_positions(db, patient_id=patient.id)

        result = []
        for position in positions:
            queue = crud_queue.get_daily_queue(db, queue_id=position.queue_id)
            doctor = crud_doctor.get_doctor(db, doctor_id=queue.doctor_id)

            # Рассчитываем время до приема
            patients_before = position.queue_number - queue.current_number
            estimated_time = max(0, patients_before * 15)  # 15 минут на пациента

            result.append(
                {
                    "queue_id": position.queue_id,
                    "doctor_name": doctor.full_name if doctor else "Неизвестно",
                    "specialty": doctor.specialty if doctor else "Неизвестно",
                    "my_number": position.queue_number,
                    "current_number": queue.current_number,
                    "patients_before_me": max(0, patients_before),
                    "estimated_wait_minutes": estimated_time,
                    "status": "waiting" if patients_before > 0 else "ready",
                }
            )

        return {"positions": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения позиции в очереди: {str(e)}"
        )


# ==================== УПРАВЛЕНИЕ ЗАПИСЯМИ ====================


@router.post("/appointments/cancel")
async def cancel_appointment(
    request: AppointmentCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отмена записи"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Проверяем принадлежность записи пациенту
        appointment = crud_appointment.get_appointment(
            db, appointment_id=request.appointment_id
        )

        if not appointment or appointment.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        # Проверяем возможность отмены (не менее чем за 2 часа)
        time_until_appointment = appointment.appointment_date - datetime.now()
        if time_until_appointment < timedelta(hours=2):
            raise HTTPException(
                status_code=400,
                detail="Отмена записи возможна не менее чем за 2 часа до приема",
            )

        # Отменяем запись
        success = crud_appointment.cancel_appointment(
            db, appointment_id=request.appointment_id, reason=request.reason
        )

        if success:
            # Отправляем уведомление
            bot = get_enhanced_telegram_bot()
            if patient.telegram_chat_id:
                await bot._send_message(
                    patient.telegram_chat_id,
                    f"✅ Ваша запись на {appointment.appointment_date.strftime('%d.%m.%Y %H:%M')} отменена",
                )

            return {"success": True, "message": "Запись успешно отменена"}
        else:
            raise HTTPException(status_code=500, detail="Не удалось отменить запись")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отмены записи: {str(e)}")


@router.post("/appointments/reschedule")
async def reschedule_appointment(
    request: AppointmentRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Перенос записи"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Проверяем принадлежность записи пациенту
        appointment = crud_appointment.get_appointment(
            db, appointment_id=request.appointment_id
        )

        if not appointment or appointment.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        # Проверяем возможность переноса
        time_until_appointment = appointment.appointment_date - datetime.now()
        if time_until_appointment < timedelta(hours=4):
            raise HTTPException(
                status_code=400,
                detail="Перенос записи возможен не менее чем за 4 часа до приема",
            )

        # Переносим запись
        new_datetime = datetime.fromisoformat(request.new_date)
        if request.new_time:
            time_parts = request.new_time.split(":")
            new_datetime = new_datetime.replace(
                hour=int(time_parts[0]), minute=int(time_parts[1])
            )

        success = crud_appointment.reschedule_appointment(
            db,
            appointment_id=request.appointment_id,
            new_datetime=new_datetime,
            reason=request.reason,
        )

        if success:
            # Отправляем уведомление
            bot = get_enhanced_telegram_bot()
            if patient.telegram_chat_id:
                await bot._send_message(
                    patient.telegram_chat_id,
                    f"✅ Ваша запись перенесена на {new_datetime.strftime('%d.%m.%Y %H:%M')}",
                )

            return {
                "success": True,
                "message": "Запись успешно перенесена",
                "new_date": new_datetime.isoformat(),
            }
        else:
            raise HTTPException(status_code=500, detail="Не удалось перенести запись")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка переноса записи: {str(e)}")


# ==================== ОБРАТНАЯ СВЯЗЬ ====================


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отправка обратной связи"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Создаем запись обратной связи
        feedback_data = {
            "patient_id": patient.id,
            "type": request.type,
            "rating": request.rating,
            "message": request.message,
            "appointment_id": request.appointment_id,
            "created_at": datetime.now(),
            "status": "new",
        }

        feedback = crud_patient.create_feedback(db, feedback_data)

        # Отправляем уведомление администраторам
        bot = get_enhanced_telegram_bot()
        admin_message = f"""📝 **Новая обратная связь**

Тип: {request.type}
Пациент: {patient.full_name}
Оценка: {request.rating}/5 ⭐
Сообщение: {request.message}

ID: #{feedback.id}"""

        await bot.send_admin_notification(admin_message, db)

        return {
            "success": True,
            "message": "Спасибо за обратную связь!",
            "feedback_id": feedback.id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка отправки обратной связи: {str(e)}"
        )


# ==================== ЭКСТРЕННАЯ ПОМОЩЬ ====================


@router.post("/emergency/contact")
async def emergency_contact(
    request: EmergencyContactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Экстренная связь"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Создаем запись экстренного обращения
        emergency_data = {
            "patient_id": patient.id,
            "type": request.type,
            "message": request.message,
            "location": request.location,
            "created_at": datetime.now(),
            "status": "active",
        }

        emergency = crud_patient.create_emergency_contact(db, emergency_data)

        # Отправляем срочное уведомление
        bot = get_enhanced_telegram_bot()
        urgent_message = f"""🚨 **ЭКСТРЕННОЕ ОБРАЩЕНИЕ**

Пациент: {patient.full_name}
Телефон: {patient.phone}
Тип: {request.type}
Сообщение: {request.message or 'Не указано'}

⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
ID: #{emergency.id}"""

        await bot.send_admin_notification(urgent_message, db)

        # Возвращаем контактную информацию
        contacts = {
            "ambulance": {"phone": "103", "description": "Скорая медицинская помощь"},
            "emergency_doctor": {
                "phone": "+998 XX XXX-XX-XX",
                "description": "Дежурный врач клиники",
            },
            "clinic": {
                "phone": "+998 XX XXX-XX-XX",
                "description": "Регистратура клиники",
                "address": "Адрес клиники",
            },
        }

        return {
            "success": True,
            "message": "Ваше обращение зарегистрировано. С вами свяжутся в ближайшее время.",
            "emergency_id": emergency.id,
            "contacts": contacts,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка экстренного обращения: {str(e)}"
        )


# ==================== ПРОФИЛЬ И НАСТРОЙКИ ====================


@router.put("/profile")
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление профиля пациента"""
    try:
        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Обновляем данные
        update_data = {}
        if request.full_name:
            update_data["full_name"] = request.full_name
        if request.birth_date:
            update_data["birth_date"] = datetime.fromisoformat(
                request.birth_date
            ).date()
        if request.address:
            update_data["address"] = request.address
        if request.emergency_contact:
            update_data["emergency_contact"] = request.emergency_contact
        if request.allergies:
            update_data["allergies"] = request.allergies
        if request.chronic_conditions:
            update_data["chronic_conditions"] = request.chronic_conditions

        updated_patient = crud_patient.update_patient(
            db, patient_id=patient.id, update_data=update_data
        )

        return {
            "success": True,
            "message": "Профиль успешно обновлен",
            "patient": {
                "id": updated_patient.id,
                "full_name": updated_patient.full_name,
                "phone": updated_patient.phone,
                "birth_date": (
                    updated_patient.birth_date.isoformat()
                    if updated_patient.birth_date
                    else None
                ),
                "address": updated_patient.address,
                "emergency_contact": updated_patient.emergency_contact,
                "allergies": updated_patient.allergies,
                "chronic_conditions": updated_patient.chronic_conditions,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка обновления профиля: {str(e)}"
        )


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Загрузка аватара пациента"""
    try:
        # Проверяем тип файла
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="Можно загружать только изображения"
            )

        # Проверяем размер файла (максимум 5MB)
        if file.size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="Размер файла не должен превышать 5MB"
            )

        patient = crud_patient.get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Сохраняем файл (здесь должна быть логика сохранения в файловую систему или облако)
        file_path = f"avatars/patient_{patient.id}_{datetime.now().timestamp()}.jpg"

        # Обновляем путь к аватару в базе данных
        crud_patient.update_patient(
            db, patient_id=patient.id, update_data={"avatar_url": file_path}
        )

        return {
            "success": True,
            "message": "Аватар успешно загружен",
            "avatar_url": file_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка загрузки аватара: {str(e)}"
        )


@router.put("/settings/notifications")
async def update_notification_settings(
    request: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление настроек уведомлений"""
    try:
        # Обновляем настройки пользователя
        settings_data = {
            "push_notifications": request.push_enabled,
            "sms_notifications": request.sms_enabled,
            "email_notifications": request.email_enabled,
            "appointment_reminders": request.appointment_reminders,
            "lab_results_notifications": request.lab_results,
            "promotions_notifications": request.promotions,
        }

        crud_user.update_notification_settings(
            db, user_id=current_user.id, settings=settings_data
        )

        return {
            "success": True,
            "message": "Настройки уведомлений обновлены",
            "settings": settings_data,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка обновления настроек: {str(e)}"
        )


@router.get("/settings/notifications")
async def get_notification_settings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Получение текущих настроек уведомлений"""
    try:
        settings = crud_user.get_notification_settings(db, user_id=current_user.id)

        return {
            "push_enabled": settings.get("push_notifications", True),
            "sms_enabled": settings.get("sms_notifications", True),
            "email_enabled": settings.get("email_notifications", True),
            "appointment_reminders": settings.get("appointment_reminders", True),
            "lab_results": settings.get("lab_results_notifications", True),
            "promotions": settings.get("promotions_notifications", False),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения настроек: {str(e)}"
        )


# ==================== ДОПОЛНИТЕЛЬНЫЕ ENDPOINTS ====================


@router.get("/clinic/info")
async def get_clinic_info(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Информация о клинике"""
    try:
        clinic_info = {
            "name": "Медицинская клиника",
            "address": "Адрес клиники",
            "phone": "+998 XX XXX-XX-XX",
            "email": "info@clinic.uz",
            "website": "https://clinic.uz",
            "working_hours": {
                "monday": "08:00-18:00",
                "tuesday": "08:00-18:00",
                "wednesday": "08:00-18:00",
                "thursday": "08:00-18:00",
                "friday": "08:00-18:00",
                "saturday": "09:00-15:00",
                "sunday": "Выходной",
            },
            "services": [
                "Терапия",
                "Кардиология",
                "Дерматология",
                "Стоматология",
                "Лабораторная диагностика",
                "УЗИ диагностика",
            ],
            "emergency_phone": "103",
            "location": {"latitude": 41.2995, "longitude": 69.2401},
        }

        return clinic_info

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения информации о клинике: {str(e)}"
        )


@router.get("/version")
async def get_api_version():
    """Версия мобильного API"""
    return {
        "version": "2.0.0",
        "build": "20250926",
        "features": [
            "Расширенный поиск врачей и услуг",
            "Управление записями (отмена, перенос)",
            "Статус очередей в реальном времени",
            "Обратная связь и рейтинги",
            "Экстренная помощь",
            "Загрузка аватара",
            "Настройки уведомлений",
            "Информация о клинике",
        ],
        "last_updated": datetime.now().isoformat(),
    }
