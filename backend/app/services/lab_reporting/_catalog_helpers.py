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


