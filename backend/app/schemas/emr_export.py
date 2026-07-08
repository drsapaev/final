"""Pydantic schemas for EMR export/import endpoints.

P0-7 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously the EMR export endpoints accepted `emr_data: dict`,
`json_data: dict`, and `data: dict` with no validation, allowing
PHI schema drift, memory abuse via oversized payloads, and potential
deserialization attacks. These schemas enforce:
- Required core fields (patient_id, doctor_id) for export endpoints
- Size caps on string values (prevent multi-MB payloads)
- Rejection of pickle/deserialization attack keys (__class__, __init__, etc.)
- Type validation for known fields
- extra="allow" for the polymorphic EMR content (different templates
  have different fields)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


# Keys that are dangerous in deserialization contexts — reject them
# to prevent pickle-style attacks even if the dict is just JSON.
_DANGEROUS_KEYS = frozenset({
    "__class__",
    "__init__",
    "__new__",
    "__reduce__",
    "__reduce_ex__",
    "__del__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
    "__getstate__",
    "__setstate__",
    "__globals__",
    "__builtins__",
    "__import__",
    "subprocess",
    "os",
    "sys",
    "eval",
    "exec",
    "compile",
})

# Maximum string value length for any single field in the EMR data.
# Prevents multi-MB payloads that could OOM the export service.
_MAX_STRING_VALUE_LENGTH = 100_000  # 100KB per string value

# Maximum number of top-level keys in the EMR data dict.
_MAX_TOP_LEVEL_KEYS = 100

# Maximum nesting depth for the EMR data.
_MAX_NESTING_DEPTH = 10

# Maximum list length.
_MAX_LIST_LENGTH = 1000


def _validate_dict_recursive(data: Any, _depth: int = 0) -> None:
    """Recursively validate dict structure: reject dangerous keys,
    cap string lengths, cap nesting depth, cap list sizes."""
    if _depth > _MAX_NESTING_DEPTH:
        raise ValueError(
            f"EMR data nesting too deep (max {_MAX_NESTING_DEPTH} levels)"
        )
    if isinstance(data, str):
        if len(data) > _MAX_STRING_VALUE_LENGTH:
            raise ValueError(
                f"string value exceeds {_MAX_STRING_VALUE_LENGTH} characters"
            )
    elif isinstance(data, dict):
        if len(data) > _MAX_TOP_LEVEL_KEYS:
            raise ValueError(
                f"object has too many keys (max {_MAX_TOP_LEVEL_KEYS})"
            )
        for key in data:
            if isinstance(key, str) and key in _DANGEROUS_KEYS:
                raise ValueError(
                    f"dangerous key '{key}' is not allowed in EMR data"
                )
        for v in data.values():
            _validate_dict_recursive(v, _depth + 1)
    elif isinstance(data, list):
        if len(data) > _MAX_LIST_LENGTH:
            raise ValueError(
                f"list has too many items (max {_MAX_LIST_LENGTH})"
            )
        for item in data:
            _validate_dict_recursive(item, _depth + 1)


# =============================================================================
# EXPORT REQUESTS
# =============================================================================


class EMRExportDataRequest(BaseModel):
    """Request body for EMR export endpoints (JSON, XML, CSV, ZIP, estimate-size).

    EMR data is inherently polymorphic (different templates have different
    fields), so we use extra="allow" for the content. However, we enforce:
    - patient_id and doctor_id as required core fields
    - No dangerous deserialization keys
    - String value length caps (100KB per string)
    - Nesting depth limits (max 10 levels)
    - Top-level key count limits (max 100 keys)
    - List size limits (max 1000 items)
    """

    patient_id: int = Field(..., ge=1, description="Patient ID")
    doctor_id: int = Field(..., ge=1, description="Doctor ID")

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("EMR data must be a JSON object")
        _validate_dict_recursive(data)
        return data


# =============================================================================
# IMPORT REQUESTS
# =============================================================================


class EMRImportJsonRequest(BaseModel):
    """Request body for POST /emr/import/json.

    The imported JSON is the full export structure (metadata + emr +
    optional versions/templates/attachments). It's more polymorphic than
    the export request, so we don't require patient_id/doctor_id at the
    top level — they're inside the `emr` sub-object. We still enforce
    size caps and reject dangerous keys.
    """

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("import data must be a JSON object")
        _validate_dict_recursive(data)
        return data


# =============================================================================
# VALIDATE REQUEST
# =============================================================================


class EMRValidateDataRequest(BaseModel):
    """Request body for POST /emr/validate.

    The validate endpoint accepts arbitrary data to check against a
    format type. We enforce size caps and reject dangerous keys.
    """

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("validation data must be a JSON object")
        _validate_dict_recursive(data)
        return data


__all__ = [
    "EMRExportDataRequest",
    "EMRImportJsonRequest",
    "EMRValidateDataRequest",
]
