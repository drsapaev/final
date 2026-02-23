from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes, log_critical_change
from app.crud.patient import (
    normalize_patient_name,
    patient as patient_crud,
    validate_birthdate,
)
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient_validation import PatientValidationService

logger = logging.getLogger(__name__)


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.validation_service = PatientValidationService()

    def create_patient(
        self,
        *,
        request: Request,
        patient_in: PatientCreate,
        current_user: User,
    ) -> Patient:
        if patient_in.phone:
            existing_patient = patient_crud.get_patient_by_phone(
                self.db, phone=patient_in.phone
            )
            if existing_patient:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером телефона уже существует",
                )

        if patient_in.doc_number:
            existing_by_doc = (
                self.db.query(Patient)
                .filter(Patient.doc_number == patient_in.doc_number)
                .first()
            )
            if existing_by_doc:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером документа уже зарегистрирован",
                )

        has_full_name = patient_in.full_name and patient_in.full_name.strip()
        has_individual_names = (patient_in.last_name and patient_in.last_name.strip()) or (
            patient_in.first_name and patient_in.first_name.strip()
        )

        if not has_full_name and not has_individual_names:
            raise HTTPException(
                status_code=422,
                detail="Необходимо указать либо полное ФИО (full_name), либо фамилию и имя (last_name, first_name)",
            )

        name_parts = normalize_patient_name(
            full_name=patient_in.full_name.strip() if has_full_name else None,
            last_name=(
                patient_in.last_name.strip()
                if (patient_in.last_name and patient_in.last_name.strip())
                else None
            ),
            first_name=(
                patient_in.first_name.strip()
                if (patient_in.first_name and patient_in.first_name.strip())
                else None
            ),
            middle_name=(
                patient_in.middle_name.strip()
                if (patient_in.middle_name and patient_in.middle_name.strip())
                else None
            ),
        )

        patient_in.last_name = name_parts["last_name"] or ""
        patient_in.first_name = name_parts["first_name"] or ""
        patient_in.middle_name = name_parts.get("middle_name") or None
        if name_parts.get("full_name"):
            patient_in.full_name = name_parts["full_name"]

        patient_dict = patient_in.model_dump(exclude_unset=True)
        patient_dict = self.validation_service.sanitize_patient_data(patient_dict)
        is_valid, errors = self.validation_service.validate_patient_data(patient_dict)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail=f"Validation errors: {'; '.join(errors)}",
            )

        for key, value in patient_dict.items():
            if hasattr(patient_in, key):
                setattr(patient_in, key, value)

        normalized_last_name = (name_parts["last_name"] or "").strip()
        normalized_first_name = (name_parts["first_name"] or "").strip()
        normalized_middle_name = name_parts.get("middle_name")

        logger.debug(
            "Нормализация имени пациента: full_name=%s, last_name=%s, first_name=%s",
            patient_in.full_name,
            patient_in.last_name,
            patient_in.first_name,
        )

        if not normalized_last_name:
            raise HTTPException(
                status_code=422,
                detail="Фамилия пациента обязательна для заполнения и не может быть пустой",
            )
        if not normalized_first_name:
            raise HTTPException(
                status_code=422,
                detail="Имя пациента обязательно для заполнения и не может быть пустым",
            )

        if patient_in.birth_date and not validate_birthdate(patient_in.birth_date):
            raise HTTPException(status_code=400, detail="Некорректная дата рождения")

        validated_patient = PatientCreate(
            last_name=normalized_last_name,
            first_name=normalized_first_name,
            middle_name=normalized_middle_name,
            birth_date=patient_in.birth_date,
            sex=patient_in.sex,
            phone=patient_in.phone,
            doc_number=patient_in.doc_number,
            address=patient_in.address,
        )

        patient = patient_crud.create(db=self.db, obj_in=validated_patient)
        self.db.refresh(patient)
        if not patient.last_name or not patient.last_name.strip():
            raise HTTPException(
                status_code=500,
                detail="Ошибка сохранения: фамилия пациента не была сохранена",
            )
        if not patient.first_name or not patient.first_name.strip():
            raise HTTPException(
                status_code=500,
                detail="Ошибка сохранения: имя пациента не было сохранено",
            )

        _, new_data = extract_model_changes(None, patient)
        log_critical_change(
            db=self.db,
            user_id=current_user.id,
            action="CREATE",
            table_name="patients",
            row_id=patient.id,
            old_data=None,
            new_data=new_data,
            request=request,
            description=f"Создан пациент: {patient.last_name} {patient.first_name}",
        )
        self.db.commit()

        return patient

    def update_patient(
        self,
        *,
        request: Request,
        patient_id: int,
        patient_in: PatientUpdate,
        current_user: User,
    ) -> Patient:
        patient = patient_crud.get(self.db, id=patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Пациент не найден")

        if patient_in.phone and patient_in.phone != patient.phone:
            existing_patient = patient_crud.get_patient_by_phone(
                self.db, phone=patient_in.phone
            )
            if existing_patient and existing_patient.id != patient_id:
                raise HTTPException(
                    status_code=400,
                    detail="Пациент с таким номером телефона уже существует",
                )

        old_data, _ = extract_model_changes(patient, None)
        patient = patient_crud.update(db=self.db, db_obj=patient, obj_in=patient_in)
        self.db.refresh(patient)

        _, new_data = extract_model_changes(None, patient)
        log_critical_change(
            db=self.db,
            user_id=current_user.id,
            action="UPDATE",
            table_name="patients",
            row_id=patient.id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=f"Обновлен пациент: {patient.last_name} {patient.first_name}",
        )
        self.db.commit()

        return patient

    def delete_patient(
        self,
        *,
        request: Request,
        patient_id: int,
        current_user: User,
    ) -> dict[str, str]:
        patient = patient_crud.get(self.db, id=patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Пациент не найден")

        if patient_crud.has_active_appointments(self.db, patient_id=patient_id):
            raise HTTPException(
                status_code=400, detail="Нельзя удалить пациента с активными записями"
            )

        old_data, _ = extract_model_changes(patient, None)
        patient_name = f"{patient.last_name} {patient.first_name}"

        try:
            patient_crud.remove(db=self.db, id=patient_id)
            log_critical_change(
                db=self.db,
                user_id=current_user.id,
                action="DELETE",
                table_name="patients",
                row_id=patient_id,
                old_data=old_data,
                new_data=None,
                request=request,
                description=f"Удален пациент: {patient_name}",
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка удаления пациента: {str(exc)}",
            )

        return {"message": "Пациент успешно удален"}
