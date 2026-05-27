"""Schemas for laboratory report templates and instances."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LabOrderSummaryOut(BaseModel):
    id: int
    patient_id: int | None = None
    visit_id: int | None = None
    status: str
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LabReportFieldDefPayload(BaseModel):
    analyte_code: str | None = Field(default=None, max_length=64)
    unit_code: str | None = Field(default=None, max_length=32)
    field_key: str = Field(..., max_length=64)
    label: str = Field(..., max_length=255)
    value_type: str = Field(default="text", max_length=16)
    unit: str | None = Field(default=None, max_length=64)
    reference_mode: str = Field(default="static_text", max_length=16)
    reference_text: str | None = None
    reference_rule: dict[str, Any] | None = None
    visibility_rule: dict[str, Any] | None = None
    highlight_rule: dict[str, Any] | None = None
    choice_options: list[str] | None = None
    sort_order: int = 0
    required: bool = False


class LabReportSectionPayload(BaseModel):
    key: str = Field(..., max_length=64)
    title: str | None = Field(default=None, max_length=255)
    sort_order: int = 0
    section_style: dict[str, Any] | None = None
    fields: list[LabReportFieldDefPayload] = Field(default_factory=list)


class LabReportTemplateVersionPayload(BaseModel):
    layout_preset: str = Field(..., max_length=64)
    page_settings: dict[str, Any] = Field(default_factory=dict)
    branding_overrides: dict[str, Any] = Field(default_factory=dict)
    signer_defaults: dict[str, Any] = Field(default_factory=dict)
    footer_notes: str | None = None
    sections: list[LabReportSectionPayload] = Field(default_factory=list)


class LabReportTemplateCreate(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    family: str = Field(..., max_length=64)
    description: str | None = None
    is_active: bool = True
    initial_version: LabReportTemplateVersionPayload


class LabReportTemplateVersionCreate(BaseModel):
    source_version_id: int | None = None


class LabReportTemplateSummaryOut(BaseModel):
    id: int
    code: str
    name: str
    family: str
    description: str | None = None
    is_active: bool
    draft_version_id: int | None = None
    published_version_id: int | None = None
    latest_version_id: int | None = None


class LabReportFieldDefOut(BaseModel):
    id: int
    analyte_code: str | None = None
    unit_code: str | None = None
    field_key: str
    label: str
    value_type: str
    unit: str | None = None
    reference_mode: str
    reference_text: str | None = None
    reference_rule: dict[str, Any] | None = None
    visibility_rule: dict[str, Any] | None = None
    highlight_rule: dict[str, Any] | None = None
    choice_options: list[str] | None = None
    sort_order: int
    required: bool

    model_config = ConfigDict(from_attributes=True)


class LabReportSectionOut(BaseModel):
    id: int
    key: str
    title: str | None = None
    sort_order: int
    section_style: dict[str, Any]
    fields: list[LabReportFieldDefOut]

    model_config = ConfigDict(from_attributes=True)


class LabReportTemplateVersionOut(BaseModel):
    id: int
    template_id: int
    version_no: int
    status: str
    available_actions: list[str] = Field(default_factory=list)
    can_update: bool = False
    can_publish: bool = False
    can_create_draft: bool = False
    layout_preset: str
    page_settings: dict[str, Any]
    branding_overrides: dict[str, Any]
    signer_defaults: dict[str, Any]
    footer_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    seed_signature: str | None = None
    sections: list[LabReportSectionOut]

    model_config = ConfigDict(from_attributes=True)


class LabReportTemplateOut(BaseModel):
    id: int
    code: str
    name: str
    family: str
    description: str | None = None
    is_active: bool
    draft_version_id: int | None = None
    published_version_id: int | None = None
    latest_version_id: int | None = None
    versions: list[LabReportTemplateVersionOut]


class LabServiceContextItemIn(BaseModel):
    service_id: int | None = None
    code: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=255)


class LabReportInstanceCreate(BaseModel):
    patient_id: int
    template_id: int
    order_id: int | None = None
    appointment_id: int | None = None
    visit_id: int | None = None
    template_version_id: int | None = None
    service_codes: list[str] = Field(default_factory=list)
    service_items: list[LabServiceContextItemIn] = Field(default_factory=list)
    signer_overrides: dict[str, Any] = Field(default_factory=dict)
    branding_overrides: dict[str, Any] = Field(default_factory=dict)


class LabReportInstanceUpdate(BaseModel):
    signer_snapshot: dict[str, Any] | None = None
    branding_snapshot: dict[str, Any] | None = None


class LabReportValueIn(BaseModel):
    field_key: str = Field(..., max_length=64)
    value_text: str | None = None
    value_numeric: Decimal | None = None
    comment: str | None = None


class LabReportRenderedFieldOut(BaseModel):
    id: int
    analyte_code: str | None = None
    unit_code: str | None = None
    field_key: str
    label: str
    value_type: str
    unit: str | None = None
    required: bool
    reference_mode: str
    reference_text: str | None = None
    visibility_rule: dict[str, Any] | None = None
    highlight_rule: dict[str, Any] | None = None
    value_text: str | None = None
    value_numeric: Decimal | None = None
    comment: str | None = None
    resolved_flag: str | None = None
    resolved_flag_source: str | None = None
    resolved_flag_severity: int | None = None
    resolved_flag_meta: dict[str, Any] | None = None


class LabReportRenderedSectionOut(BaseModel):
    id: int
    key: str
    title: str | None = None
    sort_order: int
    section_style: dict[str, Any]
    fields: list[LabReportRenderedFieldOut]


class LabCriticalFindingOut(BaseModel):
    section_key: str
    section_title: str | None = None
    field_key: str
    label: str
    analyte_code: str | None = None
    unit: str | None = None
    value_text: str | None = None
    value_numeric: Decimal | None = None
    value_display: str
    reference_text: str | None = None
    resolved_flag: str
    resolved_flag_source: str | None = None
    resolved_flag_severity: int
    resolved_flag_meta: dict[str, Any] | None = None
    threshold_display: str | None = None


class LabReportInstanceOut(BaseModel):
    id: int
    order_id: int | None = None
    visit_id: int | None = None
    patient_id: int
    template_id: int
    template_version_id: int
    status: str
    patient_snapshot: dict[str, Any]
    branding_snapshot: dict[str, Any]
    signer_snapshot: dict[str, Any]
    supersedes_instance_id: int | None = None
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None = None
    printed_at: datetime | None = None
    template: LabReportTemplateSummaryOut
    template_version: LabReportTemplateVersionOut
    sections: list[LabReportRenderedSectionOut]
    critical_findings: list[LabCriticalFindingOut] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
    can_edit: bool = False
    can_save_draft: bool = False
    can_mark_ready: bool = False
    can_finalize: bool = False
    can_revise: bool = False
    can_print: bool = False


class LabReportInstanceSummaryOut(BaseModel):
    id: int
    patient_id: int
    visit_id: int | None = None
    template_id: int
    template_version_id: int
    status: str
    created_at: datetime
    finalized_at: datetime | None = None
    printed_at: datetime | None = None
    patient_snapshot: dict[str, Any]
    template: LabReportTemplateSummaryOut
    flagged_findings_count: int = 0
    critical_findings_count: int = 0
    max_flag_severity: int | None = None
    available_actions: list[str] = Field(default_factory=list)
    can_edit: bool = False
    can_save_draft: bool = False
    can_mark_ready: bool = False
    can_finalize: bool = False
    can_revise: bool = False
    can_print: bool = False


class LabReportBulkSaveResponse(BaseModel):
    instance: LabReportInstanceOut
    updated_field_keys: list[str]


class LabCatalogUnitOut(BaseModel):
    code: str
    name: str
    symbol: str
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LabCatalogAnalyteOut(BaseModel):
    code: str
    name: str
    short_name: str | None = None
    category: str
    default_unit_code: str | None = None
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LabCatalogReferenceRangeOut(BaseModel):
    id: int
    analyte_code: str
    sex: str | None = None
    age_min_months: int | None = None
    age_max_months: int | None = None
    text: str | None = None
    low: Decimal | None = None
    high: Decimal | None = None
    warning_low: Decimal | None = None
    warning_high: Decimal | None = None
    critical_low: Decimal | None = None
    critical_high: Decimal | None = None
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LabTemplateResolutionIn(BaseModel):
    patient_id: int | None = Field(default=None, ge=1)
    appointment_id: int | None = Field(default=None, ge=1)
    visit_id: int | None = Field(default=None, ge=1)
    service_codes: list[str] = Field(default_factory=list)
    service_items: list[LabServiceContextItemIn] = Field(default_factory=list)


class LabTemplateResolutionOut(BaseModel):
    patient_id: int | None = None
    visit_id: int | None = None
    resolution_mode: str
    service_codes: list[str] = Field(default_factory=list)
    service_names: list[str] = Field(default_factory=list)
    matched_service_codes: list[str] = Field(default_factory=list)
    unmapped_service_codes: list[str] = Field(default_factory=list)
    default_template: LabReportTemplateSummaryOut | None = None
    allowed_templates: list[LabReportTemplateSummaryOut] = Field(default_factory=list)
