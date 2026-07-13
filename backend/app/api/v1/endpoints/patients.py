
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.audit import log_critical_change
from app.core.i18n import t  # noqa: F401
from app.crud.patient import patient as patient_crud
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.schemas import lab as lab_schemas
from app.schemas import patient as patient_schemas
from app.services.patient_portal_service import (
    PatientPortalDomainError,
    PatientPortalService,
)
from app.services.patient_service import PatientService

router = APIRouter()


def _ensure_patient_self_access(current_user: User, patient_id: int) -> None:
    if current_user.role != "Patient":
        return
    if not current_user.patient or current_user.patient.id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/appointments", response_model=list[appointment_schemas.Appointment])
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
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    service = PatientPortalService(db)
    try:
        return service.get_my_appointment_details(
            appointment_id=appointment_id,
            patient_id=current_user.patient.id,
        )
    except PatientPortalDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/results", response_model=list[lab_schemas.LabOrderOut])
def get_my_results(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить результаты анализов текущего пациента
    """
    if not current_user.patient:
        return []

    return PatientPortalService(db).get_my_results(patient_id=current_user.patient.id)


@router.get("/", response_model=list[patient_schemas.Patient])
def list_patients(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: str | None = Query(None, description="Поиск по ФИО, телефону или документу"),
    phone: str | None = Query(None, description="Точный поиск по номеру телефона"),
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


@router.get("/deleted", response_model=list[patient_schemas.Patient])
def get_deleted_patients(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    from app.crud.patient import get_deleted_patients as do_get_deleted

    return do_get_deleted(db, skip=skip, limit=limit)


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
    _ensure_patient_self_access(current_user, patient_id)
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))
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


@router.delete("/{patient_id}", response_model=dict[str, Any])
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


@router.get("/{patient_id}/appointments", response_model=dict[str, Any])
def get_patient_appointments(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", "Doctor", "Patient")),
):
    """
    Получить все записи пациента
    """
    _ensure_patient_self_access(current_user, patient_id)
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    appointments = patient_crud.get_patient_appointments(db, patient_id=patient_id)
    return appointments


# ===================== SOFT-DELETE ENDPOINTS =====================


@router.delete("/{patient_id}/soft", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
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
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

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


@router.post("/{patient_id}/restore", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
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
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

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


# ===================== FAMILY RELATIONS ENDPOINTS =====================


@router.get("/{patient_id}/family", response_model=dict[str, Any])
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
    from app.crud.family_relation import get_patient_as_relative
    from app.crud.family_relation import get_patient_family as do_get_family

    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

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


@router.post("/{patient_id}/family", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def add_family_relation(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    related_patient_id: int = Query(..., description="ID родственника"),
    relation_type: str = Query("other", description="Тип связи: parent, child, guardian, spouse, sibling, other"),
    description: str | None = Query(None, description="Описание связи"),
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

    except ValueError:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.delete("/{patient_id}/family/{relation_id}", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
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


@router.get("/{patient_id}/primary-contact", response_model=dict[str, Any])
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
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

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

