"""Normalize report values before persisting or classifying them."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.lab_reporting._base import LabReportingDomainError

COMPARATORS = {"<": "lt", "<=": "lte", "≤": "lte", ">": "gt", ">=": "gte", "≥": "gte"}
COMPARATOR_LABELS = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥"}
NUMERIC_TEXT = re.compile(
    r"([<>]=?|[≤≥])?\s*([+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)(?:[Ee][+-]?[0-9]{1,3})?)"
)
METHOD_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
QUALITATIVE_ALIASES = {
    "negative": {
        "negative",
        "not detected",
        "отрицательно",
        "отрицательный",
        "не обнаружено",
        "не обнаружен",
        "аникланмайди",
        "аниқланмайди",
        "аниқланмади",
        "аниқланмаган",
        "aniqlanmadi",
        "aniqlanmaydi",
        "бўлмайди",
        "булмайди",
        "bo'lmaydi",
    },
    "positive": {
        "positive",
        "detected",
        "положительно",
        "положительный",
        "обнаружено",
        "обнаружен",
        "аникланади",
        "аниқланади",
        "аниқланди",
        "aniqlanadi",
        "aniqlandi",
    },
    "indeterminate": {
        "indeterminate",
        "equivocal",
        "неопределённо",
        "неопределенно",
        "сомнительно",
        "ноаниқ",
        "ноаник",
        "noaniq",
    },
}


def qualitative_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.casefold().replace("’", "'").replace("ʻ", "'").split())
    return next(
        (
            code
            for code, aliases in QUALITATIVE_ALIASES.items()
            if normalized in aliases
        ),
        None,
    )


def age_components(
    birth_date: date | None, reference_date: date | None
) -> dict[str, int | None]:
    if birth_date is None or reference_date is None or reference_date < birth_date:
        return {"age_days": None, "age_months": None, "age_years": None}
    months = (
        (reference_date.year - birth_date.year) * 12
        + reference_date.month
        - birth_date.month
    )
    months -= reference_date.day < birth_date.day
    return {
        "age_days": (reference_date - birth_date).days,
        "age_months": months,
        "age_years": months // 12,
    }


def _numeric_parts(value: Any, field_key: str) -> tuple[Decimal, str | None]:
    # Reject values the Numeric(18, 4) column would silently round or overflow.
    raw = str(value).strip()
    match = NUMERIC_TEXT.fullmatch(raw) if len(raw) <= 128 else None
    if match:
        symbol, digits = match.groups()
        try:
            number = Decimal(digits.replace(",", "."))
            if abs(number) < 10**14 and number.quantize(Decimal("0.0001")) == number:
                return (Decimal(0) if number.is_zero() else number), COMPARATORS.get(
                    symbol
                )
        except InvalidOperation:
            pass
    raise LabReportingDomainError(400, f"Invalid numeric value for {field_key}")


def _incompatible_fields(field_key: str) -> LabReportingDomainError:
    return LabReportingDomainError(400, f"Incompatible result fields for {field_key}")


def _normalize_numeric_result(
    field_key: str,
    value_text: str | None,
    number_input: Any,
    result_kind: str | None,
    comparator: str | None,
) -> tuple[str | None, Decimal | None, dict[str, str] | None]:
    representations = [
        _numeric_parts(item, field_key)
        for item in (number_input, value_text)
        if item is not None
    ]
    if not representations:
        if comparator is not None or result_kind is not None:
            raise _incompatible_fields(field_key)
        return None, None, None

    number = representations[0][0]
    if any(parsed != number for parsed, _ in representations):
        raise _incompatible_fields(field_key)
    comparators = {parsed for _, parsed in representations if parsed is not None}
    if comparator is not None:
        if not isinstance(comparator, str) or comparator not in COMPARATOR_LABELS:
            raise _incompatible_fields(field_key)
        comparators.add(comparator)
    if len(comparators) > 1:
        raise _incompatible_fields(field_key)

    comparator = next(iter(comparators), None)
    kind = "qualified_numeric" if comparator else "numeric"
    if result_kind not in (None, kind):
        raise _incompatible_fields(field_key)
    result = {"kind": kind}
    if comparator:
        result["comparator"] = comparator
    if comparator or value_text is None:
        rendered = format(number.normalize(), "f")
        value_text = (
            f"{COMPARATOR_LABELS[comparator]}{rendered}" if comparator else rendered
        )
    return value_text, number, result


def _normalize_text_result(
    field_key: str,
    value_text: str | None,
    result_kind: str | None,
    code: str | None,
    choice_options: list[str] | None,
) -> tuple[str | None, dict[str, str] | None]:
    inferred_code = qualitative_code(value_text)
    if code is not None and (
        result_kind == "text"
        or not isinstance(code, str)
        or code not in QUALITATIVE_ALIASES
        or (value_text is not None and inferred_code != code)
    ):
        raise _incompatible_fields(field_key)
    code = code or inferred_code
    if choice_options and (value_text is not None or code is not None):
        selected_option = next(
            (
                option
                for option in choice_options
                if (
                    value_text is not None
                    and option.strip().casefold() == value_text.casefold()
                )
                or (code is not None and qualitative_code(option) == code)
            ),
            None,
        )
        if selected_option is None:
            raise LabReportingDomainError(400, f"Invalid choice for {field_key}")
        value_text = value_text or selected_option
    if result_kind == "coded_qualitative" and code is None:
        raise _incompatible_fields(field_key)
    if code is not None and result_kind != "text":
        return value_text or code, {
            "kind": "coded_qualitative",
            "qualitative_code": code,
        }
    if value_text is not None:
        return value_text, {"kind": "text"}
    if result_kind == "text":
        raise _incompatible_fields(field_key)
    return None, None


def normalize_result_value(
    payload: dict[str, Any],
    *,
    field_key: str,
    value_type: str,
    choice_options: list[str] | None,
) -> dict[str, Any]:
    result_kind = payload.get("result_kind")
    comparator = payload.get("comparator")
    code = payload.get("qualitative_code")
    method_code = payload.get("method_code")
    reason = payload.get("absence_reason")
    number_input = payload.get("value_numeric")
    value_text = payload.get("value_text")
    if value_text is not None and not isinstance(value_text, str):
        raise _incompatible_fields(field_key)
    value_text = value_text.strip() or None if value_text is not None else None
    number_input = None if number_input == "" else number_input
    number = None

    if result_kind == "absent":
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise _incompatible_fields(field_key)
        if any(
            item is not None for item in (value_text, number_input, comparator, code)
        ):
            raise _incompatible_fields(field_key)
        result = {"kind": "absent", "absence_reason": reason.strip()}
    elif reason is not None:
        raise _incompatible_fields(field_key)
    elif value_type == "numeric":
        if code is not None or result_kind not in (
            None,
            "numeric",
            "qualified_numeric",
        ):
            raise _incompatible_fields(field_key)
        value_text, number, result = _normalize_numeric_result(
            field_key,
            value_text,
            number_input,
            result_kind,
            comparator,
        )
    else:
        if (
            number_input is not None
            or comparator is not None
            or result_kind not in (None, "coded_qualitative", "text")
        ):
            raise _incompatible_fields(field_key)
        value_text, result = _normalize_text_result(
            field_key,
            value_text,
            result_kind,
            code,
            choice_options,
        )

    if method_code is not None:
        if (
            not isinstance(method_code, str)
            or not METHOD_CODE.fullmatch(method_code)
            or not result
            or result["kind"] == "absent"
        ):
            raise _incompatible_fields(field_key)
        result["method_code"] = method_code

    return {
        "value_text": value_text,
        "value_numeric": number,
        "comment": payload.get("comment"),
        "result_payload": result,
    }
