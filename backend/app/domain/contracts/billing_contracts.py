from __future__ import annotations

import logging
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from app.domain.contracts.contract_logging import ContractMethodLogger

logger = logging.getLogger(__name__)


class PaymentStatusSnapshot(BaseModel):
    visit_id: int
    status: str
    paid_amount: Decimal = Decimal("0")
    due_amount: Decimal = Decimal("0")


class BillingContract(Protocol):
    def get_payment_status(
        self,
        visit_id: int,
        request_id: str | None = None,
    ) -> PaymentStatusSnapshot: ...

    def create_charge(
        self,
        visit_id: int,
        amount: Decimal,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> str: ...


class BillingContractFacade:
    """Contract wrapper with explicit entry/exit debug logging."""

    def __init__(self, contract: BillingContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "billing")

    def get_payment_status(
        self,
        visit_id: int,
        request_id: str | None = None,
    ) -> PaymentStatusSnapshot:
        self._contract_logger.log_entry(
            "get_payment_status",
            request_id,
            visit_id=visit_id,
        )
        status = self._contract.get_payment_status(
            visit_id=visit_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "get_payment_status",
            request_id,
            payment_status=status.status,
            due_amount=str(status.due_amount),
        )
        return status

    def create_charge(
        self,
        visit_id: int,
        amount: Decimal,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> str:
        self._contract_logger.log_entry(
            "create_charge",
            request_id,
            visit_id=visit_id,
            amount=str(amount),
            actor_user_id=actor_user_id,
        )
        charge_id = self._contract.create_charge(
            visit_id=visit_id,
            amount=amount,
            actor_user_id=actor_user_id,
            request_id=request_id,
        )
        self._contract_logger.log_exit(
            "create_charge",
            request_id,
            charge_id=charge_id,
        )
        return charge_id

