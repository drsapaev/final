from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.patient import patient as patient_crud
from app.core.audit import log_critical_change
from app.models.user import User
from app.schemas import patient as patient_schemas
from app.services.patient_service import PatientService

from app.models.appointment import Appointment
from app.models.lab import LabOrder
from app.schemas import appointment as appointment_schemas
from app.schemas import lab as lab_schemas

router = APIRouter()


@router.get("/appointments", response_model=List[appointment_schemas.Appointment])
def get_my_appointments(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить записи текущего пациента
    """
    if not current_user.patient:
        return []

    appointments = patient_crud.get_patient_appointments(db, patient_id=current_user.patient.id)
    return appointments


@router.get("/appointments/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_my_appointment_details(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить детали записи текущего пациента
    """
    if not current_user.patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Ищем запись, которая принадлежит этому пациенту
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.patient_id == current_user.patient.id
        )
        .first()
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    return appointment


@router.get("/results", response_model=List[lab_schemas.LabOrderOut])
def get_my_results(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить результаты анализов текущего пациента
    """
    if not current_user.patient:
        return []

    # Получаем результаты (LabOrder) для пациента
    results = (
        db.query(LabOrder)
        .filter(LabOrder.patient_id == current_user.patient.id)
        .all()
    )
    
    return results


@router.get("/", response_model=List[patient_schemas.Patient])
def list_patients(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: Optional[str] = Query(None, description="Поиск по ФИО, телефону или документу"),
    phone: Optional[str] = Query(None, description="Точный поиск по номеру телефона"),
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "Nurse")),
):
    """
    Получить список пациентов с возможностью поиска и пагинации

    - q: общий поиск по всем полям (частичное совпадение)
    - phone: точный поиск по телефону (приоритет над q)
    """
    patients = patient_crud.get_patients(
        db, skip=skip, limit=limit, search_query=q, phone=phone
    )
    return patients


@router.post("/", response_model=patient_schemas.Patient)
def create_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_in: patient_schemas.PatientCreate,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    service = PatientService(db)
    return service.create_patient(
        request=request, patient_in=patient_in, current_user=current_user
    )


@router.get("/{patient_id}", response_model=patient_schemas.Patient)
def get_patient(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "Nurse", "Patient")),
):
    """
    Получить пациента по ID
    """
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return patient


@router.put("/{patient_id}", response_model=patient_schemas.Patient)
def update_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    patient_in: patient_schemas.PatientUpdate,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    service = PatientService(db)
    return service.update_patient(
        request=request,
        patient_id=patient_id,
        patient_in=patient_in,
        current_user=current_user,
    )


@router.delete("/{patient_id}")
def delete_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin")),
):
    service = PatientService(db)
    return service.delete_patient(
        request=request, patient_id=patient_id, current_user=current_user
    )


@router.get("/{patient_id}/appointments")
def get_patient_appointments(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor", "Patient")),
):
    """
    Получить все записи пациента
    """
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    appointments = patient_crud.get_patient_appointments(db, patient_id=patient_id)
    return appointments


# ===================== SOFT-DELETE ENDPOINTS =====================


@router.delete("/{patient_id}/soft", status_code=status.HTTP_200_OK)
def soft_delete_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Мягкое удаление пациента (пометка как удалённый).
    
    Пациент остаётся в базе, но не отображается в списках.
    Можно восстановить через POST /{patient_id}/restore
    """
    from app.crud.patient import soft_delete_patient as do_soft_delete
    
    patient = do_soft_delete(db, patient_id=patient_id, deleted_by=current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    # Audit log
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="SOFT_DELETE",
        table_name="patients",
        row_id=patient_id,
        old_data={"is_deleted": False},
        new_data={"is_deleted": True},
        request=request,
        description=f"Мягкое удаление пациента: {patient.short_name()}",
    )
    
    return {"message": "Пациент помечен как удалённый", "patient_id": patient_id}


@router.post("/{patient_id}/restore", status_code=status.HTTP_200_OK)
def restore_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """
    Восстановить удалённого пациента.
    
    Только администраторы могут восстанавливать пациентов.
    """
    from app.crud.patient import restore_patient as do_restore
    
    patient = do_restore(db, patient_id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    # Audit log
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="RESTORE",
        table_name="patients",
        row_id=patient_id,
        old_data={"is_deleted": True},
        new_data={"is_deleted": False},
        request=request,
        description=f"Восстановлен пациент: {patient.short_name()}",
    )
    
    return {"message": "Пациент восстановлен", "patient_id": patient_id}


@router.get("/deleted", response_model=List[patient_schemas.Patient])
def get_deleted_patients(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """
    Получить список удалённых пациентов.
    
    Только администраторы могут видеть удалённых пациентов.
    """
    from app.crud.patient import get_deleted_patients as do_get_deleted
    
    return do_get_deleted(db, skip=skip, limit=limit)


# ===================== FAMILY RELATIONS ENDPOINTS =====================


@router.get("/{patient_id}/family")
def get_patient_family(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить семью/родственников пациента.
    
    Возвращает список связей с данными родственников.
    """
    from app.crud.family_relation import get_patient_family as do_get_family
    from app.crud.family_relation import get_patient_as_relative
    
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    # Получаем родственников пациента
    family = do_get_family(db, patient_id=patient_id)
    
    # Получаем пациентов, для которых данный пациент является родственником
    as_relative_of = get_patient_as_relative(db, patient_id=patient_id)
    
    return {
        "patient_id": patient_id,
        "patient_name": patient.short_name(),
        "family": family,
        "is_relative_of": as_relative_of,
    }


@router.post("/{patient_id}/family", status_code=status.HTTP_201_CREATED)
def add_family_relation(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    related_patient_id: int = Query(..., description="ID родственника"),
    relation_type: str = Query("other", description="Тип связи: parent, child, guardian, spouse, sibling, other"),
    description: Optional[str] = Query(None, description="Описание связи"),
    is_primary_contact: bool = Query(False, description="Основное контактное лицо"),
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Добавить связь с родственником.
    
    Типы связей:
    - parent: родитель
    - child: ребёнок
    - guardian: опекун
    - spouse: супруг(а)
    - sibling: брат/сестра
    - other: другое
    """
    from app.crud.family_relation import create_family_relation
    
    try:
        relation = create_family_relation(
            db,
            patient_id=patient_id,
            related_patient_id=related_patient_id,
            relation_type=relation_type,
            description=description,
            is_primary_contact=is_primary_contact,
            created_by=current_user.id,
        )
        
        return {
            "message": "Связь добавлена",
            "relation_id": relation.id,
            "patient_id": patient_id,
            "related_patient_id": related_patient_id,
            "relation_type": relation_type,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{patient_id}/family/{relation_id}", status_code=status.HTTP_200_OK)
def remove_family_relation(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    relation_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Удалить связь с родственником.
    """
    from app.crud.family_relation import delete_family_relation
    
    success = delete_family_relation(db, relation_id=relation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    
    return {"message": "Связь удалена", "relation_id": relation_id}


@router.get("/{patient_id}/primary-contact")
def get_primary_contact(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить основное контактное лицо для пациента.
    
    Используется для пациентов без телефона (дети, пожилые).
    """
    from app.crud.family_relation import get_primary_contact as do_get_primary
    
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    
    primary = do_get_primary(db, patient_id=patient_id)
    
    if primary:
        return {
            "has_primary_contact": True,
            "contact": {
                "id": primary.id,
                "full_name": primary.short_name(),
                "phone": primary.phone,
            },
        }
    
    return {"has_primary_contact": False, "contact": None}

