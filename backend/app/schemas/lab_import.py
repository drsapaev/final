from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import PydanticKnownError

from app.schemas.lab_reporting import LabInstrumentFlags, LabReportValueIn

Code = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.%/^-]+$")
]
MAX_REPORT_INSTANCE_ID = 2**31 - 1
MAX_IMPORT_BATCH_ROWS = 100
ReportInstanceId = Annotated[int, Field(ge=1, le=MAX_REPORT_INSTANCE_ID)]


class LabImportValue(LabReportValueIn):
    model_config = ConfigDict(extra="forbid")

    # Stable catalog analyte code rather than a template field key or label.
    field_key: Code = Field(validation_alias="analyte_code")
    value_text: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=500)
    instrument_flags: LabInstrumentFlags = Field(
        default_factory=list,
        description="Opaque instrument warning codes in their original token form",
    )


class LabImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID
    report_instance_id: ReportInstanceId
    specimen_barcode: str = Field(
        min_length=1, max_length=24, pattern=r"^[A-Za-z0-9-]+$"
    )
    expected_updated_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    replace_existing: bool = False
    method_code: Code | None = None
    values: list[LabImportValue] = Field(min_length=1, max_length=100)


# Internal correlation for a malformed row, ordered as message ID then report ID.
MalformedLabImportRow = tuple[UUID | None, int | None]


def _parse_batch_row(value: object) -> LabImportRow | MalformedLabImportRow:
    try:
        return LabImportRow.model_validate(value)
    except ValidationError:
        # Keep only bounded identifiers for correlation. Validation details
        # can include clinical input and must not cross the batch boundary.
        if not isinstance(value, dict):
            return None, None
        message_id = value.get("message_id")
        if isinstance(message_id, str) and len(message_id) <= 45:
            try:
                message_id = UUID(message_id)
            except ValueError:
                message_id = None
        report_id = value.get("report_instance_id")
        if isinstance(report_id, str) and len(report_id) <= 10:
            if report_id.isascii() and report_id.isdecimal():
                report_id = int(report_id)
        return (
            message_id if isinstance(message_id, UUID) else None,
            (
                report_id
                if type(report_id) is int and 1 <= report_id <= MAX_REPORT_INSTANCE_ID
                else None
            ),
        )


BatchImportRow = Annotated[
    LabImportRow | SkipJsonSchema[MalformedLabImportRow],
    BeforeValidator(_parse_batch_row),
]


class LabImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["manual", "csv"]
    rows: list[BatchImportRow] = Field(
        min_length=1,
        max_length=MAX_IMPORT_BATCH_ROWS,
        description=(
            "Rows are validated individually and outcomes follow the input order."
        ),
    )

    @field_validator("rows", mode="before")
    @classmethod
    def bound_batch_size(cls, value: object) -> object:
        if isinstance(value, (list, tuple)) and len(value) > MAX_IMPORT_BATCH_ROWS:
            raise PydanticKnownError(
                "too_long",
                {
                    "field_type": "List",
                    "max_length": MAX_IMPORT_BATCH_ROWS,
                    "actual_length": len(value),
                },
            )
        return value


class LabImportRowOut(BaseModel):
    row_index: int = Field(ge=0, description="Zero-based index in the submitted batch.")
    message_id: UUID | None
    report_instance_id: ReportInstanceId | None
    status: Literal["ready", "saved", "duplicate", "error"]
    receipt_id: int | None = None
    updated_at: datetime | None = None
    existing_values: int = 0
    error_code: (
        Literal[
            "report_not_found",
            "report_locked",
            "stale_report",
            "specimen_mismatch",
            "method_mismatch",
            "unknown_analyte",
            "duplicate_analyte",
            "unit_mismatch",
            "invalid_value",
            "message_conflict",
            "values_exist",
            "invalid_row",
        ]
        | None
    ) = None


class LabImportBatchOut(BaseModel):
    rows: list[LabImportRowOut]
