from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.domain.contracts.queue_contracts import QueueContractFacade
from app.services.context_facades.emr_facade import EmrServiceContractAdapter
from app.services.context_facades.iam_facade import IamServiceContractAdapter
from app.services.context_facades.patient_facade import PatientServiceContractAdapter


class _QueueContractStub:
    def get_queue_token(self, token_id: int, request_id: str | None = None):
        _ = (token_id, request_id)
        return None

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        _ = (token_id, actor_user_id, request_id)
        return True

    def get_local_timestamp(
        self,
        db=None,
        timezone: str | None = None,
        request_id: str | None = None,
    ) -> datetime:
        _ = (db, timezone, request_id)
        return datetime(2026, 1, 1, 10, 0, 0)


def test_queue_contract_facade_delegates_get_local_timestamp() -> None:
    facade = QueueContractFacade(_QueueContractStub())

    result = facade.get_local_timestamp(db=Mock(), timezone="Asia/Tashkent")

    assert result == datetime(2026, 1, 1, 10, 0, 0)


def test_patient_service_contract_adapter_maps_patient_summary(
    monkeypatch,
) -> None:
    patient_obj = SimpleNamespace(
        id=10,
        full_name="Test Patient",
        phone="+998900000000",
        birth_date=date(1990, 5, 12),
    )
    monkeypatch.setattr("app.crud.patient.get", lambda db, id: patient_obj)

    adapter = PatientServiceContractAdapter(db=Mock())
    summary = adapter.get_patient_summary(patient_id=10)

    assert summary is not None
    assert summary.patient_id == 10
    assert summary.full_name == "Test Patient"
    assert summary.birth_date == date(1990, 5, 12)


def test_iam_service_contract_adapter_permission_matrix() -> None:
    actor = SimpleNamespace(id=42, role="Doctor")
    adapter = IamServiceContractAdapter(actor=actor)

    allowed = adapter.check_permission(actor_user_id=42, permission_code="emr.write")
    denied = adapter.check_permission(actor_user_id=42, permission_code="unknown")

    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.reason == "permission_unknown:unknown"


def test_emr_service_contract_adapter_indexes_via_phrase_indexer(monkeypatch) -> None:
    indexer = SimpleNamespace(
        index_single_emr=lambda emr_id, doctor_id, specialty: 7,
    )
    monkeypatch.setattr(
        "app.services.emr_phrase_indexer.get_emr_phrase_indexer",
        lambda db: indexer,
    )

    adapter = EmrServiceContractAdapter(db=Mock())
    indexed = adapter.index_emr_phrases(
        emr_id=5,
        doctor_id=9,
        specialty="cardio",
    )

    assert indexed == 7

