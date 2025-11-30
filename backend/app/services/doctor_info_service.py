"""
Сервис для получения информации о врачах и отделениях
Используется для улучшения уведомлений с реальными данными
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.user import User
from app.models.visit import Visit

logger = logging.getLogger(__name__)


class DoctorInfoService:
    """Сервис для получения информации о врачах и отделениях"""

    def __init__(self, db: Session):
        self.db = db

    # ===================== ИНФОРМАЦИЯ О ВРАЧАХ =====================

    def get_doctor_full_info(self, doctor_id: int) -> Dict[str, Any]:
        """Получает полную информацию о враче"""
        try:
            doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
            if not doctor:
                return {
                    "id": doctor_id,
                    "full_name": f"Врач #{doctor_id}",
                    "specialization": "Неизвестно",
                    "department": "Неизвестно",
                    "cabinet": None,
                    "phone": None,
                    "email": None,
                    "is_active": False,
                }

            # Получаем информацию о пользователе
            user_info = {}
            if doctor.user:
                user_info = {
                    "full_name": doctor.user.full_name or doctor.user.username,
                    "phone": getattr(doctor.user, 'phone', None),
                    "email": doctor.user.email,
                    "is_active": doctor.user.is_active,
                }
            else:
                user_info = {
                    "full_name": f"Врач #{doctor.id}",
                    "phone": None,
                    "email": None,
                    "is_active": False,
                }

            # Получаем информацию об отделении по специальности
            department_info = self.get_department_info(doctor.specialty)

            return {
                "id": doctor.id,
                "full_name": user_info["full_name"],
                "specialization": doctor.specialty or "Врач общей практики",
                "department": (
                    department_info["name"] if department_info else "Общее отделение"
                ),
                "specialty": doctor.specialty,
                "cabinet": {"number": doctor.cabinet, "floor": None, "building": None},
                "phone": user_info["phone"],
                "email": user_info["email"],
                "is_active": user_info["is_active"] and doctor.active,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else None
                ),
                "max_online_per_day": doctor.max_online_per_day,
            }

        except Exception as e:
            logger.error(f"Ошибка получения информации о враче {doctor_id}: {e}")
            return {
                "id": doctor_id,
                "full_name": f"Врач #{doctor_id}",
                "specialization": "Неизвестно",
                "department": "Неизвестно",
                "cabinet": None,
                "phone": None,
                "email": None,
                "is_active": False,
            }

    def get_doctor_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает информацию о враче по ID пользователя"""
        try:
            doctor = self.db.query(Doctor).filter(Doctor.user_id == user_id).first()
            if doctor:
                return self.get_doctor_full_info(doctor.id)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения врача по user_id {user_id}: {e}")
            return None

    def get_doctors_by_specialization(
        self, specialization: str
    ) -> List[Dict[str, Any]]:
        """Получает список врачей по специализации"""
        try:
            doctors = (
                self.db.query(Doctor)
                .filter(
                    and_(
                        Doctor.specialty.ilike(f"%{specialization}%"),
                        Doctor.active == True,
                    )
                )
                .all()
            )

            return [self.get_doctor_full_info(doctor.id) for doctor in doctors]
        except Exception as e:
            logger.error(
                f"Ошибка получения врачей по специализации {specialization}: {e}"
            )
            return []

    # ===================== ИНФОРМАЦИЯ ОБ ОТДЕЛЕНИЯХ =====================

    def get_department_info(self, specialty: str) -> Optional[Dict[str, Any]]:
        """Получает информацию об отделении по специальности"""
        try:
            if not specialty:
                return None

            # Получаем врачей данной специальности
            doctors = (
                self.db.query(Doctor)
                .filter(and_(Doctor.specialty == specialty, Doctor.active == True))
                .all()
            )

            # Формируем информацию об отделении на основе специальности
            department_names = {
                "cardiology": "Кардиология",
                "dermatology": "Дерматология",
                "stomatology": "Стоматология",
                "therapy": "Терапия",
                "neurology": "Неврология",
                "pediatrics": "Педиатрия",
                "general": "Общая практика",
            }

            return {
                "specialty": specialty,
                "name": department_names.get(specialty, specialty.title()),
                "doctors_count": len(doctors),
                "active_doctors": [d.id for d in doctors if d.active],
                "cabinets": list(set([d.cabinet for d in doctors if d.cabinet])),
                "description": f"Отделение {department_names.get(specialty, specialty)}",
            }

        except Exception as e:
            logger.error(f"Ошибка получения информации об отделении {specialty}: {e}")
            return None

    def get_department_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Получает отделение по названию"""
        try:
            # Маппинг названий на специальности
            name_to_specialty = {
                "кардиология": "cardiology",
                "дерматология": "dermatology",
                "стоматология": "stomatology",
                "терапия": "therapy",
                "неврология": "neurology",
                "педиатрия": "pediatrics",
            }

            specialty = name_to_specialty.get(name.lower())
            if specialty:
                return self.get_department_info(specialty)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения отделения по названию {name}: {e}")
            return None

    def get_all_departments(self) -> List[Dict[str, Any]]:
        """Получает список всех отделений"""
        try:
            # Получаем уникальные специальности
            specialties = (
                self.db.query(Doctor.specialty)
                .filter(Doctor.active == True)
                .distinct()
                .all()
            )
            departments = []

            for (specialty,) in specialties:
                if specialty:
                    dept_info = self.get_department_info(specialty)
                    if dept_info:
                        departments.append(dept_info)

            return departments
        except Exception as e:
            logger.error(f"Ошибка получения списка отделений: {e}")
            return []

    # ===================== СПЕЦИАЛИЗИРОВАННЫЕ МЕТОДЫ =====================

    def get_appointment_doctor_info(
        self, appointment_id: int, appointment_type: str = "appointment"
    ) -> Dict[str, Any]:
        """Получает информацию о враче для записи"""
        try:
            if appointment_type == "visit":
                appointment = (
                    self.db.query(Visit).filter(Visit.id == appointment_id).first()
                )
            else:
                appointment = (
                    self.db.query(Appointment)
                    .filter(Appointment.id == appointment_id)
                    .first()
                )

            if not appointment or not appointment.doctor_id:
                return {
                    "doctor": {
                        "full_name": "Врач не назначен",
                        "specialization": "Неизвестно",
                        "department": "Неизвестно",
                    },
                    "department": {"name": "Неизвестно"},
                }

            doctor_info = self.get_doctor_full_info(appointment.doctor_id)
            department_info = (
                self.get_department_info(doctor_info["specialty"])
                if doctor_info["specialty"]
                else None
            )

            return {
                "doctor": doctor_info,
                "department": department_info or {"name": "Неизвестно"},
            }

        except Exception as e:
            logger.error(
                f"Ошибка получения информации о враче для записи {appointment_id}: {e}"
            )
            return {
                "doctor": {
                    "full_name": "Ошибка получения данных",
                    "specialization": "Неизвестно",
                    "department": "Неизвестно",
                },
                "department": {"name": "Неизвестно"},
            }

    def get_doctors_by_department(self, department_name: str) -> List[Dict[str, Any]]:
        """Получает врачей по названию отделения"""
        try:
            # Сначала находим отделение
            department = self.get_department_by_name(department_name)
            if not department:
                return []

            # Затем находим врачей этой специальности
            return self.get_doctors_by_specialization(department["specialty"])

        except Exception as e:
            logger.error(f"Ошибка получения врачей отделения {department_name}: {e}")
            return []

    def format_doctor_info_for_notification(self, doctor_info: Dict[str, Any]) -> str:
        """Форматирует информацию о враче для уведомления"""
        try:
            name = doctor_info.get("full_name", "Неизвестный врач")
            specialization = doctor_info.get("specialization", "")
            department = doctor_info.get("department", "")
            cabinet = doctor_info.get("cabinet", {})

            # Формируем строку с информацией о враче
            result = name

            if specialization and specialization != "Неизвестно":
                result += f" ({specialization})"

            if department and department != "Неизвестно":
                result += f" - {department}"

            if cabinet and cabinet.get("number"):
                cabinet_info = f"каб. {cabinet['number']}"
                result += f" - {cabinet_info}"

            return result

        except Exception as e:
            logger.error(f"Ошибка форматирования информации о враче: {e}")
            return doctor_info.get("full_name", "Неизвестный врач")

    def format_department_info_for_notification(
        self, department_info: Dict[str, Any]
    ) -> str:
        """Форматирует информацию об отделении для уведомления"""
        try:
            name = department_info.get("name", "Неизвестное отделение")
            doctors_count = department_info.get("doctors_count", 0)

            result = name
            if doctors_count > 0:
                result += f" ({doctors_count} врачей)"

            return result

        except Exception as e:
            logger.error(f"Ошибка форматирования информации об отделении: {e}")
            return department_info.get("name", "Неизвестное отделение")

    # ===================== КЭШИРОВАНИЕ =====================

    def get_cached_doctor_info(self, doctor_id: int) -> Dict[str, Any]:
        """Получает информацию о враче с кэшированием"""
        # Здесь можно добавить кэширование через Redis или память
        # Пока возвращаем обычную информацию
        return self.get_doctor_full_info(doctor_id)

    def invalidate_doctor_cache(self, doctor_id: int):
        """Инвалидирует кэш информации о враче"""
        # Здесь можно добавить логику инвалидации кэша
        pass


# Глобальный экземпляр сервиса
def get_doctor_info_service(db: Session) -> DoctorInfoService:
    """Получить экземпляр сервиса информации о врачах"""
    return DoctorInfoService(db)
