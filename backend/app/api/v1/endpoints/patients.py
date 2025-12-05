import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.patient import patient as patient_crud
from app.models.user import User
from app.schemas import patient as patient_schemas
from app.core.audit import log_critical_change, extract_model_changes

logger = logging.getLogger(__name__)

router = APIRouter()


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
    """
    Создать нового пациента.

    Поддерживает как полное ФИО (full_name), так и отдельные поля (last_name, first_name, middle_name).
    Использует единую функцию normalize_patient_name для нормализации (Single Source of Truth).
    """
    # Проверяем, не существует ли уже пациент с таким телефоном
    if patient_in.phone:
        existing_patient = patient_crud.get_patient_by_phone(db, phone=patient_in.phone)
        if existing_patient:
            raise HTTPException(
                status_code=400,
                detail="Пациент с таким номером телефона уже существует",
            )

    # Нормализуем ФИО используя единую функцию (Single Source of Truth)
    from app.crud.patient import normalize_patient_name, validate_birthdate

    # ✅ УЛУЧШЕННАЯ ВАЛИДАЦИЯ: Проверяем входные данные ДО нормализации
    has_full_name = patient_in.full_name and patient_in.full_name.strip()
    has_individual_names = (patient_in.last_name and patient_in.last_name.strip()) or (
        patient_in.first_name and patient_in.first_name.strip()
    )

    if not has_full_name and not has_individual_names:
        raise HTTPException(
            status_code=422,
            detail="Необходимо указать либо полное ФИО (full_name), либо фамилию и имя (last_name, first_name)",
        )
    
    # ✅ ИСПРАВЛЕНО: Нормализуем имя ПЕРЕД валидацией, чтобы валидация работала с разобранными полями
    # Это позволяет использовать full_name, который будет разобран на last_name, first_name, middle_name
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
    
    # Обновляем patient_in с нормализованными именами
    patient_in.last_name = name_parts["last_name"] or ""
    patient_in.first_name = name_parts["first_name"] or ""
    patient_in.middle_name = name_parts.get("middle_name") or None
    if name_parts.get("full_name"):
        patient_in.full_name = name_parts["full_name"]
    
    # ✅ SECURITY: Comprehensive validation and sanitization
    from app.services.patient_validation import PatientValidationService
    
    validation_service = PatientValidationService()
    
    # Convert Pydantic model to dict for validation (после нормализации)
    patient_dict = patient_in.model_dump(exclude_unset=True)
    
    # Sanitize data first
    patient_dict = validation_service.sanitize_patient_data(patient_dict)
    
    # Validate data (теперь с нормализованными именами)
    is_valid, errors = validation_service.validate_patient_data(patient_dict)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail=f"Validation errors: {'; '.join(errors)}",
        )
    
    # Update patient_in with sanitized data
    for key, value in patient_dict.items():
        if hasattr(patient_in, key):
            setattr(patient_in, key, value)

    # ✅ ИСПРАВЛЕНО: Используем результаты первого вызова normalize_patient_name (строки 74-91)
    # Второй вызов был избыточным, так как данные уже нормализованы и обновлены в patient_in
    # Используем уже нормализованные значения из name_parts (первый вызов)
    normalized_last_name = name_parts["last_name"]
    normalized_first_name = name_parts["first_name"]
    normalized_middle_name = name_parts.get("middle_name")

    # ✅ DEBUG: Логируем результат нормализации для диагностики (используем logger вместо print)
    logger.debug(
        "Нормализация имени пациента: full_name=%s, last_name=%s, first_name=%s",
        patient_in.full_name,
        patient_in.last_name,
        patient_in.first_name,
    )
    logger.debug(
        "Результат нормализации: last_name='%s', first_name='%s'",
        normalized_last_name,
        normalized_first_name,
    )

    # ✅ СТРОГАЯ ВАЛИДАЦИЯ: Проверяем, что после нормализации обязательные поля не пустые
    # Это критическая проверка - если после нормализации поля пустые, значит входные данные некорректны
    normalized_last_name = normalized_last_name.strip() if normalized_last_name else ""
    normalized_first_name = (
        normalized_first_name.strip() if normalized_first_name else ""
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

    # Валидируем дату рождения
    if patient_in.birth_date and not validate_birthdate(patient_in.birth_date):
        raise HTTPException(status_code=400, detail="Некорректная дата рождения")

    # ✅ ИСПРАВЛЕНО: Создаем PatientCreate с нормализованными данными
    # full_name НЕ передаем, так как нормализация уже произошла
    # Нормализованные last_name и first_name гарантированно не пустые (проверено выше)
    from app.schemas.patient import PatientCreate

    # Создаем PatientCreate с нормализованными данными (БЕЗ full_name и email)
    # Это гарантирует, что в БД сохранятся только нормализованные поля
    # ВАЖНО: email не существует в модели Patient, поэтому не передаем его
    validated_patient = PatientCreate(
        last_name=normalized_last_name,
        first_name=normalized_first_name,
        middle_name=normalized_middle_name,
        birth_date=patient_in.birth_date,
        sex=patient_in.sex,
        phone=patient_in.phone,
        # email НЕ передаем - это поле не существует в модели Patient
        doc_number=patient_in.doc_number,
        address=patient_in.address,
        # full_name НЕ передаем - он уже использован для нормализации
    )

    # Создаем пациента через CRUD (full_name будет исключен в crud.base.create)
    patient = patient_crud.create(db=db, obj_in=validated_patient)

    # ✅ ФИНАЛЬНАЯ ПРОВЕРКА: Убеждаемся, что данные сохранены корректно
    # Это критическая проверка - если после сохранения поля пустые, значит что-то пошло не так
    db.refresh(patient)
    if not patient.last_name or not patient.last_name.strip():
        raise HTTPException(
            status_code=500,
            detail="Ошибка сохранения: фамилия пациента не была сохранена",
        )
    if not patient.first_name or not patient.first_name.strip():
        raise HTTPException(
            status_code=500, detail="Ошибка сохранения: имя пациента не было сохранено"
        )

    # ✅ AUDIT LOG: Логируем создание пациента (юридически обязательное)
    _, new_data = extract_model_changes(None, patient)
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        table_name="patients",
        row_id=patient.id,
        old_data=None,
        new_data=new_data,
        request=request,
        description=f"Создан пациент: {patient.last_name} {patient.first_name}",
    )
    db.commit()

    return patient


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
    """
    Обновить данные пациента
    """
    patient = patient_crud.get(db, id=patient_id)
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

    # Сохраняем старые данные для аудит-лога
    old_data, _ = extract_model_changes(patient, None)
    
    patient = patient_crud.update(db=db, db_obj=patient, obj_in=patient_in)
    
    # ✅ AUDIT LOG: Логируем обновление пациента
    db.refresh(patient)
    _, new_data = extract_model_changes(None, patient)
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        table_name="patients",
        row_id=patient.id,
        old_data=old_data,
        new_data=new_data,
        request=request,
        description=f"Обновлен пациент: {patient.last_name} {patient.first_name}",
    )
    db.commit()
    
    return patient


@router.delete("/{patient_id}")
def delete_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """
    Удалить пациента
    """
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Проверяем, есть ли у пациента активные записи
    if patient_crud.has_active_appointments(db, patient_id=patient_id):
        raise HTTPException(
            status_code=400, detail="Нельзя удалить пациента с активными записями"
        )

    # ✅ Сохраняем данные для аудита перед удалением
    old_data, _ = extract_model_changes(patient, None)
    patient_name = f"{patient.last_name} {patient.first_name}"
    
    # ✅ FIX: Выполняем удаление и логирование в одной транзакции для атомарности
    try:
        patient_crud.remove(db=db, id=patient_id)
        
        # ✅ AUDIT LOG: Логируем удаление пациента в той же транзакции
        log_critical_change(
            db=db,
            user_id=current_user.id,
            action="DELETE",
            table_name="patients",
            row_id=patient_id,
            old_data=old_data,
            new_data=None,
            request=request,
            description=f"Удален пациент: {patient_name}",
        )
        
        # ✅ FIX: Один commit для атомарности - если аудит не запишется, удаление откатится
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления пациента: {str(e)}",
        )
    
    return {"message": "Пациент успешно удален"}


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
