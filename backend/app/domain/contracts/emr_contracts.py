from __future__ import annotations

import logging
from typing import Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger


logger = logging.getLogger(__name__)


class VisitClinicalSnapshot(BaseModel):
    visit_id: int
    patient_id: int
    diagnosis: str | None = None
    clinical_status: str = "draft"


class EmrContract(Protocol):
    def get_visit_clinical_snapshot(
        self,
        visit_id: int,
        request_id: str | None = None,
    ) -> VisitClinicalSnapshot | None: ...

    def append_clinical_note(
        self,
        visit_id: int,
        note_text: str,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool: ...

    def index_emr_phrases(
        self,
        emr_id: int,
        doctor_id: int,
        specialty: str | None = None,
        request_id: str | None = None,
    ) -> int: ...


class EmrContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: EmrContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "emr")

    def get_visit_clinical_snapshot(
        self,
        visit_id: int,
        request_id: str | None = None,
    ) -> VisitClinicalSnapshot | None:
        self._contract_logger.log_entry(
            "get_visit_clinical_snapshot",
            request_id,
            visit_id=visit_id,
        )
        result = self._contract.get_visit_clinical_snapshot(
            visit_id=visit_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_visit_clinical_snapshot",
            request_id,
            found=result is not None,
        )
        return result

    def append_clinical_note(
        self,
        visit_id: int,
        note_text: str,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        self._contract_logger.log_entry(
            "append_clinical_note",
            request_id,
            visit_id=visit_id,
            actor_user_id=actor_user_id,
        )
        written = self._contract.append_clinical_note(
            visit_id=visit_id,
            note_text=note_text,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "append_clinical_note",
            request_id,
            written=written,
        )
        return written

    def index_emr_phrases(
        self,
        emr_id: int,
        doctor_id: int,
        specialty: str | None = None,
        request_id: str | None = None,
    ) -> int:
        self._contract_logger.log_entry(
            "index_emr_phrases",
            request_id,
            emr_id=emr_id,
            doctor_id=doctor_id,
            specialty=specialty,
        )
        indexed = self._contract.index_emr_phrases(
            emr_id=emr_id,
            doctor_id=doctor_id,
            specialty=specialty,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "index_emr_phrases",
            request_id,
            indexed=indexed,
        )
        return indexed
