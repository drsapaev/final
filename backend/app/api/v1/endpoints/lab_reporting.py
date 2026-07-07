from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.clinic import Doctor
from app.models.visit import Visit
from app.schemas.lab_reporting import (
    LabCatalogAnalyteOut,
    LabCatalogReferenceRangeOut,
    LabCatalogUnitOut,
    LabCriticalFindingOut,
    LabOrderSummaryOut,
    LabReportBulkSaveResponse,
    LabReportInstanceCreate,
    LabReportInstanceOut,
    LabReportInstanceSummaryOut,
    LabReportInstanceUpdate,
    LabReportRenderedFieldOut,
    LabReportRenderedSectionOut,
    LabReportSectionOut,
    LabReportTemplateCreate,
    LabReportTemplateOut,
    LabReportTemplateSummaryOut,
    LabReportTemplateVersionCreate,
    LabReportTemplateVersionOut,
    LabReportTemplateVersionPayload,
    LabReportValueIn,
    LabTemplateResolutionIn,
    LabTemplateResolutionOut,
)
from app.services.lab_report_pdf_service import lab_report_pdf_service
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)

router = APIRouter(prefix="/lab", tags=["lab-reporting"])


def _handle_domain_error(exc: LabReportingDomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _doctor_allowed_visit_ids(
    db: Session,
    current_user,
    requested_visit_ids: list[int] | None = None,
) -> list[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_doctor_ids.add(current_user.id)

    query = db.query(Visit.id).filter(Visit.doctor_id.in_(allowed_doctor_ids))
    if requested_visit_ids:
        requested_ids = {int(visit_id) for visit_id in requested_visit_ids}
        allowed_ids = {row[0] for row in query.filter(Visit.id.in_(requested_ids)).all()}
        if allowed_ids != requested_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        return sorted(allowed_ids)

    return [row[0] for row in query.all()]


def _ensure_doctor_can_read_lab_instance(db: Session, instance, current_user) -> None:
    """LAB-AUDIT-28 P0-1: ранее non-Doctor roles (Lab) bypassed ownership check
    (early return). Теперь все non-Admin роли без Doctor profile получают 403.
    Lab role could read ANY patient's lab results by sequential instance_id
    enumeration — patient_snapshot (full_name, phone, address, DOB, sex),
    all lab values, critical findings.
    """
    if getattr(current_user, "is_superuser", False):
        return
    if getattr(current_user, "role", None) == "Admin":
        return
    # All other roles (including Lab) must go through Doctor ownership check
    if not instance.visit_id:
        raise HTTPException(status_code=403, detail="Access denied")
    _doctor_allowed_visit_ids(db, current_user, requested_visit_ids=[instance.visit_id])


def _template_summary_out(template) -> LabReportTemplateSummaryOut:
    latest_version = max(template.versions, key=lambda item: item.version_no, default=None)
    draft = max(
        (version for version in template.versions if version.status == "DRAFT"),
        key=lambda item: item.version_no,
        default=None,
    )
    published = max(
        (version for version in template.versions if version.status == "PUBLISHED"),
        key=lambda item: item.version_no,
        default=None,
    )
    return LabReportTemplateSummaryOut(
        id=template.id,
        code=template.code,
        name=template.name,
        family=template.family,
        description=template.description,
        is_active=template.is_active,
        draft_version_id=draft.id if draft else None,
        published_version_id=published.id if published else None,
        latest_version_id=latest_version.id if latest_version else None,
    )


def _version_out(service: LabReportingService, version) -> LabReportTemplateVersionOut:
    available_actions = service.template_version_available_actions(version)
    return LabReportTemplateVersionOut(
        id=version.id,
        template_id=version.template_id,
        version_no=version.version_no,
        status=version.status,
        available_actions=available_actions,
        **service.template_version_action_flags(version),
        layout_preset=version.layout_preset,
        page_settings=version.page_settings or {},
        branding_overrides=version.branding_overrides or {},
        signer_defaults=version.signer_defaults or {},
        footer_notes=version.footer_notes,
        created_at=version.created_at,
        updated_at=version.updated_at,
        published_at=version.published_at,
        seed_signature=version.seed_signature,
        sections=[
            LabReportSectionOut(
                id=section.id,
                key=section.key,
                title=section.title,
                sort_order=section.sort_order,
                section_style=section.section_style or {},
                fields=list(section.fields),
            )
            for section in sorted(version.sections, key=lambda item: item.sort_order)
        ],
    )


def _template_out(service: LabReportingService, template) -> LabReportTemplateOut:
    summary = _template_summary_out(template)
    return LabReportTemplateOut(
        **summary.model_dump(),
        versions=[
            _version_out(service, version)
            for version in sorted(template.versions, key=lambda item: item.version_no)
        ],
    )


def _instance_out(service: LabReportingService, instance) -> LabReportInstanceOut:
    sections = service.materialize_instance(instance)
    critical_findings = service.summarize_critical_findings(sections)
    available_actions = service.instance_available_actions(instance)
    return LabReportInstanceOut(
        id=instance.id,
        order_id=instance.order_id,
        visit_id=instance.visit_id,
        patient_id=instance.patient_id,
        template_id=instance.template_id,
        template_version_id=instance.template_version_id,
        status=instance.status,
        patient_snapshot=instance.patient_snapshot or {},
        branding_snapshot=instance.branding_snapshot or {},
        signer_snapshot=instance.signer_snapshot or {},
        supersedes_instance_id=instance.supersedes_instance_id,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        finalized_at=instance.finalized_at,
        printed_at=instance.printed_at,
        template=_template_summary_out(instance.template),
        template_version=_version_out(service, instance.template_version),
        sections=[
            LabReportRenderedSectionOut(
                id=section["id"],
                key=section["key"],
                title=section.get("title"),
                sort_order=section["sort_order"],
                section_style=section.get("section_style") or {},
                fields=[
                    LabReportRenderedFieldOut(**field)
                    for field in section.get("fields") or []
                ],
            )
            for section in sections
        ],
        critical_findings=[
            LabCriticalFindingOut(**finding) for finding in critical_findings
        ],
        available_actions=available_actions,
        **service.instance_action_flags(instance),
    )


def _instance_summary_out(
    service: LabReportingService, instance
) -> LabReportInstanceSummaryOut:
    sections = service.materialize_instance(instance)
    severity_metrics = service.summarize_instance_severity(sections)
    available_actions = service.instance_available_actions(instance)
    return LabReportInstanceSummaryOut(
        id=instance.id,
        patient_id=instance.patient_id,
        visit_id=instance.visit_id,
        template_id=instance.template_id,
        template_version_id=instance.template_version_id,
        status=instance.status,
        created_at=instance.created_at,
        finalized_at=instance.finalized_at,
        printed_at=instance.printed_at,
        patient_snapshot=instance.patient_snapshot or {},
        template=_template_summary_out(instance.template),
        flagged_findings_count=severity_metrics["flagged_findings_count"],
        critical_findings_count=severity_metrics["critical_findings_count"],
        max_flag_severity=severity_metrics["max_flag_severity"],
        available_actions=available_actions,
        **service.instance_action_flags(instance),
    )


@router.get("/orders", response_model=list[LabOrderSummaryOut])
def list_lab_orders(
    status: str | None = Query(default=None, max_length=32),
    patient_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor", "Registrar", "Receptionist", "Cashier")),
):
    service = LabReportingService(db)
    return service.list_orders(status=status, patient_id=patient_id, limit=limit, offset=offset)


# P-03 fix: lab-specific façade для очереди лаборатории.
#
# Раньше frontend (LabPanel.jsx:207) делал прямой fetch к
# /registrar/queues/today?department=lab. Это создавало 3 проблемы:
#   1. Жёсткая связка: любое изменение формата ответа registrar endpoint
#      молча ломало панель лаборатории (regression-тесты registrar этого
#      не покрывали).
#   2. RBAC-конфликт: если админ убирал роль Lab из /registrar/queues,
#      лаборатория «слепла» без видимой причины.
#   3. Бизнес-логика фильтрации «что считать лабораторной записью»
#      была размазана между backend (department=lab) и frontend
#      (formatAppointmentEntry normalize).
#
# Façade решает все 3 проблемы: собственный контракт, собственная RBAC,
# нормализация в lab-специфичный формат на backend.
#
# Внутренне делегирует к существующей функции get_today_queues из
# registrar_integration, чтобы не дублировать ~1700 строк логики.
# Возвращает плоский массив записей (а не nested queues[]) — это
# упрощает frontend и убирает промежуточную нормализацию.
@router.get("/queue/today")
def list_lab_queue_today(
    target_date: str | None = Query(default=None, description="Дата (YYYY-MM-DD), по умолчанию сегодня"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    """
    Получить лабораторную очередь на указанную дату.

    Façade над /registrar/queues/today?department=lab с собственным
    контрактом и RBAC. Возвращает плоский массив записей, нормализованных
    в формат, ожидаемый LabPanel (с latest_lab_report, service_details и т.д.).

    Доступ: Admin, Lab, Doctor.
    """
    # Импортируем внутри функции, чтобы избежать circular import
    # (registrar_integration импортирует много зависимостей).
    from app.api.v1.endpoints.registrar_integration import get_today_queues

    # Делегируем к существующей функции с явным department=lab.
    # current_user передаём как есть — RBAC уже проверена этим endpoint'ом.
    raw_payload = get_today_queues(
        target_date=target_date,
        department="lab",
        db=db,
        current_user=user,
    )

    # Нормализуем nested {queues: [{entries: [...]}]} → плоский массив.
    # Каждая запись получает поля, которые frontend ожидает после
    # formatAppointmentEntry (см. LabPanel.jsx:35).
    flat_entries = []
    for queue in raw_payload.get("queues", []):
        queue_specialty = queue.get("specialty")
        for entry in queue.get("entries", []):
            # Если registrar endpoint уже отдал latest_lab_report — берём как есть.
            # Если нет — оставляем null; frontend сам подтянет через
            # /lab/report-instances?patient_id=... при выборе записи.
            latest_lab_report = entry.get("latest_lab_report")

            flat_entries.append({
                # Идентификаторы
                "id": entry.get("id"),
                "appointment_id": entry.get("appointment_id"),
                "visit_id": entry.get("visit_id"),
                "patient_id": entry.get("patient_id"),
                # Пациент
                "patient_fio": entry.get("patient_name")
                    or entry.get("patient_fio")
                    or "",
                "patient_phone": entry.get("phone", ""),
                "patient_birth_year": entry.get("patient_birth_year", ""),
                "address": entry.get("address", ""),
                # Услуги
                "services": entry.get("services", []),
                "service_codes": entry.get("service_codes", []),
                "service_details": entry.get("service_details", []),
                "service_name": entry.get("service_name", ""),
                "service_id": entry.get("service_id"),
                # Статусы
                "status": entry.get("status"),
                "queue_status": entry.get("status"),
                "status_source": "queue",
                "specialty": queue_specialty,
                "payment_status": entry.get("payment_status"),
                # Время
                "appointment_time": entry.get("visit_time", "")
                    or entry.get("appointment_time", ""),
                "created_at": entry.get("created_at"),
                # Лабораторный бланк (если registrar его отдал)
                "latest_lab_report": latest_lab_report,
                "lab_report_status": latest_lab_report.get("status") if latest_lab_report else None,
                "report_status_source": "lab-report" if latest_lab_report else None,
                "report_instance_id": latest_lab_report.get("id") if latest_lab_report else None,
                "report_template_name": latest_lab_report.get("template_name", "") if latest_lab_report else "",
                "flagged_findings_count": latest_lab_report.get("flagged_findings_count", 0) if latest_lab_report else 0,
                "critical_findings_count": latest_lab_report.get("critical_findings_count", 0) if latest_lab_report else 0,
                "max_flag_severity": latest_lab_report.get("max_flag_severity") if latest_lab_report else None,
            })

    return {
        "entries": flat_entries,
        "total": len(flat_entries),
        "date": raw_payload.get("date"),
        "timezone": raw_payload.get("timezone", "Asia/Tashkent"),
    }


@router.get("/catalog/units", response_model=list[LabCatalogUnitOut])
def list_lab_catalog_units(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    return service.list_catalog_units()


@router.get("/catalog/analytes", response_model=list[LabCatalogAnalyteOut])
def list_lab_catalog_analytes(
    category: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    return service.list_catalog_analytes(category=category)


@router.get(
    "/catalog/reference-ranges",
    response_model=list[LabCatalogReferenceRangeOut],
)
def list_lab_catalog_reference_ranges(
    analyte_code: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    return service.list_catalog_reference_ranges(analyte_code=analyte_code)


@router.get("/templates", response_model=list[LabReportTemplateSummaryOut])
def list_lab_templates(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    return [_template_summary_out(template) for template in service.list_templates()]


@router.post("/template-resolutions/resolve", response_model=LabTemplateResolutionOut)
def resolve_lab_templates_for_context(
    payload: LabTemplateResolutionIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor", "Registrar")),
):
    service = LabReportingService(db)
    try:
        resolution = service.resolve_template_options(**payload.model_dump())
        return LabTemplateResolutionOut(
            patient_id=resolution["patient_id"],
            visit_id=resolution["visit_id"],
            resolution_mode=resolution["resolution_mode"],
            service_codes=resolution["service_codes"],
            service_names=resolution["service_names"],
            matched_service_codes=resolution["matched_service_codes"],
            unmapped_service_codes=resolution["unmapped_service_codes"],
            default_template=(
                _template_summary_out(resolution["default_template"])
                if resolution["default_template"]
                else None
            ),
            allowed_templates=[
                _template_summary_out(template)
                for template in resolution["allowed_templates"]
            ],
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/templates", response_model=LabReportTemplateOut)
def create_lab_template(
    payload: LabReportTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        template = service.create_template(payload.model_dump())
        return _template_out(service, template)
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.get("/templates/{template_id}", response_model=LabReportTemplateOut)
def get_lab_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    try:
        return _template_out(service, service.get_template(template_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/templates/{template_id}/versions", response_model=LabReportTemplateVersionOut)
def create_lab_template_version(
    template_id: int,
    payload: LabReportTemplateVersionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        version = service.create_template_version(template_id, payload.source_version_id)
        return _version_out(service, version)
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.get("/template-versions/{version_id}", response_model=LabReportTemplateVersionOut)
def get_lab_template_version(
    version_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    try:
        version = service.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        return _version_out(service, version)
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.put("/template-versions/{version_id}", response_model=LabReportTemplateVersionOut)
def update_lab_template_version(
    version_id: int,
    payload: LabReportTemplateVersionPayload,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        version = service.update_template_version(version_id, payload.model_dump())
        return _version_out(service, version)
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/template-versions/{version_id}/publish", response_model=LabReportTemplateVersionOut)
def publish_lab_template_version(
    version_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _version_out(service, service.publish_template_version(version_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/template-versions/{version_id}/archive", response_model=LabReportTemplateVersionOut)
def archive_lab_template_version(
    version_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _version_out(service, service.archive_template_version(version_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/templates/{template_id}/clone", response_model=LabReportTemplateOut)
def clone_lab_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _template_out(service, service.clone_template(template_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.get("/report-instances", response_model=list[LabReportInstanceSummaryOut])
def list_lab_report_instances(
    patient_id: int | None = Query(default=None, ge=1),
    visit_ids: list[int] | None = Query(default=None),
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    scoped_visit_ids = visit_ids
    if getattr(user, "role", None) == "Doctor" and not getattr(
        user, "is_superuser", False
    ):
        scoped_visit_ids = _doctor_allowed_visit_ids(
            db,
            user,
            requested_visit_ids=visit_ids,
        )
        if not scoped_visit_ids:
            return []
    return [
        _instance_summary_out(service, instance)
        for instance in service.list_instances(
            patient_id=patient_id,
            visit_ids=scoped_visit_ids,
            status=status,
            limit=limit,
            offset=offset,
        )
    ]


@router.post("/report-instances", response_model=LabReportInstanceOut)
def create_lab_report_instance(
    payload: LabReportInstanceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        actor_name = getattr(user, "full_name", None) or getattr(user, "username", None)
        return _instance_out(
            service,
            service.create_instance(payload.model_dump(), actor_name=actor_name),
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.get("/report-instances/{instance_id}", response_model=LabReportInstanceOut)
def get_lab_report_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    try:
        instance = service.get_instance(instance_id)
        _ensure_doctor_can_read_lab_instance(db, instance, user)
        return _instance_out(service, instance)
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.put("/report-instances/{instance_id}", response_model=LabReportInstanceOut)
def update_lab_report_instance(
    instance_id: int,
    payload: LabReportInstanceUpdate,
    # WF-06 fix: optimistic locking — frontend передаёт updated_at последнего чтения
    expected_updated_at: str | None = Query(default=None, alias="expected_updated_at"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.update_instance(
            instance_id, payload.model_dump(), expected_updated_at=expected_updated_at
        ))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/report-instances/{instance_id}/bulk-values", response_model=LabReportBulkSaveResponse)
def bulk_save_lab_report_values(
    instance_id: int,
    payload: list[LabReportValueIn],
    # WF-06 fix: optimistic locking — frontend передаёт updated_at последнего чтения
    expected_updated_at: str | None = Query(default=None, alias="expected_updated_at"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        instance, updated = service.bulk_upsert_values(
            instance_id,
            [item.model_dump(mode="json") for item in payload],
            expected_updated_at=expected_updated_at,
        )
        return LabReportBulkSaveResponse(
            instance=_instance_out(service, instance),
            updated_field_keys=[item.field_key for item in updated],
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


# L-2 fix: /report-instances/{instance_id}/mark-ready endpoint removed.
# WF-round5: Mark Ready was a functionally empty operation — backend allowed
# the same actions for DRAFT/IN_PROGRESS/READY statuses, so the frontend
# stopped calling this endpoint. The implementation was dead code.


@router.post("/report-instances/{instance_id}/finalize", response_model=LabReportInstanceOut)
def finalize_lab_report(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.finalize(instance_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/report-instances/{instance_id}/revise", response_model=LabReportInstanceOut)
def revise_lab_report(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.revise(instance_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/report-instances/{instance_id}/mark-printed", response_model=LabReportInstanceOut)
def mark_lab_report_printed(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.mark_printed(instance_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.get("/report-instances/{instance_id}/pdf")
def download_lab_report_pdf(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab", "Doctor")),
):
    service = LabReportingService(db)
    try:
        instance = service.get_instance(instance_id)
        _ensure_doctor_can_read_lab_instance(db, instance, user)
        if instance.status not in {"FINALIZED", "PRINTED"}:
            raise LabReportingDomainError(409, "Only finalized reports can be exported to PDF")
        materialized_sections = service.materialize_instance(instance)
        critical_findings = service.summarize_critical_findings(materialized_sections)
        pdf_bytes = lab_report_pdf_service.render_report(
            {
                "template_name": instance.template.name,
                "layout_preset": instance.template_version.layout_preset,
                "page_settings": instance.template_version.page_settings or {},
                "branding": instance.branding_snapshot or {},
                "patient": instance.patient_snapshot or {},
                "signers": instance.signer_snapshot or {},
                "sections": materialized_sections,
                "critical_findings": critical_findings,
                "footer_notes": instance.template_version.footer_notes,
                "report_date": (
                    instance.finalized_at or instance.created_at or datetime.utcnow()
                ).strftime("%d.%m.%Y"),
            }
        )
        filename = f"lab-report-{instance.id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


# =============================================================================
# P1 fix: Doctor-initiated lab orders — allows doctors to order lab tests
# directly from their panel during a patient visit.
# =============================================================================

from pydantic import BaseModel as PydBaseModel


class LabOrderCreate(PydBaseModel):
    """Doctor-initiated lab order request."""
    template_id: int
    patient_id: int
    visit_id: int | None = None
    notes: str | None = None


class LabOrderResponse(PydBaseModel):
    """Response after creating a lab order."""
    instance_id: int
    template_name: str
    patient_id: int
    visit_id: int | None
    status: str
    message: str


@router.post("/orders", response_model=LabOrderResponse)
def create_lab_order(
    payload: LabOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """
    Create a lab order from a doctor panel.

    P1 fix: previously doctors had no way to order lab tests during a visit.
    This endpoint creates a LabReportInstance in DRAFT status linked to the
    visit, so the lab technician sees it in their queue immediately.
    """
    service = LabReportingService(db)
    try:
        template = service.get_template(payload.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        if user.role not in ("Admin", "Lab") and payload.visit_id:
            visit = db.query(Visit).filter(Visit.id == payload.visit_id).first()
            if not visit:
                raise HTTPException(status_code=404, detail="Визит не найден")
            doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
            if doctor and visit.doctor_id != doctor.id:
                raise HTTPException(status_code=403, detail="Нет доступа к этому визиту")

        version = None
        if template.published_version_id:
            version = service.get_template_version(template.published_version_id)
        if not version and template.versions:
            version = template.versions[-1]
        if not version:
            raise HTTPException(status_code=400, detail="У шаблона нет версий")

        actor_name = getattr(user, "full_name", None) or getattr(user, "username", None)
        create_data = {
            "template_id": payload.template_id,
            "patient_id": payload.patient_id,
            "visit_id": payload.visit_id,
            "notes": payload.notes or f"Заказан врачом: {actor_name}",
        }
        instance = service.create_instance(create_data, actor_name=actor_name)

        template_name = template.name or template.code or "Лабораторный отчёт"
        return LabOrderResponse(
            instance_id=instance.id,
            template_name=template_name,
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            status=instance.status,
            message=f"Заказ «{template_name}» создан. Лаборатория увидит его в очереди.",
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)
