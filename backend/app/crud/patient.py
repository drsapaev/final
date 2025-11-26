from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate


class CRUDPatient(CRUDBase[Patient, PatientCreate, PatientUpdate]):
    def get_patients(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> List[Patient]:
        """
        Получить список пациентов с поиском
        
        Args:
            phone: Точный поиск по номеру телефона (приоритет)
            search_query: Общий поиск по всем полям
        """
        query = db.query(self.model)

        # Приоритет 1: Точный поиск по телефону
        if phone:
            # Нормализуем телефон для поиска (убираем пробелы, дефисы и т.д.)
            normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("+", "")
            
            # Ищем точное совпадение (с учетом форматирования)
            query = query.filter(
                or_(
                    self.model.phone == phone,  # Точное совпадение
                    self.model.phone.like(f"%{normalized_phone}"),  # Совпадение без форматирования
                )
            )
            return query.offset(skip).limit(limit).all()

        # Приоритет 2: Общий поиск
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(search_term),
                    self.model.last_name.ilike(search_term),
                    self.model.middle_name.ilike(search_term),
                    self.model.phone.ilike(search_term),
                    self.model.doc_number.ilike(search_term),
                )
            )

        return query.offset(skip).limit(limit).all()

    def get_patient_by_phone(self, db: Session, *, phone: str) -> Optional[Patient]:
        """
        Получить пациента по номеру телефона
        """
        return db.query(self.model).filter(self.model.phone == phone).first()

    def has_active_appointments(self, db: Session, *, patient_id: int) -> bool:
        """
        Проверить, есть ли у пациента активные записи
        """
        from app.models.appointment import Appointment

        today = datetime.now().date()

        active_appointments = (
            db.query(Appointment)
            .filter(
                and_(
                    Appointment.patient_id == patient_id,
                    Appointment.appointment_date >= today,
                    Appointment.status != "cancelled",
                )
            )
            .count()
        )

        return active_appointments > 0

    def get_patient_appointments(
        self, db: Session, *, patient_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получить все записи пациента
        """
        from app.models.appointment import Appointment

        appointments = (
            db.query(Appointment)
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc())
            .all()
        )

        return [
            {
                "id": apt.id,
                "appointment_date": apt.appointment_date,
                "appointment_time": apt.appointment_time,
                "department": apt.department,
                "doctor_id": apt.doctor_id,
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ]


patient = CRUDPatient(Patient)


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===

def get_patient_by_user_id(db: Session, user_id: int) -> Optional[Patient]:
    """Получить пациента по ID пользователя"""
    return db.query(Patient).filter(Patient.user_id == user_id).first()


def create_patient_from_user(db: Session, user: User) -> Patient:
    """Создать профиль пациента из данных пользователя"""
    # Используем единую функцию нормализации
    name_parts = normalize_patient_name(user.full_name or "")
    
    # ✅ ВАЛИДАЦИЯ: Проверяем, что после нормализации обязательные поля не пустые
    normalized_last_name = (name_parts["last_name"] or "").strip()
    normalized_first_name = (name_parts["first_name"] or "").strip()
    
    # Если поля пустые, используем username как fallback
    if not normalized_last_name and not normalized_first_name:
        if user.username:
            normalized_last_name = user.username
            normalized_first_name = user.username
        else:
            normalized_last_name = "Пользователь"
            normalized_first_name = str(user.id)
    
    patient_data = {
        "user_id": user.id,
        "first_name": normalized_first_name,
        "last_name": normalized_last_name,
        "middle_name": name_parts.get("middle_name"),
        "phone": user.phone,
        # email НЕ передаем - это поле не существует в модели Patient
        "created_at": datetime.utcnow()
    }
    
    patient = Patient(**patient_data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    
    # ✅ ФИНАЛЬНАЯ ПРОВЕРКА: Убеждаемся, что данные сохранены корректно
    if not patient.last_name or not patient.last_name.strip():
        raise ValueError(f"Ошибка сохранения: фамилия пациента не была сохранена (patient_id={patient.id})")
    if not patient.first_name or not patient.first_name.strip():
        raise ValueError(f"Ошибка сохранения: имя пациента не было сохранено (patient_id={patient.id})")
    
    return patient


# ===================== ЕДИНЫЕ ФУНКЦИИ - SINGLE SOURCE OF TRUTH =====================

def normalize_patient_name(
    full_name: Optional[str] = None,
    last_name: Optional[str] = None,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None
) -> Dict[str, str]:
    """
    Нормализация ФИО пациента - единая функция для всего проекта.
    
    Принимает либо полное ФИО (full_name), либо отдельные поля.
    Если переданы отдельные поля - использует их напрямую.
    Если передано полное ФИО - парсит его на части.
    
    Args:
        full_name: Полное ФИО в формате "Фамилия Имя Отчество"
        last_name: Фамилия (если передана отдельно)
        first_name: Имя (если передано отдельно)
        middle_name: Отчество (если передано отдельно)
    
    Returns:
        Dict с ключами: last_name, first_name, middle_name (может быть None)
    """
    # ✅ УЛУЧШЕННАЯ ЛОГИКА: Приоритет отдельным полям, если они не пустые
    # Проверяем, что отдельные поля не пустые после strip()
    # ВАЖНО: Пустые строки '' после strip() становятся '', а не None
    # Поэтому проверяем явно на пустую строку после strip()
    last_name_clean = (last_name or "").strip() if last_name else ""
    first_name_clean = (first_name or "").strip() if first_name else ""
    # ✅ КРИТИЧНО: has_individual_fields = True только если хотя бы одно поле НЕ пустое
    # Пустые строки '' не считаются валидными полями
    has_individual_fields = bool(last_name_clean) or bool(first_name_clean)
    
    # Если переданы непустые отдельные поля - используем их
    if has_individual_fields:
        # ✅ ГАРАНТИЯ: Если одно из полей пустое, но другое есть - используем его для обоих
        # Это предотвращает ситуацию, когда last_name есть, а first_name пустое
        if not last_name_clean and first_name_clean:
            # Если есть только имя - используем его как фамилию и имя
            last_name_clean = first_name_clean
        elif last_name_clean and not first_name_clean:
            # Если есть только фамилия - используем её как фамилию и имя
            first_name_clean = last_name_clean
        
        return {
            "last_name": last_name_clean,
            "first_name": first_name_clean,
            "middle_name": (middle_name or "").strip() if middle_name else None
        }
    
    # Если передано полное ФИО - парсим его
    if full_name and full_name.strip():
        # Парсим full_name (логика ниже)
        pass
    else:
        # Нет ни full_name, ни отдельных полей - возвращаем пустые строки
        # (вызывающий код должен проверить это и выбросить ошибку)
        return {
            "last_name": "",
            "first_name": "",
            "middle_name": None
        }
    
    # Нормализуем: убираем лишние пробелы, разбиваем на части
    # (достигаем сюда только если full_name не пустое)
    name_parts = full_name.strip().split()
    name_parts = [part for part in name_parts if part]  # Убираем пустые строки
    
    if len(name_parts) == 0:
        return {
            "last_name": "",
            "first_name": "",
            "middle_name": None
        }
    elif len(name_parts) == 1:
        # Только одно слово - используем как фамилию и имя
        return {
            "last_name": name_parts[0],
            "first_name": name_parts[0],
            "middle_name": None
        }
    elif len(name_parts) == 2:
        # Два слова - фамилия и имя
        return {
            "last_name": name_parts[0],
            "first_name": name_parts[1],
            "middle_name": None
        }
    else:
        # Три и более слов - фамилия, имя, остальное как отчество
        return {
            "last_name": name_parts[0],
            "first_name": name_parts[1],
            "middle_name": " ".join(name_parts[2:]) if len(name_parts) > 2 else None
        }


def validate_birthdate(birth_date: Optional[date]) -> bool:
    """
    Валидация даты рождения пациента.
    
    Args:
        birth_date: Дата рождения для проверки
    
    Returns:
        True если дата валидна, False если нет
    """
    if birth_date is None:
        return True  # Дата рождения не обязательна
    
    today = date.today()
    
    # Дата не должна быть в будущем
    if birth_date > today:
        return False
    
    # Дата не должна быть слишком старой (более 150 лет назад)
    min_date = date(today.year - 150, 1, 1)
    if birth_date < min_date:
        return False
    
    return True


def find_patient(
    db: Session,
    *,
    phone: Optional[str] = None,
    search_query: Optional[str] = None,
    patient_id: Optional[int] = None
) -> Optional[Patient]:
    """
    Универсальный поиск пациента - единая функция для всего проекта.
    
    Ищет пациента по телефону, ID или текстовому запросу (ФИО, документ).
    Приоритет: patient_id > phone > search_query
    
    Args:
        db: Сессия базы данных
        phone: Номер телефона для поиска
        search_query: Текстовый запрос (ФИО, документ)
        patient_id: ID пациента
    
    Returns:
        Найденный Patient или None
    """
    # Приоритет 1: Поиск по ID
    if patient_id:
        return db.query(Patient).filter(Patient.id == patient_id).first()
    
    # Приоритет 2: Поиск по телефону
    if phone:
        # Нормализуем телефон: убираем пробелы, дефисы, скобки
        normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        patient = db.query(Patient).filter(
            Patient.phone.like(f"%{normalized_phone}%")
        ).first()
        if patient:
            return patient
    
    # Приоритет 3: Текстовый поиск
    if search_query:
        search_term = f"%{search_query}%"
        patient = db.query(Patient).filter(
            or_(
                Patient.first_name.ilike(search_term),
                Patient.last_name.ilike(search_term),
                Patient.middle_name.ilike(search_term),
                Patient.phone.ilike(search_term),
                Patient.doc_number.ilike(search_term)
            )
        ).first()
        if patient:
            return patient
    
    return None


def find_or_create_patient(
    db: Session,
    patient_data: Dict[str, Any]
) -> Patient:
    """
    Найти существующего пациента или создать нового.
    
    Ищет пациента по телефону. Если не найден - создает нового.
    
    Args:
        db: Сессия базы данных
        patient_data: Данные пациента (должен содержать phone или full_name)
    
    Returns:
        Найденный или созданный Patient
    """
    # Ищем по телефону
    phone = patient_data.get("phone")
    if phone:
        existing = find_patient(db, phone=phone)
        if existing:
            return existing
    
    # Если не найден - создаем нового
    # ✅ УЛУЧШЕННАЯ ВАЛИДАЦИЯ: Проверяем входные данные ДО нормализации
    full_name = patient_data.get("full_name")
    last_name_input = patient_data.get("last_name")
    first_name_input = patient_data.get("first_name")
    
    has_full_name = full_name and full_name.strip()
    has_individual_names = (
        (last_name_input and last_name_input.strip()) or
        (first_name_input and first_name_input.strip())
    )
    
    if not has_full_name and not has_individual_names:
        raise ValueError("Необходимо указать либо полное ФИО (full_name), либо фамилию и имя (last_name, first_name)")
    
    # Нормализуем ФИО
    name_parts = normalize_patient_name(
        full_name=full_name,
        last_name=last_name_input,
        first_name=first_name_input,
        middle_name=patient_data.get("middle_name")
    )
    
    # ✅ СТРОГАЯ ВАЛИДАЦИЯ: Проверяем, что после нормализации обязательные поля не пустые
    normalized_last_name = name_parts["last_name"].strip() if name_parts["last_name"] else ""
    normalized_first_name = name_parts["first_name"].strip() if name_parts["first_name"] else ""
    
    if not normalized_last_name:
        raise ValueError("Фамилия пациента обязательна для заполнения и не может быть пустой")
    if not normalized_first_name:
        raise ValueError("Имя пациента обязательно для заполнения и не может быть пустым")
    
    # ✅ КРИТИЧНО: Используем ТОЛЬКО нормализованные данные для создания пациента
    # НЕ используем patient_data.get("last_name") или patient_data.get("first_name") после нормализации
    # Это гарантирует, что нормализованные данные не перезаписываются исходными (которые могут быть пустыми)
    
    # Валидируем дату рождения
    birth_date = patient_data.get("birth_date")
    if birth_date and not validate_birthdate(birth_date):
        raise ValueError("Некорректная дата рождения")
    
    # ✅ Создаем пациента ИСКЛЮЧИТЕЛЬНО из нормализованных данных
    # НЕ используем patient_data для last_name/first_name, только для других полей
    new_patient = Patient(
        last_name=normalized_last_name,  # ✅ ТОЛЬКО нормализованное значение
        first_name=normalized_first_name,  # ✅ ТОЛЬКО нормализованное значение
        middle_name=name_parts.get("middle_name"),  # ✅ ТОЛЬКО нормализованное значение
        birth_date=birth_date,
        sex=patient_data.get("sex"),
        phone=phone,
        doc_type=patient_data.get("doc_type"),
        doc_number=patient_data.get("doc_number"),
        address=patient_data.get("address")
    )
    
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    
    # ✅ ФИНАЛЬНАЯ ПРОВЕРКА: Убеждаемся, что данные сохранены корректно
    # Это критическая проверка - если после сохранения поля пустые, значит что-то пошло не так
    if not new_patient.last_name or not new_patient.last_name.strip():
        raise ValueError(f"Ошибка сохранения: фамилия пациента не была сохранена (patient_id={new_patient.id})")
    if not new_patient.first_name or not new_patient.first_name.strip():
        raise ValueError(f"Ошибка сохранения: имя пациента не было сохранено (patient_id={new_patient.id})")
    
    return new_patient


def search_patients(
    db: Session,
    query: str,
    limit: int = 10
) -> List[Patient]:
    """
    Поиск пациентов с сортировкой по релевантности.
    
    Сортирует результаты: точное совпадение телефона > точное совпадение ФИО > частичное совпадение
    
    Args:
        db: Сессия базы данных
        query: Поисковый запрос
        limit: Максимальное количество результатов
    
    Returns:
        Список найденных пациентов, отсортированный по релевантности
    """
    if not query:
        return []
    
    search_term = f"%{query}%"
    query_lower = query.lower()
    
    # Получаем всех подходящих пациентов
    patients = db.query(Patient).filter(
        or_(
            Patient.first_name.ilike(search_term),
            Patient.last_name.ilike(search_term),
            Patient.middle_name.ilike(search_term),
            Patient.phone.ilike(search_term),
            Patient.doc_number.ilike(search_term)
        )
    ).limit(limit * 2).all()  # Берем больше, чтобы отсортировать
    
    # Сортируем по релевантности
    def get_relevance_score(patient: Patient) -> int:
        score = 0
        phone = (patient.phone or "").lower()
        full_name = f"{patient.last_name} {patient.first_name} {patient.middle_name or ''}".lower().strip()
        
        # Точное совпадение телефона - высший приоритет
        if phone == query_lower:
            score += 1000
        
        # Точное совпадение ФИО
        if full_name == query_lower:
            score += 500
        
        # Начало телефона
        if phone.startswith(query_lower):
            score += 100
        
        # Начало ФИО
        if full_name.startswith(query_lower):
            score += 50
        
        # Частичное совпадение
        if query_lower in phone or query_lower in full_name:
            score += 10
        
        return score
    
    # Сортируем и ограничиваем
    sorted_patients = sorted(patients, key=get_relevance_score, reverse=True)
    return sorted_patients[:limit]
