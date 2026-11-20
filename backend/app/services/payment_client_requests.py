"""Persist and replay payment results in the transaction that moves money."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import PaymentClientRequest

logger = logging.getLogger(__name__)


def find_payment_client_request(
    db: Session, client_request_id: str
) -> PaymentClientRequest | None:
    """Look up the idempotency anchor row for a client key (issue 3859).

    Module-level (not a closure) so the concurrent-race test can simulate
    a lookup that missed the winner's row before either request committed.
    """
    return (
        db.query(PaymentClientRequest)
        .filter(PaymentClientRequest.client_request_id == client_request_id)
        .first()
    )


def replay_payment_client_request(
    db: Session,
    client_request_id: str,
    endpoint: str,
    *,
    request_fingerprint: str | None = None,
    current_user_id: int | None = None,
) -> dict[str, Any] | None:
    """Return the stored response payload for a duplicate client key.

    A repeated ``client_request_id`` must get the ORIGINAL operation's
    result (200 + stored snapshot), never a second payment row and never
    a re-derivation from today's DB state — the visit debt may have moved
    on since the first attempt, so re-running validation would 400 a
    legitimate retry. A key minted by the OTHER endpoint is refused with
    409 instead of being replayed through a mismatched response model.

    RETRO-FIN-001 (intent binding): the anchor also stores the SHA-256
    fingerprint of the original request's SEMANTIC intent (endpoint +
    patient/visit allocation + amount + method). A repeated key carrying
    a DIFFERENT intent is refused with 409
    ``client_request_id_intent_mismatch`` — it must never replay the
    original success as if the new intent had been charged. Historical
    anchors (fingerprint NULL, minted before this guard) keep the
    existing fingerprint compatibility for the verified anchor owner.
    A receipt with an unknown owner requires reconciliation.
    """
    stored = find_payment_client_request(db, client_request_id)
    if stored is None:
        return None
    if current_user_id is None or stored.created_by is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "client_request_id_owner_unverified",
                "message": "Владелец квитанции не подтверждён. Сверьте операцию перед повтором.",
            },
        )
    if stored.created_by != current_user_id:
        logger.warning(
            "payment.client_request_owner_mismatch client_request_id=%s "
            "endpoint=%s stored_owner=%s requesting_user=%s",
            client_request_id,
            endpoint,
            stored.created_by,
            current_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "client_request_id_owner_mismatch",
                "message": (
                    "Ключ идемпотентности принадлежит другой учётной записи. "
                    "Сгенерируйте новый ключ для новой операции."
                ),
            },
        )
    if stored.endpoint != endpoint:
        logger.warning(
            "payment.client_request_endpoint_mismatch client_request_id=%s "
            "stored_endpoint=%s requested_endpoint=%s",
            client_request_id,
            stored.endpoint,
            endpoint,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "client_request_id_endpoint_mismatch",
                "message": (
                    "Этот ключ идемпотентности был создан другим эндпоинтом "
                    "оплаты. Сгенерируйте новый ключ для новой операции."
                ),
            },
        )
    if (
        (endpoint in {"refund", "billing"} and not stored.request_fingerprint)
        or (request_fingerprint is not None and stored.request_fingerprint is not None
            and stored.request_fingerprint != request_fingerprint)
    ):
        logger.warning(
            "payment.client_request_intent_mismatch client_request_id=%s "
            "endpoint=%s stored_fingerprint=%s requested_fingerprint=%s",
            client_request_id,
            endpoint,
            stored.request_fingerprint,
            request_fingerprint,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "client_request_id_intent_mismatch",
                "message": (
                    "Ключ идемпотентности использован с другим платёжным "
                    "назначением (пациент/визит/сумма/метод). Сгенерируйте "
                    "новый ключ для новой операции."
                ),
            },
        )
    payload = stored.response_payload
    if isinstance(payload, str):  # Historical serialized JSON responses.
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=409, detail="Запись платежа требует сверки")
    logger.info(
        "payment.client_request_replayed client_request_id=%s endpoint=%s payment_id=%s",
        client_request_id,
        endpoint,
        payload.get("id"),
    )
    return payload


def commit_with_client_request(
    db: Session,
    *,
    client_request_id: str,
    endpoint: str,
    response_payload: dict[str, Any],
    created_by: int | None,
    request_fingerprint: str | None = None,
) -> dict[str, Any] | None:
    """Commit the payment rows together with their idempotency anchor.

    The anchor insert rides the CALLER-OWNED transaction (the payment
    service must be invoked with ``commit=False``), so a crash can never
    leave a payment without its anchor (duplicate charge window) or an
    anchor without its payment (phantom replay). A concurrent duplicate
    loses the unique-index race here: its whole transaction (payments +
    anchor) rolls back and the caller replays the winner's snapshot.

    RETRO-FIN-001: the anchor persists the request intent fingerprint.
    Concurrent recovery applies the same endpoint, intent and owner
    checks as an ordinary replay.

    Returns ``None`` on a clean commit, or the WINNER's stored payload
    when this request lost the concurrent race (the caller must replay it
    with 200 instead of surfacing an error to the cashier).
    """
    db.add(
        PaymentClientRequest(
            client_request_id=client_request_id,
            endpoint=endpoint,
            response_payload=response_payload,
            request_fingerprint=request_fingerprint,
            created_by=created_by,
        )
    )
    try:
        db.commit()
        logger.info(
            "payment.client_request_committed client_request_id=%s endpoint=%s user_id=%s payment_id=%s",
            client_request_id,
            endpoint,
            created_by,
            response_payload.get("id"),
        )
        return None
    except IntegrityError:
        db.rollback()
        replay = replay_payment_client_request(
            db,
            client_request_id,
            endpoint,
            request_fingerprint=request_fingerprint,
            current_user_id=created_by,
        )
        if replay is not None:
            logger.info(
                "payment.client_request_race_recovered client_request_id=%s "
                "endpoint=%s",
                client_request_id,
                endpoint,
            )
            return replay
        if endpoint == "refund":
            raise HTTPException(status_code=409, detail="Запись возврата требует сверки") from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "payment_already_in_progress",
                "message": (
                    "Платёж с этим ключом уже обрабатывается. "
                    "Обновите список платежей."
                ),
            },
        )
