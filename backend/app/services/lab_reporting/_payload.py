"""Payload mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class PayloadMixin(LabReportingServiceMixinBase):
    """Payload methods for LabReportingService."""

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
                version.published_at = datetime.now(UTC)
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
                version.published_at = datetime.now(UTC)
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
            version.published_at = datetime.now(UTC)
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


