from __future__ import annotations

import logging
from datetime import datetime

from app.domain.contracts.scheduling_contracts import (
    AppointmentSnapshot,
    SchedulingContract,
    SchedulingContractFacade,
)

logger = logging.getLogger(__name__)


class SchedulingContextFacade:
    """Public entry point for cross-context scheduling operations."""

    def __init__(self, contract: SchedulingContract) -> None:
        self._contract = SchedulingContractFacade(contract)

    def get_appointment_snapshot(
        self,
        appointment_id: int,
        correlation_id: str | None = None,
    ) -> AppointmentSnapshot | None:
        logger.info(
            "scheduling_facade.get_appointment_snapshot correlation_id=%s appointment_id=%s",
            correlation_id or "-",
            appointment_id,
        )
        try:
            return self._contract.get_appointment_snapshot(
                appointment_id=appointment_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "scheduling_facade.get_appointment_snapshot failed correlation_id=%s appointment_id=%s",
                correlation_id or "-",
                appointment_id,
            )
            raise

    def reschedule_appointment(
        self,
        appointment_id: int,
        new_start: datetime,
        new_end: datetime,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> bool:
        logger.info(
            (
                "scheduling_facade.reschedule_appointment correlation_id=%s appointment_id=%s "
                "actor_user_id=%s"
            ),
            correlation_id or "-",
            appointment_id,
            actor_user_id,
        )
        try:
            return self._contract.reschedule_appointment(
                appointment_id=appointment_id,
                new_start=new_start,
                new_end=new_end,
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                (
                    "scheduling_facade.reschedule_appointment failed correlation_id=%s "
                    "appointment_id=%s actor_user_id=%s"
                ),
                correlation_id or "-",
                appointment_id,
                actor_user_id,
            )
            raise

