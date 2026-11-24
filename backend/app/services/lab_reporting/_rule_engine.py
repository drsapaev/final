"""Rule_Engine mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase
from app.services.lab_reporting._result_values import (
    COMPARATOR_LABELS,
    qualitative_code,
)


class RuleEngineMixin(LabReportingServiceMixinBase):
    """Rule_Engine methods for LabReportingService."""

    def _extract_effective_value(self, value: LabReportValue) -> Any:
        if (value.result_payload or {}).get("kind") == "qualified_numeric":
            return self._format_result_display(value)
        return value.value_numeric if value.value_numeric is not None else value.value_text


    def _build_rule_context(
        self, patient_snapshot: dict[str, Any], field_values: dict[str, Any]
    ) -> dict[str, Any]:
        patient = dict(patient_snapshot or {})
        if isinstance(patient.get("sex"), str):
            sex = patient["sex"].strip().upper()
            patient["sex"] = sex if sex in {"M", "F", "X"} else None
        return {"patient": patient, "field": field_values}


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
        self, condition: dict[str, Any] | None, context: dict[str, Any],
        *, evaluate_qualitative: bool = False,
    ) -> bool:
        if not condition:
            return True
        if "all" in condition:
            return all(
                self._evaluate_condition(item, context, evaluate_qualitative=evaluate_qualitative)
                for item in condition["all"]
            )
        if "any" in condition:
            return any(
                self._evaluate_condition(item, context, evaluate_qualitative=evaluate_qualitative)
                for item in condition["any"]
            )

        source = condition.get("source")
        left = self._lookup_context_value(source, context)
        op = condition.get("op", "exists")
        right = condition.get("value")
        if evaluate_qualitative and source and source.startswith("field.") and op in {"eq", "neq", "ieq", "ineq"}:
            expected_code = qualitative_code(right)
            if expected_code is not None:
                actual_code = qualitative_code(left)
                if op in {"eq", "ieq"}:
                    return actual_code == expected_code
                return {actual_code, expected_code} == {"negative", "positive"}
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
        if op in {"gt", "gte", "lt", "lte", "between"}:
            left = self._coerce_decimal(left)
            right = self._coerce_decimal(right)
            if left is None:
                return False
            if op == "between":
                minimum = self._coerce_decimal(condition.get("min"))
                maximum = self._coerce_decimal(condition.get("max"))
                return minimum is not None and maximum is not None and minimum <= left <= maximum
            if right is None:
                return False
            return {
                "gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right,
            }[op]
        if op == "in":
            return left in (condition.get("values") or [])
        return False


    def _resolve_rule_payload(
        self, rule: dict[str, Any] | None, context: dict[str, Any]
    ) -> dict[str, Any]:
        if not rule:
            return {}
        cases = rule.get("cases") or []
        for case in cases:
            if self._evaluate_condition(case.get("when"), context, evaluate_qualitative=True):
                return case
        if any(self._missing_age_context(case.get("when"), context) for case in cases):
            return {}
        default = rule.get("default")
        return default if isinstance(default, dict) else {}

    def _missing_age_context(self, condition: dict[str, Any] | None, context: dict[str, Any]) -> bool:
        if not condition:
            return False
        source = condition.get("source")
        if source in {"patient.age_days", "patient.age_months", "patient.age_years"}:
            return self._lookup_context_value(source, context) is None
        return any(
            self._missing_age_context(child, context)
            for combinator in ("all", "any")
            for child in condition.get(combinator) or []
        )


    def _resolve_reference(
        self, field_def: LabReportFieldDef, context: dict[str, Any]
    ) -> dict[str, Any]:
        if field_def.reference_mode == "catalog":
            return self._resolve_catalog_reference(field_def, context)
        if field_def.reference_mode == "rule_based":
            payload = self._resolve_rule_payload(field_def.reference_rule, context)
            fallback_text = (field_def.reference_text or "") if payload or not context.get("patient") else ""
            return {
                "text": payload.get("text") or fallback_text,
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
                "provenance": {"mode": "template_rule", "rule": self._json_safe_value(payload)},
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
            parsed = Decimal(str(value).strip().replace(",", "."))
            return parsed if parsed.is_finite() else None
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

    def _format_result_display(self, value: LabReportValue) -> str:
        comparator = (value.result_payload or {}).get("comparator")
        if comparator in COMPARATOR_LABELS and value.value_numeric is not None:
            return f"{COMPARATOR_LABELS[comparator]}{self._format_decimal_display(value.value_numeric)}"
        return self._value_display(value.value_numeric, value.value_text)


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
            "unit_code": self._resolve_field_unit_code(field_def),
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
            matches = numeric_value < threshold if comparison == "lt" else numeric_value > threshold
            if not matches:
                continue
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
                    matched_threshold={"key": threshold_key, "operator": comparison, "value": threshold},
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
        if effective_value in (None, "") or (
            field_def.value_type == "numeric" and self._coerce_decimal(effective_value) is None
        ):
            return {
                "flag": None,
                "source": None,
                "severity_rank": None,
                "meta": None,
            }
        numeric_value = self._coerce_decimal(effective_value)

        payload, source = self._flag_rule(field_def, context, reference)
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

    def _flag_rule(
        self, field_def: LabReportFieldDef, context: dict[str, Any], reference: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        rule = field_def.highlight_rule or {}
        mode = rule.get("mode")
        if mode == "range":
            return rule, "range_rule"
        if mode == "rule_based_reference":
            return reference, f"{field_def.reference_mode}_reference"
        if rule:
            return self._resolve_rule_payload(rule, context), "highlight_rule"
        return {}, None

    def _refresh_result_evaluation(
        self, instance: LabReportInstance, *, validate_existing: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Refresh every saved field against the same packet and specimen context."""
        field_map = self._field_map(instance.template_version)
        self._normalize_existing_results(instance, field_map, strict=validate_existing)
        current_values = {
            value.field_key: self._extract_effective_value(value) for value in instance.values
        }
        specimen_context = self._refresh_reference_context(instance)
        context = {
            **self._build_rule_context(instance.patient_snapshot, current_values),
            "specimen": specimen_context,
        }
        for value in instance.values:
            field_def = field_map.get(value.field_key)
            if field_def is None:
                continue
            self._evaluate_saved_result(instance, field_def, value, context)
        return current_values, context

    def _normalize_existing_results(
        self, instance: LabReportInstance, field_map: dict[str, LabReportFieldDef], *, strict: bool,
    ) -> None:
        updates = []
        for value in instance.values:
            field_def = field_map.get(value.field_key)
            if field_def is None or (value.result_payload and not strict):
                continue
            payload = dict(value.result_payload or {})
            payload.update({
                "result_kind": payload.pop("kind", None),
                "value_text": value.value_text,
                "value_numeric": value.value_numeric,
                "comment": value.comment,
            })
            try:
                normalized = self._normalize_value_payload(payload, field_def)
            except LabReportingDomainError:
                if strict:
                    raise
                continue
            updates.append((value, normalized))
        for value, normalized in updates:
            value.value_text = normalized["value_text"]
            value.value_numeric = normalized["value_numeric"]
            result = normalized["result_payload"]
            source_specimen_id = (value.result_payload or {}).get("source_specimen_id")
            if result and result["kind"] != "absent" and source_specimen_id is not None:
                result = {**result, "source_specimen_id": source_specimen_id}
            value.result_payload = result

    def _evaluate_saved_result(
        self, instance: LabReportInstance, field_def: LabReportFieldDef, value: LabReportValue,
        context: dict[str, Any],
    ) -> None:
        result = value.result_payload or {}
        field_context = {**context, "method_code": result.get("method_code")}
        visible = self._is_visible(field_def.visibility_rule, field_context)
        reference = self._resolve_reference(field_def, field_context) if visible else {}
        effective_value = field_context["field"].get(value.field_key)
        flag = self._resolve_flag(
            field_def=field_def,
            effective_value=effective_value if visible and result else None,
            context=field_context,
            reference=reference,
        )
        value.resolved_reference_text = reference.get("text")
        value.resolved_flag = flag["flag"]
        value.resolved_flag_source = flag["source"]
        value.resolved_flag_severity = flag["severity_rank"]
        value.resolved_flag_meta = flag["meta"]
        rule, rule_source = self._flag_rule(field_def, field_context, reference)
        status, interpretation = self._evaluation_outcome(result, effective_value, visible, flag, rule)
        value.evaluation_snapshot = self._json_safe_value({
            "status": status,
            "interpretation": interpretation,
            "visible": visible,
            "template_version_id": instance.template_version_id,
            "analyte_code": field_def.analyte_code,
            "unit": self._resolve_field_unit(field_def),
            "unit_code": self._resolve_field_unit_code(field_def),
            "material_code": field_context["specimen"].get("material_code"),
            "method_code": result.get("method_code"),
            "age_at_date": instance.patient_snapshot.get("age_at_date"),
            "age_days": instance.patient_snapshot.get("age_days"),
            "reference_date_source": instance.patient_snapshot.get("age_date_source"),
            "reference": reference.get("provenance"),
            "rule_source": rule_source,
            "thresholds": self._threshold_snapshot(rule),
        })

    def _evaluation_outcome(
        self, result: dict[str, Any], effective_value: Any, visible: bool,
        flag: dict[str, Any], rule: dict[str, Any],
    ) -> tuple[str, str | None]:
        if not visible or result.get("kind") == "absent":
            return "not_applicable", None
        if effective_value in (None, ""):
            return "missing", None
        if not result or result.get("kind") == "qualified_numeric":
            return "not_evaluated", None
        if flag.get("flag"):
            interpretation = flag["flag"]
            if interpretation not in {"normal", "low", "high", "warning", "abnormal", "critical", "negative", "positive", "indeterminate"}:
                interpretation = "abnormal"
            return "evaluated", interpretation
        qualitative = result.get("qualitative_code")
        if qualitative in {"positive", "negative"}:
            return "evaluated", qualitative
        if qualitative == "indeterminate":
            return "not_evaluated", qualitative
        if result.get("kind") == "text" and rule:
            return "not_evaluated", None
        if result.get("kind") == "numeric" and any(
            self._coerce_decimal(rule.get(key)) is not None for key in ("low", "high")
        ):
            return "evaluated", "normal"
        return "not_applicable", None


