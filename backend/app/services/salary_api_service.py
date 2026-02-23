"""Service layer for salary endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.salary_history import SalaryHistory, SalaryPayment
from app.repositories.salary_api_repository import SalaryApiRepository


@dataclass
class SalaryApiDomainError(Exception):
    status_code: int
    detail: str


class SalaryApiService:
    """Handles business rules and payload building for salary APIs."""

    def __init__(
        self,
        db: Session,
        repository: SalaryApiRepository | None = None,
    ):
        self.repository = repository or SalaryApiRepository(db)

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None:
            return None
        return float(value)

    def get_salary_history(self, *, user_id: int, limit: int) -> list[dict[str, Any]]:
        history = self.repository.list_salary_history(user_id=user_id, limit=limit)
        return [
            {
                "id": record.id,
                "old_salary": self._to_float(record.old_salary),
                "new_salary": self._to_float(record.new_salary),
                "currency": record.currency,
                "change_type": record.change_type,
                "change_amount": self._to_float(record.change_amount),
                "change_percentage": self._to_float(record.change_percentage),
                "is_increase": record.is_increase,
                "reason": record.reason,
                "effective_date": record.effective_date.isoformat(),
                "is_confirmed": record.is_confirmed,
                "created_at": record.created_at.isoformat(),
            }
            for record in history
        ]

    def create_salary_change(
        self,
        *,
        payload: dict[str, Any],
        changed_by_id: int,
    ) -> dict[str, Any]:
        last_record = self.repository.get_latest_salary_history(user_id=payload["user_id"])
        old_salary = last_record.new_salary if last_record else None

        change_percentage = None
        if old_salary and old_salary > 0:
            change_percentage = (
                (payload["new_salary"] - old_salary) / old_salary
            ) * Decimal("100")

        record = SalaryHistory(
            user_id=payload["user_id"],
            old_salary=old_salary,
            new_salary=payload["new_salary"],
            currency=payload.get("currency", "UZS"),
            change_type=payload.get("change_type", "adjustment"),
            change_percentage=change_percentage,
            reason=payload.get("reason"),
            effective_date=payload["effective_date"],
            changed_by_id=changed_by_id,
            created_at=datetime.utcnow(),
        )

        self.repository.add(record)
        self.repository.commit()
        self.repository.refresh(record)

        return {
            "success": True,
            "id": record.id,
            "message": "Изменение зарплаты записано",
            "change_percentage": self._to_float(change_percentage),
        }

    def confirm_salary_change(self, *, record_id: int, confirmed_by_id: int) -> dict[str, Any]:
        record = self.repository.get_salary_history_record(record_id=record_id)
        if not record:
            raise SalaryApiDomainError(404, "Запись не найдена")

        record.is_confirmed = True
        record.confirmed_at = datetime.utcnow()
        record.confirmed_by_id = confirmed_by_id
        self.repository.commit()

        return {"success": True, "message": "Изменение подтверждено"}

    def get_salary_payments(
        self,
        *,
        user_id: int,
        year: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        payments = self.repository.list_salary_payments(
            user_id=user_id,
            year=year,
            limit=limit,
        )
        return [
            {
                "id": payment.id,
                "period_start": payment.period_start.isoformat(),
                "period_end": payment.period_end.isoformat(),
                "base_salary": self._to_float(payment.base_salary),
                "bonuses": self._to_float(payment.bonuses),
                "deductions": self._to_float(payment.deductions),
                "taxes": self._to_float(payment.taxes),
                "net_amount": self._to_float(payment.net_amount),
                "currency": payment.currency,
                "status": payment.status,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "payment_method": payment.payment_method,
            }
            for payment in payments
        ]

    def create_salary_payment(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        net_amount = (
            payload["base_salary"]
            + payload.get("bonuses", Decimal("0"))
            - payload.get("deductions", Decimal("0"))
            - payload.get("taxes", Decimal("0"))
        )

        payment = SalaryPayment(
            user_id=payload["user_id"],
            period_start=payload["period_start"],
            period_end=payload["period_end"],
            base_salary=payload["base_salary"],
            bonuses=payload.get("bonuses", Decimal("0")),
            deductions=payload.get("deductions", Decimal("0")),
            taxes=payload.get("taxes", Decimal("0")),
            net_amount=net_amount,
            currency=payload.get("currency", "UZS"),
            notes=payload.get("notes"),
            status="pending",
            created_at=datetime.utcnow(),
        )

        self.repository.add(payment)
        self.repository.commit()
        self.repository.refresh(payment)

        return {
            "success": True,
            "id": payment.id,
            "net_amount": self._to_float(net_amount),
        }

    def update_payment_status(
        self,
        *,
        payment_id: int,
        new_status: str,
        payment_date: datetime | None,
        payment_method: str | None,
    ) -> dict[str, Any]:
        payment = self.repository.get_salary_payment(payment_id=payment_id)
        if not payment:
            raise SalaryApiDomainError(404, "Выплата не найдена")

        valid_statuses = ["pending", "approved", "paid", "cancelled"]
        if new_status not in valid_statuses:
            raise SalaryApiDomainError(400, f"Неверный статус: {new_status}")

        payment.status = new_status
        if new_status == "paid":
            payment.payment_date = payment_date or datetime.utcnow()
            payment.payment_method = payment_method

        self.repository.commit()
        return {"success": True, "message": f"Статус обновлён на {new_status}"}

    def get_salary_summary(self, *, user_id: int, year: int) -> dict[str, Any]:
        payments = self.repository.list_salary_payments_for_year(user_id=user_id, year=year)

        total_base = sum(self._to_float(payment.base_salary) for payment in payments)
        total_bonuses = sum(self._to_float(payment.bonuses) for payment in payments)
        total_deductions = sum(self._to_float(payment.deductions) for payment in payments)
        total_taxes = sum(self._to_float(payment.taxes) for payment in payments)
        total_net = sum(self._to_float(payment.net_amount) for payment in payments)

        return {
            "user_id": user_id,
            "year": year,
            "payments_count": len(payments),
            "total_base_salary": total_base,
            "total_bonuses": total_bonuses,
            "total_deductions": total_deductions,
            "total_taxes": total_taxes,
            "total_net_amount": total_net,
            "average_monthly": total_net / 12 if payments else 0,
        }

    def rollback(self) -> None:
        self.repository.rollback()
