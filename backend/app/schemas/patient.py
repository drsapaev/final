from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import EmailStr, Field, model_validator

from app.schemas.base import ORMModel


class PatientBase(ORMModel):
    # Поддержка как полного ФИО, так и отдельных полей (для Single Source of Truth)
    # full_name - опциональное поле для удобства, если передано - будет нормализовано
    full_name: Optional[str] = Field(
        None,
        max_length=384,
        description="Полное ФИО в формате 'Фамилия Имя Отчество' (альтернатива last_name+first_name)",
    )
    # Для обратной совместимости оставляем last_name и first_name обязательными, если не передан full_name
    # НО: если передан full_name, то last_name и first_name могут быть пустыми (они будут нормализованы из full_name)
    last_name: str = Field(..., max_length=128)
    first_name: str = Field(..., max_length=128)
    middle_name: Optional[str] = Field(None, max_length=128)

    # ✅ ВАЛИДАТОР МОДЕЛИ: Проверяем, что либо full_name передан, либо last_name и first_name не пустые
    @model_validator(mode='before')
    @classmethod
    def validate_name_fields(cls, data: dict):
        # Если данные - это словарь (при создании из JSON)
        if isinstance(data, dict):
            full_name = data.get("full_name")
            last_name = data.get("last_name", "")
            first_name = data.get("first_name", "")

            has_full_name = full_name and str(full_name).strip()
            last_name_clean = (last_name or "").strip() if last_name else ""
            first_name_clean = (first_name or "").strip() if first_name else ""
            has_individual_names = bool(last_name_clean) or bool(first_name_clean)

            # Если передан full_name, то last_name и first_name могут быть пустыми (они будут нормализованы)
            if has_full_name:
                # Если full_name передан, разрешаем пустые last_name и first_name
                # Они будут нормализованы в endpoint
                return data

            # Если full_name не передан, то last_name и first_name обязательны и не должны быть пустыми
            if not has_individual_names:
                raise ValueError(
                    "Необходимо указать либо полное ФИО (full_name), либо фамилию и имя (last_name, first_name)"
                )

            # Очищаем и проверяем отдельные поля
            if not last_name_clean:
                raise ValueError(
                    "Фамилия пациента обязательна для заполнения и не может быть пустой"
                )
            if not first_name_clean:
                raise ValueError(
                    "Имя пациента обязательно для заполнения и не может быть пустым"
                )

            # Обновляем очищенные значения
            data["last_name"] = last_name_clean
            data["first_name"] = first_name_clean

        return data

    birth_date: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=8)  # M|F|X
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    doc_number: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=512)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(ORMModel):
    last_name: Optional[str] = Field(None, max_length=128)
    first_name: Optional[str] = Field(None, max_length=128)
    middle_name: Optional[str] = Field(None, max_length=128)
    birth_date: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=8)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    doc_number: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=512)


class Patient(PatientBase):
    id: int
    created_at: datetime


# Схемы для очередей (оставляем существующие)
class DailyQueueOut(ORMModel):
    id: int
    date: date
    department: str = Field(max_length=64)
    last_ticket: int
    created_at: Optional[datetime] = None


class QueueEntryBase(ORMModel):
    daily_queue_id: int
    patient_id: Optional[int] = None
    ticket_number: int
    status: str = Field(default="waiting", max_length=16)
    window_no: Optional[str] = Field(default=None, max_length=16)
    notes: Optional[str] = Field(default=None, max_length=512)


class QueueEntryOut(QueueEntryBase):
    id: int
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
