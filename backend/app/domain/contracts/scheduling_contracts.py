from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger


logger = logging.getLogger(__name__)


class AppointmentSnapshot(BaseModel):
    appointment_id: int
    patient_id: int
    doctor_id: int | None = None
    starts_at: datetime | None = None
    status: str = "scheduled"


class SchedulingContract(Protocol):
    def get_appointment_snapshot(
        self,
        appointment_id: int,
        request_id: str | None = None,
    ) -> AppointmentSnapshot | None: ...

    def reschedule_appointment(
        self,
        appointment_id: int,
        new_start: datetime,
        new_end: datetime,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool: ...


class SchedulingContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: SchedulingContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "scheduling")

    def get_appointment_snapshot(
        self,
        appointment_id: int,
        request_id: str | None = None,
    ) -> AppointmentSnapshot | None:
        self._contract_logger.log_entry(
            "get_appointment_snapshot",
            request_id,
            appointment_id=appointment_id,
        )
        result = self._contract.get_appointment_snapshot(
            appointment_id=appointment_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_appointment_snapshot",
            request_id,
            found=result is not None,
        )
        return result

    def reschedule_appointment(
        self,
        appointment_id: int,
        new_start: datetime,
        new_end: datetime,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        self._contract_logger.log_entry(
            "reschedule_appointment",
            request_id,
            appointment_id=appointment_id,
            actor_user_id=actor_user_id,
            new_start=new_start.isoformat(),
            new_end=new_end.isoformat(),
        )
        changed = self._contract.reschedule_appointment(
            appointment_id=appointment_id,
            new_start=new_start,
            new_end=new_end,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "reschedule_appointment",
            request_id,
            changed=changed,
        )
        return changed

