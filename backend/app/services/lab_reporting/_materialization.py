"""Materialization mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class MaterializationMixin(LabReportingServiceMixinBase):
    """Materialization methods for LabReportingService."""

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


