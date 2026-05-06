from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.domain.contracts.queue_contracts import (
    QueueContract,
    QueueContractFacade,
    QueueTokenSnapshot,
)

logger = logging.getLogger(__name__)


class QueueServiceContractAdapter:
    """Adapter from legacy queue service to queue contract."""

    def __init__(self) -> None:
        from app.services.queue_service import queue_service

        self._queue_service = queue_service

    def allocate_ticket(
        self,
        *,
        allocation_mode: str = "create_entry",
        request_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        _ = request_id
        if allocation_mode == "create_entry":
            db = kwargs.pop("db")
            return self._queue_service.create_queue_entry(db, **kwargs)
        if allocation_mode == "join_with_token":
            db = kwargs.pop("db")
            return self._queue_service.join_queue_with_token(db, **kwargs)
        raise ValueError(f"Unsupported allocation_mode: {allocation_mode}")

    def get_queue_token(
        self,
        token_id: int,
        request_id: str | None = None,
    ) -> QueueTokenSnapshot | None:
        _ = request_id
        return None

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        _ = (token_id, actor_user_id, request_id)
        return False

    def get_local_timestamp(
        self,
        db: Any = None,
        timezone: str | None = None,
        request_id: str | None = None,
    ) -> datetime:
        _ = request_id
        return self._queue_service.get_local_timestamp(db=db, timezone=timezone)


class QueueDomainServiceContractAdapter:
    """Adapter from queue domain boundary to queue contract."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def allocate_ticket(
        self,
        *,
        allocation_mode: str = "create_entry",
        request_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        _ = request_id
        from app.services.queue_domain_service import QueueDomainService

        service = QueueDomainService(self._db)
        return service.allocate_ticket(
            allocation_mode=allocation_mode,
            **kwargs,
        )

    def get_queue_token(
        self,
        token_id: int,
        request_id: str | None = None,
    ) -> QueueTokenSnapshot | None:
        _ = (token_id, request_id)
        return None

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        _ = (token_id, actor_user_id, request_id)
        return False

    def get_local_timestamp(
        self,
        db: Any = None,
        timezone: str | None = None,
        request_id: str | None = None,
    ) -> datetime:
        from app.services.queue_service import queue_service

        _ = request_id
        return queue_service.get_local_timestamp(db=db, timezone=timezone)


class QueueContextFacade:
    """Public entry point for cross-context queue operations."""

    def __init__(self, contract: QueueContract) -> None:
        self._contract = QueueContractFacade(contract)

    def allocate_ticket(
        self,
        *,
        allocation_mode: str = "create_entry",
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        logger.info(
            "queue_facade.allocate_ticket correlation_id=%s allocation_mode=%s",
            correlation_id or "-",
            allocation_mode,
        )
        try:
            return self._contract.allocate_ticket(
                allocation_mode=allocation_mode,
                request_id=correlation_id,
                **kwargs,
            )
        except Exception:
            logger.exception(
                "queue_facade.allocate_ticket failed correlation_id=%s allocation_mode=%s",
                correlation_id or "-",
                allocation_mode,
            )
            raise

    def get_queue_token(
        self,
        token_id: int,
        correlation_id: str | None = None,
    ) -> QueueTokenSnapshot | None:
        logger.info(
            "queue_facade.get_queue_token correlation_id=%s token_id=%s",
            correlation_id or "-",
            token_id,
        )
        try:
            return self._contract.get_queue_token(
                token_id=token_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "queue_facade.get_queue_token failed correlation_id=%s token_id=%s",
                correlation_id or "-",
                token_id,
            )
            raise

    def mark_token_called(
        self,
        token_id: int,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> bool:
        logger.info(
            "queue_facade.mark_token_called correlation_id=%s token_id=%s actor_user_id=%s",
            correlation_id or "-",
            token_id,
            actor_user_id,
        )
        try:
            return self._contract.mark_token_called(
                token_id=token_id,
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "queue_facade.mark_token_called failed correlation_id=%s token_id=%s actor_user_id=%s",
                correlation_id or "-",
                token_id,
                actor_user_id,
            )
            raise

    def get_local_timestamp(
        self,
        db: Any = None,
        timezone: str | None = None,
        correlation_id: str | None = None,
    ) -> datetime:
        logger.info(
            "queue_facade.get_local_timestamp correlation_id=%s timezone=%s",
            correlation_id or "-",
            timezone or "-",
        )
        try:
            return self._contract.get_local_timestamp(
                db=db,
                timezone=timezone,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "queue_facade.get_local_timestamp failed correlation_id=%s timezone=%s",
                correlation_id or "-",
                timezone or "-",
            )
            raise
