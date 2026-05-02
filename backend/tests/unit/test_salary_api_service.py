from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.salary_api_service import SalaryApiDomainError, SalaryApiService


@pytest.mark.unit
class TestSalaryApiService:
    def test_confirm_salary_change_raises_when_missing(self):
        class Repository:
            def get_salary_history_record(self, *, record_id):
                return None

        service = SalaryApiService(db=None, repository=Repository())
        with pytest.raises(SalaryApiDomainError) as exc_info:
            service.confirm_salary_change(record_id=1, confirmed_by_id=2)
        assert exc_info.value.status_code == 404

    def test_create_salary_payment_calculates_net_amount(self):
        state = {"committed": False, "added": None}

        class Repository:
            def add(self, obj):
                state["added"] = obj

            def commit(self):
                state["committed"] = True

            def refresh(self, obj):
                obj.id = 101

        service = SalaryApiService(db=None, repository=Repository())
        result = service.create_salary_payment(
            payload={
                "user_id": 5,
                "period_start": datetime(2026, 1, 1),
                "period_end": datetime(2026, 1, 31),
                "base_salary": Decimal("1000"),
                "bonuses": Decimal("200"),
                "deductions": Decimal("50"),
                "taxes": Decimal("100"),
                "currency": "UZS",
            }
        )

        assert result["id"] == 101
        assert result["net_amount"] == 1050.0
        assert state["committed"] is True
        assert state["added"].status == "pending"

    def test_update_payment_status_validates_status(self):
        payment = SimpleNamespace(
            status="pending",
            payment_date=None,
            payment_method=None,
        )

        class Repository:
            def get_salary_payment(self, *, payment_id):
                return payment

            def commit(self):
                raise AssertionError("commit must not be called")

        service = SalaryApiService(db=None, repository=Repository())
        with pytest.raises(SalaryApiDomainError) as exc_info:
            service.update_payment_status(
                payment_id=11,
                new_status="unknown",
                payment_date=None,
                payment_method=None,
            )
        assert exc_info.value.status_code == 400
