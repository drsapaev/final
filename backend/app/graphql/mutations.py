"""
GraphQL мутации для API клиники
"""
import strawberry
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.db.session import get_db
from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.visit import Visit, VisitService
from app.models.online_queue import OnlineQueueEntry, DailyQueue
from app.crud import patient as crud_patient
from app.crud import appointment as crud_appointment
from app.crud import visit as crud_visit
from app.crud import service as crud_service
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
from app.graphql.types import (
    PatientInput, PatientUpdateInput, AppointmentInput, VisitInput, ServiceInput,
    DoctorInput, QueueEntryInput, PatientMutationResponse, AppointmentMutationResponse,
    VisitMutationResponse, ServiceMutationResponse, DoctorMutationResponse,
    QueueMutationResponse, MutationResponse
)
from app.graphql.resolvers import (
    patient_to_type, appointment_to_type, visit_to_type, service_to_type,
    doctor_to_type, queue_entry_to_type, get_db_session
)


@strawberry.type
class Mutation:
    """GraphQL Mutations"""
    
    # ===================== PATIENT MUTATIONS =====================
    
    @strawberry.mutation
    def create_patient(self, input: PatientInput) -> PatientMutationResponse:
        """Создать нового пациента"""
        try:
            db = get_db_session()
            
            # Проверяем, не существует ли пациент с таким телефоном
            existing = db.query(Patient).filter(Patient.phone == input.phone).first()
            if existing:
                return PatientMutationResponse(
                    success=False,
                    message="Пациент с таким номером телефона уже существует",
                    errors=["PHONE_EXISTS"]
                )
            
            # Создаем нового пациента
            patient_data = {
                "full_name": input.full_name,
                "phone": input.phone,
                "email": input.email,
                "birth_date": input.birth_date,
                "address": input.address,
                "passport_series": input.passport_series,
                "passport_number": input.passport_number
            }
            
            patient = crud_patient.create(db, obj_in=patient_data)
            
            return PatientMutationResponse(
                success=True,
                message="Пациент успешно создан",
                patient=patient_to_type(patient)
            )
            
        except Exception as e:
            return PatientMutationResponse(
                success=False,
                message=f"Ошибка создания пациента: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def update_patient(self, id: int, input: PatientUpdateInput) -> PatientMutationResponse:
        """Обновить данные пациента"""
        try:
            db = get_db_session()
            
            patient = db.query(Patient).filter(Patient.id == id).first()
            if not patient:
                return PatientMutationResponse(
                    success=False,
                    message="Пациент не найден",
                    errors=["PATIENT_NOT_FOUND"]
                )
            
            # Обновляем только переданные поля
            update_data = {}
            if input.full_name is not None:
                update_data["full_name"] = input.full_name
            if input.phone is not None:
                update_data["phone"] = input.phone
            if input.email is not None:
                update_data["email"] = input.email
            if input.birth_date is not None:
                update_data["birth_date"] = input.birth_date
            if input.address is not None:
                update_data["address"] = input.address
            if input.passport_series is not None:
                update_data["passport_series"] = input.passport_series
            if input.passport_number is not None:
                update_data["passport_number"] = input.passport_number
            
            updated_patient = crud_patient.update(db, db_obj=patient, obj_in=update_data)
            
            return PatientMutationResponse(
                success=True,
                message="Пациент успешно обновлен",
                patient=patient_to_type(updated_patient)
            )
            
        except Exception as e:
            return PatientMutationResponse(
                success=False,
                message=f"Ошибка обновления пациента: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def delete_patient(self, id: int) -> MutationResponse:
        """Удалить пациента"""
        try:
            db = get_db_session()
            
            patient = db.query(Patient).filter(Patient.id == id).first()
            if not patient:
                return MutationResponse(
                    success=False,
                    message="Пациент не найден",
                    errors=["PATIENT_NOT_FOUND"]
                )
            
            # Проверяем, есть ли связанные записи
            appointments_count = db.query(Appointment).filter(Appointment.patient_id == id).count()
            visits_count = db.query(Visit).filter(Visit.patient_id == id).count()
            
            if appointments_count > 0 or visits_count > 0:
                return MutationResponse(
                    success=False,
                    message="Нельзя удалить пациента с существующими записями или визитами",
                    errors=["HAS_RELATED_RECORDS"]
                )
            
            crud_patient.remove(db, id=id)
            
            return MutationResponse(
                success=True,
                message="Пациент успешно удален"
            )
            
        except Exception as e:
            return MutationResponse(
                success=False,
                message=f"Ошибка удаления пациента: {str(e)}",
                errors=[str(e)]
            )
    
    # ===================== APPOINTMENT MUTATIONS =====================
    
    @strawberry.mutation
    def create_appointment(self, input: AppointmentInput) -> AppointmentMutationResponse:
        """Создать новую запись"""
        try:
            db = get_db_session()
            
            # Проверяем существование пациента, врача и услуги
            patient = db.query(Patient).filter(Patient.id == input.patient_id).first()
            if not patient:
                return AppointmentMutationResponse(
                    success=False,
                    message="Пациент не найден",
                    errors=["PATIENT_NOT_FOUND"]
                )
            
            doctor = db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
            if not doctor:
                return AppointmentMutationResponse(
                    success=False,
                    message="Врач не найден",
                    errors=["DOCTOR_NOT_FOUND"]
                )
            
            service = db.query(Service).filter(Service.id == input.service_id).first()
            if not service:
                return AppointmentMutationResponse(
                    success=False,
                    message="Услуга не найдена",
                    errors=["SERVICE_NOT_FOUND"]
                )
            
            # Создаем запись
            appointment_data = {
                "patient_id": input.patient_id,
                "doctor_id": input.doctor_id,
                "service_id": input.service_id,
                "appointment_date": input.appointment_date,
                "notes": input.notes,
                "status": "scheduled",
                "payment_status": "pending",
                "payment_amount": service.price
            }
            
            appointment = crud_appointment.create(db, obj_in=appointment_data)
            
            return AppointmentMutationResponse(
                success=True,
                message="Запись успешно создана",
                appointment=appointment_to_type(appointment)
            )
            
        except Exception as e:
            return AppointmentMutationResponse(
                success=False,
                message=f"Ошибка создания записи: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def update_appointment_status(self, id: int, status: str) -> AppointmentMutationResponse:
        """Обновить статус записи"""
        try:
            db = get_db_session()
            
            appointment = db.query(Appointment).filter(Appointment.id == id).first()
            if not appointment:
                return AppointmentMutationResponse(
                    success=False,
                    message="Запись не найдена",
                    errors=["APPOINTMENT_NOT_FOUND"]
                )
            
            valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]
            if status not in valid_statuses:
                return AppointmentMutationResponse(
                    success=False,
                    message=f"Недопустимый статус. Допустимые: {', '.join(valid_statuses)}",
                    errors=["INVALID_STATUS"]
                )
            
            updated_appointment = crud_appointment.update(
                db, db_obj=appointment, obj_in={"status": status}
            )
            
            return AppointmentMutationResponse(
                success=True,
                message="Статус записи успешно обновлен",
                appointment=appointment_to_type(updated_appointment)
            )
            
        except Exception as e:
            return AppointmentMutationResponse(
                success=False,
                message=f"Ошибка обновления статуса записи: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def cancel_appointment(self, id: int, reason: Optional[str] = None) -> AppointmentMutationResponse:
        """Отменить запись"""
        try:
            db = get_db_session()
            
            appointment = db.query(Appointment).filter(Appointment.id == id).first()
            if not appointment:
                return AppointmentMutationResponse(
                    success=False,
                    message="Запись не найдена",
                    errors=["APPOINTMENT_NOT_FOUND"]
                )
            
            if appointment.status == "completed":
                return AppointmentMutationResponse(
                    success=False,
                    message="Нельзя отменить завершенную запись",
                    errors=["CANNOT_CANCEL_COMPLETED"]
                )
            
            update_data = {
                "status": "cancelled",
                "notes": f"{appointment.notes or ''}\nОтменено: {reason or 'Без указания причины'}"
            }
            
            updated_appointment = crud_appointment.update(
                db, db_obj=appointment, obj_in=update_data
            )
            
            return AppointmentMutationResponse(
                success=True,
                message="Запись успешно отменена",
                appointment=appointment_to_type(updated_appointment)
            )
            
        except Exception as e:
            return AppointmentMutationResponse(
                success=False,
                message=f"Ошибка отмены записи: {str(e)}",
                errors=[str(e)]
            )
    
    # ===================== VISIT MUTATIONS =====================
    
    @strawberry.mutation
    def create_visit(self, input: VisitInput) -> VisitMutationResponse:
        """Создать новый визит"""
        try:
            db = get_db_session()
            
            # Проверяем существование пациента и врача
            patient = db.query(Patient).filter(Patient.id == input.patient_id).first()
            if not patient:
                return VisitMutationResponse(
                    success=False,
                    message="Пациент не найден",
                    errors=["PATIENT_NOT_FOUND"]
                )
            
            doctor = db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
            if not doctor:
                return VisitMutationResponse(
                    success=False,
                    message="Врач не найден",
                    errors=["DOCTOR_NOT_FOUND"]
                )
            
            # Проверяем услуги
            services = db.query(Service).filter(Service.id.in_(input.service_ids)).all()
            if len(services) != len(input.service_ids):
                return VisitMutationResponse(
                    success=False,
                    message="Одна или несколько услуг не найдены",
                    errors=["SERVICES_NOT_FOUND"]
                )
            
            # Рассчитываем общую стоимость
            total_amount = sum(service.price for service in services)
            if input.all_free:
                total_amount = 0
            elif input.discount_mode == "repeat":
                total_amount *= 0.8  # 20% скидка для повторных визитов
            elif input.discount_mode == "benefit":
                total_amount *= 0.5  # 50% скидка для льготных
            
            # Создаем визит
            visit_data = {
                "patient_id": input.patient_id,
                "doctor_id": input.doctor_id,
                "visit_date": input.visit_date,
                "visit_time": input.visit_time,
                "status": "scheduled",
                "discount_mode": input.discount_mode,
                "all_free": input.all_free,
                "total_amount": total_amount,
                "payment_status": "paid" if input.all_free else "pending"
            }
            
            visit = crud_visit.create(db, obj_in=visit_data)
            
            # Добавляем услуги к визиту
            for service in services:
                service_price = 0 if input.all_free else service.price
                if input.discount_mode == "repeat":
                    service_price *= 0.8
                elif input.discount_mode == "benefit":
                    service_price *= 0.5
                
                visit_service = VisitService(
                    visit_id=visit.id,
                    service_id=service.id,
                    price=service_price,
                    quantity=1,
                    total_price=service_price
                )
                db.add(visit_service)
            
            db.commit()
            
            return VisitMutationResponse(
                success=True,
                message="Визит успешно создан",
                visit=visit_to_type(visit)
            )
            
        except Exception as e:
            db.rollback()
            return VisitMutationResponse(
                success=False,
                message=f"Ошибка создания визита: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def update_visit_status(self, id: int, status: str) -> VisitMutationResponse:
        """Обновить статус визита"""
        try:
            db = get_db_session()
            
            visit = db.query(Visit).filter(Visit.id == id).first()
            if not visit:
                return VisitMutationResponse(
                    success=False,
                    message="Визит не найден",
                    errors=["VISIT_NOT_FOUND"]
                )
            
            valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled"]
            if status not in valid_statuses:
                return VisitMutationResponse(
                    success=False,
                    message=f"Недопустимый статус. Допустимые: {', '.join(valid_statuses)}",
                    errors=["INVALID_STATUS"]
                )
            
            updated_visit = crud_visit.update(
                db, db_obj=visit, obj_in={"status": status}
            )
            
            return VisitMutationResponse(
                success=True,
                message="Статус визита успешно обновлен",
                visit=visit_to_type(updated_visit)
            )
            
        except Exception as e:
            return VisitMutationResponse(
                success=False,
                message=f"Ошибка обновления статуса визита: {str(e)}",
                errors=[str(e)]
            )
    
    # ===================== SERVICE MUTATIONS =====================
    
    @strawberry.mutation
    def create_service(self, input: ServiceInput) -> ServiceMutationResponse:
        """Создать новую услугу"""
        try:
            db = get_db_session()
            
            # Проверяем уникальность кода
            existing = db.query(Service).filter(Service.code == input.code).first()
            if existing:
                return ServiceMutationResponse(
                    success=False,
                    message="Услуга с таким кодом уже существует",
                    errors=["CODE_EXISTS"]
                )
            
            # Проверяем врача, если указан
            if input.doctor_id:
                doctor = db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
                if not doctor:
                    return ServiceMutationResponse(
                        success=False,
                        message="Врач не найден",
                        errors=["DOCTOR_NOT_FOUND"]
                    )
            
            # Создаем услугу
            service_data = {
                "name": input.name,
                "code": input.code,
                "price": input.price,
                "category": input.category,
                "description": input.description,
                "duration_minutes": input.duration_minutes,
                "doctor_id": input.doctor_id,
                "active": True
            }
            
            service = crud_service.create(db, obj_in=service_data)
            
            return ServiceMutationResponse(
                success=True,
                message="Услуга успешно создана",
                service=service_to_type(service)
            )
            
        except Exception as e:
            return ServiceMutationResponse(
                success=False,
                message=f"Ошибка создания услуги: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def update_service_price(self, id: int, price: float) -> ServiceMutationResponse:
        """Обновить цену услуги"""
        try:
            db = get_db_session()
            
            service = db.query(Service).filter(Service.id == id).first()
            if not service:
                return ServiceMutationResponse(
                    success=False,
                    message="Услуга не найдена",
                    errors=["SERVICE_NOT_FOUND"]
                )
            
            if price < 0:
                return ServiceMutationResponse(
                    success=False,
                    message="Цена не может быть отрицательной",
                    errors=["INVALID_PRICE"]
                )
            
            updated_service = crud_service.update(
                db, db_obj=service, obj_in={"price": price}
            )
            
            return ServiceMutationResponse(
                success=True,
                message="Цена услуги успешно обновлена",
                service=service_to_type(updated_service)
            )
            
        except Exception as e:
            return ServiceMutationResponse(
                success=False,
                message=f"Ошибка обновления цены услуги: {str(e)}",
                errors=[str(e)]
            )
    
    # ===================== QUEUE MUTATIONS =====================
    
    @strawberry.mutation
    def join_queue(self, input: QueueEntryInput) -> QueueMutationResponse:
        """Встать в очередь"""
        try:
            db = get_db_session()
            
            # Проверяем существование пациента и врача
            patient = db.query(Patient).filter(Patient.id == input.patient_id).first()
            if not patient:
                return QueueMutationResponse(
                    success=False,
                    message="Пациент не найден",
                    errors=["PATIENT_NOT_FOUND"]
                )
            
            doctor = db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
            if not doctor:
                return QueueMutationResponse(
                    success=False,
                    message="Врач не найден",
                    errors=["DOCTOR_NOT_FOUND"]
                )
            
            # Проверяем, не стоит ли пациент уже в очереди к этому врачу сегодня
            today = date.today()
            existing_entry = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.patient_id == input.patient_id,
                OnlineQueueEntry.doctor_id == input.doctor_id,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
                func.date(OnlineQueueEntry.created_at) == today
            ).first()
            
            if existing_entry:
                return QueueMutationResponse(
                    success=False,
                    message="Пациент уже стоит в очереди к этому врачу сегодня",
                    errors=["ALREADY_IN_QUEUE"]
                )
            
            # Получаем или создаем дневную очередь
            daily_queue = crud_queue.get_or_create_daily_queue(
                db, doctor_id=input.doctor_id, queue_date=today, queue_tag=input.queue_tag
            )
            
            # Проверяем лимит онлайн записей
            online_entries_count = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.doctor_id == input.doctor_id,
                func.date(OnlineQueueEntry.created_at) == today
            ).count()
            
            if online_entries_count >= doctor.max_online_per_day:
                return QueueMutationResponse(
                    success=False,
                    message="Превышен лимит онлайн записей на сегодня",
                    errors=["QUEUE_LIMIT_EXCEEDED"]
                )
            
            # Создаем запись в очереди
            queue_number = daily_queue.current_number + 1
            daily_queue.current_number = queue_number
            
            queue_entry = OnlineQueueEntry(
                patient_id=input.patient_id,
                doctor_id=input.doctor_id,
                queue_number=queue_number,
                status="waiting"
            )
            
            db.add(queue_entry)
            db.commit()
            
            return QueueMutationResponse(
                success=True,
                message=f"Вы встали в очередь под номером {queue_number}",
                queue_entry=queue_entry_to_type(queue_entry)
            )
            
        except Exception as e:
            db.rollback()
            return QueueMutationResponse(
                success=False,
                message=f"Ошибка постановки в очередь: {str(e)}",
                errors=[str(e)]
            )
    
    @strawberry.mutation
    def call_next_patient(self, doctor_id: int, queue_tag: Optional[str] = None) -> QueueMutationResponse:
        """Вызвать следующего пациента"""
        try:
            db = get_db_session()
            
            # Находим следующего пациента в очереди
            query = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.doctor_id == doctor_id,
                OnlineQueueEntry.status == "waiting",
                func.date(OnlineQueueEntry.created_at) == date.today()
            )
            
            if queue_tag:
                # Если указан тег очереди, ищем в соответствующей очереди
                daily_queue = db.query(DailyQueue).filter(
                    DailyQueue.doctor_id == doctor_id,
                    DailyQueue.queue_date == date.today(),
                    DailyQueue.queue_tag == queue_tag
                ).first()
                if daily_queue:
                    query = query.filter(OnlineQueueEntry.created_at >= daily_queue.created_at)
            
            next_entry = query.order_by(OnlineQueueEntry.queue_number).first()
            
            if not next_entry:
                return QueueMutationResponse(
                    success=False,
                    message="Нет пациентов в очереди",
                    errors=["NO_PATIENTS_IN_QUEUE"]
                )
            
            # Обновляем статус и время вызова
            next_entry.status = "called"
            next_entry.called_at = datetime.utcnow()
            
            # Обновляем последний вызванный номер в дневной очереди
            daily_queue = db.query(DailyQueue).filter(
                DailyQueue.doctor_id == doctor_id,
                DailyQueue.queue_date == date.today()
            ).first()
            
            if daily_queue:
                daily_queue.last_called_number = next_entry.queue_number
            
            db.commit()
            
            return QueueMutationResponse(
                success=True,
                message=f"Вызван пациент под номером {next_entry.queue_number}",
                queue_entry=queue_entry_to_type(next_entry)
            )
            
        except Exception as e:
            db.rollback()
            return QueueMutationResponse(
                success=False,
                message=f"Ошибка вызова пациента: {str(e)}",
                errors=[str(e)]
            )
