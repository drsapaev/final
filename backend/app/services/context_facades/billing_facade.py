from __future__ import annotations

import logging
from decimal import Decimal

from app.domain.contracts.billing_contracts import (
    BillingContract,
    BillingContractFacade,
    PaymentStatusSnapshot,
)

logger = logging.getLogger(__name__)


class BillingContextFacade:
    """Public entry point for cross-context billing operations."""

    def __init__(self, contract: BillingContract) -> None:
        self._contract = BillingContractFacade(contract)

    def get_payment_status(
        self,
        visit_id: int,
        correlation_id: str | None = None,
    ) -> PaymentStatusSnapshot:
        logger.info(
            "billing_facade.get_payment_status correlation_id=%s visit_id=%s",
            correlation_id or "-",
            visit_id,
        )
        try:
            return self._contract.get_payment_status(
                visit_id=visit_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "billing_facade.get_payment_status failed correlation_id=%s visit_id=%s",
                correlation_id or "-",
                visit_id,
            )
            raise

    def create_charge(
        self,
        visit_id: int,
        amount: Decimal,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> str:
        logger.info(
            "billing_facade.create_charge correlation_id=%s visit_id=%s actor_user_id=%s amount=%s",
            correlation_id or "-",
            visit_id,
            actor_user_id,
            amount,
        )
        try:
            return self._contract.create_charge(
                visit_id=visit_id,
                amount=amount,
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "billing_facade.create_charge failed correlation_id=%s visit_id=%s actor_user_id=%s",
                correlation_id or "-",
                visit_id,
                actor_user_id,
            )
            raise

