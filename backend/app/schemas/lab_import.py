from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.lab_reporting import LabReportValueIn

Code = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.%/^-]+$")
]


class LabImportValue(LabReportValueIn):
    model_config = ConfigDict(extra="forbid")

    # Stable catalog analyte code rather than a template field key or label.
    field_key: Code = Field(validation_alias="analyte_code")
    value_text: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=500)


class LabImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID
    report_instance_id: int = Field(gt=0)
    specimen_barcode: str = Field(
        min_length=1, max_length=24, pattern=r"^[A-Za-z0-9-]+$"
    )
    expected_updated_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    replace_existing: bool = False
    method_code: Code | None = None
    values: list[LabImportValue] = Field(min_length=1, max_length=100)


class LabImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["manual", "csv"]
    rows: list[LabImportRow] = Field(min_length=1, max_length=100)


class LabImportRowOut(BaseModel):
    message_id: UUID
    report_instance_id: int
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
        ]
        | None
    ) = None


class LabImportBatchOut(BaseModel):
    rows: list[LabImportRowOut]
