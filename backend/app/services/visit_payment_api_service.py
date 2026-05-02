"""Service layer for visit-payments API endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.visit_payment_integration import VisitPaymentIntegrationService


@dataclass
class VisitPaymentApiDomainError(Exception):
    status_code: int
    detail: str


class VisitPaymentApiService:
    """Orchestrates visit-payment API responses and validation."""

    VALID_PAYMENT_STATUSES = ("unpaid", "pending", "paid", "failed", "refunded")

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.db = db

    def get_visit_payment_info(self, *, visit_id: int) -> dict[str, Any]:
        success, message, payment_info = (
            VisitPaymentIntegrationService.get_visit_payment_info(self.db, visit_id)
        )
        if not success:
            raise VisitPaymentApiDomainError(status_code=404, detail=message)
        return {"success": True, "message": message, "payment_info": payment_info}

    def get_visits_by_payment_status(
        self, *, payment_status: str, limit: int, offset: int
    ) -> dict[str, Any]:
        success, message, visits = (
            VisitPaymentIntegrationService.get_visits_by_payment_status(
                self.db, payment_status, limit, offset
            )
        )
        if not success:
            raise VisitPaymentApiDomainError(status_code=400, detail=message)
        return {
            "success": True,
            "message": message,
            "payment_status": payment_status,
            "visits": visits,
            "total": len(visits),
            "limit": limit,
            "offset": offset,
        }

    def update_visit_payment_status(
        self, *, visit_id: int, payment_status: str
    ) -> dict[str, Any]:
        if payment_status not in self.VALID_PAYMENT_STATUSES:
            raise VisitPaymentApiDomainError(
                status_code=400,
                detail=(
                    "Неверный статус платежа. Допустимые значения: "
                    + ", ".join(self.VALID_PAYMENT_STATUSES)
                ),
            )

        success, message = VisitPaymentIntegrationService.update_visit_payment_status(
            self.db, visit_id, payment_status
        )
        if not success:
            raise VisitPaymentApiDomainError(status_code=400, detail=message)
        return {
            "success": True,
            "message": message,
            "visit_id": visit_id,
            "new_payment_status": payment_status,
        }

    def get_visit_payments_summary(self) -> dict[str, Any]:
        summary = {}
        for status in self.VALID_PAYMENT_STATUSES:
            success, _, visits = VisitPaymentIntegrationService.get_visits_by_payment_status(
                self.db, status, limit=1000, offset=0
            )
            if success:
                summary[status] = {
                    "count": len(visits),
                    "total_amount": sum(
                        float(v.get("payment_amount", 0))
                        for v in visits
                        if v.get("payment_amount")
                    ),
                }
            else:
                summary[status] = {"count": 0, "total_amount": 0}

        total_visits = sum(summary[s]["count"] for s in summary)
        total_paid_amount = summary.get("paid", {}).get("total_amount", 0)
        total_pending_amount = summary.get("pending", {}).get("total_amount", 0)

        return {
            "success": True,
            "summary": summary,
            "total_visits": total_visits,
            "total_paid_amount": total_paid_amount,
            "total_pending_amount": total_pending_amount,
            "payment_success_rate": (
                summary.get("paid", {}).get("count", 0) / max(total_visits, 1)
            )
            * 100,
        }

    def create_visit_from_payment(
        self,
        *,
        visit_id: int,
        patient_id: int | None,
        doctor_id: int | None,
        notes: str | None,
    ) -> dict[str, Any]:
        visit_data = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "notes": notes or "Визит создан вручную",
            "payment_status": "paid",
        }
        success, message = VisitPaymentIntegrationService.update_visit_payment_status(
            self.db, visit_id, "paid", additional_data=visit_data
        )
        if not success:
            raise VisitPaymentApiDomainError(status_code=400, detail=message)
        return {"success": True, "message": message, "visit_id": visit_id}
