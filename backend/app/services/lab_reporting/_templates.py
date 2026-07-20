"""Templates mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class TemplatesMixin(LabReportingServiceMixinBase):
    """Templates methods for LabReportingService."""

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

    # ============================================================
    # === CATALOG MANAGEMENT ===
    # ============================================================


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


