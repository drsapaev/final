"""Rule_Engine mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class RuleEngineMixin(LabReportingServiceMixinBase):
    """Rule_Engine methods for LabReportingService."""

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


