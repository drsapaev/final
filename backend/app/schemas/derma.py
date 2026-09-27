from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import ORMModel


class DermaExaminationCreate(ORMModel):
    patient_id: int
    visit_id: int | None = None
    examination_date: date
    skin_type: str = Field(min_length=1, max_length=255)
    skin_condition: str | None = Field(default=None, max_length=4000)
    lesions: str | None = Field(default=None, max_length=4000)
    distribution: str | None = Field(default=None, max_length=4000)
    symptoms: str | None = Field(default=None, max_length=4000)
    diagnosis: str | None = Field(default=None, max_length=4000)
    treatment_plan: str | None = Field(default=None, max_length=4000)


class DermaExaminationOut(ORMModel):
    id: int
    patient_id: int
    visit_id: int | None = None
    doctor_id: int | None = None
    examination_date: date
    skin_type: str
    skin_condition: str | None = None
    lesions: str | None = None
    distribution: str | None = None
    symptoms: str | None = None
    diagnosis: str | None = None
    treatment_plan: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DermaProcedureCreate(ORMModel):
    patient_id: int
    visit_id: int | None = None
    procedure_date: date
    procedure_type: str = Field(min_length=1, max_length=255)
    area_treated: str | None = Field(default=None, max_length=4000)
    products_used: str | None = Field(default=None, max_length=4000)
    results: str | None = Field(default=None, max_length=4000)
    follow_up: str | None = Field(default=None, max_length=4000)
    total_cost: float | None = None


class DermaProcedureOut(ORMModel):
    id: int
    patient_id: int
    visit_id: int | None = None
    doctor_id: int | None = None
    procedure_date: date
    procedure_type: str
    area_treated: str | None = None
    products_used: str | None = None
    results: str | None = None
    follow_up: str | None = None
    total_cost: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- P2-4b: unified history surface (EMR specialty_data + legacy fallback) ---
#
# The derma history GETs now union two read-only sources:
#   source="emr"    — rows projected out of dermatology EMRRecord
#                     (EMR v2, data.specialty_data); id is the synthetic
#                     string "emr-<emr_record_id>" (procedures append
#                     "-<index>" per entry inside the visit EMR);
#   source="legacy" — read-only rows from the closed legacy tables
#                     derma_examinations / derma_procedures (id int).
class DermaExaminationHistoryOut(DermaExaminationOut):
    id: int | str
    source: Literal["emr", "legacy"] = "legacy"


class DermaProcedureHistoryOut(DermaProcedureOut):
    id: int | str
    source: Literal["emr", "legacy"] = "legacy"


class DermaHistoryOut(ORMModel):
    """Единый read-model истории дерматологии (triage P2 follow-up).

    Обе секции объединяют ЭМК- и legacy-строки (newest-first, limit на
    секцию) и проецируются из одного скана ЭМК-кандидатов — фронтенд-хук
    истории читает оба раздела одним запросом.
    """

    examinations: list[DermaExaminationHistoryOut] = Field(default_factory=list)
    procedures: list[DermaProcedureHistoryOut] = Field(default_factory=list)
