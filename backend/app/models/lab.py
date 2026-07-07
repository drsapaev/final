from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, object_session, relationship

from app.db.base_class import Base

FINAL_INSTANCE_STATUSES = {"FINALIZED", "PRINTED"}
IMMUTABLE_TEMPLATE_VERSION_STATUSES = {"PUBLISHED", "ARCHIVED"}


class LabOrder(Base):
    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ordered"
    )  # ordered|in_progress|done|canceled
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    report_instances: Mapped[list[LabReportInstance]] = relationship(
        back_populates="order"
    )


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    test_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_range: Mapped[str | None] = mapped_column(String(64), nullable=True)
    abnormal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class LabCatalogUnit(Base):
    __tablename__ = "lab_catalog_units"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LabCatalogAnalyte(Base):
    __tablename__ = "lab_catalog_analytes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    default_unit_code: Mapped[str | None] = mapped_column(
        ForeignKey("lab_catalog_units.code", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    default_unit: Mapped[LabCatalogUnit | None] = relationship()
    reference_ranges: Mapped[list[LabCatalogReferenceRange]] = relationship(
        back_populates="analyte",
        cascade="all, delete-orphan",
        order_by="LabCatalogReferenceRange.sort_order",
    )


class LabCatalogReferenceRange(Base):
    __tablename__ = "lab_catalog_reference_ranges"
    __table_args__ = (
        UniqueConstraint(
            "analyte_code",
            "sex",
            "age_min_months",
            "age_max_months",
            "sort_order",
            name="uq_lab_catalog_reference_range_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analyte_code: Mapped[str] = mapped_column(
        ForeignKey("lab_catalog_analytes.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    age_min_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_max_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    warning_low: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    warning_high: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    critical_low: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    critical_high: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    analyte: Mapped[LabCatalogAnalyte] = relationship(back_populates="reference_ranges")


class LabReportTemplate(Base):
    __tablename__ = "lab_report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    versions: Mapped[list[LabReportTemplateVersion]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="LabReportTemplateVersion.version_no",
    )
    service_bindings: Mapped[list[LabTemplateServiceBinding]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="LabTemplateServiceBinding.service_code",
    )
    report_instances: Mapped[list[LabReportInstance]] = relationship(
        back_populates="template"
    )


class LabTemplateServiceBinding(Base):
    __tablename__ = "lab_template_service_bindings"
    __table_args__ = (
        UniqueConstraint(
            "service_code",
            "template_code",
            name="uq_lab_template_service_binding",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    template_code: Mapped[str] = mapped_column(
        ForeignKey("lab_report_templates.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    template: Mapped[LabReportTemplate] = relationship(back_populates="service_bindings")


class LabReportTemplateVersion(Base):
    __tablename__ = "lab_report_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_no", name="uq_lab_template_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DRAFT", index=True
    )  # DRAFT|PUBLISHED|ARCHIVED
    layout_preset: Mapped[str] = mapped_column(String(64), nullable=False)
    page_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    branding_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    signer_defaults: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    footer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seed_signature: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    template: Mapped[LabReportTemplate] = relationship(back_populates="versions")
    sections: Mapped[list[LabReportSection]] = relationship(
        back_populates="template_version",
        cascade="all, delete-orphan",
        order_by="LabReportSection.sort_order",
    )
    report_instances: Mapped[list[LabReportInstance]] = relationship(
        back_populates="template_version"
    )


class LabReportSection(Base):
    __tablename__ = "lab_report_sections"
    __table_args__ = (
        UniqueConstraint("template_version_id", "key", name="uq_lab_report_section_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_version_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_template_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section_style: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    template_version: Mapped[LabReportTemplateVersion] = relationship(
        back_populates="sections"
    )
    fields: Mapped[list[LabReportFieldDef]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="LabReportFieldDef.sort_order",
    )


class LabReportFieldDef(Base):
    __tablename__ = "lab_report_field_defs"
    __table_args__ = (
        UniqueConstraint("section_id", "field_key", name="uq_lab_report_field_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analyte_code: Mapped[str | None] = mapped_column(
        ForeignKey("lab_catalog_analytes.code", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit_code: Mapped[str | None] = mapped_column(
        ForeignKey("lab_catalog_units.code", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="text")
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="static_text"
    )
    reference_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_rule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    visibility_rule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    highlight_rule: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    choice_options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    section: Mapped[LabReportSection] = relationship(back_populates="fields")
    analyte: Mapped[LabCatalogAnalyte | None] = relationship()
    unit_catalog: Mapped[LabCatalogUnit | None] = relationship()


class LabReportInstance(Base):
    __tablename__ = "lab_report_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_version_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", index=True
    )  # DRAFT|IN_PROGRESS|READY|FINALIZED|PRINTED
    patient_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    branding_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    signer_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    supersedes_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    printed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    order: Mapped[LabOrder | None] = relationship(back_populates="report_instances")
    template: Mapped[LabReportTemplate] = relationship(back_populates="report_instances")
    template_version: Mapped[LabReportTemplateVersion] = relationship(
        back_populates="report_instances"
    )
    values: Mapped[list[LabReportValue]] = relationship(
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="LabReportValue.id",
    )
    supersedes_instance: Mapped[LabReportInstance | None] = relationship(
        remote_side="LabReportInstance.id"
    )


class LabReportValue(Base):
    __tablename__ = "lab_report_values"
    __table_args__ = (
        UniqueConstraint("instance_id", "field_key", name="uq_lab_report_value_field"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_numeric: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    resolved_reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_flag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_flag_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_flag_severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_flag_meta: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    instance: Mapped[LabReportInstance] = relationship(back_populates="values")


def _previous_status(state_attr, current_value: str | None) -> str | None:
    if state_attr.history.deleted:
        return state_attr.history.deleted[0]
    return current_value


@event.listens_for(LabReportInstance, "before_update", propagate=True)
def _enforce_finalized_instance_immutability(mapper, connection, target) -> None:
    state = inspect(target)
    previous_status = _previous_status(state.attrs.status, target.status)
    if previous_status not in FINAL_INSTANCE_STATUSES:
        return

    dirty_fields = {
        attr.key for attr in state.attrs if attr.history.has_changes() and attr.key != "updated_at"
    }
    allowed_fields = {"status", "printed_at"}
    if (
        previous_status in FINAL_INSTANCE_STATUSES
        and dirty_fields.issubset(allowed_fields)
        and target.status == "PRINTED"
    ):
        return

    raise ValueError("Finalized lab report instances are immutable")


def _assert_parent_instance_mutable(target: LabReportValue) -> None:
    parent_instance = target.instance
    if parent_instance is not None:
        parent_state = inspect(parent_instance)
        previous_status = _previous_status(parent_state.attrs.status, parent_instance.status)
        if previous_status not in FINAL_INSTANCE_STATUSES:
            return

    session = object_session(target)
    if session is None:
        return
    instance_status = session.execute(
        select(LabReportInstance.status).where(LabReportInstance.id == target.instance_id)
    ).scalar_one_or_none()
    if instance_status in FINAL_INSTANCE_STATUSES:
        raise ValueError("Cannot mutate values for finalized lab report instances")


@event.listens_for(LabReportValue, "before_update", propagate=True)
def _prevent_finalized_value_update(mapper, connection, target) -> None:
    _assert_parent_instance_mutable(target)


@event.listens_for(LabReportValue, "before_delete", propagate=True)
def _prevent_finalized_value_delete(mapper, connection, target) -> None:
    _assert_parent_instance_mutable(target)


@event.listens_for(LabReportTemplateVersion, "before_update", propagate=True)
def _enforce_published_template_version_immutability(mapper, connection, target) -> None:
    state = inspect(target)
    previous_status = _previous_status(state.attrs.status, target.status)
    if previous_status not in IMMUTABLE_TEMPLATE_VERSION_STATUSES:
        return

    scalar_field_keys = {attr.key for attr in mapper.column_attrs}
    dirty_fields = {
        attr.key
        for attr in state.attrs
        if attr.key in scalar_field_keys
        and attr.history.has_changes()
        and attr.key not in {"updated_at", "seed_signature"}
    }
    if not dirty_fields:
        return
    if dirty_fields == {"seed_signature"}:
        return
    if (
        previous_status == "PUBLISHED"
        and dirty_fields == {"status"}
        and target.status == "ARCHIVED"
    ):
        return

    raise ValueError("Published lab report template versions are immutable")


@event.listens_for(LabReportTemplateVersion, "before_delete", propagate=True)
def _prevent_published_template_version_delete(mapper, connection, target) -> None:
    if target.status in IMMUTABLE_TEMPLATE_VERSION_STATUSES:
        raise ValueError("Published lab report template versions cannot be deleted")


def _resolve_template_version_status(
    *,
    version_id: int | None = None,
    version: LabReportTemplateVersion | None = None,
    session=None,
) -> str | None:
    if version is not None:
        version_state = inspect(version)
        return _previous_status(version_state.attrs.status, version.status)

    if session is None or version_id is None:
        return None

    return session.execute(
        select(LabReportTemplateVersion.status).where(LabReportTemplateVersion.id == version_id)
    ).scalar_one_or_none()


def _assert_template_structure_mutable(target: LabReportSection | LabReportFieldDef) -> None:
    parent_version = None
    version_id = None

    if isinstance(target, LabReportSection):
        parent_version = target.template_version
        version_id = target.template_version_id
    elif isinstance(target, LabReportFieldDef):
        if target.section is not None:
            parent_version = target.section.template_version
            version_id = target.section.template_version_id
        else:
            session = object_session(target)
            if session is not None and target.section_id is not None:
                version_id = session.execute(
                    select(LabReportSection.template_version_id).where(
                        LabReportSection.id == target.section_id
                    )
                ).scalar_one_or_none()

    session = object_session(target)
    parent_status = _resolve_template_version_status(
        version_id=version_id,
        version=parent_version,
        session=session,
    )
    if parent_status in IMMUTABLE_TEMPLATE_VERSION_STATUSES:
        raise ValueError("Only draft lab report template versions can change structure")


@event.listens_for(LabReportSection, "before_insert", propagate=True)
@event.listens_for(LabReportSection, "before_update", propagate=True)
@event.listens_for(LabReportSection, "before_delete", propagate=True)
def _prevent_published_section_mutation(mapper, connection, target) -> None:
    _assert_template_structure_mutable(target)


@event.listens_for(LabReportFieldDef, "before_insert", propagate=True)
@event.listens_for(LabReportFieldDef, "before_update", propagate=True)
@event.listens_for(LabReportFieldDef, "before_delete", propagate=True)
def _prevent_published_field_mutation(mapper, connection, target) -> None:
    _assert_template_structure_mutable(target)
