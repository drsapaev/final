"""Service layer for laboratory templates, versions, instances, and PDF workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabCatalogAnalyte,
    LabCatalogReferenceRange,
    LabCatalogUnit,
    LabOrder,
    LabReportFieldDef,
    LabReportInstance,
    LabReportSection,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabReportValue,
    LabResult,
    LabTemplateServiceBinding,
)
from app.models.user import User
from app.models.clinic import Doctor
from app.repositories.lab_reporting_api_repository import LabReportingApiRepository
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.lab_catalog_seed_data import (
    DEFAULT_LAB_ANALYTE_DEFINITIONS,
    DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS,
    DEFAULT_LAB_UNIT_DEFINITIONS,
)
from app.services.lab_seed_data import DEFAULT_LAB_TEMPLATE_DEFINITIONS
from app.services.lab_template_binding_seed_data import (
    DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS,
)
from app.services.notifications import notification_sender_service
from app.services.service_mapping import normalize_service_code

logger = logging.getLogger(__name__)

FLAG_SEVERITY_RANKS = {
    "warning": 100,
    "low": 200,
    "high": 200,
    "abnormal": 250,
    "critical": 300,
}


@dataclass
class LabReportingDomainError(Exception):
    status_code: int
    detail: str


class LabReportingService:
    """Orchestrates lab template and report instance workflows."""

    def __init__(
        self,
        db: Session,
        repository: LabReportingApiRepository | None = None,
    ):
        self.db = db
        self.repository = repository or LabReportingApiRepository(db)
        self._catalog_unit_cache: dict[str, LabCatalogUnit | None] = {}
        self._catalog_analyte_cache: dict[str, LabCatalogAnalyte | None] = {}
        self._catalog_reference_cache: dict[str, list[LabCatalogReferenceRange]] = {}

    def list_orders(
        self,
        *,
        status: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[LabOrder]:
        logger.info(
            "[LAB] list_orders status=%s has_patient_filter=%s limit=%s offset=%s",
            status,
            patient_id is not None,
            limit,
            offset,
        )
        return self.repository.list_orders(
            status=status,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )

    def list_templates(self) -> list[LabReportTemplate]:
        logger.info("[LAB] list_templates")
        self.ensure_default_catalog()
        self.ensure_default_templates()
        return self.repository.list_templates()

    def get_template(self, template_id: int) -> LabReportTemplate:
        logger.info("[LAB] get_template template_id=%s", template_id)
        self.ensure_default_catalog()
        self.ensure_default_templates()
        template = self.repository.get_template(template_id)
        if not template:
            raise LabReportingDomainError(404, "Lab report template not found")
        return template

    def resolve_template_options(
        self,
        *,
        patient_id: int | None = None,
        appointment_id: int | None = None,
        visit_id: int | None = None,
        service_codes: list[str] | None = None,
        service_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "[LAB] resolve_template_options has_patient_context=%s has_appointment_context=%s has_visit_context=%s service_code_count=%s service_item_count=%s",
            patient_id is not None,
            appointment_id is not None,
            visit_id is not None,
            len(service_codes or []),
            len(service_items or []),
        )
        self.ensure_default_templates()
        self.ensure_default_template_bindings()

        resolved_visit_id = self._resolve_visit_context(
            visit_id=visit_id,
            appointment_id=appointment_id,
            create_if_missing=False,
        )
        service_context = self._collect_service_context(
            visit_id=resolved_visit_id,
            service_codes=service_codes,
            service_items=service_items,
        )
        normalized_codes = service_context["service_codes"]
        service_names = service_context["service_names"]
        if not normalized_codes:
            return {
                "patient_id": patient_id,
                "visit_id": resolved_visit_id,
                "resolution_mode": "no_service_context",
                "service_codes": [],
                "service_names": service_names,
                "matched_service_codes": [],
                "unmapped_service_codes": [],
                "default_template": None,
                "allowed_templates": [],
            }

        bindings = [
            binding
            for binding in self.repository.list_service_bindings(service_codes=normalized_codes)
            if binding.is_active
        ]
        matched_codes = sorted({binding.service_code for binding in bindings})
        unmapped_codes = [code for code in normalized_codes if code not in matched_codes]

        template_rank_by_code: dict[str, tuple[int, int, int]] = {}
        default_template_code: str | None = None
        service_order = {code: index for index, code in enumerate(normalized_codes)}

        for binding in bindings:
            template_rank = (
                service_order.get(binding.service_code, len(service_order)),
                0 if binding.is_default else 1,
                binding.sort_order,
            )
            current_rank = template_rank_by_code.get(binding.template_code)
            if current_rank is None or template_rank < current_rank:
                template_rank_by_code[binding.template_code] = template_rank
            if binding.is_default:
                if default_template_code is None:
                    default_template_code = binding.template_code
                else:
                    current_default_rank = template_rank_by_code.get(
                        default_template_code,
                        (len(service_order), 1, 10**9),
                    )
                    if template_rank < current_default_rank:
                        default_template_code = binding.template_code

        ordered_template_codes = [
            item[0]
            for item in sorted(
                template_rank_by_code.items(),
                key=lambda item: (item[1], item[0]),
            )
        ]
        templates_by_code = {
            template.code: template
            for template in self.repository.list_templates_by_codes(ordered_template_codes)
            if template.is_active
        }
        allowed_templates = [
            templates_by_code[template_code]
            for template_code in ordered_template_codes
            if template_code in templates_by_code
        ]
        default_template = (
            templates_by_code.get(default_template_code)
            if default_template_code
            else (allowed_templates[0] if allowed_templates else None)
        )

        return {
            "patient_id": patient_id,
            "visit_id": resolved_visit_id,
            "resolution_mode": "mapped" if allowed_templates else "unmapped",
            "service_codes": normalized_codes,
            "service_names": service_names,
            "matched_service_codes": matched_codes,
            "unmapped_service_codes": unmapped_codes,
            "default_template": default_template,
            "allowed_templates": allowed_templates,
        }

    def list_catalog_units(self) -> list[LabCatalogUnit]:
        logger.info("[LAB] list_catalog_units")
        self.ensure_default_catalog()
        return self.repository.list_catalog_units()

    def list_catalog_analytes(
        self, *, category: str | None = None
    ) -> list[LabCatalogAnalyte]:
        logger.info("[LAB] list_catalog_analytes category=%s", category)
        self.ensure_default_catalog()
        return self.repository.list_catalog_analytes(category=category)

    def list_catalog_reference_ranges(
        self, *, analyte_code: str | None = None
    ) -> list[LabCatalogReferenceRange]:
        logger.info("[LAB] list_catalog_reference_ranges analyte_code=%s", analyte_code)
        self.ensure_default_catalog()
        return self.repository.list_catalog_reference_ranges(analyte_code=analyte_code)

    def create_template(self, payload: dict[str, Any]) -> LabReportTemplate:
        logger.info("[LAB] create_template code=%s", payload.get("code"))
        self.ensure_default_catalog()
        if self.repository.get_template_by_code(payload["code"]):
            raise LabReportingDomainError(400, "Template code already exists")
        self._validate_catalog_links(payload["initial_version"].get("sections") or [])

        template = LabReportTemplate(
            code=payload["code"],
            name=payload["name"],
            family=payload["family"],
            description=payload.get("description"),
            is_active=payload.get("is_active", True),
        )
        self.repository.add_template(template)
        version_payload = payload["initial_version"]
        version = LabReportTemplateVersion(
            template_id=template.id,
            version_no=1,
            status="DRAFT",
            layout_preset=version_payload["layout_preset"],
            page_settings=version_payload.get("page_settings") or {},
            branding_overrides=version_payload.get("branding_overrides") or {},
            signer_defaults=version_payload.get("signer_defaults") or {},
            footer_notes=version_payload.get("footer_notes"),
            seed_signature=None,
        )
        self.repository.add_template_version(version)
        self._replace_version_sections(version, version_payload.get("sections") or [])
        self.repository.commit()
        logger.info("[LAB] create_template completed template_id=%s", template.id)
        return self.get_template(template.id)

    def create_template_version(
        self, template_id: int, source_version_id: int | None = None
    ) -> LabReportTemplateVersion:
        logger.info(
            "[LAB] create_template_version template_id=%s source_version_id=%s",
            template_id,
            source_version_id,
        )
        template = self.get_template(template_id)
        source = (
            self.repository.get_template_version(source_version_id)
            if source_version_id
            else self.repository.get_latest_draft_version(template.id)
            or self.repository.get_latest_published_version(template.id)
            or self.repository.get_latest_version(template.id)
        )
        next_version = (
            self.repository.get_latest_version(template.id).version_no + 1
            if template.versions
            else 1
        )
        draft = LabReportTemplateVersion(
            template_id=template.id,
            version_no=next_version,
            status="DRAFT",
            layout_preset=source.layout_preset if source else "lab_table_classic_v1",
            page_settings=deepcopy(source.page_settings) if source else {"paper_size": "A4"},
            branding_overrides=deepcopy(source.branding_overrides) if source else {},
            signer_defaults=deepcopy(source.signer_defaults) if source else {},
            footer_notes=source.footer_notes if source else None,
            seed_signature=None,
        )
        self.repository.add_template_version(draft)
        if source:
            self._replace_version_sections(draft, self._sections_to_payload(source.sections))
        self.repository.commit()
        logger.info("[LAB] create_template_version created version_id=%s", draft.id)
        return self.repository.get_template_version(draft.id)

    def template_version_available_actions(
        self, version: LabReportTemplateVersion,
    ) -> list[str]:
        if version.status == "DRAFT":
            return ["update", "publish"]
        return ["create_draft"]

    def template_version_action_flags(
        self, version: LabReportTemplateVersion,
    ) -> dict[str, bool]:
        available_actions = set(self.template_version_available_actions(version))
        return {
            "can_update": "update" in available_actions,
            "can_publish": "publish" in available_actions,
            "can_create_draft": "create_draft" in available_actions,
        }

    def update_template_version(
        self, version_id: int, payload: dict[str, Any]
    ) -> LabReportTemplateVersion:
        logger.info("[LAB] update_template_version version_id=%s", version_id)
        self.ensure_default_catalog()
        self._validate_catalog_links(payload.get("sections") or [])
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        if version.status != "DRAFT":
            raise LabReportingDomainError(409, "Only draft versions can be updated")

        version.layout_preset = payload["layout_preset"]
        version.page_settings = payload.get("page_settings") or {}
        version.branding_overrides = payload.get("branding_overrides") or {}
        version.signer_defaults = payload.get("signer_defaults") or {}
        version.footer_notes = payload.get("footer_notes")
        version.seed_signature = None
        self._replace_version_sections(version, payload.get("sections") or [])
        self.repository.commit()
        logger.info("[LAB] update_template_version saved version_id=%s", version.id)
        return self.repository.get_template_version(version.id)

    def publish_template_version(self, version_id: int) -> LabReportTemplateVersion:
        logger.info("[LAB] publish_template_version version_id=%s", version_id)
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        if version.status != "DRAFT":
            raise LabReportingDomainError(409, "Only draft versions can be published")

        published = self.repository.get_latest_published_version(version.template_id)
        if published and published.id != version.id:
            published.status = "ARCHIVED"
        version.status = "PUBLISHED"
        version.published_at = datetime.utcnow()
        self.repository.commit()
        return self.repository.get_template_version(version.id)

    def archive_template_version(self, version_id: int) -> LabReportTemplateVersion:
        logger.info("[LAB] archive_template_version version_id=%s", version_id)
        version = self.repository.get_template_version(version_id)
        if not version:
            raise LabReportingDomainError(404, "Template version not found")
        version.status = "ARCHIVED"
        self.repository.commit()
        return self.repository.get_template_version(version.id)

    def clone_template(self, template_id: int) -> LabReportTemplate:
        logger.info("[LAB] clone_template template_id=%s", template_id)
        source = self.get_template(template_id)
        code = self._make_clone_code(source.code)
        template = LabReportTemplate(
            code=code,
            name=f"{source.name} Copy",
            family=source.family,
            description=source.description,
            is_active=False,
        )
        self.repository.add_template(template)
        source_version = (
            self.repository.get_latest_draft_version(source.id)
            or self.repository.get_latest_published_version(source.id)
            or self.repository.get_latest_version(source.id)
        )
        version = LabReportTemplateVersion(
            template_id=template.id,
            version_no=1,
            status="DRAFT",
            layout_preset=source_version.layout_preset,
            page_settings=deepcopy(source_version.page_settings),
            branding_overrides=deepcopy(source_version.branding_overrides),
            signer_defaults=deepcopy(source_version.signer_defaults),
            footer_notes=source_version.footer_notes,
            seed_signature=None,
        )
        self.repository.add_template_version(version)
        self._replace_version_sections(version, self._sections_to_payload(source_version.sections))
        self.repository.commit()
        return self.get_template(template.id)

    def list_instances(
        self,
        *,
        patient_id: int | None,
        visit_ids: list[int] | None = None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[LabReportInstance]:
        logger.info(
            "[LAB] list_instances has_patient_filter=%s visit_filter_count=%s status=%s limit=%s offset=%s",
            patient_id is not None,
            len(visit_ids or []),
            status,
            limit,
            offset,
        )
        return self.repository.list_instances(
            patient_id=patient_id,
            visit_ids=visit_ids,
            status=status,
            limit=limit,
            offset=offset,
        )

    def get_instance(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] get_instance instance_id=%s", instance_id)
        instance = self.repository.get_instance(instance_id)
        if not instance:
            raise LabReportingDomainError(404, "Lab report instance not found")
        return instance

    def create_instance(
        self,
        payload: dict[str, Any],
        *,
        actor_name: str | None = None,
    ) -> LabReportInstance:
        logger.info(
            "[LAB] create_instance has_appointment_context=%s has_visit_context=%s has_template_version=%s",
            payload.get("appointment_id") is not None,
            payload.get("visit_id") is not None,
            payload.get("template_version_id") is not None,
        )
        patient = self.repository.get_patient(payload["patient_id"])
        if not patient:
            raise LabReportingDomainError(404, "Patient not found")

        appointment_id = payload.get("appointment_id")
        if appointment_id:
            self._assert_appointment_belongs_to_patient(
                appointment_id=int(appointment_id),
                patient_id=int(patient.id),
            )

        visit_id = self._resolve_visit_context(
            visit_id=payload.get("visit_id"),
            appointment_id=appointment_id,
            create_if_missing=True,
        )
        if visit_id:
            self._assert_visit_belongs_to_patient(
                visit_id=int(visit_id),
                patient_id=int(patient.id),
            )

        template = self.get_template(payload["template_id"])
        version = self._resolve_instance_version(
            template.id, payload.get("template_version_id")
        )
        self._validate_template_selection_for_context(
            template=template,
            patient_id=patient.id,
            visit_id=visit_id,
            service_codes=payload.get("service_codes"),
            service_items=payload.get("service_items"),
        )
        order, created_new_order = self._resolve_or_create_order(
            order_id=payload.get("order_id"),
            patient_id=patient.id,
            visit_id=visit_id,
        )

        signer_overrides = payload.get("signer_overrides") or {}
        branding_overrides = payload.get("branding_overrides") or {}
        instance = LabReportInstance(
            order_id=order.id if order else None,
            visit_id=visit_id,
            patient_id=patient.id,
            template_id=template.id,
            template_version_id=version.id,
            status="DRAFT",
            patient_snapshot=self._build_patient_snapshot(patient),
            branding_snapshot=self._build_branding_snapshot(version, branding_overrides),
            signer_snapshot=self._build_signer_snapshot(
                version,
                signer_overrides,
                actor_name=actor_name,
            ),
        )
        self.repository.add_instance(instance)
        self.repository.commit()
        if created_new_order and order is not None:
            self._emit_lab_new_study_notification(
                order=order,
                patient_id=patient.id,
                visit_id=visit_id,
            )
        logger.info("[LAB] create_instance created instance_id=%s", instance.id)
        return self.get_instance(instance.id)

    def update_instance(
        self, instance_id: int, payload: dict[str, Any], expected_updated_at: str | None = None
    ) -> LabReportInstance:
        logger.info("[LAB] update_instance instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        # WF-06 fix: optimistic locking — проверяем что никто не изменил
        # бланк с момента последнего чтения frontend'ом.
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        if "signer_snapshot" in payload and payload["signer_snapshot"] is not None:
            instance.signer_snapshot = payload["signer_snapshot"]
        if "branding_snapshot" in payload and payload["branding_snapshot"] is not None:
            instance.branding_snapshot = payload["branding_snapshot"]
        self.repository.commit()
        return self.get_instance(instance.id)

    def bulk_upsert_values(
        self, instance_id: int, values_payload: list[dict[str, Any]],
        expected_updated_at: str | None = None,
    ) -> tuple[LabReportInstance, list[LabReportValue]]:
        logger.info(
            "[LAB] bulk_upsert_values instance_id=%s items=%s",
            instance_id,
            len(values_payload),
        )
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        # WF-06 fix: optimistic locking — проверяем что никто не изменил
        # бланк с момента последнего чтения frontend'ом.
        self._assert_not_concurrently_modified(instance, expected_updated_at)
        field_map = self._field_map(instance.template_version)
        existing_by_key = {value.field_key: value for value in instance.values}
        current_values = {
            value.field_key: self._extract_effective_value(value)
            for value in instance.values
        }

        updated_values: list[LabReportValue] = []
        for item in values_payload:
            field_key = item["field_key"]
            field_def = field_map.get(field_key)
            if not field_def:
                raise LabReportingDomainError(404, f"Field '{field_key}' not found in template")
            normalized = self._normalize_value_payload(item, field_def)
            current_values[field_key] = normalized["effective_value"]
            context = self._build_rule_context(instance.patient_snapshot, current_values)
            reference = self._resolve_reference(field_def, context)
            flag = self._resolve_flag(
                field_def=field_def,
                effective_value=normalized["effective_value"],
                context=context,
                reference=reference,
            )

            lab_value = existing_by_key.get(field_key)
            if lab_value is None:
                lab_value = LabReportValue(instance_id=instance.id, field_key=field_key)
                instance.values.append(lab_value)
                existing_by_key[field_key] = lab_value

            lab_value.value_text = normalized["value_text"]
            lab_value.value_numeric = normalized["value_numeric"]
            lab_value.comment = normalized["comment"]
            lab_value.resolved_reference_text = reference.get("text")
            lab_value.resolved_flag = flag["flag"]
            lab_value.resolved_flag_source = flag["source"]
            lab_value.resolved_flag_severity = flag["severity_rank"]
            lab_value.resolved_flag_meta = flag["meta"]
            updated_values.append(lab_value)

        if instance.status == "DRAFT" and updated_values:
            instance.status = "IN_PROGRESS"
        self.repository.commit()
        return self.get_instance(instance.id), updated_values

    def mark_ready(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_ready instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        instance.status = "READY"
        self.repository.commit()
        return self.get_instance(instance.id)

    def finalize(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] finalize instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        self._assert_instance_editable(instance)
        current_values = {
            value.field_key: self._extract_effective_value(value)
            for value in instance.values
        }
        field_map = self._field_map(instance.template_version)
        context = self._build_rule_context(instance.patient_snapshot, current_values)

        visible_required_fields = []
        for field_def in field_map.values():
            if self._is_visible(field_def.visibility_rule, context):
                if field_def.required:
                    visible_required_fields.append(field_def.field_key)
                reference = self._resolve_reference(field_def, context)
                value = next(
                    (item for item in instance.values if item.field_key == field_def.field_key),
                    None,
                )
                if value:
                    value.resolved_reference_text = reference.get("text")
                    flag = self._resolve_flag(
                        field_def=field_def,
                        effective_value=current_values.get(field_def.field_key),
                        context=context,
                        reference=reference,
                    )
                    value.resolved_flag = flag["flag"]
                    value.resolved_flag_source = flag["source"]
                    value.resolved_flag_severity = flag["severity_rank"]
                    value.resolved_flag_meta = flag["meta"]

        missing = [
            field_key
            for field_key in visible_required_fields
            if current_values.get(field_key) in (None, "")
        ]
        if missing:
            raise LabReportingDomainError(
                400,
                f"Cannot finalize. Required fields missing: {', '.join(missing)}",
            )
        # Flush resolved references/flags while the row is still mutable.
        # The database trigger only allows the immutable transition after this point.
        self.repository.flush()
        instance.status = "FINALIZED"
        instance.finalized_at = datetime.utcnow()
        # P-01 bridge: sync в legacy lab_results таблицу для read-only
        # потребителей (mobile app, EMR, statistics, notifications).
        # Создаёт LabResult записи как projection из LabReportValue.
        # См. _sync_legacy_lab_results ниже для подробностей.
        self._sync_legacy_lab_results(instance, field_map)
        self.repository.commit()

        # P0 fix: emit inline notifications on finalize — no cron/scheduler needed.
        # Notifies (1) the patient via Telegram that results are ready, and
        # (2) the ordering doctor if the instance was created from a lab order.
        # Previously lab_notification_service.py was fully implemented but
        # never called — patients had to manually poll for results.
        # Now wired up: see check_critical_values() call below.
        try:
            self._emit_lab_results_ready_notification(instance)
        except Exception as notify_err:
            logger.warning(
                "[LAB] results-ready notification failed (non-blocking): %s",
                notify_err,
            )

        # Wire-up: check critical values on finalize. The
        # LabNotificationService.check_critical_values() was implemented
        # but never called. Now we invoke it inline after finalization
        # so doctors get immediate alerts for glucose >20, potassium >6.5,
        # hemoglobin <70, etc. (8 markers in CRITICAL_VALUES dict).
        # Non-blocking — a failure here does not roll back the finalization.
        try:
            from app.services.lab_notification_service import LabNotificationService
            lab_notif_svc = LabNotificationService(self.db)
            asyncio.get_event_loop().create_task(
                lab_notif_svc.check_critical_values()
            )
        except Exception as critical_err:
            logger.warning(
                "[LAB] critical values check failed (non-blocking): %s",
                critical_err,
            )

        return self.get_instance(instance.id)

    def _sync_legacy_lab_results(
        self,
        instance: LabReportInstance,
        field_map: dict[str, LabReportFieldDef],
    ) -> None:
        """P-01 bridge: projection LabReportValue → LabResult.

        Создаёт соответствующие записи в legacy таблице lab_results при
        финализации бланка, чтобы read-only потребители (mobile app
        /mobile/lab/results, EMR /patients/{id}/lab-results, statistics,
        critical value notifications, Telegram) видели новые бланки.

        Контекст: в кодовой базе 2 модели lab results:
          - Новая: lab_report_instances + lab_report_values (используется
            LabReportWorkbench через /lab/report-instances)
          - Legacy: lab_results (используется mobile app, EMR, и т.д.)

        Раньше bridge не было — новые бланки были невидимы для legacy
        потребителей. Этот метод создаёт LabResult projection при
        finalize(), используя order_id как связь (instance.order_id →
        lab_results.order_id).

        Idempotent: если для данного instance уже созданы LabResult
        записи (по order_id + test_code), повторной финализации не будет
        (state machine: FINALIZED → только revise). Но при revise()
        создаётся новый instance с новым order_id или тем же —
        теоретически могут быть дубли. Защита: проверяем существующие
        записи по (order_id, test_code) перед insert.

        Маппинг полей:
          field_def.label              → test_name
          field_def.field_key          → test_code
          value.value_text/value_numeric → value (string representation)
          field_def.unit               → unit
          value.resolved_reference_text → ref_range
          value.resolved_flag in
            {high, low, abnormal, critical, warning} → abnormal=True
        """
        if not instance.order_id:
            logger.warning(
                "[LAB] _sync_legacy_lab_results: instance %s has no order_id, "
                "skipping legacy projection",
                instance.id,
            )
            return

        # Удаляем существующие projection для этого order (на случай
        # re-finalize через revise — хотя state machine это не допускает,
        # защита не лишняя).
        existing = (
            self.db.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .all()
        )
        if existing:
            logger.info(
                "[LAB] _sync_legacy_lab_results: order %s already has %d "
                "LabResult projections, skipping (idempotent)",
                instance.order_id,
                len(existing),
            )
            return

        created_count = 0
        for value in instance.values:
            field_def = field_map.get(value.field_key)
            if not field_def:
                continue

            # Пропускаем пустые значения — нет смысла создавать LabResult
            # для незаполненного показателя.
            effective_value = self._extract_effective_value(value)
            if effective_value in (None, ""):
                continue

            # value_numeric имеет приоритет для numeric fields, иначе value_text.
            # Нормализуем Decimal: LabReportValue.value_numeric хранится как
            # Numeric(18, 4), поэтому str(Decimal('100')) = '100.0000'.
            # Для legacy LabResult.value (String(128)) убираем trailing zeros,
            # чтобы mobile app показывал '100', а не '100.0000'.
            if value.value_numeric is not None:
                numeric_str = str(value.value_numeric)
                # Decimal('100.0000') → '100', Decimal('5.2000') → '5.2'
                if '.' in numeric_str:
                    numeric_str = numeric_str.rstrip('0').rstrip('.')
                    if not numeric_str or numeric_str == '-':
                        numeric_str = '0'
                result_value = numeric_str
            else:
                result_value = value.value_text or ""

            # abnormal = True для любого непустого resolved_flag
            # (high, low, abnormal, critical, warning). None/empty → False.
            abnormal = bool(value.resolved_flag)

            lab_result = LabResult(
                order_id=instance.order_id,
                test_code=value.field_key,
                test_name=field_def.label or value.field_key,
                value=result_value[:128] if result_value else None,
                unit=(field_def.unit or "")[:32] or None,
                ref_range=(value.resolved_reference_text or "")[:64] or None,
                abnormal=abnormal,
                notes=None,
            )
            self.db.add(lab_result)
            created_count += 1

        logger.info(
            "[LAB] _sync_legacy_lab_results: created %d LabResult projections "
            "for instance %s (order %s)",
            created_count,
            instance.id,
            instance.order_id,
        )

    def revise(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] revise instance_id=%s", instance_id)
        source = self.get_instance(instance_id)
        if source.status not in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Only finalized instances can be revised")

        revision = LabReportInstance(
            order_id=source.order_id,
            visit_id=source.visit_id,
            patient_id=source.patient_id,
            template_id=source.template_id,
            template_version_id=source.template_version_id,
            status="DRAFT",
            patient_snapshot=deepcopy(source.patient_snapshot),
            branding_snapshot=deepcopy(source.branding_snapshot),
            signer_snapshot=deepcopy(source.signer_snapshot),
            supersedes_instance_id=source.id,
        )
        self.repository.add_instance(revision)
        for value in source.values:
            revision.values.append(
                LabReportValue(
                    field_key=value.field_key,
                    value_text=value.value_text,
                    value_numeric=value.value_numeric,
                    resolved_reference_text=value.resolved_reference_text,
                    resolved_flag=value.resolved_flag,
                    resolved_flag_source=value.resolved_flag_source,
                    resolved_flag_severity=value.resolved_flag_severity,
                    resolved_flag_meta=deepcopy(value.resolved_flag_meta)
                    if value.resolved_flag_meta
                    else None,
                    comment=value.comment,
                )
            )
        self.repository.commit()
        return self.get_instance(revision.id)

    def mark_printed(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] mark_printed instance_id=%s", instance_id)
        instance = self.get_instance(instance_id)
        if instance.status not in {"FINALIZED", "PRINTED"}:
            raise LabReportingDomainError(409, "Only finalized reports can be printed")
        instance.status = "PRINTED"
        instance.printed_at = datetime.utcnow()
        self.repository.commit()
        return self.get_instance(instance.id)

    def instance_available_actions(self, instance: LabReportInstance) -> list[str]:
        actions: list[str] = []
        if instance.status not in FINAL_INSTANCE_STATUSES:
            actions.extend(["edit", "save_draft", "mark_ready", "finalize"])
        if instance.status in FINAL_INSTANCE_STATUSES:
            actions.extend(["revise", "print"])
        return actions

    def instance_action_flags(self, instance: LabReportInstance) -> dict[str, bool]:
        actions = set(self.instance_available_actions(instance))
        return {
            "can_edit": "edit" in actions,
            "can_save_draft": "save_draft" in actions,
            "can_mark_ready": "mark_ready" in actions,
            "can_finalize": "finalize" in actions,
            "can_revise": "revise" in actions,
            "can_print": "print" in actions,
        }

    def _normalize_version_payload(self, sections_payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_sections: list[dict[str, Any]] = []
        for section in sorted(
            sections_payload,
            key=lambda item: (item.get("sort_order", 0), item.get("key") or ""),
        ):
            normalized_fields: list[dict[str, Any]] = []
            for field in sorted(
                section.get("fields") or [],
                key=lambda item: (item.get("sort_order", 0), item.get("field_key") or ""),
            ):
                normalized_fields.append(
                    {
                        "analyte_code": field.get("analyte_code"),
                        "unit_code": field.get("unit_code"),
                        "field_key": field.get("field_key"),
                        "label": field.get("label"),
                        "value_type": field.get("value_type"),
                        "unit": field.get("unit"),
                        "reference_mode": field.get("reference_mode"),
                        "reference_text": field.get("reference_text"),
                        "reference_rule": deepcopy(field.get("reference_rule")),
                        "visibility_rule": deepcopy(field.get("visibility_rule")),
                        "highlight_rule": deepcopy(field.get("highlight_rule")),
                        "choice_options": deepcopy(field.get("choice_options")),
                        "sort_order": field.get("sort_order", 0),
                        "required": field.get("required", False),
                    }
                )
            normalized_sections.append(
                {
                    "key": section.get("key"),
                    "title": section.get("title"),
                    "sort_order": section.get("sort_order", 0),
                    "section_style": deepcopy(section.get("section_style") or {}),
                    "fields": normalized_fields,
                }
            )
        return normalized_sections

    def _version_signature(
        self,
        *,
        layout_preset: str,
        page_settings: dict[str, Any] | None,
        branding_overrides: dict[str, Any] | None,
        signer_defaults: dict[str, Any] | None,
        footer_notes: str | None,
        sections_payload: list[dict[str, Any]],
    ) -> str:
        payload = {
            "layout_preset": layout_preset,
            "page_settings": page_settings or {},
            "branding_overrides": branding_overrides or {},
            "signer_defaults": signer_defaults or {},
            "footer_notes": footer_notes,
            "sections": self._normalize_version_payload(sections_payload),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _seed_definition_signature(self, definition: dict[str, Any]) -> str:
        initial_version = definition["initial_version"]
        return self._version_signature(
            layout_preset=initial_version["layout_preset"],
            page_settings=initial_version.get("page_settings"),
            branding_overrides=initial_version.get("branding_overrides"),
            signer_defaults=initial_version.get("signer_defaults"),
            footer_notes=initial_version.get("footer_notes"),
            sections_payload=initial_version.get("sections") or [],
        )

    def _template_version_signature(self, version: LabReportTemplateVersion) -> str:
        return self._version_signature(
            layout_preset=version.layout_preset,
            page_settings=version.page_settings,
            branding_overrides=version.branding_overrides,
            signer_defaults=version.signer_defaults,
            footer_notes=version.footer_notes,
            sections_payload=self._sections_to_payload(version.sections),
        )

    def ensure_default_catalog(self) -> None:
        logger.info("[LAB] ensure_default_catalog seeding analytes/units/reference ranges")
        touched = 0

        for definition in DEFAULT_LAB_UNIT_DEFINITIONS:
            unit = self.repository.get_catalog_unit(definition["code"])
            if unit is None:
                unit = LabCatalogUnit(
                    code=definition["code"],
                    name=definition["name"],
                    symbol=definition["symbol"],
                    sort_order=definition.get("sort_order", 0),
                    is_active=definition.get("is_active", True),
                )
                self.repository.add_catalog_unit(unit)
            else:
                unit.name = definition["name"]
                unit.symbol = definition["symbol"]
                unit.sort_order = definition.get("sort_order", 0)
                unit.is_active = definition.get("is_active", True)
            self._catalog_unit_cache[unit.code] = unit
            touched += 1

        for definition in DEFAULT_LAB_ANALYTE_DEFINITIONS:
            analyte = self.repository.get_catalog_analyte(definition["code"])
            if analyte is None:
                analyte = LabCatalogAnalyte(
                    code=definition["code"],
                    name=definition["name"],
                    short_name=definition.get("short_name"),
                    category=definition["category"],
                    default_unit_code=definition.get("default_unit_code"),
                    sort_order=definition.get("sort_order", 0),
                    is_active=definition.get("is_active", True),
                )
                self.repository.add_catalog_analyte(analyte)
            else:
                analyte.name = definition["name"]
                analyte.short_name = definition.get("short_name")
                analyte.category = definition["category"]
                analyte.default_unit_code = definition.get("default_unit_code")
                analyte.sort_order = definition.get("sort_order", 0)
                analyte.is_active = definition.get("is_active", True)
            self._catalog_analyte_cache[analyte.code] = analyte
            touched += 1

        seeded_ranges_by_key = {
            self._catalog_reference_key(definition): definition
            for definition in DEFAULT_LAB_REFERENCE_RANGE_DEFINITIONS
        }

        for analyte in DEFAULT_LAB_ANALYTE_DEFINITIONS:
            analyte_code = analyte["code"]
            existing_ranges = {
                self._catalog_reference_key(
                    {
                        "analyte_code": item.analyte_code,
                        "sex": item.sex,
                        "age_min_months": item.age_min_months,
                        "age_max_months": item.age_max_months,
                        "sort_order": item.sort_order,
                    }
                ): item
                for item in self.repository.list_catalog_reference_ranges(
                    analyte_code=analyte_code
                )
            }
            for key, definition in seeded_ranges_by_key.items():
                if definition["analyte_code"] != analyte_code:
                    continue
                reference_range = existing_ranges.get(key)
                if reference_range is None:
                    reference_range = LabCatalogReferenceRange(
                        analyte_code=definition["analyte_code"],
                        sex=definition.get("sex"),
                        age_min_months=definition.get("age_min_months"),
                        age_max_months=definition.get("age_max_months"),
                        sort_order=definition.get("sort_order", 0),
                    )
                    self.repository.add_catalog_reference_range(reference_range)
                reference_range.text = definition.get("text")
                reference_range.low = self._coerce_decimal(definition.get("low"))
                reference_range.high = self._coerce_decimal(definition.get("high"))
                reference_range.warning_low = self._coerce_decimal(
                    definition.get("warning_low")
                )
                reference_range.warning_high = self._coerce_decimal(
                    definition.get("warning_high")
                )
                reference_range.critical_low = self._coerce_decimal(
                    definition.get("critical_low")
                )
                reference_range.critical_high = self._coerce_decimal(
                    definition.get("critical_high")
                )
                reference_range.sort_order = definition.get("sort_order", 0)
                reference_range.is_active = definition.get("is_active", True)
                touched += 1
            self._catalog_reference_cache.pop(analyte_code, None)

        if touched:
            self.repository.commit()

    def ensure_default_templates(self) -> None:
        logger.info("[LAB] ensure_default_templates seeding pilot templates")
        seeded_count = 0
        for definition in DEFAULT_LAB_TEMPLATE_DEFINITIONS:
            template_signature = self._seed_definition_signature(definition)
            template = self.repository.get_template_by_code(definition["code"])
            if not template:
                template = LabReportTemplate(
                    code=definition["code"],
                    name=definition["name"],
                    family=definition["family"],
                    description=definition.get("description"),
                    is_active=True,
                )
                self.repository.add_template(template)
                initial_version = definition["initial_version"]
                version = LabReportTemplateVersion(
                    template_id=template.id,
                    version_no=1,
                    status="DRAFT",
                    layout_preset=initial_version["layout_preset"],
                    page_settings=initial_version.get("page_settings") or {},
                    branding_overrides=initial_version.get("branding_overrides") or {},
                    signer_defaults=initial_version.get("signer_defaults") or {},
                    footer_notes=initial_version.get("footer_notes"),
                    seed_signature=None,
                )
                self.repository.add_template_version(version)
                self._replace_version_sections(version, initial_version.get("sections") or [])
                version.status = "PUBLISHED"
                version.published_at = datetime.utcnow()
                version.seed_signature = template_signature
                seeded_count += 1
                continue

            latest_version = self.repository.get_latest_version(template.id)
            if not latest_version:
                initial_version = definition["initial_version"]
                version = LabReportTemplateVersion(
                    template_id=template.id,
                    version_no=1,
                    status="DRAFT",
                    layout_preset=initial_version["layout_preset"],
                    page_settings=initial_version.get("page_settings") or {},
                    branding_overrides=initial_version.get("branding_overrides") or {},
                    signer_defaults=initial_version.get("signer_defaults") or {},
                    footer_notes=initial_version.get("footer_notes"),
                    seed_signature=None,
                )
                self.repository.add_template_version(version)
                self._replace_version_sections(version, initial_version.get("sections") or [])
                version.status = "PUBLISHED"
                version.published_at = datetime.utcnow()
                version.seed_signature = template_signature
                seeded_count += 1
                continue

            latest_signature = latest_version.seed_signature
            current_signature = self._template_version_signature(latest_version)
            if latest_signature is None:
                if current_signature == template_signature:
                    latest_version.seed_signature = template_signature
                    seeded_count += 1
                continue

            if current_signature != latest_signature:
                logger.warning(
                    "[LAB] skipping default seed update for code=%s because the latest version was modified manually",
                    definition["code"],
                )
                continue

            if latest_signature == template_signature:
                continue

            if latest_version.status == "PUBLISHED":
                latest_version.status = "ARCHIVED"

            initial_version = definition["initial_version"]
            version = LabReportTemplateVersion(
                template_id=template.id,
                version_no=latest_version.version_no + 1,
                status="DRAFT",
                layout_preset=initial_version["layout_preset"],
                page_settings=initial_version.get("page_settings") or {},
                branding_overrides=initial_version.get("branding_overrides") or {},
                signer_defaults=initial_version.get("signer_defaults") or {},
                footer_notes=initial_version.get("footer_notes"),
                seed_signature=None,
            )
            self.repository.add_template_version(version)
            self._replace_version_sections(version, initial_version.get("sections") or [])
            version.status = "PUBLISHED"
            version.published_at = datetime.utcnow()
            version.seed_signature = template_signature
            seeded_count += 1
        if seeded_count:
            logger.info("[LAB] ensure_default_templates seeded=%s", seeded_count)
            self.repository.commit()

    def ensure_default_template_bindings(self) -> None:
        logger.info("[LAB] ensure_default_template_bindings seeding workflow mappings")
        touched = 0
        for definition in DEFAULT_LAB_TEMPLATE_BINDING_DEFINITIONS:
            service_code = normalize_service_code(definition["service_code"])
            template_code = definition["template_code"]
            if not service_code:
                continue
            if not self.repository.get_template_by_code(template_code):
                logger.warning(
                    "[LAB] skipping template binding seed service_code=%s template_code=%s because template is missing",
                    service_code,
                    template_code,
                )
                continue
            binding = self.repository.get_service_binding(
                service_code=service_code,
                template_code=template_code,
            )
            if binding is None:
                binding = LabTemplateServiceBinding(
                    service_code=service_code,
                    template_code=template_code,
                )
                self.repository.add_service_binding(binding)
            binding.sort_order = definition.get("sort_order", 0)
            binding.is_default = definition.get("is_default", False)
            binding.is_active = definition.get("is_active", True)
            touched += 1
        if touched:
            self.repository.commit()

    def materialize_instance(self, instance: LabReportInstance) -> list[dict[str, Any]]:
        value_map = {value.field_key: value for value in instance.values}
        current_values = {
            field_key: self._extract_effective_value(value)
            for field_key, value in value_map.items()
        }
        context = self._build_rule_context(instance.patient_snapshot, current_values)
        sections: list[dict[str, Any]] = []
        for section in sorted(instance.template_version.sections, key=lambda item: item.sort_order):
            rows = []
            for field_def in sorted(section.fields, key=lambda item: item.sort_order):
                if not self._is_visible(field_def.visibility_rule, context):
                    continue
                reference = self._resolve_reference(field_def, context)
                value = value_map.get(field_def.field_key)
                rows.append(
                    {
                        "id": field_def.id,
                        "analyte_code": field_def.analyte_code,
                        "unit_code": field_def.unit_code,
                        "field_key": field_def.field_key,
                        "label": field_def.label,
                        "value_type": field_def.value_type,
                        "unit": self._resolve_field_unit(field_def),
                        "required": field_def.required,
                        "reference_mode": field_def.reference_mode,
                        "reference_text": value.resolved_reference_text
                        if value and value.resolved_reference_text is not None
                        else reference.get("text"),
                        "visibility_rule": field_def.visibility_rule,
                        "highlight_rule": field_def.highlight_rule,
                        "value_text": value.value_text if value else None,
                        "value_numeric": value.value_numeric if value else None,
                        "comment": value.comment if value else None,
                        "resolved_flag": value.resolved_flag if value else None,
                        "resolved_flag_source": value.resolved_flag_source if value else None,
                        "resolved_flag_severity": value.resolved_flag_severity
                        if value
                        else None,
                        "resolved_flag_meta": deepcopy(value.resolved_flag_meta)
                        if value and value.resolved_flag_meta
                        else None,
                    }
                )
            sections.append(
                {
                    "id": section.id,
                    "key": section.key,
                    "title": section.title,
                    "sort_order": section.sort_order,
                    "section_style": section.section_style,
                    "fields": rows,
                }
            )
        return sections

    def summarize_critical_findings(
        self, materialized_sections: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for section in materialized_sections:
            for field in section.get("fields") or []:
                severity_rank = field.get("resolved_flag_severity") or 0
                if severity_rank < FLAG_SEVERITY_RANKS["critical"]:
                    continue
                findings.append(
                    {
                        "section_key": section["key"],
                        "section_title": section.get("title"),
                        "field_key": field["field_key"],
                        "label": field["label"],
                        "analyte_code": field.get("analyte_code"),
                        "unit": field.get("unit"),
                        "value_text": field.get("value_text"),
                        "value_numeric": field.get("value_numeric"),
                        "value_display": self._value_display(
                            field.get("value_numeric"),
                            field.get("value_text"),
                        ),
                        "reference_text": field.get("reference_text"),
                        "resolved_flag": field["resolved_flag"],
                        "resolved_flag_source": field.get("resolved_flag_source"),
                        "resolved_flag_severity": severity_rank,
                        "resolved_flag_meta": deepcopy(field.get("resolved_flag_meta"))
                        if field.get("resolved_flag_meta")
                        else None,
                        "threshold_display": self._threshold_display(
                            field.get("resolved_flag_meta")
                        ),
                    }
                )
        findings.sort(
            key=lambda item: (
                -(item.get("resolved_flag_severity") or 0),
                item.get("section_title") or item.get("section_key") or "",
                item.get("label") or item.get("field_key") or "",
            )
        )
        return findings

    def summarize_instance_severity(
        self, materialized_sections: list[dict[str, Any]]
    ) -> dict[str, Any]:
        flagged_findings_count = 0
        critical_findings_count = 0
        max_flag_severity: int | None = None

        for section in materialized_sections:
            for field in section.get("fields") or []:
                resolved_flag = field.get("resolved_flag")
                severity_rank = field.get("resolved_flag_severity")
                if resolved_flag:
                    flagged_findings_count += 1
                if severity_rank is None:
                    continue
                severity_rank = int(severity_rank)
                if max_flag_severity is None or severity_rank > max_flag_severity:
                    max_flag_severity = severity_rank
                if severity_rank >= FLAG_SEVERITY_RANKS["critical"]:
                    critical_findings_count += 1

        return {
            "flagged_findings_count": flagged_findings_count,
            "critical_findings_count": critical_findings_count,
            "max_flag_severity": max_flag_severity,
        }

    def _resolve_instance_version(
        self, template_id: int, template_version_id: int | None
    ) -> LabReportTemplateVersion:
        if template_version_id:
            version = self.repository.get_template_version(template_version_id)
            if not version or version.template_id != template_id:
                raise LabReportingDomainError(404, "Template version not found")
            return version
        version = self.repository.get_latest_published_version(
            template_id
        ) or self.repository.get_latest_draft_version(template_id)
        if not version:
            raise LabReportingDomainError(404, "No template version available")
        return version

    def _resolve_or_create_order(
        self,
        *,
        order_id: int | None,
        patient_id: int,
        visit_id: int | None,
    ) -> tuple[LabOrder | None, bool]:
        if order_id:
            order = self.repository.get_order(order_id)
            if not order:
                raise LabReportingDomainError(404, "Lab order not found")
            self._assert_order_belongs_to_context(
                order=order,
                patient_id=patient_id,
                visit_id=visit_id,
            )
            return order, False
        order = self.repository.find_order_by_visit_and_patient(
            visit_id=visit_id,
            patient_id=patient_id,
        )
        if order:
            return order, False
        logger.info(
            "[LAB] creating synthetic lab order has_visit_context=%s",
            visit_id is not None,
        )
        return self.repository.add_order(
            LabOrder(
                patient_id=patient_id,
                visit_id=visit_id,
                status="ordered",
                notes="Auto-created from lab report workflow",
            )
        ), True

    def _assert_appointment_belongs_to_patient(
        self, *, appointment_id: int, patient_id: int
    ) -> None:
        appointment = self.db.get(Appointment, appointment_id)
        if not appointment:
            raise LabReportingDomainError(404, "Appointment not found")
        if appointment.patient_id is None or int(appointment.patient_id) != int(
            patient_id
        ):
            raise LabReportingDomainError(
                409, "Appointment does not belong to selected patient"
            )

    def _assert_visit_belongs_to_patient(
        self, *, visit_id: int, patient_id: int
    ) -> None:
        visit = self.repository.get_visit(visit_id)
        if not visit:
            raise LabReportingDomainError(404, "Visit not found")
        if visit.patient_id is None or int(visit.patient_id) != int(patient_id):
            raise LabReportingDomainError(
                409, "Visit does not belong to selected patient"
            )

    def _assert_order_belongs_to_context(
        self,
        *,
        order: LabOrder,
        patient_id: int,
        visit_id: int | None,
    ) -> None:
        if order.patient_id is not None and int(order.patient_id) != int(patient_id):
            raise LabReportingDomainError(
                409, "Lab order does not belong to selected patient"
            )
        if order.visit_id is not None:
            self._assert_visit_belongs_to_patient(
                visit_id=int(order.visit_id),
                patient_id=int(patient_id),
            )
        if (
            visit_id is not None
            and order.visit_id is not None
            and int(order.visit_id) != int(visit_id)
        ):
            raise LabReportingDomainError(
                409, "Lab order does not belong to selected visit"
            )

    def _emit_lab_new_study_notification(
        self,
        *,
        order: LabOrder,
        patient_id: int,
        visit_id: int | None,
    ) -> None:
        recipients = (
            self.db.query(User)
            .filter(
                User.is_active.is_(True),
                func.lower(User.role).in_(["lab", "labtechnician", "lab_technician"]),
            )
            .all()
        )
        if not recipients:
            return

        async def _send(recipient: User) -> bool:
            return await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=recipient,
                event_type="lab_new_study",
                title="Назначено новое исследование",
                message=f"Для пациента #{patient_id} создано новое исследование.",
                metadata={
                    "order_id": order.id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                },
            )

        for recipient in recipients:
            try:
                canonical_created = asyncio.run(_send(recipient))
                if not canonical_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_new_study canonical delivery failed",
                        extra={
                            "has_order": order.id is not None,
                        },
                    )
            except RuntimeError as exc:
                logger.warning(
                    "[FIX:NOTIFICATIONS] lab_new_study canonical delivery skipped due runtime context",
                    extra={
                        "has_order": order.id is not None,
                        "error_type": type(exc).__name__,
                    },
                )
            except Exception as exc:
                logger.error(
                    "[FIX:NOTIFICATIONS] lab_new_study canonical delivery error",
                    extra={
                        "has_order": order.id is not None,
                        "error_type": type(exc).__name__,
                    },
                )

    def _emit_lab_results_ready_notification(self, instance: LabReportInstance) -> None:
        """
        P0 fix: emit notifications when lab results are finalized.

        Notifies:
          1. The ordering doctor (if instance has a linked LabOrder with
             requested_by_doctor_id) — so they know results are ready.
          2. The patient via Telegram (if patient has a Telegram link and
             lab_notifications enabled) — so they can pick up results.

        This replaces the old lab_notification_service.py cron
        approach with inline emission from finalize().
        lab_notification_service.py is now wired up for critical values
        checking (check_critical_values) — see the finalize() method.
        """
        patient_id = instance.patient_id
        visit_id = instance.visit_id
        template_name = ""
        if instance.template_version and instance.template_version.template:
            template_name = instance.template_version.template.name or ""

        # Count flagged findings for the notification message.
        flagged_count = sum(
            1 for v in instance.values
            if v.resolved_flag_severity and v.resolved_flag_severity > 0
        )

        # 1. Notify the ordering doctor via in-app notification.
        order = None
        if instance.lab_order_id:
            order = self.db.query(LabOrder).filter(LabOrder.id == instance.lab_order_id).first()

        doctor_id = None
        if order and hasattr(order, "requested_by_doctor_id"):
            doctor_id = order.requested_by_doctor_id

        if doctor_id:
            doctor_user = (
                self.db.query(User)
                .join(Doctor, Doctor.user_id == User.id)
                .filter(Doctor.id == doctor_id, User.is_active.is_(True))
                .first()
            )
            if doctor_user:
                try:
                    asyncio.run(
                        notification_sender_service.send_lab_event_notification(
                            db=self.db,
                            recipient=doctor_user,
                            event_type="lab_results_ready",
                            title="Результаты анализов готовы",
                            message=(
                                f"Результаты анализов{' («' + template_name + '»)' if template_name else ''} "
                                f"для пациента #{patient_id} готовы."
                                + (f" Отклонений: {flagged_count}." if flagged_count > 0 else "")
                            ),
                            metadata={
                                "instance_id": instance.id,
                                "patient_id": patient_id,
                                "visit_id": visit_id,
                                "template_name": template_name,
                                "flagged_count": flagged_count,
                            },
                        )
                    )
                    logger.info(
                        "[LAB] results-ready notification sent to doctor user_id=%s",
                        doctor_user.id,
                    )
                except RuntimeError:
                    logger.warning("[LAB] results-ready doctor notification skipped (event loop active)")
                except Exception as exc:
                    logger.error("[LAB] results-ready doctor notification error: %s", exc)

        # 2. Notify the patient via Telegram.
        # The telegram webhook's _send_clinic_lab_results function handles
        # sending PDF results to patients. Here we just log that results are
        # ready — the patient can pull results via the bot's "📄 Results"
        # button, or an admin can use POST /telegram/send-lab-results to
        # push them. A full push integration requires calling the async
        # telegram bot API from this sync context, which is deferred to
        # a background task queue in a future iteration.
        logger.info(
            "[LAB] results finalized — patient_id=%s can pull results via Telegram bot. "
            "Use POST /telegram/send-lab-results to push manually if needed.",
            patient_id,
        )

    def _validate_template_selection_for_context(
        self,
        *,
        template: LabReportTemplate,
        patient_id: int,
        visit_id: int | None,
        service_codes: list[str] | None,
        service_items: list[dict[str, Any]] | None,
    ) -> None:
        resolution = self.resolve_template_options(
            patient_id=patient_id,
            visit_id=visit_id,
            service_codes=service_codes,
            service_items=service_items,
        )
        resolved_service_codes = resolution["service_codes"]
        allowed_templates = resolution["allowed_templates"]
        if not resolved_service_codes:
            return
        if not allowed_templates:
            raise LabReportingDomainError(
                409,
                "No lab template mapping configured for the selected service context",
            )
        allowed_template_codes = {item.code for item in allowed_templates}
        if template.code not in allowed_template_codes:
            raise LabReportingDomainError(
                409,
                f"Template '{template.name}' is not allowed for services: {', '.join(resolved_service_codes)}",
            )

    def _resolve_visit_context(
        self,
        *,
        visit_id: int | None,
        appointment_id: int | None,
        create_if_missing: bool,
    ) -> int | None:
        if visit_id:
            if not self.repository.get_visit(visit_id):
                raise LabReportingDomainError(404, "Visit not found")
            return visit_id
        if not appointment_id:
            return None
        try:
            resolved_visit_id = CanonicalVisitService(self.db).resolve_canonical_visit(
                appointment_id,
                create_if_missing=create_if_missing,
            )
        except CanonicalVisitResolutionError as exc:
            if not create_if_missing and exc.status_code == 404:
                logger.info(
                    "[LAB] canonical visit is not available yet for appointment context",
                )
                return None
            raise LabReportingDomainError(exc.status_code, exc.detail) from exc
        logger.info(
            "[LAB] resolved visit context has_appointment_context=%s has_resolved_visit_context=%s",
            appointment_id is not None,
            resolved_visit_id is not None,
        )
        return resolved_visit_id

    def _collect_service_context(
        self,
        *,
        visit_id: int | None,
        service_codes: list[str] | None,
        service_items: list[dict[str, Any]] | None,
    ) -> dict[str, list[str]]:
        items = list(service_items or [])
        if visit_id:
            visit_items = self.repository.list_visit_service_context(visit_id)
            if visit_items:
                items.extend(visit_items)

        raw_codes = list(service_codes or [])
        raw_names: list[str] = []
        for item in items:
            code = item.get("code")
            if code:
                raw_codes.append(str(code))
            name = item.get("name")
            if name:
                raw_names.append(str(name).strip())

        return {
            "service_codes": self._normalize_service_codes(raw_codes),
            "service_names": self._dedupe_text_values(raw_names),
        }

    def _normalize_service_codes(self, raw_codes: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for code in raw_codes:
            normalized_code = normalize_service_code(code)
            if not normalized_code or normalized_code in seen:
                continue
            seen.add(normalized_code)
            normalized.append(normalized_code)
        return normalized

    def _dedupe_text_values(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            lowered = normalized.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(normalized)
        return deduped

    def _replace_version_sections(
        self, version: LabReportTemplateVersion, sections_payload: list[dict[str, Any]]
    ) -> None:
        version.sections.clear()
        self.repository.flush()
        for section_payload in sections_payload:
            section = LabReportSection(
                key=section_payload["key"],
                title=section_payload.get("title"),
                sort_order=section_payload.get("sort_order", 0),
                section_style=section_payload.get("section_style") or {},
            )
            for field_payload in section_payload.get("fields") or []:
                section.fields.append(
                    LabReportFieldDef(
                        analyte_code=field_payload.get("analyte_code"),
                        unit_code=field_payload.get("unit_code"),
                        field_key=field_payload["field_key"],
                        label=field_payload["label"],
                        value_type=field_payload.get("value_type", "text"),
                        unit=field_payload.get("unit"),
                        reference_mode=field_payload.get("reference_mode", "static_text"),
                        reference_text=field_payload.get("reference_text"),
                        reference_rule=field_payload.get("reference_rule"),
                        visibility_rule=field_payload.get("visibility_rule"),
                        highlight_rule=field_payload.get("highlight_rule"),
                        choice_options=field_payload.get("choice_options"),
                        sort_order=field_payload.get("sort_order", 0),
                        required=field_payload.get("required", False),
                    )
                )
            version.sections.append(section)
        self.repository.flush()

    def _sections_to_payload(
        self, sections: list[LabReportSection]
    ) -> list[dict[str, Any]]:
        payload = []
        for section in sections:
            payload.append(
                {
                    "key": section.key,
                    "title": section.title,
                    "sort_order": section.sort_order,
                    "section_style": deepcopy(section.section_style),
                    "fields": [
                        {
                            "analyte_code": field.analyte_code,
                            "unit_code": field.unit_code,
                            "field_key": field.field_key,
                            "label": field.label,
                            "value_type": field.value_type,
                            "unit": field.unit,
                            "reference_mode": field.reference_mode,
                            "reference_text": field.reference_text,
                            "reference_rule": deepcopy(field.reference_rule),
                            "visibility_rule": deepcopy(field.visibility_rule),
                            "highlight_rule": deepcopy(field.highlight_rule),
                            "choice_options": deepcopy(field.choice_options),
                            "sort_order": field.sort_order,
                            "required": field.required,
                        }
                        for field in sorted(section.fields, key=lambda item: item.sort_order)
                    ],
                }
            )
        return payload

    def _catalog_reference_key(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        return (
            payload.get("analyte_code"),
            payload.get("sex"),
            payload.get("age_min_months"),
            payload.get("age_max_months"),
            payload.get("sort_order", 0),
        )

    def _get_catalog_unit(self, code: str | None) -> LabCatalogUnit | None:
        if not code:
            return None
        if code not in self._catalog_unit_cache:
            self._catalog_unit_cache[code] = self.repository.get_catalog_unit(code)
        return self._catalog_unit_cache[code]

    def _resolve_field_unit(self, field_def: LabReportFieldDef) -> str | None:
        if field_def.unit:
            return field_def.unit
        unit = self._get_catalog_unit(field_def.unit_code)
        if unit is not None:
            return unit.symbol
        analyte = self._get_catalog_analyte(field_def.analyte_code)
        if analyte and analyte.default_unit is not None:
            return analyte.default_unit.symbol
        return None

    def _get_catalog_analyte(self, code: str | None) -> LabCatalogAnalyte | None:
        if not code:
            return None
        if code not in self._catalog_analyte_cache:
            self._catalog_analyte_cache[code] = self.repository.get_catalog_analyte(code)
        return self._catalog_analyte_cache[code]

    def _get_catalog_reference_ranges(
        self, analyte_code: str | None
    ) -> list[LabCatalogReferenceRange]:
        if not analyte_code:
            return []
        if analyte_code not in self._catalog_reference_cache:
            self._catalog_reference_cache[analyte_code] = (
                self.repository.list_catalog_reference_ranges(analyte_code=analyte_code)
            )
        return self._catalog_reference_cache[analyte_code]

    def _format_decimal_display(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        normalized = value.normalize()
        text = format(normalized, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    def _catalog_reference_to_payload(
        self, reference_range: LabCatalogReferenceRange
    ) -> dict[str, Any]:
        text = reference_range.text
        if not text and reference_range.low is not None and reference_range.high is not None:
            low_text = self._format_decimal_display(reference_range.low)
            high_text = self._format_decimal_display(reference_range.high)
            text = f"{low_text} - {high_text}"
        return {
            "text": text or "",
            "low": reference_range.low,
            "high": reference_range.high,
            "warning_low": reference_range.warning_low,
            "warning_high": reference_range.warning_high,
            "critical_low": reference_range.critical_low,
            "critical_high": reference_range.critical_high,
            "low_flag": None,
            "high_flag": None,
            "warning_low_flag": None,
            "warning_high_flag": None,
            "critical_low_flag": None,
            "critical_high_flag": None,
            "flag": None,
        }

    def _resolve_catalog_reference(
        self, field_def: LabReportFieldDef, context: dict[str, Any]
    ) -> dict[str, Any]:
        patient = context.get("patient", {})
        patient_sex = patient.get("sex")
        age_months = patient.get("age_months")
        matched: list[LabCatalogReferenceRange] = []
        for reference_range in self._get_catalog_reference_ranges(field_def.analyte_code):
            if not reference_range.is_active:
                continue
            if reference_range.sex and patient_sex and reference_range.sex != patient_sex:
                continue
            if reference_range.sex and not patient_sex:
                continue
            if (
                reference_range.age_min_months is not None
                and (age_months is None or age_months < reference_range.age_min_months)
            ):
                continue
            if (
                reference_range.age_max_months is not None
                and (age_months is None or age_months > reference_range.age_max_months)
            ):
                continue
            matched.append(reference_range)

        if not matched:
            return {
                "text": field_def.reference_text or "",
                "low": None,
                "high": None,
                "warning_low": None,
                "warning_high": None,
                "critical_low": None,
                "critical_high": None,
                "low_flag": None,
                "high_flag": None,
                "warning_low_flag": None,
                "warning_high_flag": None,
                "critical_low_flag": None,
                "critical_high_flag": None,
                "flag": None,
            }

        matched.sort(
            key=lambda item: (
                0 if item.sex else 1,
                0
                if item.age_min_months is not None or item.age_max_months is not None
                else 1,
                (item.age_max_months or 10**9) - (item.age_min_months or 0),
                item.sort_order,
                item.id,
            )
        )
        return self._catalog_reference_to_payload(matched[0])

    def _build_patient_snapshot(self, patient) -> dict[str, Any]:
        today = date.today()
        age_years = None
        age_months = None
        if patient.birth_date:
            age_years = today.year - patient.birth_date.year - (
                (today.month, today.day) < (patient.birth_date.month, patient.birth_date.day)
            )
            age_months = max(age_years * 12 + today.month - patient.birth_date.month, 0)
        return {
            "patient_id": patient.id,
            "full_name": patient.short_name() if hasattr(patient, "short_name") else patient.first_name,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "middle_name": patient.middle_name,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "sex": patient.sex,
            "age_years": age_years,
            "age_months": age_months,
            "phone": patient.phone,
            "address": patient.address,
        }

    def _build_branding_snapshot(
        self,
        version: LabReportTemplateVersion,
        branding_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        defaults = self.repository.get_clinic_settings_map("clinic")
        snapshot = {
            "clinic_name": defaults.get("clinic_name") or "Doktor Laboratoriyasi",
            "address": defaults.get("address") or "",
            "phone": defaults.get("phone") or "",
            "logo_url": defaults.get("logo_url") or "",
            "document_title": "",
            "document_subtitle": "",
        }
        snapshot.update(version.branding_overrides or {})
        snapshot.update(branding_overrides or {})
        return snapshot

    def _build_signer_snapshot(
        self,
        version: LabReportTemplateVersion,
        signer_overrides: dict[str, Any] | None = None,
        *,
        actor_name: str | None = None,
    ) -> dict[str, Any]:
        snapshot = {
            "lab_technician_label": "Лаборант",
            "lab_technician_name": "",
            "approver_label": "Подпись",
            "approver_name": "",
        }
        snapshot.update(version.signer_defaults or {})
        normalized_actor_name = (actor_name or "").strip()
        if normalized_actor_name:
            snapshot["lab_technician_name"] = normalized_actor_name
            snapshot["approver_name"] = normalized_actor_name
        snapshot.update(signer_overrides or {})
        return snapshot

    def _field_map(self, version: LabReportTemplateVersion) -> dict[str, LabReportFieldDef]:
        return {
            field.field_key: field
            for section in version.sections
            for field in section.fields
        }

    def _normalize_value_payload(
        self, payload: dict[str, Any], field_def: LabReportFieldDef
    ) -> dict[str, Any]:
        value_text = payload.get("value_text")
        value_numeric = payload.get("value_numeric")
        if (
            value_numeric in ("", None)
            and value_text not in (None, "")
            and field_def.value_type == "numeric"
        ):
            try:
                value_numeric = Decimal(str(value_text).replace(",", "."))
            except (InvalidOperation, ValueError):
                value_numeric = None
        elif value_numeric not in ("", None):
            try:
                value_numeric = Decimal(str(value_numeric).replace(",", "."))
            except (InvalidOperation, ValueError) as exc:
                raise LabReportingDomainError(
                    400, f"Invalid numeric value for {field_def.field_key}"
                ) from exc
        if value_text in ("", None) and value_numeric is not None:
            value_text = str(value_numeric.normalize())
        effective_value = value_numeric if value_numeric is not None else value_text
        return {
            "value_text": value_text,
            "value_numeric": value_numeric,
            "comment": payload.get("comment"),
            "effective_value": effective_value,
        }

    def _validate_catalog_links(self, sections_payload: list[dict[str, Any]]) -> None:
        for section in sections_payload:
            for field in section.get("fields") or []:
                analyte_code = field.get("analyte_code")
                unit_code = field.get("unit_code")
                if analyte_code and self._get_catalog_analyte(analyte_code) is None:
                    raise LabReportingDomainError(
                        400, f"Unknown analyte code '{analyte_code}'"
                    )
                if unit_code and self._get_catalog_unit(unit_code) is None:
                    raise LabReportingDomainError(
                        400, f"Unknown unit code '{unit_code}'"
                    )

    def _extract_effective_value(self, value: LabReportValue) -> Any:
        return value.value_numeric if value.value_numeric is not None else value.value_text

    def _build_rule_context(
        self, patient_snapshot: dict[str, Any], field_values: dict[str, Any]
    ) -> dict[str, Any]:
        return {"patient": patient_snapshot, "field": field_values}

    def _lookup_context_value(self, source: str | None, context: dict[str, Any]) -> Any:
        if not source:
            return None
        current: Any = context
        for part in source.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                return None
        return current

    def _evaluate_condition(
        self, condition: dict[str, Any] | None, context: dict[str, Any]
    ) -> bool:
        if not condition:
            return True
        if "all" in condition:
            return all(self._evaluate_condition(item, context) for item in condition["all"])
        if "any" in condition:
            return any(self._evaluate_condition(item, context) for item in condition["any"])

        left = self._lookup_context_value(condition.get("source"), context)
        op = condition.get("op", "exists")
        right = condition.get("value")
        if op == "exists":
            return left is not None and left != ""
        if op == "eq":
            return left == right
        if op == "neq":
            return left != right
        if op == "ieq":
            if left is None or right is None:
                return left == right
            return str(left).strip().casefold() == str(right).strip().casefold()
        if op == "ineq":
            if left is None or right is None:
                return left != right
            return str(left).strip().casefold() != str(right).strip().casefold()
        if op == "gt":
            return left is not None and left > right
        if op == "gte":
            return left is not None and left >= right
        if op == "lt":
            return left is not None and left < right
        if op == "lte":
            return left is not None and left <= right
        if op == "between":
            return left is not None and condition.get("min") <= left <= condition.get("max")
        if op == "in":
            return left in (condition.get("values") or [])
        return False

    def _resolve_rule_payload(
        self, rule: dict[str, Any] | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        if not rule:
            return {}
        for case in rule.get("cases") or []:
            if self._evaluate_condition(case.get("when"), context):
                return case
        default = rule.get("default")
        return default if isinstance(default, dict) else {}

    def _resolve_reference(
        self, field_def: LabReportFieldDef, context: dict[str, Any]
    ) -> dict[str, Any]:
        if field_def.reference_mode == "catalog":
            return self._resolve_catalog_reference(field_def, context)
        if field_def.reference_mode == "rule_based":
            payload = self._resolve_rule_payload(field_def.reference_rule, context)
            return {
                "text": payload.get("text") or field_def.reference_text or "",
                "low": payload.get("low"),
                "high": payload.get("high"),
                "warning_low": payload.get("warning_low"),
                "warning_high": payload.get("warning_high"),
                "critical_low": payload.get("critical_low"),
                "critical_high": payload.get("critical_high"),
                "low_flag": payload.get("low_flag"),
                "high_flag": payload.get("high_flag"),
                "warning_low_flag": payload.get("warning_low_flag"),
                "warning_high_flag": payload.get("warning_high_flag"),
                "critical_low_flag": payload.get("critical_low_flag"),
                "critical_high_flag": payload.get("critical_high_flag"),
                "flag": payload.get("flag"),
            }
        return {
            "text": field_def.reference_text or "",
            "low": None,
            "high": None,
            "warning_low": None,
            "warning_high": None,
            "critical_low": None,
            "critical_high": None,
            "low_flag": None,
            "high_flag": None,
            "warning_low_flag": None,
            "warning_high_flag": None,
            "critical_low_flag": None,
            "critical_high_flag": None,
            "flag": None,
        }

    def _is_visible(self, rule: dict[str, Any] | None, context: dict[str, Any]) -> bool:
        return self._evaluate_condition(rule, context)

    def _coerce_decimal(self, value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _json_safe_value(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return self._format_decimal_display(value)
        if isinstance(value, dict):
            return {
                str(key): self._json_safe_value(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, list):
            return [self._json_safe_value(item) for item in value]
        return value

    def _value_display(self, value_numeric: Decimal | None, value_text: str | None) -> str:
        if value_numeric is not None:
            return self._format_decimal_display(value_numeric) or ""
        return value_text or ""

    def _flag_direction(self, flag: str | None) -> str | None:
        if flag == "low":
            return "low"
        if flag == "high":
            return "high"
        return None

    def _flag_severity_rank(self, flag: str | None) -> int | None:
        if not flag:
            return None
        return FLAG_SEVERITY_RANKS.get(flag, 150)

    def _threshold_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._json_safe_value(
            {
                "warning_low": payload.get("warning_low"),
                "low": payload.get("low"),
                "high": payload.get("high"),
                "warning_high": payload.get("warning_high"),
                "critical_low": payload.get("critical_low"),
                "critical_high": payload.get("critical_high"),
            }
        )

    def _flag_meta(
        self,
        *,
        field_def: LabReportFieldDef,
        effective_value: Any,
        payload: dict[str, Any],
        source: str | None,
        reference_text: str | None,
        direction: str | None,
        matched_threshold: dict[str, Any] | None,
        severity_rank: int | None,
    ) -> dict[str, Any]:
        meta = {
            "source": source,
            "reference_text": reference_text,
            "reference_mode": field_def.reference_mode,
            "analyte_code": field_def.analyte_code,
            "unit_code": field_def.unit_code,
            "effective_value": self._json_safe_value(effective_value),
            "severity_rank": severity_rank,
            "direction": direction,
            "thresholds": self._threshold_snapshot(payload),
        }
        if matched_threshold:
            meta["matched_threshold"] = self._json_safe_value(matched_threshold)
        return self._json_safe_value(meta)

    def _threshold_display(self, meta: dict[str, Any] | None) -> str | None:
        if not meta:
            return None
        matched_threshold = meta.get("matched_threshold") or {}
        threshold_value = matched_threshold.get("value")
        if threshold_value in (None, ""):
            return None
        operator = matched_threshold.get("operator")
        operator_display = {
            "lt": "<",
            "lte": "<=",
            "gt": ">",
            "gte": ">=",
        }.get(operator, operator or "")
        return f"{operator_display} {threshold_value}".strip()

    def _resolve_threshold_flag(
        self,
        *,
        numeric_value: Decimal | None,
        payload: dict[str, Any],
        source: str | None,
        field_def: LabReportFieldDef,
        effective_value: Any,
        reference_text: str | None,
    ) -> dict[str, Any] | None:
        if numeric_value is None:
            return None

        threshold_rules = (
            ("critical_low", "critical_low_flag", "critical", "lt", "low"),
            ("low", "low_flag", "low", "lt", "low"),
            ("warning_low", "warning_low_flag", "warning", "lt", "low"),
            ("critical_high", "critical_high_flag", "critical", "gt", "high"),
            ("high", "high_flag", "high", "gt", "high"),
            ("warning_high", "warning_high_flag", "warning", "gt", "high"),
        )
        for threshold_key, flag_key, default_flag, comparison, direction in threshold_rules:
            threshold = self._coerce_decimal(payload.get(threshold_key))
            if threshold is None:
                continue
            if comparison == "lt" and numeric_value < threshold:
                flag = str(payload.get(flag_key) or default_flag)
                severity_rank = self._flag_severity_rank(flag)
                return {
                    "flag": flag,
                    "source": source,
                    "severity_rank": severity_rank,
                    "meta": self._flag_meta(
                        field_def=field_def,
                        effective_value=effective_value,
                        payload=payload,
                        source=source,
                        reference_text=reference_text,
                        direction=direction,
                        matched_threshold={
                            "key": threshold_key,
                            "operator": comparison,
                            "value": threshold,
                        },
                        severity_rank=severity_rank,
                    ),
                }
            if comparison == "gt" and numeric_value > threshold:
                flag = str(payload.get(flag_key) or default_flag)
                severity_rank = self._flag_severity_rank(flag)
                return {
                    "flag": flag,
                    "source": source,
                    "severity_rank": severity_rank,
                    "meta": self._flag_meta(
                        field_def=field_def,
                        effective_value=effective_value,
                        payload=payload,
                        source=source,
                        reference_text=reference_text,
                        direction=direction,
                        matched_threshold={
                            "key": threshold_key,
                            "operator": comparison,
                            "value": threshold,
                        },
                        severity_rank=severity_rank,
                    ),
                }
        return None

    def _resolve_flag(
        self,
        *,
        field_def: LabReportFieldDef,
        effective_value: Any,
        context: dict[str, Any],
        reference: dict[str, Any],
    ) -> dict[str, Any]:
        if effective_value in (None, ""):
            return {
                "flag": None,
                "source": None,
                "severity_rank": None,
                "meta": None,
            }
        numeric_value = self._coerce_decimal(effective_value)

        rule = field_def.highlight_rule or {}
        mode = rule.get("mode")
        payload: dict[str, Any]
        source: str | None
        if mode == "range":
            payload = rule
            source = "range_rule"
        elif mode == "rule_based_reference":
            payload = reference
            source = f"{field_def.reference_mode}_reference"
        elif rule:
            payload = self._resolve_rule_payload(rule, context)
            source = "highlight_rule"
        else:
            payload = {}
            source = None

        threshold_flag = self._resolve_threshold_flag(
            numeric_value=numeric_value,
            payload=payload,
            source=source,
            field_def=field_def,
            effective_value=effective_value,
            reference_text=reference.get("text"),
        )
        if threshold_flag:
            return threshold_flag

        if payload.get("flag"):
            flag = str(payload["flag"])
            return {
                "flag": flag,
                "source": source,
                "severity_rank": self._flag_severity_rank(flag),
                "meta": self._flag_meta(
                    field_def=field_def,
                    effective_value=effective_value,
                    payload=payload,
                    source=source,
                    reference_text=reference.get("text"),
                    direction=self._flag_direction(flag),
                    matched_threshold=None,
                    severity_rank=self._flag_severity_rank(flag),
                ),
            }
        return {
            "flag": None,
            "source": None,
            "severity_rank": None,
            "meta": None,
        }

    def _assert_instance_editable(self, instance: LabReportInstance) -> None:
        if instance.status in FINAL_INSTANCE_STATUSES:
            raise LabReportingDomainError(409, "Finalized reports are immutable; use revise")

    def _assert_not_concurrently_modified(
        self, instance: LabReportInstance, expected_updated_at: str | None
    ) -> None:
        """WF-06 fix: optimistic locking via updated_at.

        Если frontend передал expected_updated_at (ISO string), проверяем
        что instance.updated_at не изменился с момента последнего чтения.
        Если изменился — другой пользователь сохранил изменения, 409 Conflict.

        Это предотвращает silent data loss когда два лаборанта редактируют
        один бланк одновременно (last-write-wins без этой проверки).
        """
        if not expected_updated_at:
            return  # optimistic locking опционален, backward compatible
        try:
            from datetime import datetime
            # Парсим ISO string (frontend передаёт ISO 8601)
            expected_dt = datetime.fromisoformat(
                expected_updated_at.replace("Z", "+00:00")
            )
            actual_dt = instance.updated_at
            if actual_dt and actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=UTC)
            if expected_dt and actual_dt and abs((actual_dt - expected_dt).total_seconds()) > 1:
                raise LabReportingDomainError(
                    409,
                    "Бланк был изменён другим пользователем. "
                    "Обновите страницу, чтобы получить актуальные данные.",
                )
        except (ValueError, TypeError):
            # Если не удалось распарсить дату — не блокируем (graceful degradation)
            logger.warning(
                "[LAB] _assert_not_concurrently_modified: failed to parse "
                "expected_updated_at=%s, skipping lock check",
                expected_updated_at,
            )

    def _make_clone_code(self, source_code: str) -> str:
        suffix = 2
        while True:
            candidate = f"{source_code}_copy_{suffix}"
            if not self.repository.get_template_by_code(candidate):
                return candidate
            suffix += 1
