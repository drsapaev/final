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
    if getattr(current_user, "role", None) != "Doctor":
        return
    if getattr(current_user, "is_superuser", False):
        return
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


def _version_out(version) -> LabReportTemplateVersionOut:
    return LabReportTemplateVersionOut(
        id=version.id,
        template_id=version.template_id,
        version_no=version.version_no,
        status=version.status,
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


def _template_out(template) -> LabReportTemplateOut:
    summary = _template_summary_out(template)
    return LabReportTemplateOut(
        **summary.model_dump(),
        versions=[_version_out(version) for version in sorted(template.versions, key=lambda item: item.version_no)],
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
        template_version=_version_out(instance.template_version),
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
        return _template_out(template)
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
        return _template_out(service.get_template(template_id))
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
        return _version_out(version)
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
        return _version_out(version)
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
        return _version_out(version)
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
        return _version_out(service.publish_template_version(version_id))
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
        return _version_out(service.archive_template_version(version_id))
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
        return _template_out(service.clone_template(template_id))
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
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.update_instance(instance_id, payload.model_dump()))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/report-instances/{instance_id}/bulk-values", response_model=LabReportBulkSaveResponse)
def bulk_save_lab_report_values(
    instance_id: int,
    payload: list[LabReportValueIn],
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        instance, updated = service.bulk_upsert_values(
            instance_id,
            [item.model_dump(mode="json") for item in payload],
        )
        return LabReportBulkSaveResponse(
            instance=_instance_out(service, instance),
            updated_field_keys=[item.field_key for item in updated],
        )
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


@router.post("/report-instances/{instance_id}/mark-ready", response_model=LabReportInstanceOut)
def mark_lab_report_ready(
    instance_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Lab")),
):
    service = LabReportingService(db)
    try:
        return _instance_out(service, service.mark_ready(instance_id))
    except LabReportingDomainError as exc:
        _handle_domain_error(exc)


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
