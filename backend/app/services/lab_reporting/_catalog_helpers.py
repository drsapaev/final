"""Catalog_Helpers mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class CatalogHelpersMixin(LabReportingServiceMixinBase):
    """Catalog_Helpers methods for LabReportingService."""

    def _catalog_reference_key(self, payload: dict[str, Any]) -> tuple[Any, ...]:
        return (
            payload.get("analyte_code"),
            payload.get("sex"),
            payload.get("age_min_months"),
            payload.get("age_max_months"),
            payload.get("material_code"),
            payload.get("method_code"),
            payload.get("unit_code"),
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

    def _resolve_field_unit_code(self, field_def: LabReportFieldDef) -> str | None:
        if field_def.unit_code:
            return field_def.unit_code
        analyte = self._get_catalog_analyte(field_def.analyte_code)
        if analyte and analyte.default_unit is not None and field_def.unit in (None, "", analyte.default_unit.symbol):
            return analyte.default_unit.code
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
            "provenance": {
                "mode": "catalog",
                "reference_range_id": reference_range.id,
                "analyte_code": reference_range.analyte_code,
                "sex": reference_range.sex,
                "age_min_months": reference_range.age_min_months,
                "age_max_months": reference_range.age_max_months,
                "material_code": reference_range.material_code,
                "method_code": reference_range.method_code,
                "unit_code": reference_range.unit_code,
            },
        }


    def _resolve_catalog_reference(
        self, field_def: LabReportFieldDef, context: dict[str, Any]
    ) -> dict[str, Any]:
        patient = context.get("patient", {})
        patient_sex = patient.get("sex")
        age_months = patient.get("age_months")
        specimen = context.get("specimen", {})
        unit_code = self._resolve_field_unit_code(field_def)
        analyte = self._get_catalog_analyte(field_def.analyte_code)
        default_unit_code = analyte.default_unit_code if analyte else None
        matched: list[LabCatalogReferenceRange] = []
        for reference_range in self._get_catalog_reference_ranges(field_def.analyte_code):
            if not reference_range.is_active:
                continue
            if reference_range.material_code and reference_range.material_code != specimen.get("material_code"):
                continue
            if reference_range.method_code and reference_range.method_code != context.get("method_code"):
                continue
            reference_unit_code = reference_range.unit_code or default_unit_code
            if reference_unit_code != unit_code or (unit_code is None and field_def.unit):
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
                "text": (field_def.reference_text or "") if not patient else "",
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
                -sum(bool(code) for code in (item.material_code, item.method_code, item.unit_code)),
                0 if item.sex else 1,
                0
                if item.age_min_months is not None or item.age_max_months is not None
                else 1,
                (item.age_max_months if item.age_max_months is not None else 10**9)
                - (item.age_min_months or 0),
                item.sort_order,
                item.id,
            )
        )
        return self._catalog_reference_to_payload(matched[0])


    def _resolve_clinical_configuration_reference(
        self, field_def: LabReportFieldDef, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        configuration = context.get("clinical_configuration")
        if not configuration:
            return None
        snapshot = configuration.get("configuration_snapshot") or {}
        analyte_code = field_def.analyte_code
        unit_code = self._resolve_field_unit_code(field_def)
        method_code = context.get("method_code")
        entries = snapshot.get("reference_intervals") or []
        configured_scope = [
            item
            for item in entries
            if item.get("analyte_code") == analyte_code
            and item.get("unit_code") == unit_code
        ]
        if not configured_scope:
            return None

        patient = context.get("patient", {})
        specimen = context.get("specimen", {})
        age_months = patient.get("age_months")
        sex = patient.get("sex")
        material_code = specimen.get("material_code")
        matches = []
        for item in configured_scope:
            if item.get("method_code") != method_code:
                continue
            if item.get("material_code") and item.get("material_code") != material_code:
                continue
            if item.get("sex") and item.get("sex") != sex:
                continue
            if item.get("sex") and not sex:
                continue
            if item.get("age_min_months") is not None and (
                age_months is None or age_months < item["age_min_months"]
            ):
                continue
            if item.get("age_max_months") is not None and (
                age_months is None or age_months > item["age_max_months"]
            ):
                continue
            matches.append(item)

        def rank(item: dict[str, Any]) -> tuple[int, int, str]:
            dimensions = ("material_code", "sex", "age_min_months", "age_max_months")
            specificity = sum(item.get(name) is not None for name in dimensions)
            low = item.get("age_min_months")
            high = item.get("age_max_months")
            age_width = high - low if low is not None and high is not None else 10**9
            return (-specificity, age_width, item["rule_code"])

        version_id = configuration["version_id"]
        version_no = configuration["version_no"]
        if not matches:
            reference = self._empty_reference_payload()
            reference["provenance"] = {
                "mode": "clinic_configuration",
                "clinical_configuration_version_id": version_id,
                "clinical_configuration_version_no": version_no,
                "status": "no_demographic_match",
                "configured_scope_rule_codes": sorted(
                    item["rule_code"] for item in configured_scope
                ),
            }
            return self._apply_clinical_critical_values(
                reference, field_def, context
            )

        selected = sorted(matches, key=rank)[0]
        low = selected.get("low")
        high = selected.get("high")
        reference = {
            "text": selected.get("text") or (
                f"{low} - {high}" if low is not None and high is not None else ""
            ),
            "low": low,
            "high": high,
            "warning_low": selected.get("warning_low"),
            "warning_high": selected.get("warning_high"),
            "critical_low": selected.get("critical_low"),
            "critical_high": selected.get("critical_high"),
            "low_flag": None,
            "high_flag": None,
            "warning_low_flag": None,
            "warning_high_flag": None,
            "critical_low_flag": None,
            "critical_high_flag": None,
            "flag": None,
            "provenance": {
                "mode": "clinic_configuration",
                "clinical_configuration_version_id": version_id,
                "clinical_configuration_version_no": version_no,
                "rule_code": selected["rule_code"],
                "source_ref": selected.get("source_ref"),
            },
        }
        return self._apply_clinical_critical_values(reference, field_def, context)


    def _apply_clinical_critical_values(
        self,
        reference: dict[str, Any],
        field_def: LabReportFieldDef,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        configuration = context.get("clinical_configuration")
        if not configuration:
            return reference
        provenance = reference.get("provenance") or {}
        # Clinic-specific critical thresholds supersede global/template values.
        # A locally configured reference interval may itself carry its approved
        # critical bounds, so retain those only for that exact matched rule.
        if provenance.get("mode") != "clinic_configuration":
            reference["critical_low"] = None
            reference["critical_high"] = None

        snapshot = configuration.get("configuration_snapshot") or {}
        analyte_code = field_def.analyte_code
        unit_code = self._resolve_field_unit_code(field_def)
        method_code = context.get("method_code")
        scoped = [
            item
            for item in snapshot.get("critical_values", [])
            if item.get("analyte_code") == analyte_code
            and item.get("unit_code") == unit_code
        ]
        patient = context.get("patient", {})
        specimen = context.get("specimen", {})
        matches = []
        for item in scoped:
            if item.get("method_code") != method_code:
                continue
            if item.get("material_code") and item.get("material_code") != specimen.get("material_code"):
                continue
            if item.get("sex") and item.get("sex") != patient.get("sex"):
                continue
            if item.get("sex") and not patient.get("sex"):
                continue
            age_months = patient.get("age_months")
            if item.get("age_min_months") is not None and (
                age_months is None or age_months < item["age_min_months"]
            ):
                continue
            if item.get("age_max_months") is not None and (
                age_months is None or age_months > item["age_max_months"]
            ):
                continue
            matches.append(item)

        def critical_rank(item: dict[str, Any]) -> tuple[int, int, str]:
            specificity = sum(
                item.get(name) is not None
                for name in ("material_code", "sex", "age_min_months", "age_max_months")
            )
            low = item.get("age_min_months")
            high = item.get("age_max_months")
            age_width = high - low if low is not None and high is not None else 10**9
            return (-specificity, age_width, item["rule_code"])

        matches.sort(key=critical_rank)
        for item in matches:
            key = "critical_low" if item["direction"] == "below" else "critical_high"
            if reference.get(key) is None:
                reference[key] = item["threshold"]
        provenance = dict(provenance)
        provenance["clinical_configuration_version_id"] = configuration["version_id"]
        provenance["clinical_configuration_version_no"] = configuration["version_no"]
        provenance["critical_rule_codes"] = [item["rule_code"] for item in matches]
        reference["provenance"] = provenance
        return reference


    @staticmethod
    def _empty_reference_payload() -> dict[str, Any]:
        return {
            "text": "",
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


