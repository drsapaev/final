from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from app.domain.contracts.billing_contracts import (
    BillingContract,
    BillingContractFacade,
    PaymentStatusSnapshot,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.payment_invoice import PaymentInvoice
    from app.models.visit import Visit
    from app.services.encounter_benefit_net import BenefitVisitQuote

logger = logging.getLogger(__name__)


def quote_visit_for_confirmation(db: Session, visit: Visit) -> BenefitVisitQuote:
    """Read the billing quote within the caller's confirmation transaction."""
    from app.services.payment_invariant_service import PaymentInvariantService

    return PaymentInvariantService(db).compute_visit_quote(visit)


def require_visible_queue_cancellation_evidence(db: Session) -> None:
    """Require complete payment and queue state in the caller transaction."""
    from app.services.payment_refund_guard import (
        require_visible_checkout_queue,
        require_visible_visit_payments,
    )

    require_visible_visit_payments(db)
    require_visible_checkout_queue(db)


def require_visible_unpaid_draft_cancellation_evidence(db: Session) -> None:
    """Require visible service and refund evidence before releasing a share."""
    from app.services.payment_refund_guard import require_visible_unpaid_draft_evidence

    require_visible_unpaid_draft_evidence(db)


def append_invoice_visit_release_audit(
    db: Session,
    invoice: PaymentInvoice,
    *,
    visit_id: int,
    previous_total: Decimal,
    released_amount: Decimal,
    actor_user_id: int | None,
    actor_role: str | None,
) -> None:
    """Record the release in the caller transaction."""
    from app.repositories.payment_invoice_repository import record_invoice_visit_release

    record_invoice_visit_release(
        db,
        invoice,
        visit_id=visit_id,
        previous_total=previous_total,
        released_amount=released_amount,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )


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

