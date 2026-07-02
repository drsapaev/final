from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.context_facades.emr_facade import (
    EmrContextFacade,
    EmrServiceContractAdapter,
)
from app.services.context_facades.patient_facade import (
    PatientContextFacade,
    PatientServiceContractAdapter,
)


def test_patient_facade_adapter_bridge_reads_birth_date(monkeypatch) -> None:
    patient_obj = SimpleNamespace(
        id=11,
        full_name="Facade Patient",
        phone="+998901111111",
        birth_date=date(1988, 7, 7),
    )
    monkeypatch.setattr("app.crud.patient.get", lambda db, id: patient_obj)

    facade = PatientContextFacade(PatientServiceContractAdapter(db=Mock()))
    summary = facade.lookup_patient_summary(patient_id=11, correlation_id="it-1")

    assert summary is not None
    assert summary.full_name == "Facade Patient"
    assert summary.birth_date == date(1988, 7, 7)


def test_emr_facade_adapter_bridge_indexes_phrases(monkeypatch) -> None:
    indexer = SimpleNamespace(
        index_single_emr=lambda emr_id, doctor_id, specialty: 4,
    )
    monkeypatch.setattr(
        "app.services.emr_phrase_indexer.get_emr_phrase_indexer",
        lambda db: indexer,
    )

    facade = EmrContextFacade(EmrServiceContractAdapter(db=Mock()))
    indexed = facade.index_emr_phrases(
        emr_id=21,
        doctor_id=31,
        specialty="dentist",
        correlation_id="it-2",
    )

    assert indexed == 4

