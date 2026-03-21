"""Repository helpers for laboratory report templates and instances."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.lab import (
    LabCatalogAnalyte,
    LabCatalogReferenceRange,
    LabCatalogUnit,
    LabOrder,
    LabReportInstance,
    LabReportSection,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabTemplateServiceBinding,
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.setting import Setting
from app.models.visit import Visit, VisitService


class LabReportingApiRepository:
    """Encapsulates ORM access for the lab reporting workflow."""

    def __init__(self, db: Session):
        self.db = db

    def list_orders(
        self,
        *,
        status: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[LabOrder]:
        stmt = (
            select(LabOrder)
            .order_by(LabOrder.created_at.desc(), LabOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(LabOrder.status == status)
        if patient_id:
            stmt = stmt.where(LabOrder.patient_id == patient_id)
        return self.db.execute(stmt).scalars().all()

    def get_order(self, order_id: int) -> LabOrder | None:
        return self.db.get(LabOrder, order_id)

    def find_order_by_visit_and_patient(
        self, *, visit_id: int | None, patient_id: int
    ) -> LabOrder | None:
        stmt = select(LabOrder).where(LabOrder.patient_id == patient_id)
        if visit_id:
            stmt = stmt.where(LabOrder.visit_id == visit_id)
        stmt = stmt.order_by(LabOrder.id.desc()).limit(1)
        return self.db.execute(stmt).scalars().first()

    def add_order(self, order: LabOrder) -> LabOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def list_templates(self) -> list[LabReportTemplate]:
        stmt = (
            select(LabReportTemplate)
            .options(joinedload(LabReportTemplate.versions))
            .order_by(LabReportTemplate.name.asc(), LabReportTemplate.id.asc())
        )
        return self.db.execute(stmt).scalars().unique().all()

    def get_template(self, template_id: int) -> LabReportTemplate | None:
        stmt = (
            select(LabReportTemplate)
            .where(LabReportTemplate.id == template_id)
            .options(
                joinedload(LabReportTemplate.versions)
                .joinedload(LabReportTemplateVersion.sections)
                .joinedload(LabReportSection.fields)
            )
        )
        return self.db.execute(stmt).scalars().unique().first()

    def get_template_by_code(self, code: str) -> LabReportTemplate | None:
        stmt = (
            select(LabReportTemplate)
            .where(LabReportTemplate.code == code)
            .options(
                joinedload(LabReportTemplate.versions)
                .joinedload(LabReportTemplateVersion.sections)
                .joinedload(LabReportSection.fields)
            )
        )
        return self.db.execute(stmt).scalars().unique().first()

    def list_templates_by_codes(self, codes: list[str]) -> list[LabReportTemplate]:
        if not codes:
            return []
        stmt = (
            select(LabReportTemplate)
            .where(LabReportTemplate.code.in_(codes))
            .options(joinedload(LabReportTemplate.versions))
        )
        return self.db.execute(stmt).scalars().unique().all()

    def get_template_version(self, version_id: int) -> LabReportTemplateVersion | None:
        stmt = (
            select(LabReportTemplateVersion)
            .where(LabReportTemplateVersion.id == version_id)
            .options(
                joinedload(LabReportTemplateVersion.template),
                joinedload(LabReportTemplateVersion.sections).joinedload(
                    LabReportSection.fields
                ),
            )
        )
        return self.db.execute(stmt).scalars().unique().first()

    def get_latest_published_version(
        self, template_id: int
    ) -> LabReportTemplateVersion | None:
        stmt = (
            select(LabReportTemplateVersion)
            .where(
                LabReportTemplateVersion.template_id == template_id,
                LabReportTemplateVersion.status == "PUBLISHED",
            )
            .options(
                joinedload(LabReportTemplateVersion.sections).joinedload(
                    LabReportSection.fields
                )
            )
            .order_by(LabReportTemplateVersion.version_no.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().unique().first()

    def get_latest_draft_version(
        self, template_id: int
    ) -> LabReportTemplateVersion | None:
        stmt = (
            select(LabReportTemplateVersion)
            .where(
                LabReportTemplateVersion.template_id == template_id,
                LabReportTemplateVersion.status == "DRAFT",
            )
            .options(
                joinedload(LabReportTemplateVersion.sections).joinedload(
                    LabReportSection.fields
                )
            )
            .order_by(LabReportTemplateVersion.version_no.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().unique().first()

    def get_latest_version(self, template_id: int) -> LabReportTemplateVersion | None:
        stmt = (
            select(LabReportTemplateVersion)
            .where(LabReportTemplateVersion.template_id == template_id)
            .options(
                joinedload(LabReportTemplateVersion.sections).joinedload(
                    LabReportSection.fields
                )
            )
            .order_by(LabReportTemplateVersion.version_no.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().unique().first()

    def add_template(self, template: LabReportTemplate) -> LabReportTemplate:
        self.db.add(template)
        self.db.flush()
        return template

    def add_template_version(
        self, version: LabReportTemplateVersion
    ) -> LabReportTemplateVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def list_service_bindings(
        self, *, service_codes: list[str] | None = None
    ) -> list[LabTemplateServiceBinding]:
        stmt = (
            select(LabTemplateServiceBinding)
            .options(joinedload(LabTemplateServiceBinding.template).joinedload(LabReportTemplate.versions))
            .order_by(
                LabTemplateServiceBinding.service_code.asc(),
                LabTemplateServiceBinding.sort_order.asc(),
                LabTemplateServiceBinding.id.asc(),
            )
        )
        if service_codes:
            stmt = stmt.where(LabTemplateServiceBinding.service_code.in_(service_codes))
        return self.db.execute(stmt).scalars().unique().all()

    def get_service_binding(
        self, *, service_code: str, template_code: str
    ) -> LabTemplateServiceBinding | None:
        stmt = select(LabTemplateServiceBinding).where(
            LabTemplateServiceBinding.service_code == service_code,
            LabTemplateServiceBinding.template_code == template_code,
        )
        return self.db.execute(stmt).scalars().first()

    def add_service_binding(
        self, binding: LabTemplateServiceBinding
    ) -> LabTemplateServiceBinding:
        self.db.add(binding)
        self.db.flush()
        return binding

    def list_catalog_units(self) -> list[LabCatalogUnit]:
        stmt = select(LabCatalogUnit).order_by(
            LabCatalogUnit.sort_order.asc(), LabCatalogUnit.code.asc()
        )
        return self.db.execute(stmt).scalars().all()

    def get_catalog_unit(self, code: str) -> LabCatalogUnit | None:
        return self.db.get(LabCatalogUnit, code)

    def add_catalog_unit(self, unit: LabCatalogUnit) -> LabCatalogUnit:
        self.db.add(unit)
        self.db.flush()
        return unit

    def list_catalog_analytes(
        self, *, category: str | None = None
    ) -> list[LabCatalogAnalyte]:
        stmt = (
            select(LabCatalogAnalyte)
            .options(joinedload(LabCatalogAnalyte.default_unit))
            .order_by(LabCatalogAnalyte.sort_order.asc(), LabCatalogAnalyte.code.asc())
        )
        if category:
            stmt = stmt.where(LabCatalogAnalyte.category == category)
        return self.db.execute(stmt).scalars().all()

    def get_catalog_analyte(self, code: str) -> LabCatalogAnalyte | None:
        stmt = (
            select(LabCatalogAnalyte)
            .where(LabCatalogAnalyte.code == code)
            .options(
                joinedload(LabCatalogAnalyte.default_unit),
                joinedload(LabCatalogAnalyte.reference_ranges),
            )
        )
        return self.db.execute(stmt).scalars().first()

    def add_catalog_analyte(self, analyte: LabCatalogAnalyte) -> LabCatalogAnalyte:
        self.db.add(analyte)
        self.db.flush()
        return analyte

    def list_catalog_reference_ranges(
        self, *, analyte_code: str | None = None
    ) -> list[LabCatalogReferenceRange]:
        stmt = (
            select(LabCatalogReferenceRange)
            .order_by(
                LabCatalogReferenceRange.analyte_code.asc(),
                LabCatalogReferenceRange.sort_order.asc(),
                LabCatalogReferenceRange.id.asc(),
            )
        )
        if analyte_code:
            stmt = stmt.where(LabCatalogReferenceRange.analyte_code == analyte_code)
        return self.db.execute(stmt).scalars().all()

    def add_catalog_reference_range(
        self, reference_range: LabCatalogReferenceRange
    ) -> LabCatalogReferenceRange:
        self.db.add(reference_range)
        self.db.flush()
        return reference_range

    def list_instances(
        self,
        *,
        patient_id: int | None,
        visit_ids: list[int] | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[LabReportInstance]:
        stmt = (
            select(LabReportInstance)
            .options(
                joinedload(LabReportInstance.template),
                joinedload(LabReportInstance.template_version)
                .joinedload(LabReportTemplateVersion.sections)
                .joinedload(LabReportSection.fields),
                joinedload(LabReportInstance.values),
            )
            .order_by(LabReportInstance.created_at.desc(), LabReportInstance.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if patient_id:
            stmt = stmt.where(LabReportInstance.patient_id == patient_id)
        if visit_ids:
            stmt = stmt.where(LabReportInstance.visit_id.in_(visit_ids))
        if status:
            stmt = stmt.where(LabReportInstance.status == status)
        return self.db.execute(stmt).scalars().unique().all()

    def get_instance(self, instance_id: int) -> LabReportInstance | None:
        stmt = (
            select(LabReportInstance)
            .where(LabReportInstance.id == instance_id)
            .options(
                joinedload(LabReportInstance.template),
                joinedload(LabReportInstance.template_version)
                .joinedload(LabReportTemplateVersion.sections)
                .joinedload(LabReportSection.fields),
                joinedload(LabReportInstance.values),
            )
        )
        return self.db.execute(stmt).scalars().unique().first()

    def add_instance(self, instance: LabReportInstance) -> LabReportInstance:
        self.db.add(instance)
        self.db.flush()
        return instance

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.get(Patient, patient_id)

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.get(Visit, visit_id)

    def list_visit_service_context(self, visit_id: int) -> list[dict[str, str | int | None]]:
        visit_services = (
            self.db.execute(
                select(VisitService).where(VisitService.visit_id == visit_id).order_by(VisitService.id.asc())
            )
            .scalars()
            .all()
        )
        context: list[dict[str, str | int | None]] = []
        for visit_service in visit_services:
            service = None
            if visit_service.service_id:
                service = self.db.get(Service, visit_service.service_id)
            context.append(
                {
                    "service_id": visit_service.service_id,
                    "code": getattr(service, "service_code", None)
                    or getattr(service, "code", None)
                    or visit_service.code,
                    "name": getattr(service, "name", None) or visit_service.name,
                }
            )
        return context

    def get_clinic_settings_map(self, category: str = "clinic") -> dict[str, str]:
        stmt = select(Setting).where(Setting.category == category)
        rows = self.db.execute(stmt).scalars().all()
        return {row.key: row.value or "" for row in rows}

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()
