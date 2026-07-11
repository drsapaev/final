"""Split from services.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.services_ep._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.services_ep._helpers import (
    router,
    _row_to_out,
)  # noqa: F401


@router.get("", response_model=list[ServiceOut], summary="Каталог услуг")
async def list_services(
    db: Session = Depends(get_db),
    # user=Depends(
    #     require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")
    # ),
    q: str | None = Query(default=None, max_length=120),
    active: bool | None = Query(default=None),
    category_id: int | None = Query(default=None),
    department: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Delegate service listing to the service layer."""
    try:
        rows = ServicesApiService(db).list_services(
            q=q,
            active=active,
            category_id=category_id,
            department=department,
            limit=limit,
            offset=offset,
        )
        return [_row_to_out(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Error listing services: {str(exc)}",
        ) from exc


# ==================== QUEUE GROUPS (SSOT) - MUST BE BEFORE /{service_id} ====================


class QueueGroupInfo(BaseModel):
    """Schema for a single queue group"""
    display_name: str
    display_name_uz: str | None = None
    service_codes: list[str] = []
    service_prefixes: list[str] = []
    exclude_codes: list[str] = []
    queue_tag: str
    tab_key: str


class QueueGroupsResponse(BaseModel):
    """Response schema for queue-groups endpoint"""
    groups: dict[str, QueueGroupInfo] = {}
    code_to_group: dict[str, str] = {}
    tab_to_group: dict[str, str] = {}


@router.get(
    "/queue-groups",
    response_model=QueueGroupsResponse,
    summary="Получить группы очередей (SSOT)",
)
async def get_queue_groups(
    db: Session = Depends(get_db),
):
    """
    ⭐ SSOT: Возвращает структуру групп очередей для синхронизации frontend.

    Используется для:
    - Определения какие услуги относятся к какой вкладке регистратуры
    - Фильтрации записей по отделениям
    - Группировки услуг в одну очередь (Shared Queues)

    Returns:
        - groups: Словарь групп очередей с их настройками
        - code_to_group: Маппинг service_code -> group_key (K01 -> cardiology)
        - tab_to_group: Маппинг tab_key -> group_key (cardio -> cardiology)
    """
    payload = QueueDomainService(db).get_queue_groups_payload()
    groups = {
        key: QueueGroupInfo(**value)
        for key, value in payload["groups"].items()
    }
    return QueueGroupsResponse(
        groups=groups,
        code_to_group=payload["code_to_group"],
        tab_to_group=payload["tab_to_group"],
    )


# ==================== SERVICE CODE MAPPINGS (SSOT) - MUST BE BEFORE /{service_id} ====================

class ServiceCodeRepairItem(BaseModel):
    id: int
    before_code: str | None = None
    before_service_code: str | None = None
    after_code: str | None = None
    after_service_code: str | None = None
    changed: bool = False


class ServiceCodeRepairResponse(BaseModel):
    dry_run: bool
    scanned: int
    updated: int
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    affected_services: list[ServiceCodeRepairItem] = Field(default_factory=list)


@router.post(
    "/admin/repair-code-drift",
    response_model=ServiceCodeRepairResponse,
    summary="Нормализовать code/service_code в каталоге услуг",
)
async def repair_service_code_drift(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    dry_run: bool = Query(
        True,
        description="Только показать план исправления без записи в БД",
    ),
):
    """
    Deterministic repair for legacy service catalog drift.

    Canonical rule for this slice:
    - prefer `service_code` when present
    - otherwise fall back to `code`
    - write the same normalized value back to both fields

    This helper only touches the service catalog rows. It does not rewrite
    historical `VisitService` snapshots.
    """

    services = db.query(Service).order_by(Service.id).all()
    service_by_id = {service.id: service for service in services}
    seen_canonical_codes: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    affected_services: list[ServiceCodeRepairItem] = []

    for service in services:
        source_code = service.service_code or service.code
        if not source_code:
            continue

        canonical_code = normalize_service_code(source_code)
        if not canonical_code:
            continue

        owner_id = seen_canonical_codes.get(canonical_code)
        if owner_id is not None and owner_id != service.id:
            conflicts.append(
                {
                    "canonical_code": canonical_code,
                    "existing_service_id": owner_id,
                    "conflicting_service_id": service.id,
                    "existing_service_name": service_by_id[owner_id].name,
                    "conflicting_service_name": service.name,
                }
            )
            continue

        seen_canonical_codes[canonical_code] = service.id

        current_code = normalize_service_code(service.code) if service.code else None
        current_service_code = (
            normalize_service_code(service.service_code)
            if service.service_code
            else None
        )
        changed = current_code != canonical_code or current_service_code != canonical_code

        if changed:
            affected_services.append(
                ServiceCodeRepairItem(
                    id=service.id,
                    before_code=service.code,
                    before_service_code=service.service_code,
                    after_code=canonical_code,
                    after_service_code=canonical_code,
                    changed=True,
                )
            )

    if conflicts:
        logger.warning(
            "[FIX:SVC-REPAIR] Conflicts detected for service code repair: %s",
            conflicts,
        )
        if not dry_run:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Найдены конфликтующие коды услуг. Сначала устраните "
                        "дубликаты перед применением repair"
                    ),
                    "conflicts": conflicts,
                },
            )

    if not dry_run and affected_services:
        for item in affected_services:
            service = service_by_id[item.id]
            service.code = item.after_code
            service.service_code = item.after_service_code
            db.add(service)

        db.commit()
        logger.info(
            "[FIX:SVC-REPAIR] Applied service code repair: scanned=%s updated=%s conflicts=%s",
            len(services),
            len(affected_services),
            len(conflicts),
        )
    else:
        logger.info(
            "[FIX:SVC-REPAIR] Planned service code repair: scanned=%s updated=%s conflicts=%s dry_run=%s",
            len(services),
            len(affected_services),
            len(conflicts),
            dry_run,
        )

    return ServiceCodeRepairResponse(
        dry_run=dry_run,
        scanned=len(services),
        updated=len(affected_services) if not conflicts or dry_run else 0,
        conflicts=conflicts,
        affected_services=affected_services,
    )


@router.post("", response_model=ServiceOut, summary="Создать услугу")
async def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Delegate service creation to the service layer."""
    try:
        service = ServicesApiService(db).create_service(service_data=service_data)
        return _row_to_out(service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{service_id}", response_model=ServiceOut, summary="Обновить услугу")
async def update_service(
    service_id: int,
    service_data: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Delegate service updates to the service layer."""
    try:
        service = ServicesApiService(db).update_service(
            service_id=service_id,
            service_data=service_data,
        )
        return _row_to_out(service)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{service_id}", summary="Удалить услугу", response_model=dict[str, Any])
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Delegate service deletion to the service layer."""
    try:
        return ServicesApiService(db).delete_service(service_id=service_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ==================== ВРЕМЕННЫЙ ENDPOINT ДЛЯ ВРАЧЕЙ ====================


class DoctorOut(BaseModel):
    id: int
    specialty: str
    cabinet: str | None = None
    active: bool = True

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/admin/doctors",
    response_model=list[DoctorOut],
    summary="Список врачей (временный)",
)
async def list_doctors_temp(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
):
    """Delegate temporary doctor listing to the service layer."""
    # P1 FIX: cap results to prevent unbounded response
    return ServicesApiService(db).list_doctors_temp()[offset:offset + limit]


# ==================== ИСТОРИЯ ИЗМЕНЕНИЙ УСЛУГ (AUDIT LOG) ====================


class ServiceAuditLogOut(BaseModel):
    """Response schema for service audit log"""

    id: int
    service_id: int
    user_id: int | None = None
    action: str
    changes: dict | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    comment: str | None = None
    created_at: datetime

    # Enriched fields
    user_name: str | None = None
    service_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/{service_id}/history",
    response_model=list[ServiceAuditLogOut],
    summary="История изменений услуги",
)
async def get_service_history(
    service_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Получить историю изменений услуги.

    Возвращает все изменения услуги с информацией о том, кто и когда их сделал.
    """
    # Check if service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    audit_service = ServiceAuditService(db)
    logs = audit_service.get_service_history(
        service_id=service_id,
        limit=limit,
        offset=offset,
    )

    # Enrich with user and service names
    result = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "service_id": log.service_id,
            "user_id": log.user_id,
            "action": log.action,
            "changes": log.changes,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "comment": log.comment,
            "created_at": log.created_at,
            "user_name": log.user.full_name if log.user else "Система",
            "service_name": service.name,
        }
        result.append(ServiceAuditLogOut(**log_dict))

    return result


@router.get(
    "/admin/audit/recent",
    response_model=list[ServiceAuditLogOut],
    summary="Последние изменения услуг",
)
async def get_recent_service_changes(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Получить последние изменения всех услуг.

    Полезно для мониторинга активности и аудита.
    """
    audit_service = ServiceAuditService(db)
    logs = audit_service.get_recent_changes(
        limit=limit,
        offset=offset,
    )

    # Enrich with user and service names
    result = []
    for log in logs:
        service = db.query(Service).filter(Service.id == log.service_id).first()
        log_dict = {
            "id": log.id,
            "service_id": log.service_id,
            "user_id": log.user_id,
            "action": log.action,
            "changes": log.changes,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "comment": log.comment,
            "created_at": log.created_at,
            "user_name": log.user.full_name if log.user else "Система",
            "service_name": service.name if service else f"Услуга #{log.service_id}",
        }
        result.append(ServiceAuditLogOut(**log_dict))

    return result


# ==================== РАЗРЕШЕНИЕ УСЛУГ (SSOT) ====================


class ServiceResolveResponse(BaseModel):
    """Response schema для resolve_service endpoint"""

    service_id: int | None = None
    service_code: str | None = None
    normalized_code: str | None = None
    category: str | None = None
    subcategory: str | None = None
    departments: list[str] = []
    ui_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/resolve", response_model=ServiceResolveResponse, summary="Разрешить услугу (SSOT)"
)
async def resolve_service_endpoint(
    service_id: int | None = Query(None, description="ID услуги"),
    code: str | None = Query(None, description="Код услуги"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier")),
):
    """
    Универсальный endpoint для разрешения услуги.

    Возвращает полную информацию об услуге: нормализованный код, категорию,
    подкатегорию, отделения и UI-тип для фронтенда.

    Можно указать либо service_id, либо code (или оба).
    """
    from app.services.service_mapping import resolve_service

    # Валидация: должен быть указан хотя бы один параметр
    if not service_id and not code:
        raise HTTPException(
            status_code=400,
            detail="Необходимо указать либо service_id, либо code (или оба)",
        )

    # Вызов SSOT функции
    result = resolve_service(service_id=service_id, code=code, db=db)

    return ServiceResolveResponse(**result)


# ==================== SERVICE CODE MAPPINGS (SSOT) ====================


class ServiceBatchUpdateRequest(BaseModel):
    """Request schema for batch update"""

    service_ids: list[int] = Field(..., min_items=1, max_items=100)
    updates: dict[str, Any] = Field(..., min_items=1)
    comment: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ServiceBatchUpdateResponse(BaseModel):
    """Response schema for batch update"""

    updated_count: int
    failed_count: int
    updated_services: list[int] = []
    failed_services: list[dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/admin/batch-update",
    response_model=ServiceBatchUpdateResponse,
    summary="Массовое обновление услуг",
)
async def batch_update_services(
    request: ServiceBatchUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Массовое обновление нескольких услуг одновременно.

    Позволяет изменить одинаковые поля у группы услуг.
    Например: изменить цену, активность, категорию и т.д.
    """
    updated_services = []
    failed_services = []
    audit_service = ServiceAuditService(db)

    for service_id in request.service_ids:
        try:
            service = db.query(Service).filter(Service.id == service_id).first()
            if not service:
                failed_services.append({
                    "service_id": service_id,
                    "error": "Услуга не найдена"
                })
                continue

            # Snapshot old state for audit
            old_service_snapshot = Service(
                id=service.id,
                code=service.code,
                service_code=service.service_code,
                name=service.name,
                category_id=service.category_id,
                category_code=service.category_code,
                price=service.price,
                currency=service.currency,
                duration_minutes=service.duration_minutes,
                doctor_id=service.doctor_id,
                department_key=service.department_key,
                queue_tag=service.queue_tag,
                requires_doctor=service.requires_doctor,
                is_consultation=service.is_consultation,
                allow_doctor_price_override=service.allow_doctor_price_override,
                active=service.active,
            )

            # Apply updates
            for field, value in request.updates.items():
                if hasattr(service, field):
                    setattr(service, field, value)

            db.add(service)
            db.flush()  # Flush to catch any DB errors before commit

            # Log audit
            try:
                audit_service.log_service_update(
                    service_id=service.id,
                    old_service=old_service_snapshot,
                    new_service=service,
                    user_id=None,
                    comment=f"Batch update: {request.comment}" if request.comment else "Batch update",
                )
            except Exception as e:
                logger.warning(f"Failed to log batch audit for service {service_id}: {e}")

            updated_services.append(service_id)

        except Exception as e:
            logger.error(f"Failed to update service {service_id}: {e}")
            failed_services.append({
                "service_id": service_id,
                "error": str(e)
            })

    # Commit all changes
    if updated_services:
        db.commit()

    return ServiceBatchUpdateResponse(
        updated_count=len(updated_services),
        failed_count=len(failed_services),
        updated_services=updated_services,
        failed_services=failed_services,
    )


class ServiceCodeMappingsResponse(BaseModel):
    """Response schema for service code mappings endpoint"""

    specialty_to_code: dict = {}
    code_to_name: dict = {}
    category_mapping: dict = {}


@router.get(
    "/code-mappings",
    response_model=ServiceCodeMappingsResponse,
    summary="Получить маппинги кодов услуг (SSOT)",
)
async def get_service_code_mappings(
    db: Session = Depends(get_db),
):
    """
    ⭐ SSOT: Возвращает все маппинги кодов услуг для синхронизации frontend.

    Используется frontend для:
        - specialty_aliases: Алиасы для specialty (derma -> dermatology)
        - specialty_to_code: Маппинг specialty -> service_code
        - code_to_name: Человекочитаемые названия кодов
        - category_mapping: Категории услуг для фильтрации
    """
    payload = QueueDomainService(db).get_service_code_mappings_payload()
    return ServiceCodeMappingsResponse(**payload)


@router.get("/{service_id}", response_model=ServiceOut, summary="Получить услугу по ID")
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier")),
):
    """Delegate service lookup to the service layer."""
    service = ServicesApiService(db).get_service(service_id=service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _row_to_out(service)


