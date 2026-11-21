"""Validate ICD provider output without treating malformed data as no results."""

import json
import math
import re
from typing import Any


def _reject_nonstandard_number(_value: str) -> None:
    raise ValueError("non-standard JSON number")


def parse_icd_provider_suggestions(content: str) -> list[dict[str, Any]]:
    """Accept a JSON array or fenced JSON array; do not expose raw content."""
    try:
        text = content.strip()
        if text.startswith("```"):
            match = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
            if not match:
                raise ValueError("invalid code fence")
            text = match.group(1)
        result = json.loads(text, parse_constant=_reject_nonstandard_number)
        if not isinstance(result, list):
            raise ValueError("expected an array")
        for item in result:
            if not isinstance(item, dict):
                raise ValueError("expected suggestion objects")
            code = item.get("code")
            labels = (item.get("name"), item.get("label"), item.get("description"))
            if not isinstance(code, str) or not code.strip() or not any(
                isinstance(value, str) and value.strip() for value in labels
            ):
                raise ValueError("incomplete suggestion")
            if "confidence" in item:
                confidence = item["confidence"]
                if isinstance(confidence, bool) or not isinstance(confidence, (int, float, str)):
                    raise ValueError("invalid confidence")
                numeric_confidence = float(confidence)
                if not math.isfinite(numeric_confidence) or not 0 <= numeric_confidence <= 1:
                    raise ValueError("invalid confidence")
        return result
    except (AttributeError, TypeError, ValueError, OverflowError):
        # JSON decoder messages and contents may contain patient data. Do not
        # log or expose the provider payload through the fallback exception.
        raise RuntimeError("AI provider returned invalid ICD suggestions") from None
