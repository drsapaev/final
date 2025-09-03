from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.patient import patient as patient_crud
from app.models.user import User
from app.schemas import patient as patient_schemas

router = APIRouter()


@router.get("/", response_model=List[patient_schemas.Patient])
def list_patients(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: Optional[str] = Query(None, description="Поиск по ФИО, телефону или документу"),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить список пациентов с возможностью поиска и пагинации
    """
    patients = patient_crud.get_patients(db, skip=skip, limit=limit, search_query=q)
    return patients


@router.post("/", response_model=patient_schemas.Patient)
def create_patient(
    *,
    db: Session = Depends(deps.get_db),
    patient_in: patient_schemas.PatientCreate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Создать нового пациента
    """
    # Проверяем, не существует ли уже пациент с таким телефоном
    existing_patient = patient_crud.get_patient_by_phone(db, phone=patient_in.phone)
    if existing_patient:
        raise HTTPException(
            status_code=400, detail="Пациент с таким номером телефона уже существует"
        )

    patient = patient_crud.create_patient(db=db, patient=patient_in)
    return patient


@router.get("/{patient_id}", response_model=patient_schemas.Patient)
def get_patient(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить пациента по ID
    """
    patient = patient_crud.get_patient(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return patient


@router.put("/{patient_id}", response_model=patient_schemas.Patient)
def update_patient(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    patient_in: patient_schemas.PatientUpdate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Обновить данные пациента
    """
    patient = patient_crud.get_patient(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Проверяем, не занят ли телефон другим пациентом
    if patient_in.phone and patient_in.phone != patient.phone:
        existing_patient = patient_crud.get_patient_by_phone(db, phone=patient_in.phone)
        if existing_patient and existing_patient.id != patient_id:
            raise HTTPException(
                status_code=400,
                detail="Пациент с таким номером телефона уже существует",
            )

    patient = patient_crud.update_patient(db=db, db_obj=patient, obj_in=patient_in)
    return patient


@router.delete("/{patient_id}")
def delete_patient(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Удалить пациента
    """
    patient = patient_crud.get_patient(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Проверяем, есть ли у пациента активные записи
    if patient_crud.has_active_appointments(db, patient_id=patient_id):
        raise HTTPException(
            status_code=400, detail="Нельзя удалить пациента с активными записями"
        )

    patient_crud.delete_patient(db=db, id=patient_id)
    return {"message": "Пациент успешно удален"}


@router.get("/{patient_id}/appointments")
def get_patient_appointments(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить все записи пациента
    """
    patient = patient_crud.get_patient(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    appointments = patient_crud.get_patient_appointments(db, patient_id=patient_id)
    return appointments
