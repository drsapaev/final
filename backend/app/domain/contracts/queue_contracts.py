from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger

logger = logging.getLogger(__name__)


class QueueTokenSnapshot(BaseModel):
    token_id: int
    patient_id: int
    queue_number: str
    status: str


class QueueContract(Protocol):
    def allocate_ticket(
        self,
        *,
        allocation_mode: str = "create_entry",
        request_id: str | None = None,
        **kwargs: Any,
    ) -> Any: ...

    def get_queue_token(
        self,
        token_id: int,
        request_id: str | None = None,
    ) -> QueueTokenSnapshot | None: ...

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool: ...

    def get_local_timestamp(
        self,
        db: Any = None,
        timezone: str | None = None,
        request_id: str | None = None,
    ) -> datetime: ...


class QueueContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: QueueContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "queue")

    def allocate_ticket(
        self,
        *,
        allocation_mode: str = "create_entry",
        request_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        self._contract_logger.log_entry(
            "allocate_ticket",
            request_id,
            allocation_mode=allocation_mode,
        )
        result = self._contract.allocate_ticket(
            allocation_mode=allocation_mode,
            request_id=request_id,
            **kwargs,
        )
        self._contract_logger.log_exit(
            "allocate_ticket",
            request_id,
            allocation_mode=allocation_mode,
            allocated=result is not None,
        )
        return result

    def get_queue_token(
        self,
        token_id: int,
        request_id: str | None = None,
    ) -> QueueTokenSnapshot | None:
        self._contract_logger.log_entry(
            "get_queue_token",
            request_id,
            token_id=token_id,
        )
        result = self._contract.get_queue_token(
            token_id=token_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_queue_token",
            request_id,
            found=result is not None,
        )
        return result

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        self._contract_logger.log_entry(
            "mark_token_called",
            request_id,
            token_id=token_id,
            actor_user_id=actor_user_id,
        )
        updated = self._contract.mark_token_called(
            token_id=token_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "mark_token_called",
            request_id,
            updated=updated,
        )
        return updated

    def get_local_timestamp(
        self,
        db: Any = None,
        timezone: str | None = None,
        request_id: str | None = None,
    ) -> datetime:
        self._contract_logger.log_entry(
            "get_local_timestamp",
            request_id,
            timezone=timezone,
        )
        timestamp = self._contract.get_local_timestamp(
            db=db,
            timezone=timezone,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_local_timestamp",
            request_id,
            iso=timestamp.isoformat(),
        )
        return timestamp
