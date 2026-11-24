"""Repository helpers for provider webhook processing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import BigInteger, String, and_, case, cast, func, or_
from sqlalchemy.orm import Session, aliased, raiseload

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook


class ProviderWebhookRepository:
    """Encapsulates ORM operations used by provider webhook service."""

    def __init__(self, db: Session):
        self.db = db

    def get_existing_transaction(
        self, *, transaction_id: str, provider: str, for_update: bool = False
    ) -> PaymentTransaction | None:
        query = self.db.query(PaymentTransaction).filter(
            PaymentTransaction.transaction_id == transaction_id,
            PaymentTransaction.provider == provider,
        )
        if for_update:
            query = query.with_for_update().populate_existing()
        return query.first()

    def create_webhook(
        self,
        *,
        provider: str,
        webhook_id: str,
        transaction_id: str,
        amount: int,
        currency: str,
        raw_data: dict[str, Any],
        signature: str | None = None,
        status: str = "pending",
    ) -> PaymentWebhook:
        webhook = PaymentWebhook(
            provider=provider,
            webhook_id=webhook_id,
            transaction_id=transaction_id,
            status=status,
            amount=amount,
            currency=currency,
            raw_data=raw_data,
            signature=signature,
        )
        self.db.add(webhook)
        self.db.flush()
        self.db.refresh(webhook)
        return webhook

    def get_processed_webhook(
        self, *, webhook_id: int, provider: str, transaction_id: str
    ) -> PaymentWebhook | None:
        return (
            self.db.query(PaymentWebhook)
            .filter(
                PaymentWebhook.id == webhook_id,
                PaymentWebhook.provider == provider,
                PaymentWebhook.transaction_id == transaction_id,
                PaymentWebhook.status == "processed",
            )
            .first()
        )

    def iter_payme_statement(
        self, *, start: int, end: int
    ) -> Iterator[tuple[PaymentTransaction | None, Payment | None, PaymentWebhook | None, int | None]]:
        """Read both evidence sources in one snapshot, including unlinked Payme rows."""
        receipts = self.db.query(PaymentWebhook).filter(
            PaymentWebhook.provider == "payme",
            PaymentWebhook.status == "processed",
            PaymentWebhook.raw_data["method"].as_string() == "CreateTransaction",
        ).subquery()
        receipt = aliased(PaymentWebhook, receipts)
        transactions = self.db.query(PaymentTransaction).filter(
            PaymentTransaction.provider == "payme"
        ).subquery()
        transaction = aliased(PaymentTransaction, transactions)

        payload = receipt.raw_data
        time_text = cast(payload["params"]["time"].as_string(), String)
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            integer_json = func.json_typeof(payload["params"]["time"]) == "number"
        elif dialect == "sqlite":
            integer_json = func.json_type(payload, "$.params.time") == "integer"
        else:
            raise RuntimeError("Unsupported Payme statement database")

        # Keep rows with unknown Payme times visible so the caller can flag incomplete history.
        payme_time = case((
            and_(integer_json, time_text.regexp_match(r"^[1-9][0-9]{0,12}$")),
            cast(time_text, BigInteger),
        ))
        query = (
            self.db.query(transaction, Payment, receipt, payme_time)
            .select_from(receipt)
            .join(transaction, transaction.webhook_id == receipt.id, full=True)
            .outerjoin(Payment, and_(Payment.id == transaction.payment_id, Payment.provider == "payme"))
            .filter(or_(payme_time.is_(None), payme_time.between(start, end)))
            .order_by(payme_time.asc().nulls_first(), transaction.transaction_id, receipt.id)
            .options(raiseload("*"))
            .populate_existing()
            .autoflush(False)
        )
        for row in query.yield_per(500):
            yield row

    def get_payment_by_id(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_payment_by_id_for_update(
        self, payment_id: int, *, provider: str | None = None
    ) -> Payment | None:
        """Lock the payment row for update (SELECT ... FOR UPDATE).

        Used in webhook duplicate-processing to prevent TOCTOU races:
        a cashier cancellation (via PaymentCancelService →
        billing_service.update_payment_status which uses
        with_for_update) can commit a terminal status between our
        read and write. This method acquires the row lock so that
        the status we read is the status we mutate.

        Must be called inside a transaction_ctx block.
        """
        query = self.db.query(Payment).filter(Payment.id == payment_id)
        if provider is not None:
            query = query.filter(Payment.provider == provider).populate_existing()
        return query.with_for_update().first()

    def get_payment_by_provider_payment_id_for_update(
        self, *, provider: str, provider_payment_id: str
    ) -> Payment | None:
        """Lock a uniquely bound provider payment in the caller's transaction."""
        payments = (
            self.db.query(Payment)
            .filter(
                Payment.provider == provider,
                Payment.provider_payment_id == provider_payment_id,
            )
            .order_by(Payment.id)
            .with_for_update()
            .populate_existing()
            .limit(2)
            .all()
        )
        return payments[0] if len(payments) == 1 else None

    def create_transaction(
        self,
        *,
        transaction_id: str,
        provider: str,
        amount: int,
        currency: str,
        status: str,
        payment_id: int | None,
        webhook_id: int | None,
        visit_id: int | None,
        provider_data: dict[str, Any] | None,
    ) -> PaymentTransaction:
        transaction = PaymentTransaction(
            transaction_id=transaction_id,
            provider=provider,
            amount=amount,
            currency=currency,
            status=status,
            payment_id=payment_id,
            webhook_id=webhook_id,
            visit_id=visit_id,
            provider_data=provider_data,
        )
        self.db.add(transaction)
        return transaction
