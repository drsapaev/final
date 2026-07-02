from __future__ import annotations

import logging
from datetime import date
from typing import Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger

logger = logging.getLogger(__name__)


class PatientSummary(BaseModel):
    patient_id: int
    full_name: str
    phone: str | None = None
    birth_date: date | None = None
    active: bool = True


class PatientContract(Protocol):
    def get_patient_summary(
        self,
        patient_id: int,
        request_id: str | None = None,
    ) -> PatientSummary | None: ...

    def ensure_patient_edit_access(
        self,
        patient_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool: ...


class PatientContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: PatientContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "patient")

    def get_patient_summary(
        self,
        patient_id: int,
        request_id: str | None = None,
    ) -> PatientSummary | None:
        self._contract_logger.log_entry(
            "get_patient_summary",
            request_id,
            patient_id=patient_id,
        )
        result = self._contract.get_patient_summary(
            patient_id=patient_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_patient_summary",
            request_id,
            found=result is not None,
        )
        return result

    def ensure_patient_edit_access(
        self,
        patient_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        self._contract_logger.log_entry(
            "ensure_patient_edit_access",
            request_id,
            patient_id=patient_id,
            actor_user_id=actor_user_id,
        )
        allowed = self._contract.ensure_patient_edit_access(
            patient_id=patient_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "ensure_patient_edit_access",
            request_id,
            allowed=allowed,
        )
        return allowed
