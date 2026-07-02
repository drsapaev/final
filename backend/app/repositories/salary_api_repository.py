"""Repository helpers for salary endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.salary_history import SalaryHistory, SalaryPayment


class SalaryApiRepository:
    """Encapsulates ORM operations for salary API service."""

    def __init__(self, db: Session):
        self.db = db

    def list_salary_history(self, *, user_id: int, limit: int) -> list[SalaryHistory]:
        return (
            self.db.query(SalaryHistory)
            .filter(SalaryHistory.user_id == user_id)
            .order_by(desc(SalaryHistory.effective_date))
            .limit(limit)
            .all()
        )

    def get_latest_salary_history(self, *, user_id: int) -> SalaryHistory | None:
        return (
            self.db.query(SalaryHistory)
            .filter(SalaryHistory.user_id == user_id)
            .order_by(desc(SalaryHistory.effective_date))
            .first()
        )

    def get_salary_history_record(self, *, record_id: int) -> SalaryHistory | None:
        return self.db.query(SalaryHistory).filter(SalaryHistory.id == record_id).first()

    def add(self, obj) -> None:
        self.db.add(obj)

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def list_salary_payments(
        self,
        *,
        user_id: int,
        year: int | None,
        limit: int,
    ) -> list[SalaryPayment]:
        query = self.db.query(SalaryPayment).filter(SalaryPayment.user_id == user_id)
        if year:
            query = query.filter(
                SalaryPayment.period_start >= datetime(year, 1, 1),
                SalaryPayment.period_end <= datetime(year, 12, 31, 23, 59, 59),
            )
        return query.order_by(desc(SalaryPayment.period_end)).limit(limit).all()

    def list_salary_payments_for_year(
        self,
        *,
        user_id: int,
        year: int,
    ) -> list[SalaryPayment]:
        return (
            self.db.query(SalaryPayment)
            .filter(
                SalaryPayment.user_id == user_id,
                SalaryPayment.period_start >= datetime(year, 1, 1),
                SalaryPayment.period_end <= datetime(year, 12, 31, 23, 59, 59),
            )
            .all()
        )

    def get_salary_payment(self, *, payment_id: int) -> SalaryPayment | None:
        return self.db.query(SalaryPayment).filter(SalaryPayment.id == payment_id).first()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
