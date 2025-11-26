"""
Сервис для передачи данных пользователя при смене аккаунта
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.user import User
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.visit import Visit, VisitService
from app.models.online_queue import OnlineQueueEntry
from app.models.doctor_price_override import DoctorPriceOverride
from app.crud import user as crud_user
from app.crud import patient as crud_patient
from app.crud import appointment as crud_appointment
from app.crud import visit as crud_visit

logger = logging.getLogger(__name__)


class UserDataTransferService:
    """Сервис для передачи данных между пользователями"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_user_data_summary(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Получить сводку данных пользователя для передачи
        """
        try:
            user = crud_user.get(db, id=user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            # Получаем связанного пациента
            patient = crud_patient.get_patient_by_user_id(db, user_id=user_id)
            
            summary = {
                "user_id": user_id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "patient_id": patient.id if patient else None,
                "data_counts": {
                    "appointments": 0,
                    "visits": 0,
                    "queue_entries": 0,
                    "price_overrides": 0
                },
                "transferable_data": []
            }
            
            if patient:
                # Подсчитываем назначения
                appointments = db.query(Appointment).filter(
                    Appointment.patient_id == patient.id
                ).all()
                summary["data_counts"]["appointments"] = len(appointments)
                
                # Подсчитываем визиты
                visits = db.query(Visit).filter(
                    Visit.patient_id == patient.id
                ).all()
                summary["data_counts"]["visits"] = len(visits)
                
                # Подсчитываем записи в очереди
                queue_entries = db.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.patient_id == patient.id
                ).all()
                summary["data_counts"]["queue_entries"] = len(queue_entries)
                
                # Подсчитываем изменения цен
                price_overrides = db.query(DoctorPriceOverride).join(Visit).filter(
                    Visit.patient_id == patient.id
                ).all()
                summary["data_counts"]["price_overrides"] = len(price_overrides)
                
                # Формируем список передаваемых данных
                for appointment in appointments:
                    summary["transferable_data"].append({
                        "type": "appointment",
                        "id": appointment.id,
                        "date": appointment.appointment_date.isoformat() if appointment.appointment_date else None,
                        "status": appointment.status,
                        "doctor_name": appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "Неизвестно",
                        "service_name": appointment.service.name if appointment.service else "Неизвестно"
                    })
                
                for visit in visits:
                    summary["transferable_data"].append({
                        "type": "visit",
                        "id": visit.id,
                        "date": visit.visit_date.isoformat() if visit.visit_date else None,
                        "status": visit.status,
                        "doctor_name": visit.doctor.user.full_name if visit.doctor and visit.doctor.user else "Неизвестно",
                        "services_count": len(visit.services) if visit.services else 0,
                        "total_amount": float(visit.total_amount) if visit.total_amount else 0
                    })
                
                for entry in queue_entries:
                    summary["transferable_data"].append({
                        "type": "queue_entry",
                        "id": entry.id,
                        "number": entry.number,
                        "status": entry.status,
                        "queue_date": entry.queue.day.isoformat() if entry.queue else None,
                        "specialist_name": entry.queue.specialist.user.full_name if (entry.queue and entry.queue.specialist and entry.queue.specialist.user) else "Неизвестно"
                    })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Ошибка получения сводки данных пользователя {user_id}: {e}")
            return {"error": f"Ошибка получения данных: {str(e)}"}
    
    def transfer_user_data(
        self, 
        db: Session, 
        source_user_id: int, 
        target_user_id: int,
        data_types: List[str] = None,
        initiated_by_user_id: int = None
    ) -> Dict[str, Any]:
        """
        Передать данные от одного пользователя к другому
        
        Args:
            source_user_id: ID пользователя-источника
            target_user_id: ID пользователя-получателя
            data_types: Типы данных для передачи ['appointments', 'visits', 'queue_entries']
            initiated_by_user_id: ID пользователя, инициировавшего передачу
        """
        try:
            # Проверяем существование пользователей
            source_user = crud_user.get(db, id=source_user_id)
            target_user = crud_user.get(db, id=target_user_id)
            
            if not source_user:
                return {"success": False, "error": "Пользователь-источник не найден"}
            
            if not target_user:
                return {"success": False, "error": "Пользователь-получатель не найден"}
            
            # Получаем пациентов
            source_patient = crud_patient.get_patient_by_user_id(db, user_id=source_user_id)
            target_patient = crud_patient.get_patient_by_user_id(db, user_id=target_user_id)
            
            if not source_patient:
                return {"success": False, "error": "Профиль пациента-источника не найден"}
            
            if not target_patient:
                # Создаем профиль пациента для получателя
                target_patient = crud_patient.create_patient_from_user(db, user=target_user)
            
            # По умолчанию передаем все типы данных
            if data_types is None:
                data_types = ['appointments', 'visits', 'queue_entries']
            
            transfer_results = {
                "success": True,
                "transferred": {},
                "errors": [],
                "summary": {
                    "source_user": source_user.username,
                    "target_user": target_user.username,
                    "initiated_by": initiated_by_user_id,
                    "transfer_date": datetime.utcnow().isoformat()
                }
            }
            
            # Передача назначений
            if 'appointments' in data_types:
                result = self._transfer_appointments(db, source_patient.id, target_patient.id)
                transfer_results["transferred"]["appointments"] = result
            
            # Передача визитов
            if 'visits' in data_types:
                result = self._transfer_visits(db, source_patient.id, target_patient.id)
                transfer_results["transferred"]["visits"] = result
            
            # Передача записей в очереди
            if 'queue_entries' in data_types:
                result = self._transfer_queue_entries(db, source_patient.id, target_patient.id)
                transfer_results["transferred"]["queue_entries"] = result
            
            # Логируем передачу
            self.logger.info(
                f"Передача данных завершена: {source_user.username} -> {target_user.username}, "
                f"типы: {data_types}, инициатор: {initiated_by_user_id}"
            )
            
            return transfer_results
            
        except Exception as e:
            self.logger.error(f"Ошибка передачи данных {source_user_id} -> {target_user_id}: {e}")
            return {
                "success": False, 
                "error": f"Ошибка передачи данных: {str(e)}"
            }
    
    def _transfer_appointments(self, db: Session, source_patient_id: int, target_patient_id: int) -> Dict[str, Any]:
        """Передать назначения"""
        try:
            appointments = db.query(Appointment).filter(
                Appointment.patient_id == source_patient_id
            ).all()
            
            transferred_count = 0
            for appointment in appointments:
                appointment.patient_id = target_patient_id
                transferred_count += 1
            
            db.commit()
            
            return {
                "count": transferred_count,
                "success": True
            }
            
        except Exception as e:
            db.rollback()
            return {
                "count": 0,
                "success": False,
                "error": str(e)
            }
    
    def _transfer_visits(self, db: Session, source_patient_id: int, target_patient_id: int) -> Dict[str, Any]:
        """Передать визиты"""
        try:
            visits = db.query(Visit).filter(
                Visit.patient_id == source_patient_id
            ).all()
            
            transferred_count = 0
            for visit in visits:
                visit.patient_id = target_patient_id
                transferred_count += 1
            
            db.commit()
            
            return {
                "count": transferred_count,
                "success": True
            }
            
        except Exception as e:
            db.rollback()
            return {
                "count": 0,
                "success": False,
                "error": str(e)
            }
    
    def _transfer_queue_entries(self, db: Session, source_patient_id: int, target_patient_id: int) -> Dict[str, Any]:
        """Передать записи в очереди"""
        try:
            queue_entries = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.patient_id == source_patient_id
            ).all()
            
            transferred_count = 0
            for entry in queue_entries:
                entry.patient_id = target_patient_id
                transferred_count += 1
            
            db.commit()
            
            return {
                "count": transferred_count,
                "success": True
            }
            
        except Exception as e:
            db.rollback()
            return {
                "count": 0,
                "success": False,
                "error": str(e)
            }
    
    def get_transfer_history(
        self, 
        db: Session, 
        user_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получить историю передач данных
        """
        # В реальной системе здесь был бы запрос к таблице истории передач
        # Пока возвращаем заглушку
        return []
    
    def validate_transfer_request(
        self, 
        db: Session, 
        source_user_id: int, 
        target_user_id: int,
        requester_user_id: int
    ) -> Tuple[bool, str]:
        """
        Валидировать запрос на передачу данных
        
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Проверяем существование пользователей
            source_user = crud_user.get(db, id=source_user_id)
            target_user = crud_user.get(db, id=target_user_id)
            requester_user = crud_user.get(db, id=requester_user_id)
            
            if not source_user:
                return False, "Пользователь-источник не найден"
            
            if not target_user:
                return False, "Пользователь-получатель не найден"
            
            if not requester_user:
                return False, "Пользователь-инициатор не найден"
            
            # Проверяем права доступа
            if requester_user_id not in [source_user_id, target_user_id]:
                # Только администраторы могут инициировать передачу между другими пользователями
                if not any(role.name in ["Admin", "SuperAdmin"] for role in requester_user.roles):
                    return False, "Недостаточно прав для выполнения передачи"
            
            # Проверяем, что пользователи разные
            if source_user_id == target_user_id:
                return False, "Нельзя передать данные самому себе"
            
            # Проверяем активность пользователей
            if not source_user.is_active:
                return False, "Пользователь-источник неактивен"
            
            if not target_user.is_active:
                return False, "Пользователь-получатель неактивен"
            
            return True, "Валидация прошла успешно"
            
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"
    
    def create_transfer_confirmation_token(
        self, 
        db: Session, 
        source_user_id: int, 
        target_user_id: int,
        data_types: List[str],
        expires_in_hours: int = 24
    ) -> str:
        """
        Создать токен подтверждения для передачи данных
        """
        import uuid
        
        token = str(uuid.uuid4())
        
        # В реальной системе здесь было бы сохранение токена в БД
        # с информацией о передаче и временем истечения
        
        return token
    
    def confirm_transfer_by_token(
        self, 
        db: Session, 
        token: str,
        confirmed_by_user_id: int
    ) -> Dict[str, Any]:
        """
        Подтвердить передачу по токену
        """
        # В реальной системе здесь была бы проверка токена
        # и выполнение передачи данных
        
        return {
            "success": False,
            "error": "Функция подтверждения по токену не реализована"
        }


# Глобальный экземпляр сервиса
_user_data_transfer_service = None


def get_user_data_transfer_service() -> UserDataTransferService:
    """Получить экземпляр сервиса передачи данных"""
    global _user_data_transfer_service
    if _user_data_transfer_service is None:
        _user_data_transfer_service = UserDataTransferService()
    return _user_data_transfer_service

