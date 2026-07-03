from __future__ import annotations

from datetime import date, datetime
from typing import Any

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


# R-11 / P-003 (UX audit): schemas for the previously-stubbed /cardio/ecg
# endpoints. The frontend's CardiologistPanelUnified.jsx calls
# GET /cardio/ecg?patient_id=X and expects each row to expose at least
# id, ecg_date, rhythm, heart_rate, source, created_at, updated_at — see
# the historyEntries builder. Extra parsed parameters (PR, QRS, QT, ST,
# T-wave, axis) are returned too so the doctor can preview the recording
# without re-fetching the source file.
class CardioECGRecordCreate(ORMModel):
    patient_id: int
    visit_id: int | None = None
    file_id: int | None = None
    ecg_date: date
    heart_rate: float | None = None
    pr_interval: float | None = None
    qrs_duration: float | None = None
    qt_interval: float | None = None
    qt_corrected: float | None = None
    rhythm: str | None = Field(default=None, max_length=120)
    st_segment: str | None = Field(default=None, max_length=120)
    t_wave: str | None = Field(default=None, max_length=120)
    axis: str | None = Field(default=None, max_length=60)
    interpretation: str | None = Field(default=None, max_length=8000)
    source: str | None = Field(default=None, max_length=32)
    parameters: dict[str, Any] | None = None


class CardioECGRecordOut(ORMModel):
    id: int
    patient_id: int
    visit_id: int | None = None
    doctor_id: int | None = None
    file_id: int | None = None
    ecg_date: date
    heart_rate: float | None = None
    pr_interval: float | None = None
    qrs_duration: float | None = None
    qt_interval: float | None = None
    qt_corrected: float | None = None
    rhythm: str | None = None
    st_segment: str | None = None
    t_wave: str | None = None
    axis: str | None = None
    interpretation: str | None = None
    source: str | None = None
    parameters: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
