"""Canonical transactional price-override approval (SSOT).

REGPRICE-BE-001/002/003/005 (audit #3892, group 16): price-override
approval was exposed through TWO independently implemented routes that
mutated DIFFERENT halves of the financial read model:

* registrar ``POST /registrar/price-override/approve`` — wrote the
  ``Visit.doctor_price_override`` JSON mirror but NOT the chargeable
  ``VisitService.price`` (billing sums ``VisitService.price * qty``, so the
  approved price never reached the invoice);
* dental ``PUT /dental/price-override/{id}/approve`` — wrote
  ``VisitService.price``/``custom_price`` but NOT the JSON mirror.

Both routes read the override with an unlocked ``.first()`` and checked
``status == 'pending'`` outside any transaction boundary, so two approvers
could both observe ``pending`` and commit conflicting terminal decisions
(REGPRICE-BE-002). Neither route compared the captured
``visit_price_before`` snapshot with the CURRENT ``VisitService.price``
before applying a stale intent (REGPRICE-BE-003), and the registrar route
accepted an absent/blank ``rejection_reason`` (REGPRICE-BE-005).

This service is now the single approval implementation both routes delegate
to. Canonical outcome — identical for every caller:

1. lock order: ``visits`` row FIRST (the same canonical row payment flows
   lock, see ``billing_service_pkg/_payments.py``), then the
   ``doctor_price_overrides`` row with ``SELECT ... FOR UPDATE``;
2. a non-pending override after the lock is a 409 conflict — the loser of a
   concurrent decision MUST NOT report success;
3. ``approve`` fail-closes when the service is no longer attached to the
   visit (409, status stays pending — DERMAPRICE-BE-001 contract kept);
4. ``approve`` validates the captured ``visit_price_before`` against the
   current price: a stale intent is rejected with 409 so every legitimate
   chained correction re-enters the workflow with a FRESH snapshot
   (overrides created before the snapshot field existed carry
   ``visit_price_before = NULL`` and stay processable — their staleness is
   not verifiable);
5. ``approve`` updates BOTH the chargeable rows (every matching
   ``VisitService`` pair, so duplicate association rows can no longer leave
   the price half-applied) and the ``Visit.doctor_price_override`` JSON
   mirror in ONE commit;
6. ``reject`` requires a non-blank reason (400 otherwise) and persists it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.doctor_price_override import DoctorPriceOverride
from app.models.visit import Visit, VisitService


@dataclass
class PriceOverrideApprovalError(Exception):
    """Domain error translated to HTTP by every delegating endpoint."""

    status_code: int
    detail: str


PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"

# REGPRICE-BE-003 (audit 3892, group 16): shared refusal text for a SECOND
# pending override on the same visit/service. The creation-side probe itself
# lives on the repositories (``has_pending_override``) so the dental/derma
# services stay repository-boundary compliant — they must never touch the
# raw session (enforced by tests/unit/test_service_repository_boundary.py).
PENDING_DUPLICATE_DETAIL = (
    "Для этой услуги уже есть запрос изменения цены, ожидающий "
    "одобрения — дождитесь его обработки или отклоните дубликат."
)


class PriceOverrideApprovalService:
    """Single SSOT for approve/reject decisions on ``DoctorPriceOverride``."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Loading & locking (REGPRICE-BE-002)
    # ------------------------------------------------------------------
    def _load_locked(self, override_id: int) -> DoctorPriceOverride:
        """Load the override under the canonical lock order.

        Probe first (an unlocked read is enough to route the visit lock),
        then lock ``visits`` and only afterwards the override row — the
        same order payment flows use when they touch a visit, so an
        approval and a payment can never interleave into a lock cycle.
        """
        probe = (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == override_id)
            .first()
        )
        if probe is None:
            raise PriceOverrideApprovalError(
                404, "Изменение цены не найдено"
            )

        if probe.visit_id is not None:
            self.db.query(Visit).filter(Visit.id == probe.visit_id).with_for_update().first()

        override = (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == override_id)
            .with_for_update()
            .first()
        )
        if override is None:
            # Deleted between the probe and the lock — treat as 404.
            raise PriceOverrideApprovalError(404, "Изменение цены не найдено")
        return override

    # ------------------------------------------------------------------
    # Stale-intent validation (REGPRICE-BE-003, approval side)
    # ------------------------------------------------------------------
    def _load_chargeable_rows(
        self, *, visit_id: int | None, service_id: int | None
    ) -> list[VisitService]:
        """Every matching VisitService pair, ordered deterministically.

        Updating ALL matching rows keeps the chargeable read model
        consistent even for duplicate association rows (REGPRICE-BE-006,
        group 17) that would otherwise leave the price half-applied.
        """
        if visit_id is None or service_id is None:
            return []
        return (
            self.db.query(VisitService)
            .filter(
                VisitService.visit_id == visit_id,
                VisitService.service_id == service_id,
            )
            .order_by(VisitService.id.asc())
            .all()
        )

    def _ensure_fresh_intent(
        self,
        override: DoctorPriceOverride,
        chargeable_rows: list[VisitService],
    ) -> None:
        if override.visit_price_before is None:
            # Legacy row created before the snapshot existed: the staleness
            # of the intent cannot be verified, so the approval proceeds
            # (documented policy; the JSON mirror still records the truth).
            return
        if not chargeable_rows:
            # No chargeable row to compare against — fail-closed contract
            # from DERMAPRICE-BE-001 (checked by the caller before us).
            return
        current = chargeable_rows[0].price
        if current is None:
            return
        if Decimal(current) != Decimal(override.visit_price_before):
            raise PriceOverrideApprovalError(
                409,
                "Запрос устарел: цена услуги в визите изменилась после "
                "создания запроса "
                f"(было {override.visit_price_before}, стало {current}). "
                "Создайте новый запрос изменения цены.",
            )

    # ------------------------------------------------------------------
    # JSON mirror (REGPRICE-BE-001, registrar-side write)
    # ------------------------------------------------------------------
    def _apply_visit_json(self, override: DoctorPriceOverride) -> None:
        if override.visit_id is None:
            return
        visit = self.db.query(Visit).filter(Visit.id == override.visit_id).first()
        if not visit:
            return
        # REG-XC-001 (follow-up audit 2026-11-02): the column is a plain
        # mapped_column(JSON) WITHOUT MutableDict — build a NEW dict and
        # assign it so SQLAlchemy dirty-tracking fires on every approval.
        approved_at = override.approved_at or datetime.now(UTC)
        updated_override = dict(visit.doctor_price_override or {})
        updated_override[str(override.service_id)] = {
            "original_price": float(override.original_price),
            "new_price": float(override.new_price),
            "override_id": override.id,
            "approved_at": approved_at.isoformat(),
        }
        visit.doctor_price_override = updated_override

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(
        self,
        *,
        override_id: int,
        action: str,
        rejection_reason: str | None,
        approver_id: int,
    ) -> DoctorPriceOverride:
        """Apply one terminal decision. Commits on success, rolls back on error."""
        if action not in ("approve", "reject"):
            raise PriceOverrideApprovalError(
                400, "Действие должно быть 'approve' или 'reject'"
            )

        try:
            override = self._load_locked(override_id)

            # REGPRICE-BE-002: after the lock, a non-pending status means
            # another approver won the race — 409, never a fake success.
            if override.status != PENDING_STATUS:
                raise PriceOverrideApprovalError(
                    409,
                    f"Изменение цены уже обработано (статус: {override.status})",
                )

            if action == "reject":
                # REGPRICE-BE-005: the refusal must be justified — absent,
                # empty or whitespace-only reasons are refused (400) and no
                # transition happens.
                reason = (rejection_reason or "").strip()
                if not reason:
                    raise PriceOverrideApprovalError(
                        400, "При отклонении необходимо указать причину"
                    )
                override.status = REJECTED_STATUS
                override.approved_by = approver_id
                override.approved_at = datetime.now(UTC)
                override.rejection_reason = reason
                self.db.commit()
                self.db.refresh(override)
                return override

            # --- approve ---
            chargeable_rows = self._load_chargeable_rows(
                visit_id=override.visit_id, service_id=override.service_id
            )
            if not chargeable_rows:
                # DERMAPRICE-BE-001 fail-closed contract: no chargeable row
                # → the approval MUST NOT report success. Checked BEFORE any
                # status mutation so the override stays pending.
                raise PriceOverrideApprovalError(
                    409,
                    "Услуга не привязана к визиту — изменение цены не может "
                    "быть одобрено (запрос создан до привязки услуги либо "
                    "услуга удалена из визита)",
                )

            # REGPRICE-BE-003: stale intents are rejected — the request was
            # priced against a snapshot that no longer matches reality.
            self._ensure_fresh_intent(override, chargeable_rows)

            override.status = APPROVED_STATUS
            override.approved_by = approver_id
            override.approved_at = datetime.now(UTC)

            # REGPRICE-BE-001: the chargeable price AND the JSON mirror are
            # written together, in ONE commit — both routes now converge on
            # the identical canonical outcome.
            for row in chargeable_rows:
                row.price = override.new_price
                row.custom_price = override.new_price
            self._apply_visit_json(override)

            self.db.commit()
            self.db.refresh(override)
            return override
        except PriceOverrideApprovalError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise
