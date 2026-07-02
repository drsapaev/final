from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import ORMModel


class CardioBloodTestCreate(ORMModel):
    patient_id: int
    visit_id: int | None = None
    test_date: date
    cholesterol_total: float | None = None
    cholesterol_hdl: float | None = None
    cholesterol_ldl: float | None = None
    triglycerides: float | None = None
    glucose: float | None = None
    crp: float | None = None
    troponin: float | None = None
    interpretation: str | None = Field(default=None, max_length=4000)


class CardioBloodTestOut(ORMModel):
    id: int
    patient_id: int
    visit_id: int | None = None
    doctor_id: int | None = None
    test_date: date
    cholesterol_total: float | None = None
    cholesterol_hdl: float | None = None
    cholesterol_ldl: float | None = None
    triglycerides: float | None = None
    glucose: float | None = None
    crp: float | None = None
    troponin: float | None = None
    interpretation: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
