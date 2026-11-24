"""Clinical facts captured with the exact released report value."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, get_args

from app.schemas.lab_reporting import LabEvaluationStatus, LabInterpretation

NON_NUMERIC_RESULT_KINDS = ("qualified_numeric", "coded_qualitative", "text", "absent")


def frozen_assessment(
    snapshot: dict[str, Any], displayed_value: str | None
) -> tuple[LabEvaluationStatus, LabInterpretation | None, bool | None]:
    status = snapshot.get("status")
    interpretation = snapshot.get("interpretation")
    if status not in get_args(LabEvaluationStatus):
        return "unknown", None, None
    if interpretation not in get_args(LabInterpretation):
        interpretation = None
    abnormal = None
    if status == "evaluated" and displayed_value:
        if interpretation in ("low", "high", "warning", "abnormal", "critical"):
            abnormal = True
        elif interpretation == "normal":
            abnormal = False
    return status, interpretation, abnormal


@dataclass(frozen=True)
class ReleasedNumericObservation:
    observed_on: date
    value: Decimal
    context: tuple[str, ...]


def released_numeric_observation(
    displayed_value: str,
    payload: dict[str, Any] | None,
    snapshot: dict[str, Any],
    numeric: Decimal | None,
) -> ReleasedNumericObservation | None:
    if (
        not isinstance(payload, dict)
        or payload.get("kind") != "numeric"
        or payload.get("comparator") is not None
        or snapshot.get("visible") is not True
        or snapshot.get("status") not in ("evaluated", "not_evaluated", "not_applicable")
        or not isinstance(numeric, Decimal)
        or not numeric.is_finite()
    ):
        return None
    reference_date = snapshot.get("age_at_date")
    if not isinstance(reference_date, str) or snapshot.get(
        "reference_date_source"
    ) not in ("study_date", "specimen_collection"):
        return None
    context = tuple(
        snapshot.get(key)
        for key in (
            "analyte_code",
            "unit_code",
            "unit",
            "material_code",
            "method_code",
            "reference_date_source",
        )
    )
    if not all(isinstance(code, str) and code.strip() for code in context):
        return None
    try:
        observation_date = date.fromisoformat(reference_date)
        displayed_numeric = Decimal(displayed_value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if displayed_numeric != numeric or observation_date.isoformat() != reference_date:
        return None
    return ReleasedNumericObservation(observation_date, numeric, context)
